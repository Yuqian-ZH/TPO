"""Decision attribution (section 6.1): forbid the decision; infeasible -> IIS (hard constraints),
feasible -> objective preference (edge differences and objective-term deltas). Plus constraint
activity, LP-relaxation duals / reduced costs (reference only), and an LLM explanation that is checked
against the JSON."""
import json
import os
import re
import time

from cvrp import canon, ids
from cvrp.model import CVRPModel
from cvrp.validate import errors

from .llm_client import derive_seed
from .state import base_data, model_data

PROMPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")
CATEGORY_ORDER = ("business_specific", "business_general", "structural", "convention", "perturbation", "soft")


def _decision_str(d):
    return f"{d['type']}({d['i']},{d['j']})"


def describe_decision(d):
    i, j = d["i"], d["j"]
    if d["type"] == "ADJ":
        a, b = ("the depot" if v == 0 else f"customer {v}" for v in (i, j))
        return f"{a} and {b} are visited one right after the other (the direct leg e[{min(i, j)},{max(i, j)}])"
    if d["type"] == "SAME":
        return f"customers {i} and {j} are served by the same vehicle"
    return f"customers {i} and {j} are served by different vehicles"


def _related(decision, K=2):
    i, j = decision["i"], decision["j"]
    cons = [f"cap[{k}]" for k in range(1, K + 1)] + [f"depot_out[{k}]" for k in range(1, K + 1)]
    cons += [f"visit[{v}]" for v in (i, j) if v]
    if decision["type"] == "ADJ":
        var = [f"x[{k},{a},{b}]" for k in range(1, K + 1) for a, b in ((i, j), (j, i))]
    else:
        var = [f"y[{k},{v}]" for k in range(1, K + 1) for v in (i, j)]
    return cons, var


def lp_relaxation(model, decision):
    """Duals and reduced costs of the LP relaxation of the current (unperturbed) model."""
    r = model.m.relax()
    r.optimize()
    cons, var = _related(decision, model.data["K"])
    if r.Status != 2:
        return {"status": r.Status}
    return {"objective": round(r.ObjVal, 6),
            "duals": {c: round(r.getConstrByName(c).Pi, 6) for c in cons},
            "reduced_costs": {v: round(r.getVarByName(v).RC, 6) for v in var},
            "note": "LP relaxation of the three-index model is weak; values are reference only and are "
                    "not used to build the attribution set."}


def constraint_activity(sol, data):
    act = {}
    for k, r in enumerate(sol["routes"], start=1):
        load = sum(data["q"][i] for i in r)
        act[f"cap[{k}]"] = {"load": load, "capacity": data["Q"], "slack": data["Q"] - load,
                            "binding": load == data["Q"]}
    act["visit[*]"] = {"note": "equalities, always active"}
    act["depot_out[*]"] = {"note": "equalities, always active"}
    return act


def _objective_terms(old, new, data, mods):
    """Objective change split into distance, weighted terms and soft-constraint penalties."""
    mo, mn = canon.metrics(old, data), canon.metrics(new, data)
    terms = {"distance": mn["total_distance"] - mo["total_distance"]}
    for t, w in canon.objective_weights(mods).items():
        terms[f"weight:{t}"] = w * (mn[t] - mo[t])
    for m in mods:
        if m["op"] == "add_soft_constraint":
            vo = canon.violation(canon.target_value(old, data, m["target"]), m["sense"], m["rhs"])
            vn = canon.violation(canon.target_value(new, data, m["target"]), m["sense"], m["rhs"])
            terms[f"soft:{m.get('id', m['target'])}"] = m["penalty"] * (vn - vo)
    return terms


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
    pcons = model.add_primitive(perturb, "attr")
    res = model.optimize()
    out = {"decision": decision, "decision_text": _decision_str(decision),
           "decision_description": describe_decision(decision),
           "perturbation": {"constraint": perturb["type"], "ids": [c.ConstrName for c in pcons]},
           "current_objective": cur_obj}
    if res["status"] == "infeasible":
        iis = model.iis()
        by_cat = {c: [] for c in CATEGORY_ORDER}
        for cid in iis["constraints"]:
            by_cat.setdefault(ids.category(cid), []).append(cid)
        out.update({
            "conclusion": "hard_constraint_forced",
            "attribution_set": {"constraints": sorted(by_cat["business_specific"]), "variables": []},
            "iis": {"constraints_by_category": by_cat, "var_lower_bounds": iis["var_lower_bounds"],
                    "var_upper_bounds": iis["var_upper_bounds"],
                    "note": "IIS is one irreducible infeasible subset; it need not be unique. Only "
                            "business-specific constraints enter the attribution set."},
        })
    elif res["status"] == "optimal":
        new = canon.canonical(res["solution"])
        new_obj = canon.objective(new, data, mods)
        cs = canon.change_set(sol, new)
        c = data["c"]
        added = [{"edge": f"e[{a},{b}]", "distance": c[a][b]} for a, b in cs["added_edges"]]
        removed = [{"edge": f"e[{a},{b}]", "distance": c[a][b]} for a, b in cs["removed_edges"]]
        terms = _objective_terms(sol, new, data, mods)
        assert sum(e["distance"] for e in added) - sum(e["distance"] for e in removed) == terms["distance"]
        out.update({
            "conclusion": "objective_preferred",
            "attribution_set": {"constraints": [], "variables": sorted({e["edge"] for e in added + removed})},
            "objective_increase_if_forbidden": new_obj - cur_obj,
            "objective_increase_by_term": terms,
            "edges_only_in_current_plan": removed, "edges_only_in_alternative": added,
            "customers_on_other_vehicle_in_alternative": cs["moved"],
            "alternative_solution": new,
            "alternative_objective": new_obj,
        })
    else:
        out.update({"conclusion": "unknown", "solver_status": res["status"]})
    out["constraint_activity"] = constraint_activity(sol, data)
    out["lp_relaxation"] = lp
    out["solve_time_s"] = round(time.perf_counter() - t0, 4)
    return out


