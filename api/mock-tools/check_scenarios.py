"""Check documented static mock responses, not business logic or authorization.

Run from the repository root with the existing validation environment:
  .venv-api-validation/Scripts/python.exe api/mock-tools/check_scenarios.py
"""

import argparse
from collections import Counter
from datetime import datetime
from importlib.metadata import version
import json
from pathlib import Path
import re
import shlex
import socket
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from openapi_schema_validator import OAS31Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
import yaml


API = Path(__file__).resolve().parents[1]
REGISTRY_URI = 'urn:car-rental:scenario-check'
SOURCES = ['openapi.yaml', 'positive-scenarios.md', 'negative-scenarios.md']


class NoRedirect(HTTPRedirectHandler):
    """Report the actual status instead of following a mismatching redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def timestamp():
    return datetime.now(ZoneInfo('Europe/Budapest')).isoformat(timespec='seconds')


def source_hash(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve(document, value):
    seen = set()
    while isinstance(value, dict) and '$ref' in value:
        pointer = value['$ref']
        if not pointer.startswith('#/') or pointer in seen:
            raise ValueError(f'Unsupported or circular Reference Object: {pointer}')
        seen.add(pointer)
        value = document
        for part in pointer[2:].split('/'):
            part = part.replace('~1', '/').replace('~0', '~')
            value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def load_scenarios(path, prefix, expected_count):
    text = path.read_text(encoding='utf-8')
    headings = list(re.finditer(rf'^### ({prefix}-\d{{3}})\. (.+)$', text, re.M))
    scenarios = []
    for index, heading in enumerate(headings):
        block = text[heading.end():headings[index + 1].start() if index + 1 < len(headings) else len(text)]
        commands = re.findall(r'^Invoke-(?:Positive|Negative)Mock .+$', block, re.M)
        if len(commands) != 1:
            raise ValueError(f'{heading[1]}: expected exactly one documented mock command')
        tokens = shlex.split(commands[0])
        if (len(tokens) - 1) % 2:
            raise ValueError(f'{heading[1]}: malformed mock command')
        options = {}
        for number in range(1, len(tokens), 2):
            key = tokens[number].removeprefix('-')
            if key in options or key not in {'Method', 'Path', 'Status', 'Role', 'Example', 'RequestExample'}:
                raise ValueError(f'{heading[1]}: unsupported/duplicate option {key}')
            options[key] = tokens[number + 1]
        op = re.search(r'\| (?:Операція та вимоги|OP / REQ) \| (OP-\d{2})', block)
        if not op:
            raise ValueError(f'{heading[1]}: missing OP context')
        scenarios.append({
            'id': heading[1], 'title': heading[2], 'kind': 'positive' if prefix == 'POS' else 'negative_static',
            'op_id': op[1], 'source': path.name, 'documented_command': commands[0],
            'method': options['Method'].upper(), 'path': options['Path'],
            'status': int(options['Status']), 'role': options['Role'],
            'example': options.get('Example'), 'request_example': options.get('RequestExample'),
        })
    expected = [f'{prefix}-{number:03}' for number in range(1, expected_count + 1)]
    if [item['id'] for item in scenarios] != expected:
        raise ValueError(f'{path.name}: expected exactly {expected_count} consecutive {prefix} scenarios')
    return scenarios


class Checks:
    def __init__(self):
        self.items = []

    def add(self, name, passed, expected=None, actual=None, detail=None):
        item = {'name': name, 'result': 'PASS' if passed else 'FAIL'}
        if expected is not None:
            item['expected'] = expected
        if actual is not None:
            item['actual'] = actual
        if detail:
            item['detail'] = detail
        self.items.append(item)

    def skip(self, name, reason):
        self.items.append({'name': name, 'result': 'NOT_APPLICABLE', 'detail': reason})


def schema_errors(schema, instance, registry):
    validator = OAS31Validator(schema, registry=registry, _resolver=registry.resolver(REGISTRY_URI),
                               format_checker=OAS31Validator.FORMAT_CHECKER)
    return [{'path': '/'.join(map(str, error.path)) or '$', 'message': error.message}
            for error in validator.iter_errors(instance)]


def operation_for(document, scenario):
    path = urlsplit(scenario['path']).path
    found = []
    for template, methods in document['paths'].items():
        pattern = ''.join('[^/]+' if part.startswith('{') else re.escape(part)
                          for part in re.split(r'(\{[^}]+\})', template))
        if re.fullmatch(pattern, path) and scenario['method'].lower() in methods:
            found.append((template, methods[scenario['method'].lower()]))
    if len(found) != 1 or found[0][1]['x-op-id'] != scenario['op_id']:
        raise ValueError(f"{scenario['id']}: mock carrier does not match its documented OP")
    return found[0]


def prepare(document, scenario, registry):
    template, operation = operation_for(document, scenario)
    response = resolve(document, operation['responses'][str(scenario['status'])])
    media = response.get('content', {}).get('application/json')
    expected_body = None
    if scenario['example']:
        if not media or scenario['example'] not in media.get('examples', {}):
            raise ValueError(f"{scenario['id']}: selected example is not attached to the response")
        expected_body = resolve(document, media['examples'][scenario['example']])['value']
    elif scenario['status'] != 204:
        raise ValueError(f"{scenario['id']}: JSON response needs an explicit named example")
    body = None
    if scenario['request_example']:
        request_media = resolve(document, operation['requestBody'])['content']['application/json']
        if scenario['request_example'] not in request_media.get('examples', {}):
            raise ValueError(f"{scenario['id']}: request example is not attached to the operation")
        body = resolve(document, request_media['examples'][scenario['request_example']])['value']
        problems = schema_errors(request_media['schema'], body, registry)
        if problems:
            raise ValueError(f"{scenario['id']}: invalid request carrier: {problems}")
    elif operation.get('requestBody', {}).get('required'):
        raise ValueError(f"{scenario['id']}: request carrier lacks its required body")
    if scenario['role'] not in {'guest', 'client', 'administrator'}:
        raise ValueError(f"{scenario['id']}: invalid mock role label")
    if operation.get('security', document.get('security')) == [{'BearerAuth': []}] and scenario['role'] == 'guest':
        raise ValueError(f"{scenario['id']}: agreed static carrier must pass Prism's Bearer presence check")
    return template, operation, response, media, expected_body, body


def location_target(request_url, raw_location, expected_path):
    """Resolve a URI-reference against the actual request before comparing it."""
    resolved = urljoin(request_url, raw_location)
    expected = urljoin(request_url, expected_path)

    def address(uri):
        parts = urlsplit(uri)
        port = parts.port
        if port is None:
            port = {'http': 80, 'https': 443}.get(parts.scheme.lower())
        return (parts.scheme.lower(), parts.hostname, port, parts.path,
                parts.query, parts.fragment, parts.username, parts.password)

    return resolved, expected, address(resolved) == address(expected)


def check_headers(document, template, response, actual_headers, payload, scenario, registry, checks, request_url):
    for name, definition in response.get('headers', {}).items():
        definition = resolve(document, definition)
        raw = actual_headers.get(name)
        present = raw is not None
        checks.add(f'header.{name}.present', present, expected='present', actual=raw)
        if not present:
            continue
        value = raw
        header_schema = definition.get('schema')
        if header_schema:
            resolved_schema = resolve(document, header_schema)
            if resolved_schema.get('type') == 'integer':
                if not re.fullmatch(r'[0-9]+', raw):
                    checks.add(f'header.{name}.schema', False, actual=raw, detail='Expected an integer header')
                    continue
                value = int(raw)
            problems = schema_errors(header_schema, value, registry)
            checks.add(f'header.{name}.schema', not problems, actual=raw, detail=problems)
        if name.lower() == 'allow':
            expected = sorted(method.upper() for method in document['paths'][template]
                              if method in {'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'})
            actual = sorted(method.strip().upper() for method in raw.split(','))
            checks.add('header.Allow.methods', actual == expected, expected, actual)
        elif name.lower() == 'www-authenticate':
            checks.add('header.WWW-Authenticate.value', raw == 'Bearer', 'Bearer', raw)
        elif name.lower() == 'retry-after':
            # This is a static response, not a test of the business clock.
            checks.add('header.Retry-After.positive', isinstance(value, int) and value > 0,
                       expected='positive integer seconds; no countdown assertion', actual=raw)
        elif name.lower() == 'location':
            expected_path = None
            prefix = document['servers'][0]['url']
            if scenario['op_id'] == 'OP-13':
                expected_path = prefix + urlsplit(scenario['path']).path
            elif isinstance(payload, dict) and isinstance(payload.get('id'), str):
                expected_path = prefix + urlsplit(scenario['path']).path.rstrip('/') + '/' + payload['id']
            if expected_path:
                resolved, expected_url, matches = location_target(request_url, raw, expected_path)
                checks.add('header.Location.resource_path', matches,
                           expected_url, raw,
                           detail={'resolved_url': resolved, 'request_url': request_url,
                                   'rule': 'Resolve with urljoin, then compare the complete created-resource address, including origin and no extra query/fragment.'})
            else:
                checks.add('header.Location.resource_path', False, detail='Cannot derive created resource URI from response')
    if scenario['op_id'] == 'OP-04' and scenario['status'] == 201:
        checks.add('registration.no_Location', actual_headers.get('Location') is None,
                   expected='absent', actual=actual_headers.get('Location'))
    if scenario['example'] == 'INVALID_CREDENTIALS':
        checks.add('login.no_Bearer_challenge', actual_headers.get('WWW-Authenticate') is None,
                   expected='absent', actual=actual_headers.get('WWW-Authenticate'))


def run_case(document, prepared, scenario, base_url, opener, registry, timeout):
    template, operation, response_spec, media, expected_body, body = prepared
    prefer = f"code={scenario['status']}"
    if scenario['example']:
        prefer += ', example=' + scenario['example']
    headers = {'Accept': 'application/json', 'Prefer': prefer}
    if scenario['role'] != 'guest':
        headers['Authorization'] = 'Bearer mock-' + scenario['role']
    request_data = None
    if body is not None:
        headers['Content-Type'] = 'application/json'
        request_data = json.dumps(body, ensure_ascii=True).encode('utf-8')
    url = base_url + scenario['path']
    checks = Checks()
    result = {key: scenario[key] for key in ['id', 'kind', 'title', 'op_id', 'source', 'documented_command']}
    result['request'] = {'method': scenario['method'], 'url': url, 'mock_role': scenario['role'],
                         'request_example': scenario['request_example'], 'prefer': prefer,
                         'bearer_present': 'Authorization' in headers}
    result['expected'] = {'status': scenario['status'], 'named_example': scenario['example'],
                          'error_code': expected_body['error']['code'] if scenario['kind'] == 'negative_static' else None}
    result['started_at'] = timestamp()
    try:
        request = Request(url, method=scenario['method'], headers=headers, data=request_data)
        try:
            received = opener.open(request, timeout=timeout)
        except HTTPError as error:
            received = error  # Non-2xx is an expected HTTP response in NEG cases.
        with received:
            status = received.status
            received_headers = received.headers
            raw = received.read()
        payload = None
        parse_problem = None
        if raw:
            try:
                payload = json.loads(raw)
            except (UnicodeError, ValueError) as error:
                parse_problem = str(error)
        result['actual'] = {'status': status, 'headers': dict(received_headers.items()), 'body_bytes': len(raw),
                             'json': payload, 'body_text': raw.decode('utf-8', errors='replace')}
        checks.add('http.status', status == scenario['status'], scenario['status'], status)
        if scenario['status'] == 204:
            checks.add('http.no_content', not raw, expected=0, actual=len(raw))
            content_length = received_headers.get('Content-Length')
            checks.add('http.204_content_length', content_length is None or content_length == '0',
                       expected='absent or 0', actual=content_length)
            checks.skip('body.schema', '204 has no representation schema')
            checks.skip('body.named_example', '204 has no named response example')
        else:
            actual_type = received_headers.get('Content-Type', '').split(';')[0].strip().lower()
            checks.add('http.content_type', actual_type == 'application/json', 'application/json', actual_type)
            parsed = bool(raw) and parse_problem is None
            checks.add('body.json_parse', parsed, expected='non-empty JSON', detail=parse_problem)
            if parsed:
                problems = schema_errors(media['schema'], payload, registry)
                checks.add('body.schema', not problems, detail=problems)
                checks.add('body.named_example', payload == expected_body,
                           expected=expected_body, actual=payload)
            else:
                checks.add('body.schema', False, detail='No parsed JSON body to validate')
                checks.add('body.named_example', False, detail='No parsed JSON body to compare')
        if scenario['kind'] == 'negative_static':
            error = payload.get('error') if isinstance(payload, dict) else None
            structure = (isinstance(payload, dict) and set(payload) == {'error'} and isinstance(error, dict)
                         and set(error) == {'code', 'message', 'details'}
                         and isinstance(error.get('code'), str)
                         and isinstance(error.get('message'), str) and bool(error['message'].strip())
                         and isinstance(error.get('details'), dict))
            checks.add('error.structure', structure, expected='error with required code, Ukrainian message, object details')
            checks.add('error.code', isinstance(error, dict) and error.get('code') == result['expected']['error_code'],
                       expected=result['expected']['error_code'], actual=error.get('code') if isinstance(error, dict) else None)
        check_headers(document, template, response_spec, received_headers, payload, scenario, registry, checks, url)
    except (URLError, TimeoutError, OSError) as error:
        checks.add('http.transport', False, detail=str(error))
        result['transport_error'] = str(error)
    except Exception as error:
        # A check failure must be recorded rather than abort the remaining cases.
        checks.add('runner.exception', False, detail=f'{type(error).__name__}: {error}')
    result['checks'] = checks.items
    result['result'] = 'FAIL' if any(item['result'] == 'FAIL' for item in checks.items) else 'PASS'
    result['finished_at'] = timestamp()
    failures = [item['name'] for item in checks.items if item['result'] == 'FAIL']
    print(f"{scenario['id']}: {result['result']}" + (' [' + ', '.join(failures) + ']' if failures else ''))
    return result


def write_results(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:4010/api/v1')
    parser.add_argument('--output', type=Path, default=API / 'scenario-validation-results.json')
    parser.add_argument('--timeout', type=float, default=10)
    parser.add_argument('--baseline', type=Path, default=API / 'history/addendum-001-baseline/scenario-validation-results.json',
                        help='Optional previous evidence; when present, preserve its summary and failures in the new JSON')
    args = parser.parse_args()
    base_url = args.base_url.rstrip('/')
    document = yaml.safe_load((API / 'openapi.yaml').read_text(encoding='utf-8'))
    base = urlsplit(base_url)
    if base.path != document['servers'][0]['url'] or base.query or base.fragment:
        parser.error('base-url must contain the documented /api/v1 prefix exactly once')
    metadata = {'purpose': 'static_mock_response_validation_only', 'started_at': timestamp(),
                'base_url': base_url, 'command': subprocess.list2cmdline([sys.executable, *sys.argv]), 'python': sys.version.split()[0],
                'tools': {name: version(name) for name in ['openapi-schema-validator', 'jsonschema', 'PyYAML', 'referencing']},
                'source_sha256': {name: source_hash(API / name) for name in SOURCES},
                'limitations': ['No business-rule, real authentication/role/ownership or persistence verification.',
                                'NEG requests are the agreed valid mock carriers, not the real negative input.',
                                'Retry-After validates static header form, not a business countdown.',
                                'ADD-001 resolves session and calendar rules; mock does not verify actual expiry, token invalidation or calendar calculations. API-GATE is not performed.']}
    metadata['requirements_addendum_sha256'] = source_hash(API.parent / 'spec/srs-addendum-001.md')
    results = {'metadata': metadata, 'results': []}
    try:
        if args.baseline.exists():
            if args.baseline.resolve() == args.output.resolve():
                raise ValueError('Output must not overwrite the baseline evidence')
            baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
            results['baseline_evidence'] = {
                'file': str(args.baseline.resolve().relative_to(API.parent)),
                'sha256': source_hash(args.baseline), 'result': baseline['result'],
                'summary': baseline['summary'],
                'failures': [{'id': row['id'], 'op_id': row['op_id'],
                              'checks': [check for check in row['checks'] if check['result'] == 'FAIL']}
                             for row in baseline['results'] if row['result'] == 'FAIL'],
            }
        scenarios = load_scenarios(API / 'positive-scenarios.md', 'POS', 48)
        scenarios += load_scenarios(API / 'negative-scenarios.md', 'NEG', 103)
        registry = Registry().with_resource(REGISTRY_URI, Resource.from_contents(document, default_specification=DRAFT202012))
        prepared = [prepare(document, scenario, registry) for scenario in scenarios]
        results['planned'] = {'positive': 48, 'negative_static': 103, 'total': 151}
        with socket.create_connection((base.hostname, base.port or 80), timeout=args.timeout):
            pass
    except Exception as error:
        results.update({'result': 'NOT_RUN', 'setup_error': f'{type(error).__name__}: {error}',
                        'summary': {'attempted': 0, 'pass': 0, 'fail': 0}, 'finished_at': timestamp()})
        write_results(args.output, results)
        print(f'NOT_RUN: {error}; results: {args.output}')
        return 2
    opener = build_opener(NoRedirect())
    for scenario, data in zip(scenarios, prepared):
        results['results'].append(run_case(document, data, scenario, base_url, opener, registry, args.timeout))
    by_kind = {}
    for kind in ['positive', 'negative_static']:
        rows = [row for row in results['results'] if row['kind'] == kind]
        by_kind[kind] = {'attempted': len(rows), 'pass': sum(row['result'] == 'PASS' for row in rows),
                         'fail': sum(row['result'] == 'FAIL' for row in rows)}
    check_counts = Counter(check['result'] for row in results['results'] for check in row['checks'])
    results['summary'] = {'attempted': len(results['results']),
                          'pass': sum(row['result'] == 'PASS' for row in results['results']),
                          'fail': sum(row['result'] == 'FAIL' for row in results['results']),
                          'by_kind': by_kind, 'assertions': dict(check_counts)}
    results['result'] = 'FAIL' if results['summary']['fail'] else 'PASS'
    results['finished_at'] = timestamp()
    write_results(args.output, results)
    print(json.dumps(results['summary'], ensure_ascii=False))
    print(f"RESULT: {results['result']}; evidence: {args.output}")
    return 1 if results['summary']['fail'] else 0


if __name__ == '__main__':
    sys.exit(main())
