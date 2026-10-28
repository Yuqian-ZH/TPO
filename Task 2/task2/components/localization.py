"""Feedback localization (section 6.3): 5 LLM samples -> schema check -> program maps (object, aspect)
to a canonical target ID -> rule-based confidence -> high: structured critique (template text, no LLM);
low: clarifying question only, no critique."""
import json
import os
from collections import Counter

from cvrp import canon, ids
from cvrp.validate import errors

from .llm_client import derive_seed
from .state import model_data

PROMPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")
N_SAMPLES = 5
TEMPERATURE = 0.7
# confidence rule (frozen with the protocol)
RULE = {"min_agree": 4, "min_non_ambiguous": 3, "max_invalid": 1}

VEHICLE_ASPECT = {"route_length": "L", "load": "W", "stops": "S"}
GLOBAL_ASPECT = {"distance_balance": "balance", "load_balance": "load_balance", "longest_route": "makespan",
                 "average_waiting": "sum_arrival"}
PAIR_ASPECT = {"adjacency": "e", "same_vehicle": "same", "separate_vehicles": "sep"}
DATA_ASPECT = {"demand": "demand", "location": "coord"}


def map_target(s, n, K):
    """(object, aspect) -> canonical target ID, or None when the combination is not meaningful."""
    t, a, cs, v = s["object_type"], s["aspect"], s["customers"], s["vehicle"]
    if t == "vehicle" and a in VEHICLE_ASPECT and v is not None:
        tid = f"{VEHICLE_ASPECT[a]}[{v}]"
    elif t == "customer" and a in ("detour", "arrival") and len(cs) == 1:
        tid = f"A[{cs[0]}]"
    elif t == "customer_pair" and a in PAIR_ASPECT and len(cs) == 2:
        i, j = sorted(cs)
        tid = f"{PAIR_ASPECT[a]}[{i},{j}]"
    elif t == "global" and a in GLOBAL_ASPECT:
        tid = GLOBAL_ASPECT[a]
    elif t == "data" and a == "capacity":
        tid = "capacity"
    elif t == "data" and a in DATA_ASPECT and len(cs) == 1:
        tid = f"{DATA_ASPECT[a]}[{cs[0]}]"
    else:
        return None
    return tid if ids.target_exists(tid, n, K) else None


def _prompt(name):
    return open(os.path.join(PROMPTS, name)).read()


def problem_summary(state):
    data = model_data(state)
    sol = state["solution"]
    m = canon.metrics(sol, data)
    c, n = data["c"], data["n"]
    veh = canon.vehicle_of(sol)
    lines = [f"Depot: node 0 at {data['coords'][0]}. Two identical vehicles, capacity {data['Q']} units each.",
             "Customers (id: location, demand, direct distance from depot):"]
    lines += [f"  customer {i}: {data['coords'][i]}, demand {data['q'][i]}, {c[0][i]} km from depot" for i in range(1, n + 1)]
    lines += ["", "Current plan:"]
    for k, r in enumerate(sol["routes"], start=1):
        lines.append(f"  vehicle {k}: depot -> {' -> '.join(f'customer {i}' for i in r)} -> depot; "
                     f"length {m[f'L[{k}]']} km, load {m[f'W[{k}]']} units, {m[f'S[{k}]']} stops")
    lines.append("  arrival mileage (km driven from the depot until the customer is reached):")
    lines += [f"    customer {i} (vehicle {veh[i]}): {m[f'A[{i}]']} km, detour ratio "
              f"{m[f'A[{i}]'] / c[0][i]:.2f}" for i in range(1, n + 1)]
    lines.append(f"  total distance {m['total_distance']} km; route-length difference {m['balance']} km; "
                 f"load difference {m['load_balance']} units; longest route {m['makespan']} km; "
                 f"average arrival mileage {m['sum_arrival'] / n:.1f} km")
    legs = []
    for k, r in enumerate(sol["routes"], start=1):
        path = [0, *r, 0]
        legs += [f"{a}-{b}: {c[a][b]} km" for a, b in zip(path, path[1:])]
    lines.append("  legs driven: " + ", ".join(legs))
    return "\n".join(lines)


def _messages(state, complaint, clarification):
    user = _prompt("localize_user.txt").replace("{problem}", problem_summary(state)).replace("{complaint}", complaint)
    if clarification:
        user += ("\n\nYou asked the user a clarifying question and got this answer:\n"
                 f"Question: {clarification['question']}\nAnswer: {clarification['answer']}\n"
                 "Use the answer to resolve the ambiguity.")
    return [{"role": "system", "content": _prompt("localize_system.txt")}, {"role": "user", "content": user}]


