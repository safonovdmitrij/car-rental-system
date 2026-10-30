"""T08 OP-09: REQ-F-036–039,083/090; AC; BDD-006/007/010/019/020.
Persistence of confirmed price and PRICE_CHANGED are completed with T09.
"""
from sqlalchemy.orm import Session
import pytest
from car_rental.storage import Car,Occupation


@pytest.fixture
def quote_data(db):
    with Session(db) as s:
        s.add(Car(id='car',characteristics={'model':'Sport'},daily_rate='1500.00',hidden=False));s.commit()
    return {'carId':'car','startsAt':'2026-11-12T09','endsAt':'2026-11-14T09'}


def test_quote_prices_and_does_not_reserve(api,client_token,quote_data,db):
    r=api('POST','/booking-quotes',quote_data,client_token)
    assert r.status_code==200
    assert r.json()['billableDays']==2 and r.json()['totalPrice']=='3000.00'
    assert r.json()['priceConfirmationToken']
    with Session(db) as s:assert not list(s.query(Occupation))
    assert api('POST','/booking-quotes',quote_data,client_token).status_code==200


@pytest.mark.parametrize('patch',[{'startsAt':'2026-11-10T12'},{'endsAt':'2026-11-12T10'},{'endsAt':'2027-01-12T09'},{'startsAt':'2027-11-12T09','endsAt':'2027-11-14T09'}])
def test_quote_rental_limits_422(api,client_token,quote_data,patch):
    assert api('POST','/booking-quotes',{**quote_data,**patch},client_token).status_code==422


def test_hidden_quote_rejected(api,client_token,quote_data,db):
    with Session(db) as s:s.get(Car,'car').hidden=True;s.commit()
    r=api('POST','/booking-quotes',quote_data,client_token)
    assert r.status_code==409 and r.json()['error']['code']=='CAR_UNAVAILABLE'


def test_quote_roles(api,admin,quote_data):
    assert api('POST','/booking-quotes',quote_data).status_code==401
    assert api('POST','/booking-quotes',quote_data,admin).status_code==403
