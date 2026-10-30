"""Validate actual response snapshots, never static mock examples.

Run with the existing OpenAPI validation environment; no backend dependencies added.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import yaml
from openapi_schema_validator import OAS31Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

parser=argparse.ArgumentParser()
parser.add_argument('snapshots',type=Path)
parser.add_argument('output',type=Path)
args=parser.parse_args()
source=Path('api/openapi.yaml')
spec=yaml.safe_load(source.read_text(encoding='utf-8'))
uri='urn:car-rental:openapi'
registry=Registry().with_resource(uri,Resource.from_contents(spec,default_specification=DRAFT202012))


def dereference(value):
    while '$ref' in value:
        target=spec
        for token in value['$ref'][2:].split('/'):
            target=target[token]
        value=target
    return value


checks=[]
for line in args.snapshots.read_text(encoding='utf-8').splitlines():
    row=json.loads(line)
    path=row['path'].split('?')[0]
    routes=[v for key,v in spec['paths'].items() if re.fullmatch(re.sub(r'\{[^}]+\}',r'[^/]+',key),path)]
    assert len(routes)==1,path
    operation=routes[0][row['method']]
    response=dereference(operation['responses'][str(row['status'])])
    assert row['headers']['content-type'].split(';')[0]=='application/json'
    schema=response['content']['application/json']['schema']
    errors=list(OAS31Validator(schema,registry=registry,_resolver=registry.resolver(uri),format_checker=OAS31Validator.FORMAT_CHECKER).iter_errors(row['body']))
    assert not errors, (operation['x-op-id'],[e.message for e in errors])
    checks.append({'operation':operation['x-op-id'],'status':row['status'],'result':'PASS'})
args.output.write_text(json.dumps({'command':['.venv-api-validation/Scripts/python.exe','scripts/check_contract.py',str(args.snapshots),str(args.output)],'openapi_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source':'actual ASGI responses against isolated PostgreSQL','checks':checks,'result':'PASS'},indent=2)+'\n',encoding='utf-8')
print('Actual response contract checks:',len(checks),'PASS')
