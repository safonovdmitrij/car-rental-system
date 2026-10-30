"""Single-worker daily pg_dump scheduler; recovery acceptance remains Q-08."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4
from car_rental.observability import JsonEventLogger


def backup_due(directory,now,dump):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    day=now.astimezone(timezone.utc).date().isoformat()
    checkpoint=directory/'last-success.json'
    if checkpoint.exists() and json.loads(checkpoint.read_text(encoding='utf-8'))['day']==day:
        return False
    partial=directory/(day+'.partial')
    dump(partial)
    if not partial.is_file() or partial.stat().st_size==0:
        raise RuntimeError('Backup command produced no data')
    partial.replace(directory/(day+'.dump'))
    pending=directory/'checkpoint.partial'
    pending.write_text(json.dumps({'day':day})+'\n',encoding='utf-8')
    pending.replace(checkpoint)
    return True


def dump_database(path):
    # Connection/authentication is inherited through PG* / PGPASSFILE, not argv.
    os.environ['PGDATABASE']
    result=subprocess.run([os.environ.get('PG_DUMP','pg_dump'),'--format=custom','--no-password','--file',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('Database backup failed')


if __name__=='__main__':
    directory=Path(os.environ['BACKUP_DIR'])
    logger=JsonEventLogger(sys.stdout)
    while True:
        try:
            changed=backup_due(directory,datetime.now(timezone.utc),dump_database)
            if changed:logger.emit('backup.complete','success',request_id=uuid4().hex)
        except Exception:
            logger.emit('backup.complete','error',request_id=uuid4().hex)
            if '--once' in sys.argv:raise SystemExit(1)
        if '--once' in sys.argv:break
        time.sleep(60)
