"""Two mock HTTP smoke checks plus prefix routing; no business/API-GATE scenarios."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from openapi_schema_validator import OAS31Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
import yaml


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:4010')
    args = parser.parse_args()
    document = yaml.safe_load((ROOT / 'openapi.yaml').read_text(encoding='utf-8'))
    assert document['servers'][0]['url'] == '/api/v1', 'Base URL changed; review proxy config'
    registry_uri = 'urn:car-rental:mock-check'
    registry = Registry().with_resource(
        registry_uri, Resource.from_contents(document, default_specification=DRAFT202012)
    )

    def resolve(value):
        while isinstance(value, dict) and '$ref' in value:
            target = document
            for part in value['$ref'][2:].split('/'):
                target = target[part.replace('~1', '/').replace('~0', '~')]
            value = target
        return value

    prefix = document['servers'][0]['url']
    quote_request = document['components']['examples']['QuoteRequest']['value']
    results = []
    cases = [('get', '/cars', 'PublicCarList', None),
             ('post', '/booking-quotes', 'Quote', quote_request)]
    for method, path, example_name, body in cases:
        operation = document['paths'][path][method]
        if body is not None:
            request_schema = operation['requestBody']['content']['application/json']['schema']
            OAS31Validator(request_schema, registry=registry, _resolver=registry.resolver(registry_uri),
                           format_checker=OAS31Validator.FORMAT_CHECKER).validate(body)
        headers = {'Accept': 'application/json', 'Prefer': f'code=200, example={example_name}'}
        if body is not None:
            headers |= {'Authorization': 'Bearer mock-client', 'Content-Type': 'application/json'}
        request = Request(args.base_url + prefix + path, method=method.upper(), headers=headers,
                          data=None if body is None else json.dumps(body).encode('utf-8'))
        with urlopen(request, timeout=10) as response:
            status = response.status
            content_type = response.headers['Content-Type']
            payload = json.loads(response.read())
        assert status == 200, (path, status)
        assert content_type.split(';')[0] == 'application/json', content_type
        response = resolve(operation['responses'][str(status)])
        media = response['content']['application/json']
        OAS31Validator(media['schema'], registry=registry, _resolver=registry.resolver(registry_uri),
                       format_checker=OAS31Validator.FORMAT_CHECKER).validate(payload)
        expected_example = resolve(media['examples'][example_name])['value']
        assert payload == expected_example, f'{path}: named example was not selected'
        results.append({'method': method.upper(), 'path': prefix + path, 'status': status,
                        'schema_valid': True, 'example': example_name, 'body': payload})
        print(f'{method.upper()} {prefix + path}: {status}; schema PASS; example {example_name} MATCH')

    for path in ['/cars', '/api/v1/api/v1/cars']:
        try:
            with urlopen(args.base_url + path, timeout=10) as response:
                status = response.status
        except HTTPError as error:
            status = error.code
        assert status == 404, (path, status)
        results.append({'method': 'GET', 'path': path, 'status': status, 'routing_only': True})
        print(f'GET {path}: {status}; prefix routing PASS (not an API error-model test)')

    destination = Path(__file__).with_name('runtime')
    destination.mkdir(exist_ok=True)
    (destination / 'smoke-results.json').write_text(json.dumps({
        'spec_sha256': hashlib.sha256((ROOT / 'openapi.yaml').read_bytes()).hexdigest(),
        'base_url': args.base_url, 'checks': results,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('PASS: two success responses and prefix routing only; no business-rule or API-GATE verification.')


if __name__ == '__main__':
    main()
