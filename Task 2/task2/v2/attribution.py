"""Decision attribution, task2_v2 (audit finding F1). Same method as components/attribution.py (forbid the
decision and re-solve; infeasible -> IIS, feasible -> objective preference), with three changes:

1. Single anchor relative to the current plan, so "vehicle k" in the alternative is the same vehicle as in the
   current plan. Under a label-dependent term (W[1] <= 92) the anchor is not a harmless convention: it decides
   which labelled plans are allowed. The anchor is therefore the first customer, in Task 2's order (customers
   not involved in the decision or the modifications first, smallest first), under which the current plan is
   itself optimal for the current model; the current plan and the alternative are then compared on the same
   feasible set. Task 3 commits each plan under such an anchor, but the state does not record which one.
2. No relabelling, and a route is reversed only when that leaves the objective unchanged (Task 3's orient_ties
   rule). v1 put the alternative into canonical form, which changes the objective under a label-dependent
   (L[2] <= 180) or direction-dependent (A[i] <= 70) soft constraint; it reported 5,780 for a plan costing 380.
   The objective of the alternative is now checked against the solver's.
3. When forbidding the decision lowers the objective, the conclusion is "cheaper_without", not
   "objective_preferred". With the anchor of 1 this happens only when no single-customer anchor makes the
   current plan optimal, i.e. the plan is not optimal for the current model."""
import json
import os
import time

from components.attribution import (_decision_str, _objective_terms, check_explanation, constraint_activity,
                                    describe_decision, explanation_payload, lp_relaxation)
from components.llm_client import derive_seed
from components.state import base_data, model_data
from cvrp import canon, ids
from cvrp.model import CVRPModel
from cvrp.validate import errors

PROMPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")
V1_PROMPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "components", "prompts")
CATEGORY_ORDER = ("business_specific", "business_general", "structural", "convention", "perturbation", "soft")
FORCED, PREFERRED, CHEAPER = "hard_constraint_forced", "objective_preferred", "cheaper_without"
OBJ_TOL = 1e-6


def anchor_candidates(sol, decision, mods, n):
    """Task 2's single anchor for the query "forbid this decision" with the state's modifications in force,
    followed by every other customer: uninvolved first, then involved in the modifications, the decision's own
    customers last (a capacity change involves everyone, and Task 2 would then anchor customer 1)."""
    _, _, involved = canon.compile_query({"type": "APPLY_MODIFICATIONS", "mods": list(mods)}, sol)
    own = {v for v in (decision["i"], decision["j"]) if v}
    veh = canon.vehicle_of(sol)
    return [{"type": "MOVE", "i": i, "k": veh[i], "role": "anchor"}
            for i in sorted(range(1, n + 1), key=lambda i: (i in own, i in involved, i))]


def consistent_anchor(model, sol, decision, mods, cur_obj):
    """(anchor, record): the first candidate under which the current plan is optimal for the current model; the
    first candidate if there is none (then the plan is not optimal and forbidding a decision may be cheaper)."""
    cands = anchor_candidates(sol, decision, mods, model.data["n"])
    tried = []
    for a in cands:
        cons = model.add_primitive(a, "check")
        r = model.optimize()
        model.remove(cons)
        best = r.get("objective")
        tried.append({"anchor_customer": a["i"], "optimum": best})
        if r["status"] == "optimal" and best >= cur_obj - 1e-3 * max(1.0, abs(cur_obj)):
            return a, {"current_plan_optimal": True, "tried": tried}
    return cands[0], {"current_plan_optimal": False, "tried": tried}


def anchor_for(sol, decision, mods, n):
    """Task 2's convention anchor (the first candidate), without the optimality check."""
    return anchor_candidates(sol, decision, mods, n)[0]


