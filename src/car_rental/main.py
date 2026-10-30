"""Minimal ASGI bootstrap without business or documentation routes."""

import os
from sqlalchemy import create_engine
from car_rental.api import create_app


_database_url = os.environ.get("DATABASE_URL")
app = create_app(create_engine(_database_url) if _database_url else None)
