"""T08 calendar component: AC-F-036-01/02,037-01; BDD-019/020.

Expected day counts are independent literal calendar cases, not product functions.
Quote/token/persistence behavior is outside this component.
"""
from datetime import datetime
import pytest
from car_rental.pricing import billable_days, total_price


@pytest.mark.parametrize("start,end,days", [
    ("2026-11-12T09:00+02:00", "2026-11-13T09:00+02:00", 1),
    ("2026-11-12T09:00+02:00", "2026-11-13T10:00+02:00", 2),
    ("2026-03-28T03:00+02:00", "2026-03-29T04:00+03:00", 1),
    ("2026-03-28T03:00+02:00", "2026-03-29T05:00+03:00", 2),
    ("2026-03-28T03:00+02:00", "2026-03-30T03:00+03:00", 2),
    ("2026-10-24T03:00+03:00", "2026-10-25T04:00+02:00", 2),
    ("2026-02-27T03:00+02:00", "2026-03-29T04:00+03:00", 30),
])
def test_calendar_billable_days(start, end, days):
    assert billable_days(datetime.fromisoformat(start), datetime.fromisoformat(end)) == days


@pytest.mark.parametrize("rate,days,expected", [("1500.00",1,"1500.00"),("0.01",30,"0.30"),("1500.00",2,"3000.00"),("100000000000000000000000000000.01",30,"3000000000000000000000000000000.30")])
def test_decimal_price_no_float_or_arbitrary_upper_limit(rate, days, expected):
    assert total_price(rate, days) == expected
