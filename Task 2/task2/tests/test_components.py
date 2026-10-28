import json
import os

import pytest

from components.attribution import attribute, check_explanation, explanation_payload, template_explanation
from components.counterfactual import counterfactual
from components.localization import map_target
from components.state import make_state, state_for_case
from cvrp.validate import errors

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = json.load(open(os.path.join(ROOT, "cases", "dev_cases.json")))["cases"]


@pytest.mark.parametrize("case", DEV, ids=[c["id"] for c in DEV])
def test_attribution_output_schema_and_gt(case):
    a = attribute(state_for_case(case), case["why_decision"])
    assert errors("attribution_output", a) == []
    got = a["attribution_set"]["constraints"] + a["attribution_set"]["variables"]
    assert got in case["gt"]["attribution"]["acceptable_sets"]
    assert check_explanation(template_explanation(a), explanation_payload(a))["ok"]


@pytest.mark.parametrize("case", DEV, ids=[c["id"] for c in DEV])
@pytest.mark.parametrize("method", ["local", "full"])
def test_counterfactual_output_schema(case, method):
    r = counterfactual(state_for_case(case), case["what_if"], method)
    assert errors("counterfactual_output", r) == []
    assert r["feasible"] == case["gt"]["counterfactual"]["feasible"]
    if method == "local" and not r["feasible"]:
        assert [t["level"] for t in r["levels_tried"]] == ["L0", "L1", "L2"]


def test_resident_model_is_restored():
    st = make_state({"routes": [[1, 4, 7, 2], [5, 3, 6, 8]]}, [{"op": "modify_data", "field": "demand[4]", "value": 17}])
    st["solution"] = DEV[1]["solution"]
    before = counterfactual(st, {"type": "FIX_ARC", "k": 1, "i": 7, "j": 1}, "local")
    for q in ({"type": "APPLY_MODIFICATIONS", "mods": [{"op": "modify_data", "field": "demand[5]", "value": 40}]},
              {"type": "APPLY_MODIFICATIONS", "mods": [{"op": "add_soft_constraint", "target": "same[2,6]",
                                                        "sense": ">=", "rhs": 1, "penalty": 50}]},
              {"type": "FORCE_SAME", "i": 2, "j": 4}):
        counterfactual(st, q, "local")
    after = counterfactual(st, {"type": "FIX_ARC", "k": 1, "i": 7, "j": 1}, "local")
    assert before["objective"] == after["objective"] and before["change_set"] == after["change_set"]


def test_explanation_checker():
    payload = {"decision_text": "ADJ(1,4)", "objective_increase_if_forbidden": 5, "attribution_set":
               {"constraints": [], "variables": ["e[0,2]", "e[1,4]"]}, "x": 2.0213}
    assert check_explanation("Forbidding it costs 5 km more; detour ratio 2.02.", payload)["ok"]
    bad = check_explanation("It saves 12 km.", payload)
    assert bad["unmatched_numbers"] == ["12"]
    bad = check_explanation("Customer 9 and vehicle 3 are affected, see cap[7].", payload)
    assert set(bad["unknown_entities"]) == {"customer 9", "vehicle 3", "cap[7]"}


@pytest.mark.parametrize("sample,expected", [
    ({"object_type": "vehicle", "vehicle": 2, "customers": [], "aspect": "route_length"}, "L[2]"),
    ({"object_type": "vehicle", "vehicle": 1, "customers": [], "aspect": "load"}, "W[1]"),
    ({"object_type": "customer", "vehicle": None, "customers": [6], "aspect": "detour"}, "A[6]"),
    ({"object_type": "customer_pair", "vehicle": None, "customers": [8, 6], "aspect": "adjacency"}, "e[6,8]"),
    ({"object_type": "customer_pair", "vehicle": None, "customers": [4, 5], "aspect": "same_vehicle"}, "same[4,5]"),
    ({"object_type": "global", "vehicle": None, "customers": [], "aspect": "distance_balance"}, "balance"),
    ({"object_type": "data", "vehicle": None, "customers": [7], "aspect": "demand"}, "demand[7]"),
    ({"object_type": "vehicle", "vehicle": 3, "customers": [], "aspect": "load"}, None),
    ({"object_type": "customer", "vehicle": None, "customers": [9], "aspect": "arrival"}, None),
    ({"object_type": "global", "vehicle": None, "customers": [], "aspect": "stops"}, None),
])
def test_target_mapping(sample, expected):
    assert map_target(sample, 8, 2) == expected
