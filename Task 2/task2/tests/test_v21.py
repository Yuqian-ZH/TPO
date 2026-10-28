"""task2_v2.1: the defects found in task2_v2 after its runs (README 8.4), each on a constructed input, and v2.1
equal to v2 wherever v2 was right."""
import json
import os

import pytest

from components.state import make_state, model_data, state_for_case
from cvrp import canon
from cvrp.data import load_instance
from cvrp.oracle import oracle_for
from cvrp.validate import errors
from test_v2_attribution import AUDIT_STATES, _plan_decisions
from test_v2_localization import REF, TEST, _ok, sample
from v2 import attribution as att2, localization as loc2
from v21 import attribution as att21, localization as loc21

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = load_instance(os.path.join(ROOT, "instance", "cvrp_instance.json"))

# Review example: weight 0.8 on balance and W[1] <= 90 (penalty 1). The plan (412.8) is optimal under some anchors and
# not under others; anchor 3's optimum is 412.4, which v2's 0.1% tolerance took for 412.8.
TOL_MODS = [{"op": "set_objective_weight", "term": "balance", "weight": 0.8},
            {"op": "add_soft_constraint", "target": "W[1]", "sense": "<=", "rhs": 90, "penalty": 1}]
TOL_PLAN = {"routes": [[1, 7, 2, 8], [4, 5, 3, 6]]}


def _every_decision(sol):
    return _plan_decisions(sol) + [{"type": "SEP", "i": min(a, b), "j": max(a, b)}
                                   for a in sol["routes"][0] for b in sol["routes"][1]]


def _anchor(a):
    return {k: a["anchor"][k] for k in ("type", "i", "k")}


def test_exact_anchor_test_against_brute_force():
    st = make_state(TOL_PLAN, TOL_MODS)
    cur = canon.objective(TOL_PLAN, model_data(st), TOL_MODS)
    o = oracle_for(BASE, TOL_MODS)
    wrong_v2 = []
    for d in _every_decision(TOL_PLAN):
        a = att21.attribute(st, d)
        assert o.solve(TOL_MODS, [_anchor(a)])["objective"] >= cur - 1e-6
        assert a["anchor"]["current_plan_optimal"]
        gt = o.solve(TOL_MODS, [canon.forbid_decision(d), _anchor(a)])
        if not gt["feasible"]:
            assert a["conclusion"] == att21.FORCED
            continue
        assert a["conclusion"] == att21.PREFERRED
        assert a["alternative_objective"] == pytest.approx(gt["objective"])
        if att2.attribute(st, d)["conclusion"] == att2.CHEAPER:
            wrong_v2.append(a["decision_text"])
    assert "SAME(1,2)" in wrong_v2 and len(wrong_v2) == 16


def test_review_example_same_1_2():
    st, d = make_state(TOL_PLAN, TOL_MODS), {"type": "SAME", "i": 1, "j": 2}
    old, new = att2.attribute(st, d), att21.attribute(st, d)
    assert (old["anchor"]["i"], old["conclusion"]) == (3, att2.CHEAPER)
    assert old["objective_increase_if_forbidden"] == pytest.approx(-0.4)
    assert new["anchor"]["tried"][0] == {"anchor_customer": 3, "optimum": pytest.approx(412.4),
                                         "solver_objective": pytest.approx(412.4)}
    assert (new["anchor"]["i"], new["conclusion"]) == (5, att21.PREFERRED)
    assert new["objective_increase_if_forbidden"] > 0


def test_infeasible_current_plan_is_not_attributed():
    """Customer 4's demand corrected to 20: vehicle 1 of the reference plan carries 107 of 100. v2 attributed it."""
    sol = {"routes": [[1, 4, 7, 2], [5, 3, 6, 8]]}
    st = make_state(sol, [{"op": "modify_data", "field": "demand[4]", "value": 20}])
    d = {"type": "ADJ", "i": 3, "j": 6}
    assert att2.attribute(st, d)["conclusion"] in (att2.PREFERRED, att2.CHEAPER)
    a = att21.attribute(st, d)
    assert a["conclusion"] == att21.INFEASIBLE
    assert a["overloaded_routes"] == [{"vehicle": 1, "load": 107, "capacity": 100}]
    assert "anchor" not in a and "alternative_solution" not in a
    exp = att21.explain(a, llm=None, case_id="x", run=0)
    assert exp["attempts"] == [] and "107 of 100" in exp["text"]


def test_malformed_plan_is_an_error():
    with pytest.raises(ValueError):
        att21.attribute(make_state({"routes": [[1, 4, 7], [5, 3, 6, 8]]}), {"type": "ADJ", "i": 1, "j": 4})


@pytest.mark.parametrize("label,routes,mods,known", AUDIT_STATES, ids=[s[0] for s in AUDIT_STATES])
def test_same_as_v2_where_v2_was_right(label, routes, mods, known):
    """The three Task 3 states of the audit: v2's anchor claims hold exactly, so v2.1 gives the same answer."""
    sol = {"routes": routes}
    st = make_state(sol, mods)
    for d in _plan_decisions(sol):
        old, new = att2.attribute(st, d), att21.attribute(st, d)
        assert (new["conclusion"], _anchor(new)) == (old["conclusion"], _anchor(old))
        assert new.get("alternative_solution") == old.get("alternative_solution")
        assert new.get("attribution_set") == old.get("attribution_set")


# ---------------- localization ----------------

def _vehicle2(mtype, **kw):
    return sample("L[2]", "route_length", mtype, threshold=180, object_type="vehicle", vehicle=2, **kw)


