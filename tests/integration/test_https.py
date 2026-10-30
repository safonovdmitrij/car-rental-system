"""REQ-NF-005/AC-NF-005-01: actual TLS handshake and certificate verification.

Local diagnostic only, not browser trust installation or production certification.
Uses existing Caddy binary; keys remain under ignored pytest basetemp.
"""
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import time
import httpx
from sqlalchemy import create_engine
from sqlalchemy import text
from car_rental.migrations import upgrade_database
from car_rental.transport import local_tls_config


def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]


def test_real_https_proxy_and_verified_local_certificate(tmp_path):
    backend_port,https_port=port(),port()
    storage=tmp_path/'storage'
    config=local_tls_config(storage,https_port,backend_port)
    path=tmp_path/'caddy.json';path.write_text(json.dumps(config))
    env=os.environ.copy();env.update(PYTHONPATH='src',DATABASE_URL='postgresql+psycopg://car_rental_test@127.0.0.1:55432/postgres')
    engine=create_engine(env['DATABASE_URL'])
    with engine.begin() as c:
        assert Path(c.scalar(text('SHOW data_directory'))).resolve()==Path('.backend-setup/postgres-test').resolve()
        upgrade_database(c)
    engine.dispose()
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    processes=[]
    try:
        processes.append(subprocess.Popen([sys.executable,'-m','uvicorn','car_rental.main:app','--host','127.0.0.1','--port',str(backend_port),'--no-access-log'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags))
        processes.append(subprocess.Popen([str(Path('.mock-runtime/caddy-2.11.7/caddy.exe').resolve()),'run','--config',str(path)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags))
        root=storage/'pki/authorities/local/root.crt'
        response=None
        for _ in range(100):
            try:
                if root.exists():
                    with httpx.Client(verify=ssl.create_default_context(cafile=str(root)),trust_env=False,timeout=1) as client:
                        response=client.get(f'https://localhost:{https_port}/api/v1/cars')
                        if response.status_code==200:break
            except (httpx.HTTPError,OSError):pass
            time.sleep(0.1)
        assert response is not None and response.status_code==200
        assert response.headers['content-type'].startswith('application/json')
        with httpx.Client(verify=ssl.create_default_context(cafile=str(root)),trust_env=False) as client:
            r=client.get(f'https://localhost:{https_port}/api/v1/profile')
            assert r.status_code==401 and r.headers['www-authenticate']=='Bearer'
    finally:
        for process in reversed(processes):
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
