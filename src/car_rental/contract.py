"""Validation against the immutable repository OpenAPI, never generated models."""
from pathlib import Path
import re
import yaml
from openapi_schema_validator import OAS31Validator
from referencing import Registry,Resource
from referencing.jsonschema import DRAFT202012

SPEC=yaml.safe_load((Path(__file__).resolve().parents[2]/'api/openapi.yaml').read_text(encoding='utf-8'))
URI='urn:car-rental:openapi'
REGISTRY=Registry().with_resource(URI,Resource.from_contents(SPEC,default_specification=DRAFT202012))


def dereference(value):
    while '$ref' in value:
        target=SPEC
        for part in value['$ref'][2:].split('/'):target=target[part]
        value=target
    return value


def operation(method,path):
    if path.startswith('/api/v1/'):
        path=path[len('/api/v1'):]
    for route,methods in SPEC['paths'].items():
        if re.fullmatch(re.sub(r'\{[^}]+\}',r'[^/]+',route),path):
            return methods.get(method.lower())
    return None


def valid(schema,value):
    return not any(OAS31Validator(schema,registry=REGISTRY,_resolver=REGISTRY.resolver(URI),format_checker=OAS31Validator.FORMAT_CHECKER).iter_errors(value))


def response_conforms(method,path,response):
    op=operation(method,path)
    if op is None and response.status_code==405:
        op=next((operation(candidate,path) for candidate in ('get','post','put','patch','delete') if operation(candidate,path) is not None),None)
    if op is None:return False
    declared=op['responses'].get(str(response.status_code))
    if declared is None:return False
    declared=dereference(declared)
    if response.status_code==204:return response.content==b''
    if response.headers.get('content-type','').split(';')[0]!='application/json':return False
    if not valid(declared['content']['application/json']['schema'],response.json()):return False
    if response.status_code==401 and response.json()['error']['code']=='AUTHENTICATION_REQUIRED':
        if response.headers.get('www-authenticate')!='Bearer':return False
    if response.status_code==429:
        if not response.headers.get('retry-after','').isdigit() or int(response.headers['retry-after'])<=0:return False
    if response.status_code==405 and not response.headers.get('allow'):return False
    if response.status_code==201 and 'Location' in declared.get('headers',{}):
        if not response.headers.get('location','').startswith('/api/v1/'):return False
    return True
