"""task2_v2 attribution (audit finding F1): the alternative's objective must be the one the solver optimized, with
vehicle labels anchored to the current plan, and must match brute force under the same anchor."""
import json
import os

import pytest

from components.attribution import attribute as attribute_v1
from components.state import make_state, model_data, state_for_case
from cases.gt import attribution_gt
from cvrp import canon
from cvrp.data import apply_data_mods, load_instance
from cvrp.oracle import oracle_for
from cvrp.validate import errors
from v2.attribution import CHEAPER, PREFERRED, anchor_for, attribute

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = load_instance(os.path.join(ROOT, "instance", "cvrp_instance.json"))
CASES = [c for split in ("dev", "test")
         for c in json.load(open(os.path.join(ROOT, "cases", f"{split}_cases.json")))["cases"]]

# The three states behind the 18 wrong numbers of Task 3's formal run (results/formal/trials, iterations 2-3):
# (trial, input plan, modifications in force, {decision: alternative objective v1 reported})
AUDIT_STATES = [
    ("A1B0C0/T2/r3/t3", [[1, 4, 7, 2], [5, 3, 6, 8]],
     [{"op": "set_objective_weight", "term": "makespan", "weight": 5},
      {"op": "add_soft_constraint", "target": "L[1]", "sense": "<=", "rhs": 200, "penalty": 50}],
     {"ADJ(1,4)": 1753, "ADJ(4,7)": 1753, "ADJ(0,2)": 1753, "SAME(1,4)": 1753,
      "SAME(4,7)": 1753, "SAME(2,4)": 1753}),
    ("A1B1C0/T2/r2/t2", [[1, 5, 6, 8], [2, 7, 4, 3]],
     [{"op": "add_soft_constraint", "target": "load_balance", "sense": "<=", "rhs": 5, "penalty": 50},
      {"op": "add_soft_constraint", "target": "W[1]", "sense": "<=", "rhs": 94, "penalty": 50}],
     {"SAME(1,6)": 668}),
    ("A1B1C0/T2/r2/t3", [[1, 2, 4, 7], [5, 3, 6, 8]],
     [{"op": "add_soft_constraint", "target": "L[1]", "sense": "<=", "rhs": 180, "penalty": 500},
      {"op": "set_objective_weight", "term": "balance", "weight": 5}],
     {"ADJ(0,1)": 20114, "ADJ(1,2)": 14042, "ADJ(2,4)": 14042, "ADJ(4,7)": 14042,
      "ADJ(0,7)": 14042, "SAME(1,2)": 18078, "SAME(1,4)": 14042, "SAME(1,7)": 18078,
      "SAME(2,4)": 14042, "SAME(2,7)": 20612, "SAME(4,7)": 14042}),
]


def _decision(text):
    t, rest = text.split("(")
    i, j = (int(v) for v in rest[:-1].split(","))
    return {"type": t, "i": i, "j": j}


def _plan_decisions(sol):
    out = []
    for r in sol["routes"]:
        path = [0, *r, 0]
        out += [{"type": "ADJ", "i": min(a, b), "j": max(a, b)} for a, b in zip(path, path[1:])]
        out += [{"type": "SAME", "i": min(a, b), "j": max(a, b)} for x, a in enumerate(r) for b in r[x + 1:]]
    return out


def _anchored_brute_force(sol, mods, d, anchor=None):
    """Brute force of the forbidden model under the attribution's anchor (default: Task 2's convention anchor);
    also checks the anchor's claim about the current plan."""
    o = oracle_for(BASE, mods)
    if anchor is None:
        anchor = anchor_for(sol, d, mods, BASE["n"])
    else:
        cur = canon.objective(sol, apply_data_mods(BASE, mods), mods)
        unforbidden = o.solve(mods, [{k: anchor[k] for k in ("type", "i", "k")}])["objective"]
        assert (unforbidden >= cur - 1e-6) == anchor["current_plan_optimal"]
    return o.solve(mods, [canon.forbid_decision(d), {k: anchor[k] for k in ("type", "i", "k")}])


@pytest.mark.parametrize("label,routes,mods,known", AUDIT_STATES, ids=[s[0] for s in AUDIT_STATES])
def test_audit_states_match_brute_force(label, routes, mods, known):
    sol = {"routes": routes}
    st = make_state(sol, mods)
    cur = canon.objective(sol, model_data(st), mods)
    for d in _plan_decisions(sol):
        a = attribute(st, d)
        gt = _anchored_brute_force(sol, mods, d, a["anchor"])
        assert a["anchor"]["current_plan_optimal"]         # every Task 3 loop plan was committed under an anchor
        assert a["conclusion"] in (PREFERRED, CHEAPER, "hard_constraint_forced")
        if not gt["feasible"]:
            assert a["conclusion"] == "hard_constraint_forced"
            continue
        assert a["alternative_objective"] == pytest.approx(gt["objective"])
        assert a["alternative_objective"] == pytest.approx(a["solver_objective"], abs=1e-3)
        assert a["objective_increase_if_forbidden"] == pytest.approx(gt["objective"] - cur)
        assert (a["conclusion"] == CHEAPER) == (gt["objective"] < cur - 1e-6)
        if a["decision_text"] in known:
            assert a["alternative_objective"] < known[a["decision_text"]] - 1


