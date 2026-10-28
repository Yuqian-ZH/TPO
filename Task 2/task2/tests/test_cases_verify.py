import copy
import json
import os

import pytest

from cases.verify_cases import verify_case
from cvrp.data import load_instance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = load_instance(os.path.join(ROOT, "instance", "cvrp_instance.json"))
TESTS = {c["id"]: c for c in json.load(open(os.path.join(ROOT, "cases", "test_cases.json")))["cases"]}


def test_stored_cases_verify():
    for case in TESTS.values():
        assert verify_case(case, BASE)[0] == []


def mutate(cid, fn):
    case = copy.deepcopy(TESTS[cid])
    fn(case)
    return verify_case(case, BASE)[0]


@pytest.mark.parametrize("cid,fn,needle", [
    ("T1", lambda c: c["checker"]["params"].update(max=250), "already passes"),
    ("T2", lambda c: c["reference_modification"][0].update(penalty=10), "does not resolve"),
    ("T3", lambda c: c["gt"]["attribution"].update(delta=13.0), "attribution GT"),
    ("T5", lambda c: c["gt"]["counterfactual"].update(delta_distance=16), "counterfactual GT"),
    ("T7", lambda c: c["gt"]["localization"].update(targets=["balance[1]"]), "localization target"),
    ("T8", lambda c: c.update(clarity="ambiguous") or c["gt"]["localization"].update(confidence="high"),
     "low confidence"),
    ("T10", lambda c: c["why_decision"].update(type="NEAR"), "decision schema"),
])
def test_mutations_are_caught(cid, fn, needle):
    problems = mutate(cid, fn)
    assert any(needle in p for p in problems), problems
