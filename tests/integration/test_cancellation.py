"""T12: REQ-F-051–064/085/091, matching AC; BDD-011/012/013/016; OP-13.
Includes previously missing REQ-F-052/053 direct server scenarios.
"""
from datetime import datetime,timedelta
from sqlalchemy.orm import Session
from car_rental.storage import Car
import pytest


@pytest.mark.parametrize('seconds,expected',[(0,201),(1,409)])
def test_client_deadline_inclusive_and_release_history(api,reserved,client_token,seconds,expected):
    api.now=datetime.fromisoformat('2026-11-11T09:00:00+02:00')+timedelta(seconds=seconds)
    path='/bookings/'+reserved['id']
    r=api('POST',path+'/cancellation',{},client_token)
    assert r.status_code==expected
    if expected==201:
        assert r.json()['authorRole']=='client' and r.json()['reason'] is None
        assert r.headers['location']== '/api/v1'+path+'/cancellation'
        assert api('GET',path,token=client_token).json()['status']=='cancelled'
        assert api('GET','/cars/reserved-car/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09').json()['available'] is True
        assert api('POST',path+'/cancellation',{},client_token).json()['error']['code']=='ALREADY_CANCELLED'
    else:
        assert api('GET',path,token=client_token).json()['status']=='confirmed'


def test_admin_reason_and_identity_private_to_client(api,reserved,admin,client_token):
    api.now=datetime.fromisoformat('2026-11-11T10:00:00+02:00')
    path='/bookings/'+reserved['id']
    for data in ({},{'reason':' '}):assert api('POST',path+'/cancellation',data,admin).status_code==422
    assert api('POST',path+'/cancellation',{'reason':'Synthetic cancellation'},admin).status_code==201
    client=api('GET',path,token=client_token).json()['cancellation']
    owner=api('GET',path,token=admin).json()['cancellation']
    assert 'authorAccountId' not in client and owner['authorAccountId']
    assert client['reason']=='Synthetic cancellation'


@pytest.mark.parametrize('start,end,boundary',[
 ('2026-03-30T03','2026-04-01T03','2026-03-29T04:00:00+03:00'),
 ('2026-10-26T03','2026-10-28T03','2026-10-25T03:00:00+02:00'),
])
@pytest.mark.parametrize('late',[False,True],ids=['exact','one-second-after'])
def test_dst_real_cancellation_boundaries(api,db,client_token,registration,start,end,boundary,late):
    b=datetime.fromisoformat(boundary)
    api.now=b-timedelta(hours=12)
    token=api('POST','/sessions',{'email':registration['email'],'password':registration['password']}).json()['accessToken']
    with Session(db) as s:s.add(Car(id='dst',characteristics={'model':'Sport'},daily_rate='1500.00',hidden=False));s.commit()
    data={'carId':'dst','startsAt':start,'endsAt':end}
    q=api('POST','/booking-quotes',data,token).json()
    booked=api('POST','/bookings',{**data,'priceConfirmationToken':q['priceConfirmationToken']},token).json()
    assert datetime.fromisoformat(booked['clientCancellationDeadline'])==b
    api.now=b+timedelta(seconds=int(late))
    assert api('POST','/bookings/'+booked['id']+'/cancellation',{},token).status_code==(409 if late else 201)
