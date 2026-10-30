"""Europe/Kyiv rental calendar interfaces (T01)."""

from datetime import datetime, timedelta, timezone
import re
from zoneinfo import ZoneInfo


KYIV = ZoneInfo("Europe/Kyiv")
UTC = timezone.utc


def _occurrences(local: datetime) -> list[datetime]:
    moments = {}
    for fold in (0, 1):
        candidate = local.replace(tzinfo=KYIV, fold=fold)
        instant = candidate.astimezone(UTC)
        back = instant.astimezone(KYIV)
        if back.replace(tzinfo=None) == local:
            moments[instant] = back
    return [moments[key] for key in sorted(moments)]


def parse_local_hour(value: str) -> datetime:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}", value) is None:
        raise ValueError("Invalid LocalHour")
    local = datetime.strptime(value, "%Y-%m-%dT%H")
    occurrences = _occurrences(local)
    if len(occurrences) != 1:
        raise ValueError("Nonexistent or ambiguous local time")
    return occurrences[0]


def calendar_boundary(anchor: datetime, days: int) -> datetime:
    local = anchor.astimezone(KYIV).replace(tzinfo=None) + timedelta(days=days)
    occurrences = _occurrences(local)
    if occurrences:
        return occurrences[-1]
    # A gap: the original offset roundtrip moves forward by the transition size.
    return max(
        (local.replace(tzinfo=KYIV, fold=fold).astimezone(UTC).astimezone(KYIV) for fold in (0, 1)),
        key=lambda value: value.astimezone(UTC),
    )


def validate_rental(starts_at: str, ends_at: str, *, now: datetime) -> tuple[datetime, datetime]:
    start, end = parse_local_hour(starts_at), parse_local_hour(ends_at)
    a, b, instant = start.astimezone(UTC), end.astimezone(UTC), now.astimezone(UTC)
    if not a > instant or b <= a:
        raise ValueError("Rental must start in the future and end after start")
    if not calendar_boundary(start, 1).astimezone(UTC) <= b <= calendar_boundary(start, 30).astimezone(UTC):
        raise ValueError("Rental duration outside 1–30 calendar days")
    if a > calendar_boundary(now, 90).astimezone(UTC):
        raise ValueError("Rental starts beyond calendar horizon")
    return start, end
