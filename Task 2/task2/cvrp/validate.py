"""JSON Schema validation against schemas/*.schema.json (cross-file $ref resolved locally)."""
import json
import os

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schemas")
_VALIDATORS = {}


def _registry():
    resources = []
    for f in sorted(os.listdir(SCHEMA_DIR)):
        if f.endswith(".schema.json"):
            doc = json.load(open(os.path.join(SCHEMA_DIR, f)))
            resources.append((f, Resource.from_contents(doc)))
            resources.append((doc["$id"], Resource.from_contents(doc)))
    return Registry().with_resources(resources)


def validator(name):
    if name not in _VALIDATORS:
        doc = json.load(open(os.path.join(SCHEMA_DIR, f"{name}.schema.json")))
        _VALIDATORS[name] = Draft202012Validator(doc, registry=_registry())
    return _VALIDATORS[name]


def errors(name, obj):
    return [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in validator(name).iter_errors(obj)]


def is_valid(name, obj):
    return not errors(name, obj)
