"""Supplementary B01 verification of every protected operation from OpenAPI.
These are regression/coverage checks, not retrospectively invented RED evidence.
"""
import pytest


PROTECTED=[
 ('GET','/profile',None),('PATCH','/profile',{'firstName':'Synthetic'}),
 ('PUT','/profile/password',{'currentPassword':'synthetic','newPassword':'long-enough'}),
 ('POST','/booking-quotes',{'carId':'missing','startsAt':'2026-11-12T09','endsAt':'2026-11-14T09'}),
 ('POST','/bookings',{'carId':'missing','startsAt':'2026-11-12T09','endsAt':'2026-11-14T09','priceConfirmationToken':'opaque'}),
 ('GET','/bookings',None),('GET','/bookings/missing',None),('POST','/bookings/missing/cancellation',{}),
 ('GET','/admin/cars',None),('POST','/cars',{'characteristics':{'model':'Sport'},'dailyRate':'1.00'}),
 ('PATCH','/cars/missing',{'hidden':True}),('DELETE','/cars/missing',None),
 ('GET','/cars/missing/service-unavailabilities',None),('GET','/cars/missing/service-unavailabilities/missing',None),
 ('POST','/cars/missing/service-unavailabilities',{'startsAt':'2026-11-12T09','endsAt':'2026-11-13T09','reason':'Synthetic maintenance'}),
 ('PATCH','/cars/missing/service-unavailabilities/missing',{'reason':'Synthetic maintenance'}),
 ('DELETE','/cars/missing/service-unavailabilities/missing',None),
]


@pytest.mark.parametrize('method,path,data',PROTECTED,ids=[f'protected-{i:02}' for i in range(17)])
def test_every_protected_operation_requires_bearer(api,method,path,data):
    r=api(method,path,data)
    assert r.status_code==401 and r.headers['www-authenticate']=='Bearer'


@pytest.mark.parametrize('method,path,data',PROTECTED[8:],ids=[f'admin-{i:02}' for i in range(9)])
def test_every_admin_operation_denies_client(api,client_token,method,path,data):
    r=api(method,path,data,client_token)
    assert r.status_code==403


def test_service_wrong_car_and_missing_resource_indistinguishable(api,admin,reserved):
    a=api('GET','/cars/reserved-car/service-unavailabilities/missing',token=admin)
    b=api('GET','/cars/missing/service-unavailabilities/missing',token=admin)
    assert a.status_code==b.status_code==404 and a.json()==b.json()
