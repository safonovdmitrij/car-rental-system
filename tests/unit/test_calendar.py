"""T01: REQ-F-027–035, their AC incl. ADD-001; BDD-007/008/019/020.

Only calendar validation portions of these BDD; no booking creation or prices.
Expected UTC offsets/boundaries are literals from ADD-001 or ordinary calendar dates.
"""

from datetime import datetime

import pytest

from car_rental.calendar import calendar_boundary, parse_local_hour, validate_rental


@pytest.mark.parametrize("hour", range(24))
def test_all_whole_hours_without_business_hours_limit(hour):
    # AC-F-027-01/028-01: winter Kyiv is UTC+02, any whole hour allowed.
    parsed = parse_local_hour(f"2026-11-12T{hour:02}")
    assert parsed.isoformat() == f"2026-11-12T{hour:02}:00:00+02:00"
    assert parsed.tzinfo.key == "Europe/Kyiv"


@pytest.mark.parametrize("value", [
    "2026-11-12T09:00", "2026-11-12T09:01", "2026-11-12T09Z",
    "2026-11-12T09+02:00", "2026-11-12T24", "2026-02-30T09",
    "2025-02-29T09", "2026-00-12T09", "2026-13-12T09", "0000-01-01T00",
    " 2026-11-12T09", "2026-11-12T09\n", "2026-3-01T09",
    "2026-03-29T03", "2026-10-25T03",
])
def test_invalid_format_date_or_ambiguous_input_rejected(value):
    # LocalHour/OP-09/10 + AC-F-029/030: gap and fold INPUT are both invalid.
    with pytest.raises(ValueError):
        parse_local_hour(value)


@pytest.mark.parametrize("anchor,n,expected", [
    ("2026-03-28T03:00:00+02:00", 1, "2026-03-29T04:00:00+03:00"),
    ("2026-03-28T03:00:00+02:00", 2, "2026-03-30T03:00:00+03:00"),
    ("2026-10-24T03:00:00+03:00", 1, "2026-10-25T03:00:00+02:00"),
    ("2026-02-27T03:00:00+02:00", 30, "2026-03-29T04:00:00+03:00"),
    ("2025-12-29T03:00:00+02:00", 90, "2026-03-29T04:00:00+03:00"),
    ("2026-01-01T09:27:35+02:00", 90, "2026-04-01T09:27:35+03:00"),
])
def test_boundaries_from_original_anchor(anchor, n, expected):
    # AC-F-035-02/03/04, 033-02,034-02; horizon preserves full local time.
    assert calendar_boundary(datetime.fromisoformat(anchor), n).isoformat() == expected


@pytest.mark.parametrize("start,end,now,accepted", [
    ("2026-11-12T09", "2026-11-13T09", "2026-11-10T12:00:00+02:00", True),
    ("2026-11-12T09", "2026-11-13T08", "2026-11-10T12:00:00+02:00", False),
    ("2026-11-12T09", "2026-12-12T09", "2026-11-10T12:00:00+02:00", True),
    ("2026-11-12T09", "2026-12-12T10", "2026-11-10T12:00:00+02:00", False),
    ("2026-11-12T09", "2026-11-12T09", "2026-11-10T12:00:00+02:00", False),
    ("2026-11-12T09", "2026-11-11T09", "2026-11-10T12:00:00+02:00", False),
    ("2026-11-10T12", "2026-11-11T12", "2026-11-10T12:00:00+02:00", False),
    ("2026-11-10T11", "2026-11-11T11", "2026-11-10T12:00:00+02:00", False),
    ("2026-03-28T03", "2026-03-29T02", "2026-03-27T12:00:00+02:00", False),
    ("2026-03-28T03", "2026-03-29T04", "2026-03-27T12:00:00+02:00", True),
    ("2026-02-27T03", "2026-03-29T04", "2026-02-26T12:00:00+02:00", True),
    ("2026-02-27T03", "2026-03-29T05", "2026-02-26T12:00:00+02:00", False),
    ("2026-03-29T04", "2026-03-30T04", "2025-12-29T03:00:00+02:00", True),
    ("2026-03-29T05", "2026-03-30T05", "2025-12-29T03:00:00+02:00", False),
    ("2026-03-28T04", "2026-03-29T04", "2026-03-27T12:00:00+02:00", True),
    ("2026-10-24T04", "2026-10-25T04", "2026-10-23T12:00:00+03:00", True),
    ("2026-03-29T03", "2026-03-30T04", "2026-03-27T12:00:00+02:00", False),
    ("2026-10-24T03", "2026-10-25T03", "2026-10-23T12:00:00+03:00", False),
])
def test_rental_boundaries(start, end, now, accepted):
    # AC-F-031–035: inclusive min/max/horizon; future strictly > now; DST not 24h.
    if accepted:
        a, b = validate_rental(start, end, now=datetime.fromisoformat(now))
        assert a < b
    else:
        with pytest.raises(ValueError):
            validate_rental(start, end, now=datetime.fromisoformat(now))
