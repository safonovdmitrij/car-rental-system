"""Supplementary base verification; no retrospective RED or new business policy."""
import asyncio
from httpx import ASGITransport,AsyncClient
from sqlalchemy import event,select
from sqlalchemy.orm import Session
from car_rental.contract import response_conforms
from car_rental.storage import Account


def test_public_catalog_role_projection_and_invalid_optional_bearer(api,admin,reserved,client_token):
    assert 'hidden' in api('GET','/cars',token=admin).json()['items'][0]
    for token in (None,client_token,'invalid-opaque-value'):
        r=api('GET','/cars',token=token)
        assert r.status_code==200 and all('hidden' not in car for car in r.json()['items'])


def test_same_password_uses_distinct_salts(api,db,registration):
    assert api('POST','/clients',registration).status_code==201
    assert api('POST','/clients',{**registration,'email':'second@example.invalid'}).status_code==201
    with Session(db) as s:
        hashes=list(s.scalars(select(Account.password_hash)))
        assert len(set(hashes))==2
        assert all(value.startswith('$argon2id$v=19$m=19456,t=2,p=1$') for value in hashes)


def test_internal_error_is_contract_safe_without_exception_values(api,db):
    def fail(*args):raise RuntimeError('synthetic-internal-canary')
    event.listen(db,'before_cursor_execute',fail)
    try:
        async def request():
            async with AsyncClient(transport=ASGITransport(app=api.app,raise_app_exceptions=False),base_url='http://testserver') as c:
                return await c.get('/api/v1/cars')
        r=asyncio.run(request())
        assert r.status_code==500 and response_conforms('GET','/api/v1/cars',r)
        assert r.json()['error']['details']=={} and 'canary' not in r.text
    finally:event.remove(db,'before_cursor_execute',fail)
