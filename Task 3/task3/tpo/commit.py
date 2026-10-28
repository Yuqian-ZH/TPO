"""Commit solve (plan 3.3 step 4): a fresh Gurobi model of instance + case model modifications + M_t,
single anchor relative to the current solution (Task 2 convention), full solve, no warm start."""
import time

from .task2_bridge import CVRPModel, apply_data_mods, canon, oracle_for


def anchor_for(base, cur_sol, mods):
    _, _, involved = canon.compile_query({"type": "APPLY_MODIFICATIONS", "mods": list(mods)}, cur_sol)
    return canon.anchor(involved, cur_sol, base["n"])


def orient_ties(sol, data, all_mods):
    """Driving direction is a solver tie unless the objective depends on it (A[i] / sum_arrival terms).
    Tied routes take Task 2's canonical direction, so direction-dependent checkers never pass or fail on
    the solver's arbitrary pick; returns the solution and the vehicles whose direction was changed."""
    routes, flipped = [list(r) for r in sol["routes"]], []
    obj = canon.objective({"routes": routes}, data, all_mods)
    for k, r in enumerate(routes):
        o = canon.orient(r)
        if o != r:
            trial = routes[:k] + [o] + routes[k + 1:]
            if abs(canon.objective({"routes": trial}, data, all_mods) - obj) < 1e-9:
                routes, flipped = trial, flipped + [k + 1]
    return {"routes": routes}, flipped


def commit_solve(base, case_mods, cur_sol, mods):
    t0 = time.perf_counter()
    anchor = anchor_for(base, cur_sol, mods)
    all_mods = list(case_mods) + list(mods)
    model = CVRPModel(base, all_mods)
    model.add_primitive(anchor, "commit")
    r = model.optimize()
    out = {"status": r["status"], "anchor": anchor, "solver_runtime_s": r["runtime_s"],
           "wall_s": time.perf_counter() - t0}
    if r["status"] == "optimal":
        data = apply_data_mods(base, all_mods)
        sol, flipped = orient_ties(r["solution"], data, all_mods)
        out.update(solution=sol, objective=canon.objective(sol, data, all_mods), metrics=canon.metrics(sol, data),
                   reoriented=flipped)
    return out


def tie_diagnostic(base, case_mods, cur_sol, mods, resolved, commit):
    """Brute force on the committed model: do all tied optima resolve the complaint? (not scored)"""
    anchor = anchor_for(base, cur_sol, mods)
    all_mods = list(case_mods) + list(mods)
    r = oracle_for(base, all_mods).solve(all_mods, [anchor])
    if not r["feasible"]:
        return {"oracle_feasible": False, "matches_commit": commit["status"] != "optimal"}
    flags = [resolved(s) for s in r["optimal"]]
    return {"oracle_feasible": True, "oracle_objective": r["objective"],
            "matches_commit": commit["status"] == "optimal" and abs(commit["objective"] - r["objective"]) < 1e-6,
            "n_optimal": len(flags), "n_optimal_resolving": sum(flags)}
