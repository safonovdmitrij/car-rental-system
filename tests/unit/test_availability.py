"""T06/T12 shared rules: REQ-F-005/007/008,051–055; BDD-002/011.

No claims about DB concurrency or actual cancellation commands.
"""
from datetime import datetime
import pytest
from car_rental.availability import overlaps, cancellation_deadline


@pytest.mark.parametrize("c,d,expected", [(8,9,False),(11,12,False),(8,10,True),(9,10,True),(10,11,True),(9,11,True),(8,12,True),(9,12,True)])
def test_half_open_overlap(c,d,expected):
    at=lambda h:datetime.fromisoformat(f"2026-11-12T{h:02}:00:00+02:00")
    assert overlaps(at(9),at(11),at(c),at(d)) is expected


@pytest.mark.parametrize("start,expected", [
    ("2026-11-12T09:00:00+02:00","2026-11-11T09:00:00+02:00"),
    ("2026-03-30T03:00:00+03:00","2026-03-29T04:00:00+03:00"),
    ("2026-10-26T03:00:00+02:00","2026-10-25T03:00:00+02:00"),
])
def test_special_cancellation_calendar_deadline(start,expected):
    assert cancellation_deadline(datetime.fromisoformat(start)).isoformat()==expected
