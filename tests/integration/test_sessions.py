"""T03: REQ-F-087–089,093/094; AC-F-093/094-01; BDD-016/017.
Protected profile distinguishes valid-but-forbidden administrator from expired token.
"""
from datetime import datetime,timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
import pytest
from car_rental.storage import Account


@pytest.mark.parametrize('role',['client','administrator'])
def test_exact_fixed_session_ttl_both_roles(api,db,registration,role):
    assert api('POST','/clients',registration).status_code==201
    with Session(db) as s:
        a=s.scalar(select(Account));a.role=role;s.commit()
    api.now=datetime.fromisoformat('2026-03-28T12:00:00+02:00')
    token=api('POST','/sessions',{'email':registration['email'],'password':registration['password']}).json()['accessToken']
    api.now=datetime.fromisoformat('2026-03-29T12:59:59+03:00')
    assert api('GET','/profile',token=token).status_code==(200 if role=='client' else 403)
    api.now=datetime.fromisoformat('2026-03-29T13:00:00+03:00')
    for extra in (0,1):
        api.now+=timedelta(seconds=extra)
        r=api('GET','/profile',token=token)
        assert r.status_code==401 and r.headers['www-authenticate']=='Bearer'
        assert r.json()['error']['code']=='AUTHENTICATION_REQUIRED'


@pytest.mark.parametrize('token',[None,'invalid-opaque-value'])
def test_missing_invalid_bearer(api,token):
    r=api('GET','/profile',token=token)
    assert r.status_code==401 and r.headers['www-authenticate']=='Bearer'
