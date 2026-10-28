"""Counterfactual probe for condition B (decision ④ in DECISIONS.md; Task 2 recommended this change).

Identical to Task 2's frozen local method (resident model per state, warm start from the current plan,
L0 -> L1 -> L2 neighbourhoods, same single anchor, same output fields) except for the escalation rule.
Task 2 escalates only on infeasibility, which soft constraints never trigger, so a restricted level that
merely pays the penalty was returned as the answer. Here a level is also escalated when it is stuck:
  soft_violation  a soft constraint added by the query is still violated at this level;
  unchanged       the query modifies the model but the plan did not change (moves / edges) at this level;
  modify_data     the query changes input data, which changes the problem itself: always go on to L2.
L2 (every customer free) is final either way. Task 2's files are imported, never modified."""
import time

from components import counterfactual as t2cf  # Task 2, frozen (on sys.path via task2_bridge)
from cvrp.validate import errors

from .task2_bridge import apply_data_mods, canon

RULE = "task3_v1: escalate on infeasible, remaining soft violation of the query, unchanged plan, or modify_data"


def stuck(res, sol, qmods, data):
    if res["status"] != "optimal":
        return "infeasible"
    if any(q["op"] == "modify_data" for q in qmods):
        return "modify_data"
    new = res["solution"]
    for q in qmods:
        if q["op"] == "add_soft_constraint":
            v = canon.violation(canon.target_value(new, data, q["target"]), q["sense"], q["rhs"])
            if v > 1e-9:
                return "soft_violation"
    if qmods:
        cs = canon.change_set(sol, new)
        if not cs["moved"] and not cs["added_edges"]:
            return "unchanged"
    return None


class Engine(t2cf.Engine):
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
        for level in t2cf.LEVELS:
            free = self.neighbourhood(involved, level, n, c)
            fixed = [m.y[veh[i], i] for i in range(1, n + 1) if i not in free]
            for v in fixed:
                v.LB = 1
            m.m.update()
            res = m.optimize()
            solve_only += res["runtime_s"]
            reason = stuck(res, sol, qmods, m.data)
            tried.append({"level": level, "status": res["status"], "free_customers": sorted(free),
                          "runtime_s": res["runtime_s"], "escalate_reason": reason})
            for v in fixed:
                v.LB = 0
            m.m.update()
            if reason is None:
                break
        m.remove(added)
        for u in reversed(undo):
            u()
        m.clear_start()
        return res, level, tried, time.perf_counter() - t0, solve_only


_ENGINES = {}


def engine_for(state):
    key = t2cf.model_key(state)
    if key not in _ENGINES:
        _ENGINES[key] = Engine(state)
    return _ENGINES[key]


def counterfactual(state, query):
    """Task 2's counterfactual(state, query, method="local") with the new escalation rule."""
    errs = errors("query", query)
    if errs:
        raise ValueError(f"invalid query: {errs}")
    sol = state["solution"]
    prims, qmods, involved = canon.compile_query(query, sol)
    data = apply_data_mods(t2cf.model_data(state), qmods)
    anchor = canon.anchor(involved, sol, data["n"])
    prims = prims + [anchor]
    all_mods = list(state["modifications"]) + qmods
    out = {"query": query, "method": "local", "rule": RULE, "anchor": anchor, "involved_customers": sorted(involved)}
    res, level, tried, wall, solve_only = engine_for(state).solve_local(sol, prims, qmods, involved)
    out.update({"level": level if res["status"] == "optimal" else None, "levels_tried": tried,
                "latency": {"with_model_setup_s": wall, "solve_only_s": solve_only}})
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
