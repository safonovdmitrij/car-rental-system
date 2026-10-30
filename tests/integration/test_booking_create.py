"""T09: REQ-F-026,039–045,083/090; AC; BDD-006/009/010/016; OP-10.
Actual PostgreSQL locks/commits, no deterministic winner assumed.
"""
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from sqlalchemy import select
import pytest
from car_rental.storage import Car,Booking


@pytest.fixture
def booking_data(api,db,client_token):
    with Session(db) as s:
        s.add(Car(id='car',characteristics={'model':'Sport'},daily_rate='1500.00',hidden=False));s.commit()
    data={'carId':'car','startsAt':'2026-11-12T09','endsAt':'2026-11-14T09'}
    q=api('POST','/booking-quotes',data,client_token)
    return {**data,'priceConfirmationToken':q.json()['priceConfirmationToken']}


def test_booking_created_with_frozen_price_and_location(api,client_token,booking_data,db):
    r=api('POST','/bookings',booking_data,client_token)
    assert r.status_code==201 and r.headers['location']=='/api/v1/bookings/'+r.json()['id']
    assert r.json()['status']=='confirmed' and r.json()['totalPrice']=='3000.00'
    with Session(db) as s:
        b=s.scalar(select(Booking));assert b.daily_rate=='1500.00' and b.total=='3000.00'


def test_two_competing_requests_one_saved_booking(api,client_token,booking_data,db):
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(lambda _:api('POST','/bookings',booking_data,client_token).status_code,range(2)))
    assert sorted(statuses)==[201,409]
    with Session(db) as s:assert len(list(s.scalars(select(Booking))))==1


@pytest.mark.parametrize('patch',[{'priceConfirmationToken':'unknown'},{'startsAt':'2026-11-13T09','endsAt':'2026-11-15T09'},{'clientId':'forged'}])
def test_quote_context_and_owner_not_forged(api,client_token,booking_data,db,patch):
    assert api('POST','/bookings',{**booking_data,**patch},client_token).status_code==422
    with Session(db) as s:assert not list(s.scalars(select(Booking)))


def test_rate_change_and_return_requires_reconfirmation(api,client_token,booking_data,db):
    with Session(db) as s:
        c=s.get(Car,'car');c.rate_version+=2;s.commit()
    r=api('POST','/bookings',booking_data,client_token)
    assert r.status_code==409 and r.json()['error']['code']=='PRICE_CHANGED'
    with Session(db) as s:assert not list(s.scalars(select(Booking)))
    token=r.json()['error']['details']['quote']['priceConfirmationToken']
    assert api('POST','/bookings',{**booking_data,'priceConfirmationToken':token},client_token).status_code==201


def test_lost_availability_after_quote(api,client_token,booking_data,db):
    with Session(db) as s:s.get(Car,'car').hidden=True;s.commit()
    r=api('POST','/bookings',booking_data,client_token)
    assert r.status_code==409 and r.json()['error']['code']=='CAR_UNAVAILABLE'
