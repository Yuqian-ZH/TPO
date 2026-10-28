import json
import os

from cvrp import canon
from cvrp.data import load_instance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTANCE = os.path.join(ROOT, "instance", "cvrp_instance.json")


def test_canonical_form():
    sol = {"routes": [[8, 6, 3, 5], [2, 7, 4, 1]]}
    assert canon.canonical(sol) == {"routes": [[1, 4, 7, 2], [5, 3, 6, 8]]}
    assert canon.unlabeled_key(sol) == canon.unlabeled_key(canon.canonical(sol))


def test_change_set_reversal_only():
    old = {"routes": [[1, 4, 7, 2], [5, 3, 6, 8]]}
    new = {"routes": [[2, 7, 4, 1], [5, 3, 6, 8]]}
    cs = canon.change_set(old, new)
    assert cs == {"moved": [], "added_edges": [], "removed_edges": [], "reversed": [1]}


def test_change_set_move():
    old = {"routes": [[1, 4, 7, 2], [5, 3, 6, 8]]}
    new = {"routes": [[1, 4, 7, 2, 8], [5, 3, 6]]}
    cs = canon.change_set(old, new)
    assert cs["moved"] == [8]
    assert cs["added_edges"] == [[0, 6], [2, 8]]
    assert cs["removed_edges"] == [[0, 2], [6, 8]]


def test_metrics_match_instance_report():
    data = load_instance(INSTANCE)
    rep = json.load(open(os.path.join(ROOT, "instance", "oracle_report.json")))
    sol = rep["optimal"]["solution"]
    assert canon.metrics(sol, data) == rep["optimal"]["metrics"]
    assert canon.objective(sol, data, []) == rep["optimal"]["objective"]


def test_anchor_and_compile():
    sol = {"routes": [[1, 4, 7, 2], [5, 3, 6, 8]]}
    prims, mods, inv = canon.compile_query({"type": "SWAP", "i": 1, "j": 3}, sol)
    assert prims == [{"type": "MOVE", "i": 1, "k": 2}, {"type": "MOVE", "i": 3, "k": 1}] and inv == {1, 3}
    assert canon.anchor(inv, sol, 8) == {"type": "MOVE", "i": 2, "k": 1, "role": "anchor"}
    _, mods, inv = canon.compile_query({"type": "APPLY_MODIFICATIONS", "mods": [
        {"op": "add_soft_constraint", "target": "L[2]", "sense": "<=", "rhs": 180, "penalty": 5}]}, sol)
    assert inv == {5, 3, 6, 8}
    assert canon.anchor(inv, sol, 8)["i"] == 1
    _, _, inv = canon.compile_query({"type": "APPLY_MODIFICATIONS", "mods": [
        {"op": "set_objective_weight", "term": "balance", "weight": 0.5}]}, sol)
    assert canon.anchor(inv, sol, 8) == {"type": "MOVE", "i": 1, "k": 1, "role": "anchor"}


def test_instance_design_goals():
    rep = json.load(open(os.path.join(ROOT, "instance", "oracle_report.json")))
    assert rep["all_design_goals_met"]
    assert rep["gurobi_check"]["objective_equal"] and rep["gurobi_check"]["routes_equal"]
    assert rep["gurobi_check"]["within_limit"]
