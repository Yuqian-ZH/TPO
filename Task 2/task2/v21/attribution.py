"""Decision attribution, task2_v2.1: v2/attribution.py with two defects fixed.

1. Exact anchor test. v2 accepted the current plan as optimal under an anchor when the solver's optimum was within
   0.1% of the plan's objective. With fractional weights a real gap can be smaller: weight 0.8 on balance plus
   W[1] <= 90 (penalty 1), plan [[1,7,2,8],[4,5,3,6]] (412.8), SAME(1,2): anchor 3 has optimum 412.4, was accepted,
   and the decision was reported cheaper_without; under anchor 5 the plan is optimal and the objective prefers the
   decision. v2.1 accepts an anchor only if the solver's plan under it costs at least the current plan's objective,
   both by canon.objective, within OBJ_TOL. The model solves with MIPGap 0, so the solver's plan is optimal.
2. Infeasible current plan. v2 attributed a plan that is over capacity on the model's data (a demand correction can
   do that), and its objective, which no feasible plan reaches, passed the anchor test trivially. v2.1 returns the
   conclusion "current_plan_infeasible" with the overloaded routes and does not solve.

Everything else is v2's: anchor order, IIS without the anchor, no relabelling, orientation only on ties, the
cheaper_without conclusion, the explanation prompt and checker."""
import time

from components.attribution import (_decision_str, _objective_terms, constraint_activity, describe_decision,
                                    lp_relaxation)
from components.state import base_data, model_data
from cvrp import canon, ids
from cvrp.model import CVRPModel
from cvrp.validate import errors
from v2 import attribution as v2
from v2.attribution import CATEGORY_ORDER, CHEAPER, FORCED, OBJ_TOL, PREFERRED, anchor_candidates, orient_ties

INFEASIBLE = "current_plan_infeasible"
PROTOCOL = "task2_v2.1"
__all__ = ["CHEAPER", "FORCED", "INFEASIBLE", "PREFERRED", "attribute", "consistent_anchor", "explain",
           "overloaded_routes", "template_explanation"]


def consistent_anchor(model, sol, decision, mods, data, cur_obj):
    """(anchor, record): the first candidate under which the current plan is optimal for the current model, by the
    exact objective; the first candidate if there is none (then forbidding a decision may be cheaper)."""
    cands = anchor_candidates(sol, decision, mods, data["n"])
    tried = []
    for a in cands:
        cons = model.add_primitive(a, "check")
        r = model.optimize()
        model.remove(cons)
        best = canon.objective(r["solution"], data, mods) if r["status"] == "optimal" else None
        tried.append({"anchor_customer": a["i"], "optimum": best, "solver_objective": r.get("objective")})
        if best is not None and best >= cur_obj - OBJ_TOL:
            return a, {"current_plan_optimal": True, "tried": tried}
    return cands[0], {"current_plan_optimal": False, "tried": tried}


def overloaded_routes(sol, data):
    out = []
    for k, r in enumerate(sol["routes"], 1):
        load = sum(data["q"][i] for i in r)
        if load > data["Q"]:
            out.append({"vehicle": k, "load": load, "capacity": data["Q"]})
    return out


