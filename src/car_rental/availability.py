"""Shared availability and cancellation deadline rules."""
from datetime import datetime, timezone
from car_rental.calendar import calendar_boundary


def overlaps(a: datetime, b: datetime, c: datetime, d: datetime) -> bool:
    a,b,c,d = (value.astimezone(timezone.utc) for value in (a,b,c,d))
    return a < d and c < b


def cancellation_deadline(start: datetime) -> datetime:
    return calendar_boundary(start, -1)
