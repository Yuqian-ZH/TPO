import random

import pytest

from tpo.commit import anchor_for, commit_solve
from tpo.entities import decisions, extract
from tpo.proposal import check_modification, parse_choice, parse_proposal
from tpo.task2_bridge import apply_data_mods, canon, oracle_for

from conftest import REFERENCE


def random_mod(rng, n):
    kind = rng.choice(["soft", "soft", "weight", "data"])
    if kind == "weight":
        return {"op": "set_objective_weight", "term": rng.choice(["balance", "makespan", "load_balance", "sum_arrival"]),
                "weight": rng.choice([0.25, 0.8, 2.0])}
    if kind == "data":
        return {"op": "modify_data", "field": f"demand[{rng.randint(1, n)}]", "value": rng.randint(5, 40)}
    t = rng.choice(["L", "W", "S", "A", "balance", "e", "same", "sep"])
    target = {"L": f"L[{rng.randint(1, 2)}]", "W": f"W[{rng.randint(1, 2)}]", "S": f"S[{rng.randint(1, 2)}]",
              "A": f"A[{rng.randint(1, n)}]", "balance": "balance"}.get(t)
    if target is None:
        i, j = rng.sample(range(0 if t == "e" else 1, n + 1), 2)
        target = f"{t}[{i},{j}]"
    sense = "<=" if t in ("A", "balance") else rng.choice(["<=", ">=", "=="])
    rhs = {"L": 150, "W": 90, "S": 3, "A": 40, "balance": 30, "e": 0, "same": 0, "sep": 0}[t]
    return {"op": "add_soft_constraint", "target": target, "sense": sense, "rhs": rhs,
            "penalty": rng.choice([1.0, 10.0, 60.0])}


@pytest.mark.parametrize("seed", range(25))
def test_commit_matches_oracle(base, seed):
    rng = random.Random(seed)
    mods = [random_mod(rng, base["n"]) for _ in range(rng.randint(0, 3))]
    assert all(not check_modification(m, 8, 2) for m in mods), mods
    r = commit_solve(base, [], REFERENCE, mods)
    anchor = anchor_for(base, REFERENCE, mods)
    ref = oracle_for(base, mods).solve(mods, [anchor])
    if not ref["feasible"]:
        assert r["status"] == "infeasible"
        return
    assert r["status"] == "optimal"
    assert r["objective"] == pytest.approx(ref["objective"], abs=1e-9)
    assert canon.satisfies(r["solution"], anchor)
    assert canon.is_feasible(r["solution"], apply_data_mods(base, mods))


def test_commit_with_case_model_modification(base):
    case_mods = [{"op": "modify_data", "field": "demand[3]", "value": 54}]
    r = commit_solve(base, case_mods, REFERENCE, [])
    assert r["status"] == "optimal" and r["metrics"]["total_distance"] == 351


def test_tied_direction_is_canonical(base):
    # S[2] <= 3 does not depend on direction: whatever Gurobi picks, routes come back in canonical direction
    for pen in (0.5, 60):
        r = commit_solve(base, [], REFERENCE, [{"op": "add_soft_constraint", "target": "S[2]", "sense": "<=",
                                                 "rhs": 3, "penalty": pen}])
        assert all(route == canon.orient(route) for route in r["solution"]["routes"])


def test_preferred_direction_is_kept(base):
    # A[8] <= 100 is only met by driving route 2 backwards (A[8] = 44 instead of 167, same distance)
    r = commit_solve(base, [], REFERENCE, [{"op": "add_soft_constraint", "target": "A[8]", "sense": "<=",
                                            "rhs": 100, "penalty": 10}])
    assert r["solution"]["routes"][1] == [8, 6, 3, 5] and r["metrics"]["A[8]"] == 44
    assert r["metrics"]["total_distance"] == 351


def test_commit_infeasible_capacity(base):
    r = commit_solve(base, [], REFERENCE, [{"op": "modify_data", "field": "capacity", "value": 50}])
    assert r["status"] == "infeasible"