def attribute(state, decision):
    errs = errors("decision", decision)
    if errs:
        raise ValueError(f"invalid decision: {errs}")
    t0 = time.perf_counter()
    base, data, mods, sol = base_data(state), model_data(state), state["modifications"], state["solution"]
    if not canon.decision_holds(sol, decision):
        raise ValueError(f"{_decision_str(decision)} does not hold in the current solution")
    out = {"protocol": PROTOCOL, "decision": decision, "decision_text": _decision_str(decision),
           "decision_description": describe_decision(decision)}
    routes = sol["routes"]
    if not (len(routes) == data["K"] and all(routes)
            and sorted(i for r in routes for i in r) == list(range(1, data["n"] + 1))):
        raise ValueError(f"not a plan of this instance: {routes}")
    over = overloaded_routes(sol, data)
    if over:
        out.update({"conclusion": INFEASIBLE, "overloaded_routes": over,
                    "note": "The current plan violates capacity on the data in force, so no decision of it can be "
                            "attributed; re-plan on this data first.",
                    "solve_time_s": round(time.perf_counter() - t0, 4)})
        return out
    model = CVRPModel(base, mods)
    cur_obj = canon.objective(sol, data, mods)
    lp = lp_relaxation(model, decision)
    perturb = canon.forbid_decision(decision)
    anchor, anchor_check = consistent_anchor(model, sol, decision, mods, data, cur_obj)
    pcons = model.add_primitive(perturb, "attr")
    acons = model.add_primitive(anchor, "attr")
    res = model.optimize()
    out.update({"perturbation": {"constraint": perturb["type"], "ids": [c.ConstrName for c in pcons]},
                "anchor": {**anchor, "ids": [c.ConstrName for c in acons], **anchor_check},
                "current_objective": cur_obj})
    if res["status"] == "infeasible":
        # as v2: feasibility does not depend on vehicle labels, so the IIS is taken without the anchor
        model.remove(acons)
        out["anchor"]["ids"] = []
        out["anchor"]["dropped_for_iis"] = True
        iis = model.iis()
        by_cat = {c: [] for c in CATEGORY_ORDER}
        for cid in iis["constraints"]:
            by_cat.setdefault(ids.category(cid), []).append(cid)
        out.update({
            "conclusion": FORCED,
            "attribution_set": {"constraints": sorted(by_cat["business_specific"]), "variables": []},
            "iis": {"constraints_by_category": by_cat, "var_lower_bounds": iis["var_lower_bounds"],
                    "var_upper_bounds": iis["var_upper_bounds"],
                    "note": "IIS is one irreducible infeasible subset; it need not be unique. Only "
                            "business-specific constraints enter the attribution set; the anchor is a "
                            "convention and never does."},
        })
    elif res["status"] == "optimal":
        new, flipped = orient_ties(res["solution"], data, mods)
        new_obj = canon.objective(new, data, mods)
        if abs(new_obj - res["objective"]) > 1e-3 * max(1.0, abs(res["objective"])):
            raise AssertionError(f"alternative objective {new_obj} differs from the solver's {res['objective']}")
        cs = canon.change_set(sol, new)
        c = data["c"]
        added = [{"edge": f"e[{a},{b}]", "distance": c[a][b]} for a, b in cs["added_edges"]]
        removed = [{"edge": f"e[{a},{b}]", "distance": c[a][b]} for a, b in cs["removed_edges"]]
        terms = _objective_terms(sol, new, data, mods)
        assert sum(e["distance"] for e in added) - sum(e["distance"] for e in removed) == terms["distance"]
        delta = new_obj - cur_obj
        out.update({
            "conclusion": CHEAPER if delta < -OBJ_TOL else PREFERRED,
            "attribution_set": {"constraints": [], "variables": sorted({e["edge"] for e in added + removed})},
            "objective_increase_if_forbidden": delta,
            "objective_increase_by_term": terms,
            "edges_only_in_current_plan": removed, "edges_only_in_alternative": added,
            "customers_on_other_vehicle_in_alternative": cs["moved"],
            "alternative_solution": new,
            "alternative_objective": new_obj,
            "solver_objective": res["objective"],
            "alternative_reoriented": flipped,
        })
        if delta < -OBJ_TOL:
            out["note"] = ("Forbidding the decision lowers the objective: the current plan is not optimal for the "
                           "current model under any single-customer anchor, so the objective does not prefer "
                           "this decision.")
    else:
        out.update({"conclusion": "unknown", "solver_status": res["status"]})
    out["constraint_activity"] = constraint_activity(sol, data)
    out["lp_relaxation"] = lp
    out["solve_time_s"] = round(time.perf_counter() - t0, 4)
    return out


def template_explanation(att):
    if att["conclusion"] == INFEASIBLE:
        over = "; ".join(f"vehicle {o['vehicle']} carries {o['load']} of {o['capacity']}"
                         for o in att["overloaded_routes"])
        return (f"Decision {att['decision_text']} is not attributed: the current plan is over capacity on the data "
                f"in force ({over}).")
    return v2.template_explanation(att)


def explain(attribution_json, llm, case_id, run, component="explain_v2.1"):
    """v2's explanation (same prompt and checker); an infeasible plan gets the template and no LLM call."""
    if attribution_json["conclusion"] == INFEASIBLE:
        return {"text": template_explanation(attribution_json), "source": "template", "valid": True, "attempts": []}
    return v2.explain(attribution_json, llm, case_id, run, component=component)
