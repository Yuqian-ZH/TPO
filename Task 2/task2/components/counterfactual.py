"""Counterfactual explanation (section 6.2).

method="local": one resident model per state; per query the query constraints and the single anchor
are added, the model is warm-started from the current solution and re-optimized over a growing
neighbourhood (L0: the query's customers may change vehicle, everyone else stays on their vehicle,
both routes may be re-sequenced; L1: plus each involved customer's 2 nearest customers; L2: all
customers).  Escalation happens only on infeasibility, so "infeasible" is reported only after L2.
Everything added for the query is removed afterwards.
method="full": control for evaluation only; a fresh model, no warm start, full solve, same anchor."""
import time

from cvrp import canon
from cvrp.data import apply_data_mods
from cvrp.model import CVRPModel
from cvrp.validate import errors

from .state import base_data, model_data, model_key

LEVELS = ("L0", "L1", "L2")
NEAREST = 2


class Engine:
    """Resident model for one state (instance + modifications); reused across queries."""

    def __init__(self, state):
        t0 = time.perf_counter()
        self.base = base_data(state)
        self.mods = list(state["modifications"])
        self.model = CVRPModel(self.base, self.mods)
        self.build_s = time.perf_counter() - t0

    def neighbourhood(self, involved, level, n, c):
        if level == "L0":
            return set(involved)
        if level == "L1":
            free = set(involved)
            for i in involved:
                others = sorted((j for j in range(1, n + 1) if j != i), key=lambda j: (c[i][j], j))
                free.update(others[:NEAREST])
            return free
        return set(range(1, n + 1))

    def solve_local(self, sol, prims, qmods, involved):
        m = self.model
        t0 = time.perf_counter()
        undo = [m.apply_modification(q) for q in qmods]
        added = []
        for idx, p in enumerate(prims):
            added += m.add_primitive(p, f"q{idx}")
        m.set_start(sol)
        veh = canon.vehicle_of(sol)
        n, c = m.data["n"], m.data["c"]
        tried, solve_only, res, level = [], 0.0, None, None
        for level in LEVELS:
            free = self.neighbourhood(involved, level, n, c)
            fixed = [m.y[veh[i], i] for i in range(1, n + 1) if i not in free]
            for v in fixed:
                v.LB = 1
            m.m.update()
            res = m.optimize()
            solve_only += res["runtime_s"]
            tried.append({"level": level, "status": res["status"], "free_customers": sorted(free),
                          "runtime_s": res["runtime_s"]})
            for v in fixed:
                v.LB = 0
            m.m.update()
            if res["status"] == "optimal":
                break
        m.remove(added)
        for u in reversed(undo):
            u()
        m.clear_start()
        return res, level, tried, time.perf_counter() - t0, solve_only


_ENGINES = {}


def engine_for(state):
    key = model_key(state)
    if key not in _ENGINES:
        _ENGINES[key] = Engine(state)
    return _ENGINES[key]


def solve_full(base, mods, qmods, prims):
    t0 = time.perf_counter()
    m = CVRPModel(base, list(mods) + list(qmods))
    for idx, p in enumerate(prims):
        m.add_primitive(p, f"q{idx}")
    res = m.optimize()
    return res, time.perf_counter() - t0, res["runtime_s"]


def counterfactual(state, query, method="local"):
    errs = errors("query", query)
    if errs:
        raise ValueError(f"invalid query: {errs}")
    sol = state["solution"]
    prims, qmods, involved = canon.compile_query(query, sol)
    data = apply_data_mods(model_data(state), qmods)
    anchor = canon.anchor(involved, sol, data["n"])
    prims = prims + [anchor]
    all_mods = list(state["modifications"]) + qmods
    out = {"query": query, "method": method, "anchor": anchor, "involved_customers": sorted(involved)}
    if method == "local":
        eng = engine_for(state)
        res, level, tried, wall, solve_only = eng.solve_local(sol, prims, qmods, involved)
        out.update({"level": level if res["status"] == "optimal" else None, "levels_tried": tried})
    elif method == "full":
        res, wall, solve_only = solve_full(base_data(state), state["modifications"], qmods, prims)
    else:
        raise ValueError(method)
    out["latency"] = {"with_model_setup_s": wall, "solve_only_s": solve_only}
    cur_obj = canon.objective(sol, data, all_mods)
    before = canon.metrics(sol, data)
    out.update({"current_objective": cur_obj, "current_distance": before["total_distance"]})
    if res["status"] != "optimal":
        out.update({"feasible": False, "status": res["status"]})
        return out
    new = res["solution"]
    after = canon.metrics(new, data)
    cs = canon.change_set(sol, new)
    out.update({
        "feasible": True, "status": "optimal", "solution": new,
        "objective": canon.objective(new, data, all_mods), "solver_objective": res["objective"],
        "total_distance": after["total_distance"],
        "change_set": {k: cs[k] for k in ("moved", "added_edges", "removed_edges")},
        "reversed_routes": cs["reversed"],
        "metric_changes": {k: {"before": before.get(k), "after": after.get(k)}
                           for k in sorted(set(before) | set(after)) if before.get(k) != after.get(k)},
    })
    out["delta_objective"] = out["objective"] - cur_obj
    out["delta_distance"] = out["total_distance"] - out["current_distance"]
    return out