def test_label_dependent_soft_constraint():
    """Runner-up plan (368) with L[2] <= 180: v1 relabelled the alternative and charged the penalty to the wrong
    route (4,663); the alternative actually costs 369."""
    sol = {"routes": [[1, 7, 2, 8], [4, 5, 3, 6]]}
    mods = [{"op": "add_soft_constraint", "target": "L[2]", "sense": "<=", "rhs": 180, "penalty": 100}]
    st, d = make_state(sol, mods), {"type": "ADJ", "i": 3, "j": 6}
    assert attribute_v1(st, d)["alternative_objective"] == 4663
    a = attribute(st, d)
    assert a["current_objective"] == 368
    assert a["alternative_objective"] == 369 == _anchored_brute_force(sol, mods, d, a["anchor"])["objective"]
    assert canon.metrics(a["alternative_solution"], model_data(st))["L[2]"] <= 180


def test_anchor_under_which_the_plan_is_optimal():
    """Task 2's T2 reference fix (W[1] <= 92, plan 390): under the convention anchor (customer 2 stays on vehicle 2)
    a relabelled plan costs 380, so the plan looks suboptimal and every decision "cheaper to drop". The plan was
    solved with customer 3 anchored to vehicle 2; v2 finds that anchor and compares on the same feasible set."""
    sol = {"routes": [[1, 5, 4, 8], [2, 7, 3, 6]]}
    mods = [{"op": "add_soft_constraint", "target": "W[1]", "sense": "<=", "rhs": 92, "penalty": 30}]
    st, d = make_state(sol, mods), {"type": "ADJ", "i": 0, "j": 1}
    convention = _anchored_brute_force(sol, mods, {"type": "ADJ", "i": 0, "j": 1})
    assert convention["objective"] == 380 < 390
    a = attribute(st, d)
    assert (a["anchor"]["i"], a["anchor"]["k"], a["anchor"]["current_plan_optimal"]) == (3, 2, True)
    assert a["conclusion"] == PREFERRED
    assert a["alternative_objective"] == pytest.approx(_anchored_brute_force(sol, mods, d, a["anchor"])["objective"])


def test_cheaper_alternative_is_its_own_conclusion():
    """Same model as above with L[2] <= 180, plan with the two routes on the other vehicles: the long route
    violates the limit and no single-customer anchor makes this plan optimal, so forbidding a decision lowers the
    objective. v1 called that objective_preferred."""
    sol = {"routes": [[4, 5, 3, 6], [1, 7, 2, 8]]}
    mods = [{"op": "add_soft_constraint", "target": "L[2]", "sense": "<=", "rhs": 180, "penalty": 100}]
    st, d = make_state(sol, mods), {"type": "ADJ", "i": 0, "j": 4}
    assert attribute_v1(st, d)["conclusion"] == PREFERRED
    a = attribute(st, d)
    assert not a["anchor"]["current_plan_optimal"]
    assert a["conclusion"] == CHEAPER and a["objective_increase_if_forbidden"] < 0
    assert a["alternative_objective"] == pytest.approx(_anchored_brute_force(sol, mods, d, a["anchor"])["objective"])


def test_forced_decision_keeps_both_capacities():
    """A capacity change involves every customer, so Task 2's anchor rule would pick customer 1, which is in the
    decision; anchored, the IIS loses cap[2]. The anchor avoids decision customers and the IIS is taken without
    it, so both capacities are reported, as brute force requires (each one alone restores feasibility)."""
    sol = {"routes": [[1, 4, 7, 2], [5, 3, 6, 8]]}
    mods = [{"op": "modify_data", "field": "demand[3]", "value": 62},
            {"op": "modify_data", "field": "capacity", "value": 110}]
    d = {"type": "SEP", "i": 1, "j": 3}
    a = attribute(make_state(sol, mods), d)
    assert a["anchor"]["i"] not in (1, 3)
    assert a["conclusion"] == "hard_constraint_forced"
    assert a["attribution_set"]["constraints"] in attribution_gt(BASE, mods, sol, d)["acceptable_sets"]
    assert a["attribution_set"]["constraints"] == ["cap[1]", "cap[2]"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_unmodified_cases_unchanged(case):
    """Without label- or direction-dependent terms the anchor does not change the answer: the v2 set is still
    one of the ground-truth sets, and the conclusion and objective change agree with v1."""
    st, d = state_for_case(case), case["why_decision"]
    a, a1 = attribute(st, d), attribute_v1(st, d)
    assert a["conclusion"] == a1["conclusion"]
    got = a["attribution_set"]["constraints"] + a["attribution_set"]["variables"]
    assert got in case["gt"]["attribution"]["acceptable_sets"]
    if a["conclusion"] == PREFERRED:
        assert a["objective_increase_if_forbidden"] == a1["objective_increase_if_forbidden"]
        gt = attribution_gt(BASE, case["model_modifications"], case["solution"], d)
        assert a["objective_increase_if_forbidden"] == pytest.approx(gt["delta"])
    schema_errs = [e for e in errors("attribution_output", {**a, "conclusion": a1["conclusion"]})]
    assert schema_errs == []
