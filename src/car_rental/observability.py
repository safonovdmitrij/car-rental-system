"""Infrastructure interfaces only. Logging behavior awaits the RED review."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO


class JsonEventLogger:
    def __init__(self, stream: TextIO) -> None:
        self.stream = stream

    def emit(
        self, event: str, result: str, *, request_id: str | None = None,
        **fields: Any,
    ) -> None:
        raise NotImplementedError("Structured JSON event logging is not implemented")


def current_request_id() -> str:
    raise NotImplementedError("Request context correlation is not implemented")


class RequestLoggingMiddleware:
    def __init__(self, app: Any, logger: JsonEventLogger) -> None:
        self.app = app
        self.logger = logger

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        raise NotImplementedError("HTTP request logging is not implemented")


def record_test_run(
    path: Path, *, run_id: str, command: Sequence[str], exit_code: int,
    result: str,
) -> None:
    raise NotImplementedError("Test execution journal is not implemented")
