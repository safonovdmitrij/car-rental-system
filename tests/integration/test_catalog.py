"""T06 public subset: REQ-F-001–008,092; AC of those REQ; BDD-001/002.

Real dedicated PostgreSQL, no SQLite or mocked response selection.
"""
import asyncio
import json
import os
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from car_rental.catalog_api import create_catalog_app
from car_rental.storage import Base, Car, Occupation
from car_rental.migrations import upgrade_database


@pytest.fixture
def engine():
    # This is the freshly initialized workspace-only cluster, not the installed service.
    url = os.environ.get('TEST_DATABASE_URL',"postgresql+psycopg://car_rental_test@127.0.0.1:55432/postgres")
    admin = create_engine(url)
    with admin.connect() as connection:
        assert Path(connection.scalar(text('SHOW data_directory'))).resolve()==Path('.backend-setup/postgres-test').resolve(), 'Refusing a non-workspace database'
    schema = "test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text('CREATE SCHEMA "' + schema + '"'))
    db = create_engine(url, connect_args={"options": "-csearch_path=" + schema})
    with db.begin() as connection:upgrade_database(connection)
    with Session(db) as s:
        s.add_all([
            Car(id="free", characteristics={"model":"Sport"}, daily_rate="1500.00", hidden=False),
            Car(id="hidden", characteristics={"model":"Hidden"}, daily_rate="2000.00", hidden=True),
            Car(id="occupied", characteristics={"model":"Other"}, daily_rate="1000.00", hidden=False),
        ])
        s.commit()
    yield db
    db.dispose()
    with admin.begin() as connection:
        connection.execute(text('DROP SCHEMA "' + schema + '" CASCADE'))
    admin.dispose()


def request(engine, path):
    async def send():
        async with AsyncClient(transport=ASGITransport(app=create_catalog_app(engine)),base_url="http://testserver") as c:
            return await c.get("/api/v1" + path)
    response=asyncio.run(send())
    if os.environ.get("TDD_EVIDENCE_DIR"):
        with (Path(os.environ['TDD_EVIDENCE_DIR'])/'responses.jsonl').open('a',encoding='utf-8') as output:
            output.write(json.dumps({'path':path,'method':'get','status':response.status_code,
                                     'headers':dict(response.headers),'body':response.json()},ensure_ascii=False)+'\n')
    return response


def test_public_catalog_without_period(engine):
    r=request(engine,"/cars")
    assert r.status_code==200
    assert {item['id'] for item in r.json()['items']}=={"free","occupied"}
    assert all(set(item)=={"id","characteristics","dailyRate","currency"} for item in r.json()['items'])


def test_public_details_hidden_and_unknown(engine):
    assert request(engine,"/cars/free").json()=={"id":"free","characteristics":{"model":"Sport"},"dailyRate":"1500.00","currency":"UAH"}
    for car in ('hidden','unknown'):
        r=request(engine,"/cars/"+car)
        assert r.status_code==404
        assert r.json()=={"error":{"code":"NOT_FOUND","message":"Ресурс не знайдено.","details":{}}}


@pytest.mark.parametrize("kind,available",[("confirmed",False),("active",False),("service",False),("cancelled",True),("completed",True)])
def test_every_blocking_kind_and_cancelled_exclusion(engine,kind,available):
    with Session(engine) as s:
        s.add(Occupation(id="span",car_id="occupied",starts_at=datetime.fromisoformat("2026-11-12T09:00+02:00"),ends_at=datetime.fromisoformat("2026-11-14T09:00+02:00"),kind=kind));s.commit()
    path="?startsAt=2026-11-13T09&endsAt=2026-11-15T09"
    r=request(engine,"/cars/occupied/availability"+path)
    assert r.status_code==200 and r.json()['available'] is available
    listed=request(engine,"/cars"+path)
    assert ("occupied" in {c['id'] for c in listed.json()['items']}) is available


def test_adjacent_interval_and_hidden_false(engine):
    with Session(engine) as s:
        s.add(Occupation(id="span",car_id="free",starts_at=datetime.fromisoformat("2026-11-11T09:00+02:00"),ends_at=datetime.fromisoformat("2026-11-12T09:00+02:00"),kind="confirmed"));s.commit()
    query="?startsAt=2026-11-12T09&endsAt=2026-11-13T09"
    assert request(engine,"/cars/free/availability"+query).json()['available'] is True
    assert request(engine,"/cars/hidden/availability"+query).json()['available'] is False


@pytest.mark.parametrize("query",["?startsAt=2026-11-12T09","?startsAt=2026-02-30T09&endsAt=2026-03-01T09","?startsAt=2026-03-29T03&endsAt=2026-03-30T09","?startsAt=2026-10-25T03&endsAt=2026-10-26T09","?startsAt=2026-11-12T09&endsAt=2026-11-12T09","?unknown=1"])
def test_invalid_query_422(engine,query):
    r=request(engine,"/cars"+query)
    assert r.status_code==422 and r.json()['error']['code']=="VALIDATION_ERROR"
    assert r.json()['error']['details']['fields']


@pytest.mark.parametrize("query",["?startsAt=2020-01-01T09&endsAt=2020-01-01T10","?startsAt=2030-01-01T09&endsAt=2031-01-01T09"])
def test_search_does_not_inherit_rental_limits(engine,query):
    assert request(engine,"/cars"+query).status_code==200
