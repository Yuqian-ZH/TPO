"""Counterfactual latency with equal set-up for both methods (audit finding F4, second half).

task2_v1 timed the local method on a resident model built before the timed call and the full re-solve with the
model built inside it, so part of the reported speed-up was model construction. Here every method runs in two
set-ups:
  warm  the model of the state is built once, outside the timed call (one resident model per method and state);
  cold  the model is built inside every timed call.
Methods: local_v1 (Task 2's frozen escalation rule), local_v2 (Task 3's tpo/counterfactual_v2.py rule, which the
TPO loop uses), full (every customer free, no MIP start; the resident model is reset before each solve so nothing
from the previous query is reused). All three use the same single anchor and the same output fields as
components/counterfactual.py."""
import os
import sys
import time

from components import counterfactual as t2cf
from components.state import model_data, model_key
from cvrp import canon
from cvrp.data import apply_data_mods

TASK3_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                                           "Task 3", "task3"))
if TASK3_ROOT not in sys.path:
    sys.path.append(TASK3_ROOT)   # appended: Task 2's own modules of the same name win
from tpo import counterfactual_v2 as t3cf  # noqa: E402  (read-only; frozen in Task 3's protocol)

METHODS = ("local_v1", "local_v2", "full")
SETUPS = ("warm", "cold")
ENGINE = {"local_v1": t2cf.Engine, "local_v2": t3cf.Engine, "full": t2cf.Engine}


def solve_full(eng, prims, qmods):
    m = eng.model
    undo = [m.apply_modification(q) for q in qmods]
    added = []
    for idx, p in enumerate(prims):
        added += m.add_primitive(p, f"q{idx}")
    m.clear_start()
    m.m.reset()
    res = m.optimize()
    m.remove(added)
    for u in reversed(undo):
        u()
    return res


class Runner:
    def __init__(self):
        self.resident = {}

    def engine(self, method, state):
        key = (method, model_key(state))
        if key not in self.resident:
            self.resident[key] = ENGINE[method](state)
        return self.resident[key]

    def query(self, state, query, method, setup):
        sol = state["solution"]
        prims, qmods, involved = canon.compile_query(query, sol)
        data = apply_data_mods(model_data(state), qmods)
        anchor = canon.anchor(involved, sol, data["n"])
        prims = prims + [anchor]
        all_mods = list(state["modifications"]) + qmods
        out = {"query": query, "method": method, "setup": setup, "anchor": anchor,
               "involved_customers": sorted(involved)}
        if setup == "warm":
            eng = self.engine(method, state)
        t0 = time.perf_counter()
        if setup == "cold":
            eng = ENGINE[method](state)
        if method == "full":
            res = solve_full(eng, prims, qmods)
            solve_only = res["runtime_s"]
        else:
            res, level, tried, _, solve_only = eng.solve_local(sol, prims, qmods, involved)
            out.update(level=level if res["status"] == "optimal" else None,
                       levels_tried=[{k: t[k] for k in ("level", "status", "escalate_reason") if k in t}
                                     for t in tried])
        out["latency"] = {"with_model_setup_s": time.perf_counter() - t0, "solve_only_s": solve_only,
                          "model_built_in_call": setup == "cold"}
        cur_obj = canon.objective(sol, data, all_mods)
        before = canon.metrics(sol, data)
        out.update(current_objective=cur_obj, current_distance=before["total_distance"])
        if res["status"] != "optimal":
            out.update(feasible=False, status=res["status"])
            return out
        new = res["solution"]
        after = canon.metrics(new, data)
        cs = canon.change_set(sol, new)
        out.update(feasible=True, status="optimal", solution=new, objective=canon.objective(new, data, all_mods),
                   solver_objective=res["objective"], total_distance=after["total_distance"],
                   change_set={k: cs[k] for k in ("moved", "added_edges", "removed_edges")})
        out["delta_objective"] = out["objective"] - cur_obj
        return out
