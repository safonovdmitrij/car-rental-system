"""TDD plan §8: significant actions after commit, no body/contact/credential data."""
import json


def test_committed_registration_emits_safe_operation_event(api,registration,capsys):
    assert api('POST','/clients',registration).status_code==201
    output=capsys.readouterr().out
    rows=[json.loads(line) for line in output.splitlines() if line.startswith('{')]
    created=[row for row in rows if row['event']=='account.created']
    assert len(created)==1 and created[0]['result']=='success' and created[0]['request_id']
    assert all(value not in output for value in registration.values())