def test_type_must_be_admissible():
    """3:2 for set_objective_weight on L[2], which the modification schema forbids: v2 used it, v2.1 does not."""
    s = [_vehicle2(t) for t in ("set_objective_weight", "add_soft_constraint", "set_objective_weight",
                                "add_soft_constraint", "set_objective_weight")]
    assert loc2.decide(s, REF, "x")["critique"]["modification_type"] == "set_objective_weight"
    out = loc21.decide(s, REF, "Vehicle 2 drives too far.")
    _ok(out)
    assert out["critique"]["modification_type"] == "add_soft_constraint"
    assert out["diagnostics"]["modification_type_from"] == "agreeing samples"
    mod = {"op": "add_soft_constraint", "target": "L[2]", "sense": "<=", "rhs": out["critique"]["threshold"],
           "penalty": 1}
    assert errors("modification", mod) == []


def test_no_admissible_type_falls_back_to_the_target():
    s = [sample("demand[4]", "demand", "add_soft_constraint", direction="correct", corrected=13, object_type="data",
                customers=[4])] * 5
    out = loc21.decide(s, REF, "Customer 4 orders 13.")
    assert out["critique"]["modification_type"] == "modify_data"
    assert out["diagnostics"]["modification_type_from"] == "target"


def test_both_types_admissible_for_objective_terms():
    """T7 (balance <= 50, 3:2 between soft constraint and weight) is decided as in v2."""
    st = state_for_case(TEST["T7"])
    s = [sample("balance", "distance_balance", t, threshold=50)
         for t in ("set_objective_weight", "add_soft_constraint", "set_objective_weight", "add_soft_constraint",
                   "set_objective_weight")]
    old, new = loc2.decide(s, st, "x"), loc21.decide(s, st, "x")
    assert new["critique"]["modification_type"] == old["critique"]["modification_type"] == "set_objective_weight"


def test_limit_that_does_not_apply_is_ignored():
    """forbid e[3,6] with limit 0 in three samples and null in two: one meaning, not two."""
    s = [sample("e[3,6]", "adjacency", "add_soft_constraint", direction="forbid", threshold=t,
                object_type="customer_pair", customers=[3, 6]) for t in (0, None, 0, None, 0)]
    assert loc2.decide(s, REF, "x")["confidence"] == "low"
    out = loc21.decide(s, REF, "Do not drive straight from 3 to 6.")
    _ok(out)
    assert out["confidence"] == "high" and out["critique"]["threshold"] == 0


def test_threshold_does_not_settle_a_data_correction():
    s = [sample("demand[4]", "demand", "modify_data", direction="correct", threshold=t, corrected=13,
                object_type="data", customers=[4]) for t in (None, 13, None, None, 13)]
    out = loc21.decide(s, REF, "Customer 4 orders 13 now.")
    assert out["confidence"] == "high"
    assert (out["critique"]["corrected_value"], out["critique"]["threshold"]) == (13, None)


def test_corrected_value_disagreement_is_asked():
    s = [sample("demand[4]", "demand", "modify_data", direction="correct", corrected=v, object_type="data",
                customers=[4]) for v in (13, 14, 13, 14, 13)]
    out = loc21.decide(s, REF, "Customer 4's order changed.")
    _ok(out)
    assert out["diagnostics"]["disagreement"] == "corrected_value"
    assert out["clarifying_question"] == ("What is the correct value of customer 4's order size (12 units in the plan's "
                                          "data): 13 or 14?")


def test_threshold_disagreement_still_asked():
    s = [_vehicle2("add_soft_constraint")] * 3 + [sample("L[2]", "route_length", "add_soft_constraint", threshold=150,
                                                         object_type="vehicle", vehicle=2)] * 2
    out = loc21.decide(s, REF, "Vehicle 2 drives too far.")
    assert out["confidence"] == "low" and out["diagnostics"]["disagreement"] == "threshold"
    assert out["clarifying_question"] == loc2.decide(s, REF, "Vehicle 2 drives too far.")["clarifying_question"]


RECORDED = [("results/raw/localization.json", "task2_v1"), ("results_v2/raw/localization.json", "task2_v2")]


@pytest.mark.parametrize("path,label", RECORDED, ids=[r[1] for r in RECORDED])
def test_recorded_samples_decided_as_v2(path, label):
    """Every sample set Task 2's v1 and v2 runs recorded: v2.1 reaches v2's confidence, critique and question."""
    d = json.load(open(os.path.join(ROOT, path)))
    runs = d["data"] if isinstance(d, dict) else d
    n = 0
    for per in runs:
        for cid, r in per.items():
            st = state_for_case(TEST[cid])
            for phase in ("initial", "clarified"):
                old = r[phase]
                args = (old["diagnostics"]["samples"], st, old["complaint"], old["clarification"])
                a, b = loc2.decide(*args), loc21.decide(*args)
                assert (b["confidence"], b["critique"], b["clarifying_question"]) == \
                       (a["confidence"], a["critique"], a["clarifying_question"]), (label, cid, phase)
                n += 1
    assert n == 60


def test_recheck_comparators_see_a_real_change():
    """The re-check would report the review example and the L[2] type split (it is not vacuous)."""
    from v21.recheck import compare_attribution, compare_localization
    st, d = make_state(TOL_PLAN, TOL_MODS), {"type": "SAME", "i": 1, "j": 2}
    diffs = compare_attribution(att2.attribute(st, d), att21.attribute(st, d))
    assert {"conclusion", "anchor", "alternative_solution"} <= set(diffs)
    assert compare_attribution(att2.attribute(st, d), att2.attribute(st, d)) == []
    s = [_vehicle2(t) for t in ("set_objective_weight", "add_soft_constraint", "set_objective_weight",
                                "add_soft_constraint", "set_objective_weight")]
    assert compare_localization(loc2.decide(s, REF, "x"), loc21.decide(s, REF, "x")) == ["critique"]