# ---------------- natural-language explanation ----------------

_NUM = re.compile(r"\d+(?:\.\d+)?")
_ID = re.compile(r"\b([A-Za-z_]+)\[(\d+(?:\s*,\s*\d+)*)\]")
_LIST = r"(\d+(?:\s*(?:,|and|&|or|,\s*and)\s*\d+)*)"
_CUST = re.compile(r"\bcustomers?\s+" + _LIST, re.I)
_VEH = re.compile(r"\b(?:vehicles?|trucks?)\s+" + _LIST, re.I)


def _json_numbers(obj, acc):
    if isinstance(obj, bool):
        return acc
    if isinstance(obj, (int, float)):
        acc.add(abs(float(obj)))
    elif isinstance(obj, str):
        acc.update(abs(float(x)) for x in _NUM.findall(obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _json_numbers(k, acc)
            _json_numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _json_numbers(v, acc)
    return acc


def check_explanation(text, attribution_json, n=8, K=2):
    """Every number in the text must appear in the JSON (to the precision written); every customer,
    vehicle and constraint mentioned must exist."""
    allowed = _json_numbers(attribution_json, set())
    bad_numbers = []
    for tok in _NUM.findall(text):
        v = float(tok)
        places = len(tok.split(".")[1]) if "." in tok else 0
        if not any(abs(round(a, places) - v) < 1e-9 for a in allowed):
            bad_numbers.append(tok)
    bad_entities = []
    for m in _CUST.finditer(text):
        bad_entities += [f"customer {x}" for x in map(int, re.findall(r"\d+", m.group(1))) if not 1 <= x <= n]
    for m in _VEH.finditer(text):
        bad_entities += [f"vehicle {x}" for x in map(int, re.findall(r"\d+", m.group(1))) if not 1 <= x <= K]
    for m in _ID.finditer(text):
        cid = f"{m.group(1)}[{re.sub(r'\s+', '', m.group(2))}]"
        if not ids.id_exists(cid, n, K):
            bad_entities.append(cid)
    return {"ok": not bad_numbers and not bad_entities, "unmatched_numbers": bad_numbers,
            "unknown_entities": bad_entities}


def _prompt(name):
    return open(os.path.join(PROMPTS, name)).read()


def explanation_payload(att):
    """The JSON the LLM sees: the attribution output without solver bookkeeping."""
    keep = ("decision_text", "decision_description", "conclusion", "attribution_set", "current_objective",
            "objective_increase_if_forbidden", "objective_increase_by_term", "edges_only_in_current_plan",
            "edges_only_in_alternative", "customers_on_other_vehicle_in_alternative", "alternative_objective",
            "iis", "constraint_activity", "lp_relaxation")
    return {k: att[k] for k in keep if k in att}


def template_explanation(att):
    d = att["decision_text"]
    if att["conclusion"] == "hard_constraint_forced":
        cons = ", ".join(att["attribution_set"]["constraints"]) or "structural constraints"
        return (f"Decision {d} is forced by hard constraints: forbidding it makes the model infeasible. "
                f"The irreducible infeasible subset contains the business constraints {cons}.")
    edges = ", ".join(att["attribution_set"]["variables"])
    return (f"Decision {d} is preferred by the objective: forbidding it is still feasible but raises the objective "
            f"by {att['objective_increase_if_forbidden']:g}. The best alternative changes the edges {edges}.")


def explain(attribution_json, llm, case_id, run):
    """LLM explanation checked against the JSON; one regeneration on failure, then a template fallback.
    Returns {"text", "source": "llm"|"template", "valid", "attempts": [...]}"""
    payload = explanation_payload(attribution_json)
    msgs = [{"role": "system", "content": _prompt("explain_system.txt")},
            {"role": "user", "content": _prompt("explain_user.txt").replace(
                "{attribution_json}", json.dumps(payload, indent=1))}]
    attempts = []
    for sample in range(2):
        r = llm.chat(msgs, temperature=0.2, seed=derive_seed(case_id, "explain", run, sample),
                     meta={"component": "explain", "case_id": case_id, "run": run, "sample_index": sample})
        text = (r["content"] or "").strip()
        chk = check_explanation(text, payload) if r["ok"] else {"ok": False, "error": "no_response"}
        attempts.append({"sample_index": sample, "text": text, "check": chk, "latency_s": r["latency_s"]})
        if chk["ok"]:
            return {"text": text, "source": "llm", "valid": True, "attempts": attempts}
    return {"text": template_explanation(attribution_json), "source": "template", "valid": False,
            "attempts": attempts}
