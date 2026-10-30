"""T07: REQ-F-065–072,087–089; matching AC; BDD-014/016; OP-14–17.
Future/historical links use real DB fixture intervals, not fake HTTP responses.
"""
from datetime import datetime
import pytest
from sqlalchemy.orm import Session
from car_rental.storage import Occupation


def create(api,admin):
    r=api('POST','/cars',{'characteristics':{'model':'Sport'},'dailyRate':'1500.00'},admin)
    assert r.status_code==201
    return r.json()['id']


def test_create_patch_hide_show_projections_and_delete(api,admin):
    id=create(api,admin)
    assert len(api('GET','/admin/cars',token=admin).json()['items'])==1
    assert 'hidden' not in api('GET','/cars/'+id).json()
    assert 'hidden' in api('GET','/cars/'+id,token=admin).json()
    r=api('PATCH','/cars/'+id,{'hidden':True,'characteristics':{'brand':'Other'}},admin)
    assert r.status_code==200 and r.json()['warnings']==[]
    assert r.json()['car']['characteristics']=={'brand':'Other'}
    assert api('GET','/cars/'+id).status_code==404
    assert api('GET','/cars/'+id,token=admin).status_code==200
    assert api('PATCH','/cars/'+id,{'hidden':False},admin).status_code==200
    r=api('DELETE','/cars/'+id,token=admin)
    assert r.status_code==204 and r.content==b''


@pytest.mark.parametrize('rate',[0,'0.00','-1.00','1.001'])
def test_bad_tariff_rejected(api,admin,rate):
    assert api('POST','/cars',{'characteristics':{'model':'Sport'},'dailyRate':rate},admin).status_code==422


def test_related_history_blocks_delete_and_future_warning(api,db,admin):
    id=create(api,admin)
    with Session(db) as s:
        s.add(Occupation(id='future',car_id=id,starts_at=datetime.fromisoformat('2026-11-12T09:00+02:00'),ends_at=datetime.fromisoformat('2026-11-13T09:00+02:00'),kind='confirmed'));s.commit()
    r=api('PATCH','/cars/'+id,{'hidden':True},admin)
    assert r.json()['warnings']==[{'code':'FUTURE_BOOKINGS_EXIST','futureBookingsCount':1}]
    assert api('DELETE','/cars/'+id,token=admin).status_code==409
    with Session(db) as s:
        s.get(Occupation,'future').kind='completed';s.commit()
    assert api('DELETE','/cars/'+id,token=admin).status_code==409


def test_client_and_guest_cannot_manage_fleet(api,client_token):
    for token,status in [(None,401),(client_token,403)]:
        assert api('GET','/admin/cars',token=token).status_code==status
        assert api('POST','/cars',{'characteristics':{'x':'y'},'dailyRate':'1.00'},token).status_code==status
