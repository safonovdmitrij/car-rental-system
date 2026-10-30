"""T05: REQ-F-014,021–025,084/086,095/096; AC and BDD-005/016/018.
Contact-in-booking integration is completed by T10; no claim here.
"""
import pytest


def setup(api,data):
    api('POST','/clients',data)
    return [api('POST','/sessions',{'email':data['email'],'password':data['password']}).json()['accessToken'] for _ in range(2)]


def test_profile_patch_persisted_and_email_immutable(api,registration):
    token=setup(api,registration)[0]
    assert api('PATCH','/profile',{'firstName':'Changed','phone':'new-phone'},token).status_code==200
    assert api('GET','/profile',token=token).json()['firstName']=='Changed'
    for patch in ({'email':'other@example.invalid'},{'clientId':'another'},{},{'firstName':' '}):
        assert api('PATCH','/profile',patch,token).status_code==422
    assert api('GET','/profile',token=token).json()['email']==registration['email']


def test_successful_password_change_revokes_all_sessions(api,registration):
    tokens=setup(api,registration)
    r=api('PUT','/profile/password',{'currentPassword':registration['password'],'newPassword':'new-synthetic-value'},tokens[0])
    assert r.status_code==204 and r.content==b''
    for token in tokens:assert api('GET','/profile',token=token).status_code==401
    assert api('POST','/sessions',{'email':registration['email'],'password':'new-synthetic-value'}).status_code==201


@pytest.mark.parametrize('current,new',[('incorrect','new-synthetic-value'),('synthetic-password-marker','short')],ids=['wrong-current','short-new'])
def test_failed_password_change_keeps_both_sessions_and_password(api,registration,current,new):
    tokens=setup(api,registration)
    assert api('PUT','/profile/password',{'currentPassword':current,'newPassword':new},tokens[0]).status_code==422
    for token in tokens:assert api('GET','/profile',token=token).status_code==200
    assert api('POST','/sessions',{'email':registration['email'],'password':registration['password']}).status_code==201
