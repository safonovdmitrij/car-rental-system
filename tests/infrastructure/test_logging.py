"""Logging expectations from TDD plan §8 and the scoped user instruction.

No business REQ/AC is claimed covered. All payloads below are synthetic.
Test-only bare ASGI callables add no routes to car_rental.main.app.
"""

import asyncio
from collections import Counter
from datetime import datetime, timedelta
from io import StringIO
import json

from httpx import ASGITransport, AsyncClient
import pytest

from car_rental.observability import (
    JsonEventLogger, RequestLoggingMiddleware, current_request_id, record_test_run,
)


pytestmark = pytest.mark.infrastructure


def events(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def assert_event(record):
    assert isinstance(record["event"], str) and record["event"]
    assert isinstance(record["result"], str) and record["result"]
    assert isinstance(record["request_id"], str) and record["request_id"]
    timestamp = datetime.fromisoformat(record["time"].replace("Z", "+00:00"))
    assert timestamp.utcoffset() == timedelta(0)


def test_json_event_has_utc_time_type_result_and_request_id():
    stream = StringIO()
    JsonEventLogger(stream).emit("operation.complete", "success", request_id="request-test")
    records = events(stream)
    assert len(records) == 1
    assert_event(records[0])
    assert records[0]["event"] == "operation.complete"
    assert records[0]["result"] == "success"
    assert records[0]["request_id"] == "request-test"


@pytest.mark.parametrize("result", ["success", "error"])
def test_event_allowlist_excludes_sensitive_fields_even_on_error(result):
    stream = StringIO()
    # Marker values are synthetic, and assertions never echo them into evidence.
    private = {
        "body": "synthetic-body-marker", "password": "synthetic-password-marker",
        "authorization": "Bearer synthetic-token-marker", "email": "synthetic-contact-marker",
        "phone": "synthetic-phone-marker", "name": "synthetic-name-marker",
        "exception": "synthetic-exception-marker", "unknown": "synthetic-unknown-marker",
    }
    JsonEventLogger(stream).emit(
        "operation.complete", result, request_id="request-test", **private,
    )
    records = events(stream)
    assert len(records) == 1
    assert_event(records[0])
    assert set(records[0]) == {"time", "event", "result", "request_id"}
    assert all(value not in stream.getvalue() for value in private.values())


async def respond(send, status):
    await send({"type": "http.response.start", "status": status, "headers": []})
    await send({"type": "http.response.body", "body": b""})


@pytest.mark.parametrize("failure", [False, True], ids=["success", "error"])
def test_http_start_end_status_duration_and_correlation(failure):
    stream = StringIO()

    async def app(scope, receive, send):
        if failure:
            raise RuntimeError("Synthetic operation failure")
        await respond(send, 204)

    async def request():
        transport = ASGITransport(
            app=RequestLoggingMiddleware(app, JsonEventLogger(stream)),
            raise_app_exceptions=False,
        )
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/")

    response = asyncio.run(request())
    expected_status = 500 if failure else 204
    assert response.status_code == expected_status
    records = events(stream)
    assert [record["event"] for record in records] == ["request.start", "request.end"]
    for record in records:
        assert_event(record)
    assert records[0]["request_id"] == records[1]["request_id"]
    assert records[1]["status"] == expected_status
    assert records[1]["result"] == ("error" if failure else "success")
    duration = records[1]["duration_ms"]
    assert isinstance(duration, (int, float)) and not isinstance(duration, bool)
    assert 0 <= duration < float("inf")


def test_concurrent_requests_correlate_operation_events_without_context_leak():
    stream = StringIO()
    logger = JsonEventLogger(stream)

    async def app(scope, receive, send):
        await asyncio.sleep(0)  # Interleave requests to expose a global-id leak.
        logger.emit("operation.complete", "success", request_id=current_request_id())
        await respond(send, 204)

    async def requests():
        transport = ASGITransport(app=RequestLoggingMiddleware(app, logger))
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await asyncio.gather(client.get("/"), client.get("/"))

    responses = asyncio.run(requests())
    assert [response.status_code for response in responses] == [204, 204]
    records = events(stream)
    assert len(records) == 6
    for record in records:
        assert_event(record)
    ids = {record["request_id"] for record in records}
    assert len(ids) == 2
    for request_id in ids:
        assert Counter(r["event"] for r in records if r["request_id"] == request_id) == {
            "request.start": 1, "operation.complete": 1, "request.end": 1,
        }


def test_http_error_does_not_log_body_credentials_contacts_or_exception_text():
    stream = StringIO()
    payload = {
        "password": "synthetic-password-marker", "email": "synthetic-contact-marker",
        "phone": "synthetic-phone-marker", "name": "synthetic-name-marker",
    }

    async def app(scope, receive, send):
        # Deliberately include the body in the exception to test the leak boundary.
        raw = bytearray()
        while True:
            message = await receive()
            raw.extend(message.get("body", b""))
            if not message.get("more_body", False):
                break
        raise RuntimeError(raw.decode())

    async def request():
        transport = ASGITransport(
            app=RequestLoggingMiddleware(app, JsonEventLogger(stream)),
            raise_app_exceptions=False,
        )
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/?private=synthetic-query-marker", json=payload,
                headers={"Authorization": "Bearer synthetic-token-marker"},
            )

    assert asyncio.run(request()).status_code == 500
    records = events(stream)
    assert [record["event"] for record in records] == ["request.start", "request.end"]
    for record in records:
        assert_event(record)
        assert set(record) <= {
            "time", "event", "result", "request_id", "status", "duration_ms", "method",
        }
    forbidden = [*payload.values(), "synthetic-token-marker", "synthetic-query-marker"]
    assert all(value not in stream.getvalue() for value in forbidden)
    assert records[-1]["result"] == "error"


@pytest.mark.parametrize("exit_code,result", [(0, "PASS"), (1, "FAIL")])
def test_test_run_journal_records_exact_command_exit_code_and_result(tmp_path, exit_code, result):
    journal = tmp_path / "runs.jsonl"
    command = ["python", "-m", "pytest", "tests/infrastructure", "-q"]
    record_test_run(
        journal, run_id="synthetic-run", command=command, exit_code=exit_code, result=result,
    )
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["command"] == command
    assert rows[0]["exit_code"] == exit_code
    assert rows[0]["result"] == result
    assert rows[0]["run_id"] == "synthetic-run"
    assert datetime.fromisoformat(rows[0]["time"].replace("Z", "+00:00")).utcoffset() == timedelta(0)
