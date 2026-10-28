import math
import os
import random

import pytest

# Gurobi's ObjVal may sit ~1e-4 off the exact value (default integrality tolerance acting on big-M rows);
# exact agreement is required for the objective recomputed from the extracted routes.
OBJVAL_TOL = 1e-3

from cvrp import canon
from cvrp.data import load_instance, make_data
from cvrp.model import CVRPModel
from cvrp.oracle import Oracle, oracle_for

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTANCE = os.path.join(ROOT, "instance", "cvrp_instance.json")


def random_instance(rng, n):
    coords = [(50, 50)]
    while len(coords) < n + 1:
        p = (rng.randint(0, 100), rng.randint(0, 100))
        if p not in coords:
            coords.append(p)
    demand = [0] + [rng.randint(10, 55) for _ in range(n)]
    cap = max(max(demand), math.ceil(sum(demand) * rng.uniform(0.5, 0.75)))
    return make_data(coords, demand, cap)


SMALL = [random_instance(random.Random(1000 + s), 5 + s % 3) for s in range(20)]


@pytest.mark.parametrize("idx", range(20))
def test_small_instances_optimal_value(idx):
    data = SMALL[idx]
    ref = Oracle(data).solve()
    g = CVRPModel(data).optimize()
    if not ref["feasible"]:
        assert g["status"] == "infeasible"
        return
    assert g["status"] == "optimal"
    assert g["objective"] == pytest.approx(ref["objective"], abs=OBJVAL_TOL)
    assert canon.is_feasible(g["solution"], data)
    assert canon.objective(g["solution"], data, []) == pytest.approx(ref["objective"], abs=1e-9)


def random_mod(rng, n):
    kind = rng.choice(["soft", "soft", "weight", "data"])
    if kind == "weight":
        return {"op": "set_objective_weight", "term": rng.choice(canon.OBJECTIVE_TERMS),
                "weight": rng.choice([0.25, 0.5, 1.0, 2.0])}
    if kind == "data":
        i = rng.randint(1, n)
        if rng.random() < 0.5:
            return {"op": "modify_data", "field": f"demand[{i}]", "value": rng.randint(5, 30)}
        return {"op": "modify_data", "field": f"coord[{i}]", "value": [rng.randint(0, 100), rng.randint(0, 100)]}
    t = rng.choice(["L", "W", "S", "A", "balance", "makespan", "load_balance", "sum_arrival", "e", "same", "sep"])
    if t in ("L", "W", "S"):
        target = f"{t}[{rng.randint(1, 2)}]"
    elif t == "A":
        target = f"A[{rng.randint(1, n)}]"
    elif t in ("e", "same", "sep"):
        lo = 0 if t == "e" else 1
        i, j = rng.sample(range(lo, n + 1), 2)
        target = f"{t}[{i},{j}]"
    else:
        target = t
    only_le = t in ("A", "balance", "makespan", "load_balance", "sum_arrival")
    sense = "<=" if only_le else rng.choice(["<=", ">=", "=="])
    rhs = {"L": 120, "W": 90, "S": 3, "A": 40, "balance": 20, "makespan": 160, "load_balance": 10,
           "sum_arrival": 400, "e": 0, "same": 0, "sep": 0}[t]
    if t in ("e", "same", "sep") and sense == ">=":
        rhs = 1
    return {"op": "add_soft_constraint", "target": target, "sense": sense, "rhs": rhs,
            "penalty": rng.choice([0.5, 2.0, 5.0])}


def random_prim(rng, n):
    t = rng.choice(["FIX_ARC", "MOVE", "FORCE_ADJ", "FORBID_ADJ", "FORCE_SAME", "FORCE_SEP"])
    if t == "FIX_ARC":
        i, j = rng.sample(range(0, n + 1), 2)
        return {"type": t, "k": rng.randint(1, 2), "i": i, "j": j}
    if t == "MOVE":
        return {"type": t, "i": rng.randint(1, n), "k": rng.randint(1, 2)}
    lo = 0 if t.endswith("ADJ") else 1
    i, j = rng.sample(range(lo, n + 1), 2)
    return {"type": t, "i": i, "j": j}


def check_against_oracle(data, mods, prims):
    ref = oracle_for(data, mods).solve(mods, prims)
    model = CVRPModel(data, mods)
    for p in prims:
        model.add_primitive(p, "t")
    g = model.optimize()
    if not ref["feasible"]:
        assert g["status"] == "infeasible", (mods, prims)
        return
    assert g["status"] == "optimal", (mods, prims)
    assert g["objective"] == pytest.approx(ref["objective"], abs=OBJVAL_TOL), (mods, prims)
    eff = oracle_for(data, mods).data
    sol = g["solution"]
    assert canon.is_feasible(sol, eff)
    assert all(canon.satisfies(sol, p) for p in prims)
    assert canon.objective(sol, eff, mods) == pytest.approx(ref["objective"], abs=1e-9), (mods, prims)


@pytest.mark.parametrize("seed", range(40))
def test_modifications_and_primitives_on_instance(seed):
    rng = random.Random(seed)
    data = load_instance(INSTANCE)
    mods = [random_mod(rng, data["n"]) for _ in range(rng.randint(0, 2))]
    prims = [random_prim(rng, data["n"]) for _ in range(rng.randint(0, 2))]
    check_against_oracle(data, mods, prims)


@pytest.mark.parametrize("seed", range(10))
def test_modifications_on_small_instances(seed):
    rng = random.Random(500 + seed)
    data = SMALL[seed]
    mods = [random_mod(rng, data["n"]) for _ in range(rng.randint(1, 3))]
    prims = [random_prim(rng, data["n"]) for _ in range(rng.randint(0, 1))]
    check_against_oracle(data, mods, prims)


def test_undo_restores_model():
    data = load_instance(INSTANCE)
    model = CVRPModel(data)
    base = model.optimize()["objective"]
    size = model.size()
    rng = random.Random(7)
    for _ in range(15):
        undo = model.apply_modification(random_mod(rng, data["n"]))
        cons = model.add_primitive(random_prim(rng, data["n"]), "t")
        model.optimize()
        model.remove(cons)
        undo()
        assert model.size() == size
        assert model.optimize()["objective"] == pytest.approx(base)
