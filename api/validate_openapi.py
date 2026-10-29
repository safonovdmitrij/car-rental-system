"""Validate the OpenAPI document and its examples without starting an API.

Run from the repository root: python api/validate_openapi.py
Install the pinned tools from api/validation-requirements.txt first.
"""

import argparse
from collections import Counter
from importlib.metadata import version
from pathlib import Path
import re
import sys
import warnings

import yaml
from openapi_schema_validator import OAS31Validator
from openapi_spec_validator import OpenAPIV31SpecValidator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


class UniqueKeyLoader(yaml.SafeLoader):
    """Do not let a duplicated YAML mapping key silently replace an operation."""

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise ValueError(f"Duplicate YAML key {key!r}, line {key_node.start_mark.line + 1}")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def nodes(value, path=()):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from nodes(child, path + (key,))
    elif isinstance(value, list):
        for key, child in enumerate(value):
            yield from nodes(child, path + (key,))


def location(path):
    return "/".join(str(part) for part in path) or "$"


def run(spec_path):
    document = yaml.load(spec_path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    errors = []
    notes = []
    counts = Counter()
    if document.get("openapi") != "3.1.0":
        errors.append("Expected OpenAPI 3.1.0")

    def resolve(pointer):
        if not isinstance(pointer, str) or not pointer.startswith("#/"):
            raise ValueError(f"Expected an internal $ref, got {pointer!r}")
        target = document
        for token in pointer[2:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            target = target[int(token)] if isinstance(target, list) else target[token]
        return target

    def dereference(value):
        seen = set()
        while isinstance(value, dict) and "$ref" in value:
            pointer = value["$ref"]
            if pointer in seen:
                raise ValueError(f"Circular Reference Object: {pointer}")
            seen.add(pointer)
            value = resolve(pointer)
        return value

    for path, value in nodes(document):
        if isinstance(value, dict) and "$ref" in value:
            counts["refs"] += 1
            try:
                resolve(value["$ref"])
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                errors.append(f"{location(path)}: unresolved $ref: {exc}")
    if errors:
        return errors, notes, counts

    # Ready-made OpenAPI 3.1 validator, not a home-grown structural validator.
    structural_errors = list(OpenAPIV31SpecValidator(document).iter_errors())
    for error in structural_errors:
        errors.append(f"OpenAPI {location(error.path)}: {error.message}")
    counts["openapi_errors"] = len(structural_errors)

    # The standard library validator handles 2020-12 conditionals and $refs.
    # Its registry is local: validating examples never fetches a remote schema.
    base_uri = "urn:car-rental:openapi"
    registry = Registry().with_resource(
        base_uri, Resource.from_contents(document, default_specification=DRAFT202012)
    )
    used_examples = set()

    def validate_example(schema, value, context, kind):
        counts[kind] += 1
        validator = OAS31Validator(
            schema,
            registry=registry,
            _resolver=registry.resolver(base_uri),
            format_checker=OAS31Validator.FORMAT_CHECKER,
        )
        for error in validator.iter_errors(value):
            errors.append(f"Example {context}/{location(error.path)}: {error.message}")

    def examples(container, context, kind):
        if "schema" not in container:
            if "example" in container or container.get("examples"):
                errors.append(f"{context}: examples have no schema")
            return
        schema = container["schema"]
        if "example" in container:
            validate_example(schema, container["example"], context + "/example", kind)
        for name, entry in container.get("examples", {}).items():
            if "$ref" in entry:
                used_examples.add(entry["$ref"])
            entry = dereference(entry)
            if "value" not in entry:
                errors.append(f"{context}/{name}: external/missing example value cannot be verified")
                continue
            validate_example(schema, entry["value"], context + "/examples/" + name, kind)

    def content(container, context, kind):
        for media_type, media in container.get("content", {}).items():
            examples(media, context + "/" + media_type, kind)

    def response_examples(response, context):
        response = dereference(response)
        content(response, context, "response_examples")
        for name, header in response.get("headers", {}).items():
            header = dereference(header)
            examples(header, context + "/headers/" + name, "header_examples")

    # Check schema-local examples, including reusable primitive types.
    for name, schema in document.get("components", {}).get("schemas", {}).items():
        for path, node in nodes(schema):
            if not isinstance(node, dict):
                continue
            if isinstance(node.get("examples"), list):
                for number, value in enumerate(node["examples"]):
                    validate_example(node, value, f"schemas/{name}/{location(path)}/examples/{number}", "schema_examples")
            if "example" in node:
                validate_example(node, node["example"], f"schemas/{name}/{location(path)}/example", "schema_examples")
    # Unused reusable responses/parameters/headers must not hide invalid examples.
    for name, response in document.get("components", {}).get("responses", {}).items():
        response_examples(response, f"components/responses/{name}")
    for group, kind in [("parameters", "parameter_examples"), ("headers", "header_examples")]:
        for name, parameter in document.get("components", {}).get(group, {}).items():
            parameter = dereference(parameter)
            examples(parameter, f"components/{group}/{name}", kind)
            content(parameter, f"components/{group}/{name}", kind)

    operations = []
    for path, item in document.get("paths", {}).items():
        item = dereference(item)
        for method, operation in item.items():
            if method not in HTTP_METHODS:
                continue
            operations.append((path, method, operation))
            context = f"{method.upper()} {path}"
            for parameter in item.get("parameters", []) + operation.get("parameters", []):
                parameter = dereference(parameter)
                examples(parameter, context + "/parameters/" + parameter["name"], "parameter_examples")
                content(parameter, context + "/parameters/" + parameter["name"], "parameter_examples")
            if "requestBody" in operation:
                content(dereference(operation["requestBody"]), context + "/requestBody", "request_examples")
            for status, response in operation["responses"].items():
                response_examples(response, context + "/responses/" + str(status))

    counts["operations"] = len(operations)
    counts["schemas"] = len(document.get("components", {}).get("schemas", {}))
    counts["unique_examples"] = len(used_examples)
    op_ids = [operation.get("operationId") for _, _, operation in operations]
    if any(not isinstance(item, str) or not item for item in op_ids) or len(set(op_ids)) != len(op_ids):
        errors.append("Missing or duplicate operationId")
    expected_ids = {f"OP-{number:02}" for number in range(1, 23)}
    actual_ids = [operation.get("x-op-id") for _, _, operation in operations]
    if set(actual_ids) != expected_ids or len(actual_ids) != 22:
        errors.append("Expected exactly one of each OP-01 through OP-22")

    # Bind the numbered operations to their approved methods and URIs.
    operations_text = spec_path.with_name("operations.md").read_text(encoding="utf-8")
    expected_routes = {
        op_id: (method.lower(), uri)
        for op_id, method, uri in re.findall(
            r"^\| (OP-\d{2}) \| (GET|POST|PATCH|PUT|DELETE) \| ([^ ]+) \|", operations_text, re.M
        )
    }
    if set(expected_routes) != expected_ids:
        errors.append("operations.md must contain exactly the 22 expected operation IDs")
    if document.get("servers") is None or [entry["url"] for entry in document["servers"]] != ["/api/v1"]:
        errors.append("Expected the single base server /api/v1")
    scheme = document.get("components", {}).get("securitySchemes", {}).get("BearerAuth", {})
    if scheme.get("type") != "http" or scheme.get("scheme") != "bearer":
        errors.append("Expected HTTP Bearer authentication scheme")
    for path, method, operation in operations:
        op_id = operation.get("x-op-id")
        if expected_routes.get(op_id) != (method, "/api/v1" + path):
            errors.append(f"{op_id}: method/URI differ from operations.md")
        if path.startswith("/api/v1") or "servers" in operation:
            errors.append(f"{op_id}: repeated prefix or unexpected per-operation server")
        security = operation.get("security", document.get("security", []))
        public = op_id in {f"OP-{number:02}" for number in range(1, 6)}
        if public:
            if security and {} not in security:
                errors.append(f"{op_id}: a public operation requires authentication")
        elif security != [{"BearerAuth": []}]:
            errors.append(f"{op_id}: protected operation must require BearerAuth")
        for requirement in security:
            if requirement not in ({}, {"BearerAuth": []}):
                errors.append(f"{op_id}: unsupported security alternative {requirement}")

    declared_examples = document.get("components", {}).get("examples", {})
    for name in declared_examples:
        if f"#/components/examples/{name}" not in used_examples:
            errors.append(f"Example {name} has no schema-bound use and was not checked")

    # Non-failing review notes: inspect unused components instead of hiding them.
    # Reachability starts outside components; an orphan component cannot mark
    # its own dependencies as used.
    reachable = set()
    pending = [value["$ref"] for _, value in nodes({k: v for k, v in document.items() if k != "components"})
               if isinstance(value, dict) and "$ref" in value]
    for requirement in document.get("security", []):
        pending += [f"#/components/securitySchemes/{name}" for name in requirement]
    for _, _, operation in operations:
        for requirement in operation.get("security", []):
            pending += [f"#/components/securitySchemes/{name}" for name in requirement]
    while pending:
        pointer = pending.pop()
        if pointer in reachable:
            continue
        reachable.add(pointer)
        pending += [value["$ref"] for _, value in nodes(resolve(pointer))
                    if isinstance(value, dict) and "$ref" in value]
    for group, entries in document.get("components", {}).items():
        for name in entries:
            if f"#/components/{group}/{name}" not in reachable:
                notes.append(f"Unused component: {group}/{name}")

    return errors, notes, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", nargs="?", type=Path, default=Path(__file__).with_name("openapi.yaml"))
    args = parser.parse_args()
    print("Python", sys.version.split()[0])
    for package in ["openapi-spec-validator", "openapi-schema-validator", "jsonschema", "PyYAML"]:
        print(f"{package}=={version(package)}")
    # Show rather than suppress runtime/deprecation warnings from dependencies.
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        errors, notes, counts = run(args.spec.resolve())
    for warning in captured:
        notes.append(f"{warning.category.__name__}: {warning.message}")
    for error in errors:
        print("ERROR:", error)
    for note in notes:
        print("WARNING:", note)
    for name, count in sorted(counts.items()):
        print(f"{name}: {count}")
    print(f"RESULT: {'FAIL' if errors else 'PASS'}; errors={len(errors)}; warnings={len(notes)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
