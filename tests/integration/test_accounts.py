"""T02: REQ-F-009–014,082,089/NF-006; AC corresponding; BDD-003/016.

Q-09 explicitly approved: Argon2id m=19456 KiB,t=2,p=1 with random salt.
Only synthetic contacts and credentials; do not persist response bodies.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session
import pytest
from car_rental.storage import Account,LoginSession


def test_registration_and_login_trim_case_unique(api,db,registration):
    data={**registration,'email':'  Fixture@Example.invalid  '}
    r=api('POST','/clients',data)
    assert r.status_code==201 and 'location' not in r.headers
    assert set(r.json())=={'profile','role'} and r.json()['role']=='client'
    assert r.json()['profile']['email']=='Fixture@Example.invalid'
    with Session(db) as s:
        account=s.scalar(select(Account))
        assert account.password_hash.startswith('$argon2id$v=19$m=19456,t=2,p=1$')
        assert not list(s.scalars(select(LoginSession)))
    duplicate=api('POST','/clients',registration)
    assert duplicate.status_code==409 and duplicate.json()['error']['code']=='EMAIL_ALREADY_EXISTS'
    login=api('POST','/sessions',{'email':' FIXTURE@example.INVALID ','password':registration['password']})
    assert login.status_code==201 and login.json()['tokenType']=='Bearer'


@pytest.mark.parametrize('patch',[{'password':'1234567'},{'role':'administrator'},{'firstName':'   '},{'phone':'   '},{'email':'bad'}])
def test_invalid_registration_does_not_create_record(api,db,registration,patch):
    r=api('POST','/clients',{**registration,**patch})
    assert r.status_code==422 and r.json()['error']['code']=='VALIDATION_ERROR'
    with Session(db) as s:assert not list(s.scalars(select(Account)))


def test_password_is_not_trimmed_and_eight_spaces_allowed(api,registration):
    assert api('POST','/clients',{**registration,'password':' '*8}).status_code==201
    assert api('POST','/sessions',{'email':registration['email'],'password':' '*8}).status_code==201
    r=api('POST','/sessions',{'email':registration['email'],'password':''})
    assert r.status_code==401 and 'www-authenticate' not in r.headers


def test_unknown_credentials_same_failure(api):
    r=api('POST','/sessions',{'email':'missing@example.invalid','password':'synthetic-password-marker'})
    assert r.status_code==401 and r.json()['error']['code']=='INVALID_CREDENTIALS'
