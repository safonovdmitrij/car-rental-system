"""Calendar billing component of T08 / REQ-F-036–037."""

from datetime import datetime, timezone
from decimal import Decimal, localcontext
import re
from car_rental.calendar import calendar_boundary


def billable_days(start: datetime, end: datetime) -> int:
    instant = end.astimezone(timezone.utc)
    if instant <= start.astimezone(timezone.utc):
        raise ValueError("End must be after start")
    days = 1
    while instant > calendar_boundary(start, days).astimezone(timezone.utc):
        days += 1
    return days


def total_price(rate: str, days: int) -> str:
    if re.fullmatch(r"[0-9]+\.[0-9]{2}", rate) is None or Decimal(rate) <= 0 or days < 1:
        raise ValueError("Invalid positive decimal rate or day count")
    with localcontext() as context:
        context.prec = max(28, len(rate) + len(str(days)) + 4)
        return format(Decimal(rate) * days, ".2f")
