from datetime import datetime
from uuid import uuid4
import asyncio
import json
import os
from pathlib import Path
from httpx import ASGITransport,AsyncClient
import pytest
from sqlalchemy import create_engine,text
from car_rental.storage import Base,Account
from sqlalchemy import select
from sqlalchemy.orm import Session
from car_rental.api import create_app
from car_rental.migrations import upgrade_database
from car_rental.contract import response_conforms


@pytest.fixture
def db():
    url=os.environ.get('TEST_DATABASE_URL',"postgresql+psycopg://car_rental_test@127.0.0.1:55432/postgres")
    admin=create_engine(url)
    with admin.connect() as c:
        assert Path(c.scalar(text('SHOW data_directory'))).resolve()==Path('.backend-setup/postgres-test').resolve(), 'Refusing a non-workspace database'
    schema='test_'+uuid4().hex
    with admin.begin() as c:c.execute(text('CREATE SCHEMA "'+schema+'"'))
    engine=create_engine(url,connect_args={'options':'-csearch_path='+schema})
    with engine.begin() as connection:upgrade_database(connection)
    yield engine
    engine.dispose()
    with admin.begin() as c:c.execute(text('DROP SCHEMA "'+schema+'" CASCADE'))
    admin.dispose()


class API:
    def __init__(self,db):
        self.now=datetime.fromisoformat('2026-11-10T12:00:00+02:00')
        self.runtime_stream=None
        if os.environ.get('TDD_EVIDENCE_DIR'):
            self.runtime_stream=(Path(os.environ['TDD_EVIDENCE_DIR'])/'api-events.jsonl').open('a',encoding='utf-8')
        self.app=create_app(db,lambda:self.now,self.runtime_stream)

    def __call__(self,method,path,body=None,token=None):
        async def request():
            async with AsyncClient(transport=ASGITransport(app=self.app),base_url='http://testserver') as c:
                kw={}
                if body is not None:kw['json']=body
                if token is not None:kw['headers']={'Authorization':'Bearer '+token}
                return await c.request(method,'/api/v1'+path,**kw)
        r=asyncio.run(request())
        # Responses involving credentials/profile PII are validated in memory later,
        # never exported verbatim to evidence or assertion locals.
        if os.environ.get('TDD_CONTRACT_CHECK')=='1':
            conforming=response_conforms(method,'/api/v1'+path.split('?')[0],r)
            if os.environ.get('TDD_EVIDENCE_DIR'):
                with (Path(os.environ['TDD_EVIDENCE_DIR'])/'contract-checks.jsonl').open('a',encoding='utf-8') as f:
                    f.write(json.dumps({'method':method,'path':path.split('?')[0],'status':r.status_code,'conforms':conforming})+'\n')
            assert conforming,'Actual response violates approved OpenAPI'
        return r


@pytest.fixture
def api(db):
    client=API(db)
    yield client
    if client.runtime_stream is not None:client.runtime_stream.close()


@pytest.fixture
def registration():
    return {'firstName':'Synthetic','lastName':'Fixture','phone':'synthetic-phone',
            'email':'fixture@example.invalid','password':'synthetic-password-marker'}


@pytest.fixture
def admin(api,db,registration):
    data={**registration,'email':'administrator@example.invalid'}
    api('POST','/clients',data)
    with Session(db) as s:
        account=s.scalar(select(Account).where(Account.email_key==data['email']));account.role='administrator';s.commit()
    return api('POST','/sessions',{'email':data['email'],'password':data['password']}).json()['accessToken']


@pytest.fixture
def client_token(api,registration):
    api('POST','/clients',registration)
    return api('POST','/sessions',{'email':registration['email'],'password':registration['password']}).json()['accessToken']


@pytest.fixture
def reserved(api,db,client_token):
    from car_rental.storage import Car
    with Session(db) as s:
        s.add(Car(id='reserved-car',characteristics={'model':'Sport'},daily_rate='1500.00',hidden=False));s.commit()
    data={'carId':'reserved-car','startsAt':'2026-11-12T09','endsAt':'2026-11-14T09'}
    q=api('POST','/booking-quotes',data,client_token).json()
    return api('POST','/bookings',{**data,'priceConfirmationToken':q['priceConfirmationToken']},client_token).json()
