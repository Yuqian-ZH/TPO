"""Ground truth for test cases, computed by the brute-force oracle (never by Gurobi)."""
from cvrp import canon
from cvrp.data import apply_data_mods
from cvrp.oracle import oracle_for

from .checkers import complaint_resolved


def split_mods(mods):
    data_mods = [m for m in mods if m["op"] == "modify_data"]
    return data_mods, [m for m in mods if m["op"] != "modify_data"]


def edge_id(e):
    return f"e[{e[0]},{e[1]}]"


def attribution_gt(base, model_mods, sol, decision):
    data = apply_data_mods(base, model_mods)
    o = oracle_for(base, model_mods)
    assert canon.decision_holds(sol, decision), decision
    current = canon.objective(sol, data, model_mods)
    prim = canon.forbid_decision(decision)
    r = o.solve(model_mods, [prim])
    if not r["feasible"]:
        relaxed = o.solve(model_mods, [prim], capacity=False)
        # cap[k] is in every IIS iff dropping that single constraint restores feasibility
        needed = [f"cap[{k}]" for k in (1, 2)
                  if o.solve(model_mods, [prim], capacity=tuple(v for v in (1, 2) if v != k))["feasible"]]
        return {"conclusion": "capacity_forced" if relaxed["feasible"] else "forced_by_other_constraints",
                "acceptable_sets": [needed], "constraints_in_every_iis": needed}
    sets, details = [], []
    for s in r["optimal"]:
        cs = canon.change_set(sol, s)
        ids = sorted({edge_id(e) for e in cs["added_edges"] + cs["removed_edges"]})
        if ids not in sets:
            added = sum(data["c"][a][b] for a, b in cs["added_edges"])
            removed = sum(data["c"][a][b] for a, b in cs["removed_edges"])
            sets.append(ids)
            details.append({"edges": ids, "added_edges": cs["added_edges"], "removed_edges": cs["removed_edges"],
                            "added_distance": added, "removed_distance": removed,
                            "forbidden_optimum": canon.canonical(s)})
    delta = r["objective"] - current
    for d in details:
        assert abs(d["added_distance"] - d["removed_distance"] - delta) < 1e-9, (decision, d, delta)
    return {"conclusion": "objective_preferred", "delta": delta, "acceptable_sets": sets, "details": details}


def counterfactual_gt(base, model_mods, sol, query):
    prims, qmods, involved = canon.compile_query(query, sol)
    anchor = canon.anchor(involved, sol, base["n"])
    mods = list(model_mods) + qmods
    data = apply_data_mods(base, mods)
    o = oracle_for(base, mods)
    r = o.solve(mods, prims + [anchor])
    cur_obj = canon.objective(sol, data, mods)
    cur_dist = canon.metrics(sol, data)["total_distance"]
    out = {"anchor": anchor, "involved": sorted(involved), "current_objective": cur_obj,
           "current_distance": cur_dist, "feasible": r["feasible"]}
    if not r["feasible"]:
        out["infeasible_without_capacity"] = not o.solve(mods, prims + [anchor], capacity=False)["feasible"]
        out["outcome"] = "infeasible_capacity" if not out["infeasible_without_capacity"] else "infeasible_other"
        return out
    keys, change_sets = [], []
    for s in r["optimal"]:
        cs = canon.change_set(sol, s)
        if canon.change_key(cs) not in keys:
            keys.append(canon.change_key(cs))
            change_sets.append({**cs, "solution": s})
    dist = canon.metrics(r["optimal"][0], data)["total_distance"]
    out.update({"objective": r["objective"], "total_distance": dist, "delta_objective": r["objective"] - cur_obj,
                "delta_distance": dist - cur_dist, "acceptable_change_sets": change_sets})
    out["outcome"] = ("feasible_unchanged" if abs(dist - cur_dist) < 1e-9 else
                      "feasible_worse" if dist > cur_dist else "feasible_better")
    return out


def reference_check(base, case):
    """Solve the case model plus its reference modification (anchored like an APPLY_MODIFICATIONS
    query) by brute force; every optimal solution must resolve the complaint."""
    sol = case["solution"]
    q = {"type": "APPLY_MODIFICATIONS", "mods": case["reference_modification"]}
    prims, qmods, involved = canon.compile_query(q, sol)
    anchor = canon.anchor(involved, sol, base["n"])
    mods = list(case.get("model_modifications", [])) + qmods
    r = oracle_for(base, mods).solve(mods, prims + [anchor])
    if not r["feasible"]:
        return {"feasible": False, "all_optimal_resolve": False}
    checks = [complaint_resolved(case, s, base) for s in r["optimal"]]
    return {"feasible": True, "anchor": anchor, "objective": r["objective"],
            "solution": r["optimal"][0],
            "n_optimal": len(r["optimal"]), "all_optimal_resolve": all(c["resolved"] for c in checks),
            "check": checks[0]}
