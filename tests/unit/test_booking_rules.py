"""T10/T11/T12 independent rules, not operation or persistence completion.

REQ-F-048–059,073–076,081/085/091; matching AC; BDD-011–013/015/016.
"""
from datetime import datetime
import pytest
from car_rental.booking_rules import booking_status,check_cancellation,check_service_period


def dt(value):
    return datetime.fromisoformat(value)


START=dt('2026-11-12T09:00:00+02:00')
END=dt('2026-11-13T09:00:00+02:00')


@pytest.mark.parametrize('now,expected',[("2026-11-12T08:59:59+02:00","confirmed"),("2026-11-12T09:00:00+02:00","active"),("2026-11-13T08:59:59+02:00","active"),("2026-11-13T09:00:00+02:00","completed"),("2026-11-14T09:00:00+02:00","completed")])
def test_automatic_state_exact_boundaries(now,expected):
    assert booking_status(START,END,cancelled=False,now=dt(now))==expected
    assert booking_status(START,END,cancelled=True,now=dt(now))=='cancelled'


@pytest.mark.parametrize('role,owns,now,reason,allowed',[
 ('client',True,'2026-11-11T09:00:00+02:00',None,True),
 ('client',True,'2026-11-11T09:00:01+02:00',None,False),
 ('client',False,'2026-11-10T09:00:00+02:00',None,False),
 ('administrator',False,'2026-11-12T08:59:59+02:00','Maintenance',True),
 ('administrator',False,'2026-11-12T09:00:00+02:00','Maintenance',False),
 ('administrator',False,'2026-11-10T09:00:00+02:00',None,False),
 ('administrator',False,'2026-11-10T09:00:00+02:00','   ',False),
 ('client',True,'2026-11-10T09:00:00+02:00','Admin field',False),
 ('guest',True,'2026-11-10T09:00:00+02:00',None,False),
])
def test_role_and_deadline_policy(role,owns,now,reason,allowed):
    args=dict(owns=owns,start=START,end=END,cancelled=False,now=dt(now),reason=reason)
    if allowed:
        check_cancellation(role,**args)
    else:
        with pytest.raises(ValueError):check_cancellation(role,**args)


@pytest.mark.parametrize('start,boundary',[("2026-03-30T03:00:00+03:00","2026-03-29T04:00:00+03:00"),("2026-10-26T03:00:00+02:00","2026-10-25T03:00:00+02:00")])
def test_dst_client_cancellation_inclusive_and_one_second_late(start,boundary):
    from datetime import timedelta
    a=dt(start);b=dt(boundary)
    check_cancellation('client',owns=True,start=a,end=a+timedelta(days=2),cancelled=False,now=b)
    with pytest.raises(ValueError):
        check_cancellation('client',owns=True,start=a,end=a+timedelta(days=2),cancelled=False,now=b+timedelta(seconds=1))


def test_already_cancelled_cannot_cancel_again():
    with pytest.raises(ValueError):
        check_cancellation('client',owns=True,start=START,end=END,cancelled=True,now=dt('2026-11-10T09:00:00+02:00'))


@pytest.mark.parametrize('start,end,previous,allowed',[
 ('2026-11-12T09','2026-11-12T10',None,True),
 ('2026-11-12T09','2027-11-12T09',None,True),
 ('2026-11-10T09','2026-11-12T09',None,False),
 ('2026-11-12T09','2026-11-12T09',None,False),
 ('2026-11-12T09','2026-11-11T09',None,False),
 ('2026-11-12T09','2026-11-13T09','2026-11-10T09:00:00+02:00',False),
 ('2026-11-12T09','2026-11-13T09','2026-11-11T09:00:00+02:00',True),
])
def test_service_period_does_not_inherit_rental_duration(start,end,previous,allowed):
    args=dict(now=dt('2026-11-10T09:00:00+02:00'),previous_start=dt(previous) if previous else None)
    if allowed:
        a,b=check_service_period(start,end,**args);assert a<b
    else:
        with pytest.raises(ValueError):check_service_period(start,end,**args)