def orient_ties(sol, data, mods):
    """Reverse a route into Task 2's canonical direction only if the objective does not change (Task 3's
    tpo/commit.py rule). Returns the solution and the vehicles whose direction was changed."""
    routes, flipped = [list(r) for r in sol["routes"]], []
    obj = canon.objective({"routes": routes}, data, mods)
    for k, r in enumerate(routes):
        o = canon.orient(r)
        if o != r:
            trial = routes[:k] + [o] + routes[k + 1:]
            if abs(canon.objective({"routes": trial}, data, mods) - obj) < 1e-9:
                routes, flipped = trial, flipped + [k + 1]
    return {"routes": routes}, flipped


def attribute(state, decision):
    errs = errors("decision", decision)
    if errs:
        raise ValueError(f"invalid decision: {errs}")
    t0 = time.perf_counter()
    base, data, mods, sol = base_data(state), model_data(state), state["modifications"], state["solution"]
    if not canon.decision_holds(sol, decision):
        raise ValueError(f"{_decision_str(decision)} does not hold in the current solution")
    model = CVRPModel(base, mods)
    cur_obj = canon.objective(sol, data, mods)
    lp = lp_relaxation(model, decision)
    perturb = canon.forbid_decision(decision)
    anchor, anchor_check = consistent_anchor(model, sol, decision, mods, cur_obj)
    pcons = model.add_primitive(perturb, "attr")
    acons = model.add_primitive(anchor, "attr")
    res = model.optimize()
    out = {"protocol": "task2_v2", "decision": decision, "decision_text": _decision_str(decision),
           "decision_description": describe_decision(decision),
           "perturbation": {"constraint": perturb["type"], "ids": [c.ConstrName for c in pcons]},
           "anchor": {**anchor, "ids": [c.ConstrName for c in acons], **anchor_check},
           "current_objective": cur_obj}
    if res["status"] == "infeasible":
        # Feasibility does not depend on vehicle labels, so the IIS is taken without the anchor, as in v1;
        # with it, an anchored decision customer would hide one vehicle's capacity from the IIS.
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


# ---------------- natural-language explanation ----------------

def _prompt(name):
    path = os.path.join(PROMPTS, name)
    return open(path if os.path.exists(path) else os.path.join(V1_PROMPTS, name)).read()


def template_explanation(att):
    d = att["decision_text"]
    if att["conclusion"] == FORCED:
        cons = ", ".join(att["attribution_set"]["constraints"]) or "structural constraints"
        return (f"Decision {d} is forced by hard constraints: forbidding it makes the model infeasible. "
                f"The irreducible infeasible subset contains the business constraints {cons}.")
    edges = ", ".join(att["attribution_set"]["variables"])
    if att["conclusion"] == CHEAPER:
        return (f"Decision {d} is not preferred by the objective: forbidding it is feasible and changes the "
                f"objective by {att['objective_increase_if_forbidden']:g}. The cheaper alternative changes the "
                f"edges {edges}.")
    return (f"Decision {d} is preferred by the objective: forbidding it is still feasible but raises the objective "
            f"by {att['objective_increase_if_forbidden']:g}. The best alternative changes the edges {edges}.")


def explain(attribution_json, llm, case_id, run, component="explain_v2"):
    """As components.attribution.explain (checked against the JSON, one regeneration, template fallback), with
    the v2 system prompt, which also covers the "cheaper_without" conclusion."""
    payload = explanation_payload(attribution_json)
    msgs = [{"role": "system", "content": _prompt("explain_system.txt")},
            {"role": "user", "content": _prompt("explain_user.txt").replace(
                "{attribution_json}", json.dumps(payload, indent=1))}]
    attempts = []
    for sample in range(2):
        r = llm.chat(msgs, temperature=0.2, seed=derive_seed(case_id, component, run, sample),
                     meta={"component": component, "case_id": case_id, "run": run, "sample_index": sample})
        text = (r["content"] or "").strip()
        chk = check_explanation(text, payload) if r["ok"] else {"ok": False, "error": "no_response"}
        attempts.append({"sample_index": sample, "text": text, "check": chk, "latency_s": r["latency_s"]})
        if chk["ok"]:
            return {"text": text, "source": "llm", "valid": True, "attempts": attempts}
    return {"text": template_explanation(attribution_json), "source": "template", "valid": False,
            "attempts": attempts}
