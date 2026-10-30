"""Minimal ASGI bootstrap without business or documentation routes."""

from fastapi import FastAPI
import sys

from car_rental.observability import JsonEventLogger, RequestLoggingMiddleware


app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
app.add_middleware(RequestLoggingMiddleware, logger=JsonEventLogger(sys.stdout))