def evidence(target, state):
    data = model_data(state)
    sol = state["solution"]
    m = canon.metrics(sol, data)
    head = target.split("[")[0]
    idx = [int(x) for x in target[target.index("[") + 1:-1].split(",")] if "[" in target else []
    if head in ("L", "W", "S"):
        ev = {f"{head}[1]": m[f"{head}[1]"], f"{head}[2]": m[f"{head}[2]"]}
        if head == "W":
            ev["capacity"] = data["Q"]
        return ev
    if head == "A":
        i = idx[0]
        return {target: m[target], "direct_distance": data["c"][0][i], "detour_ratio": round(m[target] / data["c"][0][i], 4)}
    if head in ("balance", "makespan"):
        return {"L[1]": m["L[1]"], "L[2]": m["L[2]"], head: m[head]}
    if head == "load_balance":
        return {"W[1]": m["W[1]"], "W[2]": m["W[2]"], "load_balance": m["load_balance"]}
    if head == "sum_arrival":
        return {"sum_arrival": m["sum_arrival"], "average_arrival": m["sum_arrival"] / data["n"]}
    if head == "e":
        return {target: canon.adjacency_count(sol, *idx), "distance": data["c"][idx[0]][idx[1]]}
    if head in ("same", "sep"):
        v = canon.vehicle_of(sol)
        return {f"vehicle_of[{idx[0]}]": v[idx[0]], f"vehicle_of[{idx[1]}]": v[idx[1]]}
    if head == "demand":
        return {target: data["q"][idx[0]], "W[1]": m["W[1]"], "W[2]": m["W[2]"], "capacity": data["Q"]}
    if head == "coord":
        return {target: list(data["coords"][idx[0]])}
    return {"capacity": data["Q"], "W[1]": m["W[1]"], "W[2]": m["W[2]"]}


def critique_text(c):
    ev = ", ".join(f"{k} = {v}" for k, v in c["evidence"].items())
    extra = ""
    if c.get("threshold") is not None:
        extra = f" The user's stated limit is {c['threshold']:g}."
    if c.get("corrected_value") is not None:
        extra = f" The user states the correct value is {c['corrected_value']}."
    return (f"User complaint: \"{c['complaint']}\" It targets {c['target']} ({c['aspect']}); current values: {ev}. "
            f"Requested direction: {c['direction']}. Suggested modification type: {c['modification_type']}.{extra}")


def _agreed_value(samples, key):
    vals = [json.dumps(s[key]) for s in samples if s[key] is not None]
    if not vals:
        return None
    v, cnt = Counter(vals).most_common(1)[0]
    return json.loads(v) if cnt * 2 >= len(samples) else None


def localize(state, complaint, llm, case_id, run, clarification=None):
    data = model_data(state)
    n, K = data["n"], data["K"]
    component = "localize_clarified" if clarification else "localize"
    msgs = _messages(state, complaint, clarification)
    samples = []
    for idx in range(N_SAMPLES):
        r = llm.chat(msgs, temperature=TEMPERATURE, seed=derive_seed(case_id, component, run, idx), json_mode=True,
                     meta={"component": component, "case_id": case_id, "run": run, "sample_index": idx})
        rec = {"sample_index": idx, "parse_status": r["parse_status"], "sample": r["parsed"]}
        if r["parse_status"] != "json_ok":
            rec.update(valid=False, reason=r["parse_status"])
        elif errors("localization_sample", r["parsed"]):
            rec.update(valid=False, reason="schema", schema_errors=errors("localization_sample", r["parsed"])[:3])
        else:
            tid = map_target(r["parsed"], n, K)
            rec.update(valid=tid is not None, target=tid, reason=None if tid else "unmappable_or_unknown_object")
        samples.append(rec)
    valid = [s for s in samples if s["valid"]]
    keys = Counter((s["target"], s["sample"]["modification_type"]) for s in valid)
    target_counts = Counter(s["target"] for s in valid)
    if keys:
        # ties are broken by first occurrence in sample order (Counter preserves insertion order)
        (maj_target, maj_type), maj_count = keys.most_common(1)[0]
        majority_target = target_counts.most_common(1)[0][0]
    else:
        maj_target = maj_type = majority_target = None
        maj_count = 0
    non_amb = sum(1 for s in valid if not s["sample"]["ambiguous"])
    invalid = N_SAMPLES - len(valid)
    high = (maj_count >= RULE["min_agree"] and maj_target is not None and non_amb >= RULE["min_non_ambiguous"]
            and invalid <= RULE["max_invalid"])
    diag = {"samples": samples, "valid_samples": len(valid), "invalid_samples": invalid,
            "majority_target": majority_target, "majority_key_target": maj_target,
            "majority_modification_type": maj_type, "majority_count": maj_count, "non_ambiguous_count": non_amb,
            "target_counts": dict(target_counts), "rule": RULE}
    out = {"complaint": complaint, "clarification": clarification, "diagnostics": diag}
    if high:
        agree = [s["sample"] for s in valid if (s["target"], s["sample"]["modification_type"]) == (maj_target, maj_type)]
        first = agree[0]
        crit = {"complaint": complaint, "target": maj_target, "aspect": first["aspect"],
                "direction": Counter(s["direction"] for s in agree).most_common(1)[0][0],
                "modification_type": maj_type, "confidence": "high",
                "threshold": _agreed_value(agree, "threshold"),
                "corrected_value": _agreed_value(agree, "corrected_value"),
                "evidence": evidence(maj_target, state)}
        crit["critique_text"] = critique_text(crit)
        out.update({"confidence": "high", "critique": crit, "clarifying_question": None})
    else:
        qs = [s["sample"]["clarifying_question"] for s in valid if s["sample"]["ambiguous"] and s["sample"]["clarifying_question"]]
        qs = qs or [s["sample"]["clarifying_question"] for s in samples
                    if s.get("sample") and isinstance(s["sample"], dict) and s["sample"].get("clarifying_question")]
        question = qs[0] if qs else ("Could you say more precisely what should change: which vehicle, customer or "
                                     "data item, and which aspect (distance, load, stops, timing)?")
        out.update({"confidence": "low", "critique": None, "clarifying_question": question})
    return out
