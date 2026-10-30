"""Small JSONL sinks and ASGI request correlation; no business behavior.

Event/result labels and explicit request IDs are internal application metadata,
never user input. Optional fields use an allowlist; payloads are never rendered.
Test-run commands must be static, reviewed argv without credentials or PII.
"""

from collections.abc import Sequence
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from time import perf_counter
from typing import Any, TextIO
from uuid import uuid4


_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_http_methods = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "CONNECT", "TRACE"}


def _utc_time() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonEventLogger:
    def __init__(self, stream: TextIO) -> None:
        self.stream = stream

    def emit(
        self, event: str, result: str, *, request_id: str | None = None,
        **fields: Any,
    ) -> None:
        record: dict[str, Any] = {
            "time": _utc_time(), "event": event, "result": result,
            "request_id": request_id if request_id is not None else current_request_id(),
        }
        status = fields.get("status")
        if type(status) is int and 100 <= status <= 599:
            record["status"] = status
        duration = fields.get("duration_ms")
        if type(duration) in (int, float) and math.isfinite(duration) and duration >= 0:
            record["duration_ms"] = duration
        method = fields.get("method")
        if isinstance(method, str) and method in _http_methods:
            record["method"] = method
        self.stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        self.stream.flush()


def current_request_id() -> str:
    request_id = _request_id.get()
    if request_id is None:
        raise RuntimeError("No active request context; supply an internal request_id")
    return request_id


class RequestLoggingMiddleware:
    def __init__(self, app: Any, logger: JsonEventLogger) -> None:
        self.app = app
        self.logger = logger

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        token = _request_id.set(uuid4().hex)
        started = perf_counter()
        status = 500
        failed = False

        async def capture_status(message: Any) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            self.logger.emit("request.start", "started", method=scope.get("method"))
            await self.app(scope, receive, capture_status)
        except BaseException:
            # Preserve ASGI exception semantics; never render exception values.
            failed = True
            raise
        finally:
            try:
                self.logger.emit(
                    "request.end", "error" if failed or status >= 400 else "success",
                    status=status, duration_ms=(perf_counter() - started) * 1000,
                )
            finally:
                _request_id.reset(token)


def record_test_run(
    path: Path, *, run_id: str, command: Sequence[str], exit_code: int,
    result: str,
) -> None:
    record = {
        "time": _utc_time(), "run_id": run_id, "command": list(command),
        "exit_code": exit_code, "result": result,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
