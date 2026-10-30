"""REQ-NF-007 / AC-NF-007-01: daily automatic invocation and restart safety.
Injected writer isolates scheduler policy; not proof of PostgreSQL recovery/RPO/RTO.
"""
from datetime import datetime,timedelta,timezone
from car_rental.backups import backup_due
import pytest


def test_once_per_utc_day_and_restart_checkpoint(tmp_path):
    now=datetime(2026,11,10,12,tzinfo=timezone.utc);calls=[]
    def dump(path):calls.append(path);path.write_bytes(b'synthetic-backup')
    assert backup_due(tmp_path,now,dump) is True
    assert backup_due(tmp_path,now+timedelta(hours=1),dump) is False
    assert backup_due(tmp_path,now+timedelta(days=1),dump) is True
    assert len(calls)==2


def test_failed_backup_can_retry_without_marking_success(tmp_path):
    now=datetime(2026,11,10,12,tzinfo=timezone.utc)
    def fail(path):raise RuntimeError('Synthetic backup failure')
    with pytest.raises(RuntimeError):backup_due(tmp_path,now,fail)
    def write(path):path.write_bytes(b'synthetic-backup')
    assert backup_due(tmp_path,now,write) is True
