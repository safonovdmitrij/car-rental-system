"""T11: REQ-F-073–081/087–089/092; corresponding AC; BDD-015/016.
OP-18–22 with real conflict and mixed booking/service concurrency checks.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from car_rental.storage import Occupation,Car


def test_service_crud_adjacency_and_booking_conflict(api,admin,reserved):
    path='/cars/reserved-car/service-unavailabilities'
    data={'startsAt':'2026-11-14T09','endsAt':'2026-11-15T09','reason':'Synthetic maintenance'}
    r=api('POST',path,data,admin)
    assert r.status_code==201 and r.headers['location'].endswith('/'+r.json()['id'])
    id=r.json()['id']
    assert api('GET',path+'/'+id,token=admin).json()['reason']=='Synthetic maintenance'
    assert len(api('GET',path,token=admin).json()['items'])==1
    conflict=api('PATCH',path+'/'+id,{'startsAt':'2026-11-13T09'},admin)
    assert conflict.status_code==409 and conflict.json()['error']['code']=='SERVICE_PERIOD_CONFLICT'
    assert api('PATCH',path+'/'+id,{'reason':'Updated maintenance'},admin).status_code==200
    assert api('GET','/cars/reserved-car/availability?startsAt=2026-11-14T09&endsAt=2026-11-15T09').json()['available'] is False
    assert api('DELETE',path+'/'+id,token=admin).status_code==204
    assert api('GET',path+'/'+id,token=admin).status_code==404


def test_service_immutable_at_start_with_fresh_session(api,admin,reserved,registration):
    path='/cars/reserved-car/service-unavailabilities'
    r=api('POST',path,{'startsAt':'2026-11-20T09','endsAt':'2026-11-21T09','reason':'Synthetic maintenance'},admin)
    assert r.status_code==201
    api.now=datetime.fromisoformat('2026-11-20T09:00:00+02:00')
    token=api('POST','/sessions',{'email':'administrator@example.invalid','password':registration['password']}).json()['accessToken']
    endpoint=path+'/'+r.json()['id']
    assert api('PATCH',endpoint,{'reason':'Changed'},token).status_code==409
    assert api('DELETE',endpoint,token=token).status_code==409
    assert api('GET',endpoint,token=token).json()['reason']=='Synthetic maintenance'


def test_service_validates_reason_time_and_roles(api,admin,reserved,client_token):
    path='/cars/reserved-car/service-unavailabilities'
    for data in [ {'startsAt':'2026-11-20T09','endsAt':'2026-11-21T09'}, {'startsAt':'2026-11-20T09','endsAt':'2026-11-21T09','reason':' '}, {'startsAt':'2026-11-10T12','endsAt':'2026-11-21T09','reason':'Maintenance'} ]:
        assert api('POST',path,data,admin).status_code==422
    assert api('GET',path,token=client_token).status_code==403


def test_parallel_booking_and_service_never_save_conflict(api,db,admin,client_token):
    with Session(db) as s:s.add(Car(id='race',characteristics={'model':'Sport'},daily_rate='1500.00',hidden=False));s.commit()
    data={'carId':'race','startsAt':'2026-11-12T09','endsAt':'2026-11-14T09'}
    q=api('POST','/booking-quotes',data,client_token).json()
    def booking():return api('POST','/bookings',{**data,'priceConfirmationToken':q['priceConfirmationToken']},client_token).status_code
    def service():return api('POST','/cars/race/service-unavailabilities',{'startsAt':data['startsAt'],'endsAt':data['endsAt'],'reason':'Synthetic maintenance'},admin).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(booking);b=pool.submit(service);statuses=[a.result(),b.result()]
    assert sorted(statuses)==[201,409]
    with Session(db) as s:assert len(list(s.scalars(select(Occupation).where(Occupation.car_id=='race'))))==1