@pytest.mark.parametrize("mod,ok", [
    ({"op": "add_soft_constraint", "target": "L[1]", "sense": "<=", "rhs": 120, "penalty": 5}, True),
    ({"op": "add_soft_constraint", "target": "e[0,2]", "sense": "==", "rhs": 0, "penalty": 50}, True),
    ({"op": "add_soft_constraint", "target": "capacity", "sense": "<=", "rhs": 1, "penalty": 5}, False),
    ({"op": "add_soft_constraint", "target": "demand[3]", "sense": "<=", "rhs": 1, "penalty": 5}, False),
    ({"op": "add_soft_constraint", "target": "e[3,3]", "sense": "<=", "rhs": 0, "penalty": 5}, False),
    ({"op": "add_soft_constraint", "target": "A[5]", "sense": ">=", "rhs": 10, "penalty": 5}, False),
    ({"op": "add_soft_constraint", "target": "L[3]", "sense": "<=", "rhs": 10, "penalty": 5}, False),
    ({"op": "add_soft_constraint", "target": "L[1]", "sense": "<=", "rhs": 10, "penalty": 5000}, False),
    ({"op": "add_soft_constraint", "target": "L[1]", "sense": "<=", "rhs": 10, "penalty": 0}, False),
    ({"op": "set_objective_weight", "term": "distance", "weight": 2}, False),
    ({"op": "set_objective_weight", "term": "balance", "weight": 0.8}, True),
    ({"op": "set_objective_weight", "term": "balance", "weight": 150}, False),
    ({"op": "modify_data", "field": "demand[8]", "value": 40}, True),
    ({"op": "modify_data", "field": "demand[8]", "value": [1, 2]}, False),
    ({"op": "modify_data", "field": "coord[2]", "value": [10, 20]}, True),
    ({"op": "modify_data", "field": "coord[2]", "value": 7}, False),
    ({"op": "modify_data", "field": "capacity", "value": 120}, True),
    ({"op": "add_hard_constraint", "target": "L[1]"}, False),
    ({"op": "set_objective_weight", "term": "balance", "weight": 1, "extra": 1}, False),
])
def test_modification_whitelist(mod, ok):
    assert (not check_modification(mod, 8, 2)) == ok


def test_semantic_checks_without_task2_schema():
    # toy sizes skip Task 2's n = 8 schema; the semantic checks still apply
    assert not check_modification({"op": "add_soft_constraint", "target": "A[6]", "sense": "<=", "rhs": 1,
                                   "penalty": 1}, 6, 2)
    assert check_modification({"op": "add_soft_constraint", "target": "A[7]", "sense": "<=", "rhs": 1,
                               "penalty": 1}, 6, 2)


def test_parse_proposal_and_choice():
    good = {"parse_status": "json_ok", "parsed": {"rationale": "r", "modifications": [
        {"op": "set_objective_weight", "term": "balance", "weight": 0.8, }]}}
    assert parse_proposal(good, 8, 2)["valid"]
    too_many = {"parse_status": "json_ok", "parsed": {"modifications": [good["parsed"]["modifications"][0]] * 5}}
    assert not parse_proposal(too_many, 8, 2)["valid"]
    assert not parse_proposal({"parse_status": "json_error", "parsed": None}, 8, 2)["valid"]
    assert parse_choice({"parse_status": "json_ok", "parsed": {"choice": 2}}, 3) == {"ok": True, "index": 1,
                                                                                    "reason": None}
    assert not parse_choice({"parse_status": "json_ok", "parsed": {"choice": 4}}, 3)["ok"]
    assert not parse_choice({"parse_status": "json_ok", "parsed": {"choice": True}}, 3)["ok"]


@pytest.mark.parametrize("text,veh,cus", [
    ("The driver of vehicle 2 says today's plan is exhausting.", [2], []),
    ("Customer 5 is on a long detour.", [], [5]),
    ("Vehicle 1 visits customer 5 immediately before customer 3.", [1], [3, 5]),
    ("Customers 3, 6 and 8 complain about late deliveries.", [], [3, 6, 8]),
    ("Truck #2 makes 4 stops, too many.", [2], []),
    ("The road between customer 2 and the depot is closed.", [], [2]),
    ("Our customers wait too long on average.", [], []),
    ("Vehicle 3 and customer 12 do not exist.", [], []),
])
def test_entity_extraction(text, veh, cus):
    assert extract(text, 8, 2) == {"vehicles": veh, "customers": cus}


def test_decision_lists():
    vehicle = decisions(REFERENCE, {"vehicles": [2], "customers": []})
    assert sum(d["type"] == "ADJ" for d in vehicle) == 5 and sum(d["type"] == "SAME" for d in vehicle) == 6
    customer = decisions(REFERENCE, {"vehicles": [], "customers": [3]})
    assert {"type": "ADJ", "i": 3, "j": 5} in customer and {"type": "ADJ", "i": 3, "j": 6} in customer
    assert sum(d["type"] == "SEP" for d in customer) == 4 and sum(d["type"] == "SAME" for d in customer) == 3
    everything = decisions(REFERENCE, {"vehicles": [], "customers": []})
    assert len(everything) == 38
    assert all(canon.decision_holds(REFERENCE, d) for d in everything)
