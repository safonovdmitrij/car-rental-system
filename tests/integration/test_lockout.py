"""T04: REQ-F-015–020; all matching AC; BDD-004 incl independent expiry reset."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest


def attempt(api,data,correct=False):
    return api('POST','/sessions',{'email':data['email'],'password':data['password'] if correct else 'incorrect'})


def test_fifth_failure_blocks_fixed_deadline_and_resets_without_success(api,registration):
    api('POST','/clients',registration)
    for _ in range(4):assert attempt(api,registration).status_code==401
    fifth=attempt(api,registration)
    assert fifth.status_code==429 and fifth.headers['retry-after']=='900'
    api.now+=timedelta(seconds=1,microseconds=1)
    r=attempt(api,registration,True)
    assert r.status_code==429 and r.headers['retry-after']=='899'
    api.now+=timedelta(seconds=899)-timedelta(microseconds=1)
    # At original boundary, bad attempt is first of a NEW sequence without successful login.
    for _ in range(4):assert attempt(api,registration).status_code==401
    assert attempt(api,registration).status_code==429


def test_success_resets_and_other_account_independent(api,registration):
    api('POST','/clients',registration)
    other={**registration,'email':'other@example.invalid'}
    api('POST','/clients',other)
    for _ in range(4):attempt(api,registration)
    assert attempt(api,registration,True).status_code==201
    for _ in range(4):assert attempt(api,registration).status_code==401
    assert attempt(api,other,True).status_code==201
    assert attempt(api,registration).status_code==429


def test_parallel_failures_do_not_lose_counter_updates(api,registration):
    api('POST','/clients',registration)
    with ThreadPoolExecutor(max_workers=5) as pool:
        statuses=list(pool.map(lambda _:attempt(api,registration).status_code,range(5)))
    assert sorted(statuses)==[401,401,401,401,429]
