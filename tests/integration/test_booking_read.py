"""T10: REQ-F-024/025,043–050,084/087–089; AC; BDD-005/006/013/016; OP-11/12."""
from datetime import datetime
from sqlalchemy.orm import Session
from car_rental.storage import Car


def test_list_details_owner_and_current_contacts(api,reserved,client_token,admin):
    r=api('GET','/bookings',token=client_token)
    assert r.status_code==200 and len(r.json()['items'])==1
    id=reserved['id']
    before=api('GET','/bookings/'+id,token=client_token).json()
    assert 'client' not in before
    assert api('PATCH','/profile',{'phone':'changed-synthetic-phone'},client_token).status_code==200
    viewed=api('GET','/bookings/'+id,token=admin)
    assert viewed.status_code==200 and viewed.json()['client']['phone']=='changed-synthetic-phone'
    after=api('GET','/bookings/'+id,token=client_token).json()
    assert before==after
    assert len(api('GET','/bookings',token=admin).json()['items'])==1


def test_foreign_and_missing_same_404_and_patch_forbidden(api,reserved,client_token,registration):
    other={**registration,'email':'other@example.invalid'}
    api('POST','/clients',other)
    token=api('POST','/sessions',{'email':other['email'],'password':other['password']}).json()['accessToken']
    foreign=api('GET','/bookings/'+reserved['id'],token=token)
    missing=api('GET','/bookings/missing',token=token)
    assert foreign.status_code==missing.status_code==404 and foreign.json()==missing.json()
    own_list=api('GET','/bookings',token=token)
    assert own_list.status_code==200
    assert own_list.json()['items']==[]
    denied=api('PATCH','/bookings/'+reserved['id'],{'carId':'other'},client_token)
    assert denied.status_code==405 and 'GET' in denied.headers['allow']


def test_states_follow_clock_and_price_stays_fixed(api,reserved,client_token,db,registration):
    with Session(db) as s:s.get(Car,'reserved-car').daily_rate='2000.00';s.commit()
    for instant,status in [('2026-11-12T08:59:59+02:00','confirmed'),('2026-11-12T09:00:00+02:00','active'),('2026-11-14T09:00:00+02:00','completed')]:
        api.now=datetime.fromisoformat(instant)
        token=api('POST','/sessions',{'email':registration['email'],'password':registration['password']}).json()['accessToken']
        r=api('GET','/bookings/'+reserved['id'],token=token)
        assert r.status_code==200 and r.json()['status']==status
        assert r.json()['dailyRate']=='1500.00' and r.json()['totalPrice']=='3000.00'
