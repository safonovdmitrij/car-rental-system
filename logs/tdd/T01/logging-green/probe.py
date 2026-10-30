"""Reproduce safe error-event evidence without adding application routes."""

import asyncio
from io import StringIO
import json
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from car_rental.observability import (
    JsonEventLogger, RequestLoggingMiddleware, current_request_id,
)


async def main():
    stream = StringIO()
    logger = JsonEventLogger(stream)
    private = {key: "synthetic-" + key + "-canary" for key in ("password", "email", "phone", "name")}
    credential = "synthetic-credential-canary"

    async def app(scope, receive, send):
        raw = bytearray()
        while True:
            message = await receive()
            raw.extend(message.get("body", b""))
            if not message.get("more_body", False):
                break
        logger.emit("operation.complete", "error", exception=raw.decode(), **private)
        raise RuntimeError(raw.decode())

    transport = ASGITransport(
        app=RequestLoggingMiddleware(app, logger), raise_app_exceptions=False,
    )
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/?private=synthetic-query-canary", json=private,
            headers={"Authorization": "Bearer " + credential},
        )
    assert response.status_code == 500
    text = stream.getvalue()
    assert all(value not in text for value in [*private.values(), credential, "synthetic-query-canary"])
    rows = [json.loads(line) for line in text.splitlines()]
    assert [row["event"] for row in rows] == ["request.start", "operation.complete", "request.end"]
    assert len({row["request_id"] for row in rows}) == 1
    assert rows[-1]["status"] == 500 and rows[-1]["result"] == "error"
    for row in rows:
        assert set(row) <= {"time", "event", "result", "request_id", "method", "status", "duration_ms"}
    try:
        current_request_id()
    except RuntimeError:
        pass
    else:
        raise AssertionError("Request context was not cleared")
    # Persist only events which passed the allowlist/canary checks.
    Path(__file__).with_name("error-events.jsonl").write_text(text, encoding="utf-8")
    print("Error probe: HTTP 500; three correlated safe JSON events; context reset; PASS")


if __name__ == "__main__":
    asyncio.run(main())
