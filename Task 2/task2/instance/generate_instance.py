"""Generate the Task 2 CVRP instance: draw candidates with a fixed seed and keep the first that meets
design goals D1-D5 (all checked by the brute-force oracle).

Run from task2/:  python -m instance.generate_instance"""
import json
import os
import random

import numpy as np

from cvrp.canon import canonical, metrics, unlabeled_key
from cvrp.data import make_data
from cvrp.oracle import EPS, Oracle

SEED = 20261022
N, Q, DEPOT = 8, 100, (50, 50)
DEMAND_RANGE, TOTAL_RANGE = (10, 55), (170, 190)
HERE = os.path.dirname(os.path.abspath(__file__))


def partition(sol):
    return frozenset(frozenset(r) for r in sol["routes"])


def check_design(data, oracle=None):
    """Evaluate D1-D5; returns (all_ok, details)."""
    o = oracle or Oracle(data)
    q = data["q"]
    pairs = [[i, j, q[i] + q[j]] for i in range(1, N + 1) for j in range(i + 1, N + 1) if q[i] + q[j] > Q]
    res = o.solve()
    keys = {unlabeled_key(s) for s in res["optimal"]}
    best = canonical(res["optimal"][0])
    obj = res["obj"]
    worse = obj[np.isfinite(obj) & (obj > res["objective"] + EPS)]
    second_val = float(worse.min())
    second = canonical(o.solution(int(np.flatnonzero(obj == second_val)[0])))
    unc = o.solve(capacity=False)
    unc_parts = {partition(s) for s in unc["optimal"]}
    m = metrics(best, data)
    L, W = [m["L[1]"], m["L[2]"]], [m["W[1]"], m["W[2]"]]
    d = {
        "D1": {"ok": len(keys) == 1 and second_val > res["objective"],
               "distinct_optimal_solutions": len(keys), "optimal": res["objective"],
               "second_best": second_val, "gap": second_val - res["objective"], "second_best_solution": second},
        "D2": {"ok": bool(pairs), "pairs_over_capacity": pairs},
        "D3": {"ok": partition(best) not in unc_parts, "uncapacitated_optimal": unc["objective"],
               "uncapacitated_solutions": sorted({unlabeled_key(s) for s in unc["optimal"]})},
        "D4": {"ok": min(W) >= 0.8 * Q, "loads": W},
        "D5": {"ok": max(L) / min(L) >= 1.2, "lengths": L, "ratio": round(max(L) / min(L), 4)},
    }
    return all(v["ok"] for v in d.values()), d, best


def draw(rng):
    pts = []
    while len(pts) < N:
        p = (rng.randint(0, 100), rng.randint(0, 100))
        if p != DEPOT and p not in pts:
            pts.append(p)
    coords = [DEPOT] + pts
    draws = 0
    while True:
        draws += 1
        dem = [rng.randint(*DEMAND_RANGE) for _ in range(N)]
        if TOTAL_RANGE[0] <= sum(dem) <= TOTAL_RANGE[1]:
            return coords, [0] + dem, draws


def main():
    rng = random.Random(SEED)
    rejected = {"D2": 0, "oracle": 0}
    reasons = {}
    demand_draws = 0
    for cand in range(1, 100000):
        coords, demand, dd = draw(rng)
        demand_draws += dd
        data = make_data(coords, demand, Q)
        if not any(demand[i] + demand[j] > Q for i in range(1, N + 1) for j in range(i + 1, N + 1)):
            rejected["D2"] += 1  # D2 depends on demands only: checked before the oracle
            continue
        ok, d, best = check_design(data)
        if not ok:
            rejected["oracle"] += 1
            for key, v in d.items():
                if not v["ok"]:
                    reasons[key] = reasons.get(key, 0) + 1
            continue
        break
    inst = {
        "name": "task2_cvrp_v1",
        "protocol": "task2_v1",
        "description": "CVRP with 1 depot (node 0), 8 customers (nodes 1-8), 2 identical vehicles, no time windows.",
        "objective": "Minimize total travel distance (sum of both route lengths). Each vehicle leaves the depot "
                     "exactly once and returns to it, so both vehicles are used; every customer is served by "
                     "exactly one vehicle; the demand served by a vehicle may not exceed its capacity.",
        "distance": "c_ij = floor(euclidean(i, j) + 0.5): symmetric integers, so objective values are integers.",
        "vehicles": 2,
        "capacity": Q,
        "depot": 0,
        "nodes": [{"id": i, "x": coords[i][0], "y": coords[i][1], "demand": demand[i]} for i in range(N + 1)],
        "total_demand": sum(demand),
        "distance_matrix": data["c"],
        "conventions": {
            "vehicle_label": "In the reference solution the route containing customer 1 is vehicle 1.",
            "route_direction": "Each route runs so that its first customer has a smaller index than its last.",
        },
        "generator": {"script": "instance/generate_instance.py", "seed": SEED, "candidate_index": cand,
                      "rejected_candidates": cand - 1, "rejected_by": {"D2_precheck": rejected["D2"],
                                                                        "oracle_D1_D3_D4_D5": rejected["oracle"]},
                      "oracle_failures_by_goal": reasons, "demand_draws": demand_draws,
                      "coordinate_range": [0, 100], "depot": list(DEPOT), "demand_range": list(DEMAND_RANGE),
                      "total_demand_range": list(TOTAL_RANGE)},
    }
    with open(os.path.join(HERE, "cvrp_instance.json"), "w") as f:
        json.dump(inst, f, indent=2)
        f.write("\n")
    print(json.dumps({"candidate": cand, "rejected": rejected, "reasons": reasons,
                      "best": best, "D": {k: {kk: vv for kk, vv in v.items() if kk != "uncapacitated_solutions"}
                                          for k, v in d.items()}}, indent=2, default=str))


if __name__ == "__main__":
    main()
