"""Bootstrap checks only: these are neither calendar nor API contract tests."""

import asyncio
import importlib
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient

from car_rental.main import app


pytestmark = pytest.mark.infrastructure


def test_dependency_stack_imports():
    for name in (
        "fastapi", "uvicorn", "sqlalchemy", "psycopg", "alembic",
        "pytest", "httpx", "tzdata",
    ):
        importlib.import_module(name)


def test_minimal_asgi_app_accepts_http():
    # Unregistered URI tests ASGI startup/transport, not the business error model.
    async def request():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.get("/__infrastructure_probe__")

    response = asyncio.run(request())
    assert response.status_code == 404


def test_kyiv_timezone_data_is_available():
    assert ZoneInfo("Europe/Kyiv").key == "Europe/Kyiv"
