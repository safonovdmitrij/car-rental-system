"""Base verification: global error contract and denied mutations (API-GATE).

No business priority among multiple violations is asserted.
"""
import asyncio
from httpx import ASGITransport,AsyncClient
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
import pytest


def test_allow_is_complete_and_role_independent(api):
    r=api('PUT','/cars',{})
    assert r.status_code==405 and set(r.headers['allow'].replace(' ','').split(','))=={'GET','POST'}


def test_database_unavailable_503_without_error_details(api,db):
    def fail(*args):raise OperationalError('private-sql',{},Exception('synthetic-internal-canary'))
    event.listen(db,'before_cursor_execute',fail)
    try:
        async def request():
            async with AsyncClient(transport=ASGITransport(app=api.app,raise_app_exceptions=False),base_url='http://testserver') as c:
                return await c.get('/api/v1/cars')
        r=asyncio.run(request())
        assert r.status_code==503 and r.json()['error']['code']=='SERVICE_UNAVAILABLE'
        assert 'canary' not in r.text and r.json()['error']['details']=={}
    finally:event.remove(db,'before_cursor_execute',fail)


def test_malformed_json_400(api):
    async def request():
        async with AsyncClient(transport=ASGITransport(app=api.app),base_url='http://testserver') as c:
            return await c.post('/api/v1/clients',content=b'{',headers={'Content-Type':'application/json'})
    r=asyncio.run(request())
    assert r.status_code==400 and r.json()['error']['code']=='BAD_REQUEST'


def test_foreign_cancellation_hidden_and_client_admin_fields_rejected(api,reserved,client_token,registration):
    other={**registration,'email':'other@example.invalid'}
    api('POST','/clients',other)
    token=api('POST','/sessions',{'email':other['email'],'password':other['password']}).json()['accessToken']
    r=api('POST','/bookings/'+reserved['id']+'/cancellation',{},token)
    assert r.status_code==404 and r.json()==api('POST','/bookings/missing/cancellation',{},token).json()
    assert api('POST','/bookings/'+reserved['id']+'/cancellation',{'reason':'Admin-only'},client_token).status_code==422


def test_active_cancellation_rejected_and_history_not_deleted(api,reserved,registration):
    from datetime import datetime
    api.now=datetime.fromisoformat('2026-11-12T09:00:00+02:00')
    token=api('POST','/sessions',{'email':registration['email'],'password':registration['password']}).json()['accessToken']
    r=api('POST','/bookings/'+reserved['id']+'/cancellation',{},token)
    assert r.status_code==409 and r.json()['error']['code']=='BOOKING_NOT_CANCELLABLE'
    assert api('GET','/bookings/'+reserved['id'],token=token).json()['status']=='active'
