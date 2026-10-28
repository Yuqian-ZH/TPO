"""Feedback localization, task2_v2 (audit finding F5, and the T7 stop in Task 4).

Same prompts, sample schema, target mapping, evidence and critique text as components/localization.py; the
confidence rule and the clarifying question change.

v1 counted agreement on (target, modification type) and ignored direction and limit. That is wrong both ways:
five samples that agreed on "balance <= 50 km" but split 3:2 between a soft constraint and an objective weight
were judged low confidence, and the user could not answer a question about a choice internal to the system
(Task 4, T7, stopped); samples that agree on the target but not on the limit were judged high.

v2 counts agreement on what the user means and can answer: target, direction, threshold and corrected value.
The modification type is taken by majority among the agreeing samples and is never a reason to ask. A low
confidence result asks about the first point the samples disagree on, in the user's terms: which quantity, which
way, which limit, which value. decide() is a pure function of the samples, so the v1 samples can be re-scored."""
import json
from collections import Counter

from components.llm_client import derive_seed
from components.localization import N_SAMPLES, TEMPERATURE, _messages, critique_text, evidence, map_target
from components.state import model_data
from cvrp import canon
from cvrp.validate import errors

RULE = {"min_agree": 4, "min_non_ambiguous": 3, "max_invalid": 1,
        "agree_on": ["target", "direction", "threshold", "corrected_value"]}
MEANING = ("target", "direction", "threshold", "corrected_value")
GENERIC_QUESTION = ("Could you say more precisely what should change: which vehicle, customer or data item, and "
                    "which aspect (distance, load, stops, timing)?")
DIRECTION_WORDS = {"decrease": "be lower", "increase": "be higher", "forbid": "not happen", "require": "happen",
                   "correct": "be corrected"}


def _norm(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, list):
        return [_norm(x) for x in v]
    return v


def meaning(rec):
    """What the user means, as far as the user can say it: (target, direction, threshold, corrected value)."""
    s = rec["sample"]
    return (rec["target"], s["direction"], json.dumps(_norm(s["threshold"])), json.dumps(_norm(s["corrected_value"])))


def describe_target(tid, state):
    """The target in the user's words, with its current value."""
    data, sol = model_data(state), state["solution"]
    m = canon.metrics(sol, data)
    head = tid.split("[")[0]
    idx = [int(x) for x in tid[tid.index("[") + 1:-1].split(",")] if "[" in tid else []
    node = lambda v: "the depot" if v == 0 else f"customer {v}"  # noqa: E731
    if head == "L":
        return f"the length of vehicle {idx[0]}'s route ({m[tid]} km now)"
    if head == "W":
        return f"vehicle {idx[0]}'s load ({m[tid]} units now)"
    if head == "S":
        return f"the number of stops of vehicle {idx[0]} ({m[tid]} now)"
    if head == "A":
        return f"the distance driven before customer {idx[0]} is reached ({m[tid]} km now)"
    if head == "balance":
        return f"the difference between the two route lengths ({m['balance']} km now)"
    if head == "load_balance":
        return f"the difference between the two loads ({m['load_balance']} units now)"
    if head == "makespan":
        return f"the length of the longer route ({m['makespan']} km now)"
    if head == "sum_arrival":
        return f"the average distance driven before a customer is reached ({m['sum_arrival'] / data['n']:.1f} km now)"
    if head == "e":
        return f"{node(idx[0])} and {node(idx[1])} being visited one right after the other"
    if head == "same":
        return f"customers {idx[0]} and {idx[1]} sharing a vehicle"
    if head == "sep":
        return f"customers {idx[0]} and {idx[1]} being on different vehicles"
    if head == "demand":
        return f"customer {idx[0]}'s order size ({data['q'][idx[0]]} units in the plan's data)"
    if head == "coord":
        return f"customer {idx[0]}'s location ({list(data['coords'][idx[0]])} in the plan's data)"
    return f"the vehicle capacity ({data['Q']} units in the plan's data)"


def _values(values):
    return " or ".join(json.dumps(v) if isinstance(v, list) else f"{v:g}" for v in values)


def question_for(valid, state):
    """(question, disagreement): ask about the first of target, direction, threshold, corrected value on which the
    valid samples disagree, never about the modification type."""
    llm_qs = [s["sample"]["clarifying_question"] for s in valid
              if s["sample"]["ambiguous"] and s["sample"]["clarifying_question"]]
    targets = Counter(s["target"] for s in valid)
    if len(targets) > 1:
        if llm_qs:
            return llm_qs[0], "target"
        a, b = (t for t, _ in targets.most_common(2))
        return f"Do you mean {describe_target(a, state)} or {describe_target(b, state)}?", "target"
    if not valid:
        return GENERIC_QUESTION, "no_valid_sample"
    tid = valid[0]["target"]
    desc = describe_target(tid, state)
    dirs = list(Counter(s["sample"]["direction"] for s in valid))
    if len(dirs) > 1:
        return f"Should {desc} {' or '.join(DIRECTION_WORDS[d] for d in dirs[:2])}?", "direction"
    thr = list(dict.fromkeys(json.dumps(_norm(s["sample"]["threshold"])) for s in valid))
    if len(thr) > 1:
        nums = [json.loads(t) for t in thr if t != "null"]
        if len(nums) == 1:
            return f"Do you have a specific limit in mind for {desc}, for example {_values(nums)}?", "threshold"
        return f"Which limit do you want for {desc}: {_values(nums[:2])}?", "threshold"
    cor = list(dict.fromkeys(json.dumps(_norm(s["sample"]["corrected_value"])) for s in valid))
    if len(cor) > 1:
        nums = [json.loads(t) for t in cor if t != "null"]
        if nums:
            return f"What is the correct value of {desc}: {_values(nums[:2])}?", "corrected_value"
        return f"What is the correct value of {desc}?", "corrected_value"
    return (llm_qs[0] if llm_qs else GENERIC_QUESTION), "none"


def decide(samples, state, complaint, clarification=None):
    """Confidence, critique and question from scored samples (records with valid / target / sample)."""
    valid = [s for s in samples if s["valid"]]
    meanings = Counter(meaning(s) for s in valid)
    target_counts = Counter(s["target"] for s in valid)
    if meanings:
        # ties are broken by first occurrence in sample order (Counter preserves insertion order)
        maj_meaning, maj_count = meanings.most_common(1)[0]
        majority_target = target_counts.most_common(1)[0][0]
    else:
        maj_meaning, maj_count, majority_target = None, 0, None
    agree = [s for s in valid if meaning(s) == maj_meaning]
    type_counts = Counter(s["sample"]["modification_type"] for s in agree)
    maj_type = type_counts.most_common(1)[0][0] if type_counts else None
    non_amb = sum(1 for s in valid if not s["sample"]["ambiguous"])
    invalid = len(samples) - len(valid)
    high = (maj_count >= RULE["min_agree"] and maj_meaning is not None and non_amb >= RULE["min_non_ambiguous"]
            and invalid <= RULE["max_invalid"])
    diag = {"samples": samples, "valid_samples": len(valid), "invalid_samples": invalid,
            "majority_target": majority_target, "majority_key_target": maj_meaning[0] if maj_meaning else None,
            "majority_modification_type": maj_type, "majority_count": maj_count, "non_ambiguous_count": non_amb,
            "target_counts": dict(target_counts),
            "meaning_counts": {json.dumps(list(k)): v for k, v in meanings.items()},
            "modification_type_counts_among_agreeing": dict(type_counts), "rule": RULE, "protocol": "task2_v2"}
    out = {"complaint": complaint, "clarification": clarification, "diagnostics": diag}
    if high:
        tid, direction, thr, cor = maj_meaning
        crit = {"complaint": complaint, "target": tid, "aspect": agree[0]["sample"]["aspect"],
                "direction": direction, "modification_type": maj_type, "confidence": "high",
                "threshold": json.loads(thr), "corrected_value": json.loads(cor),
                "evidence": evidence(tid, state)}
        crit["critique_text"] = critique_text(crit)
        out.update({"confidence": "high", "critique": crit, "clarifying_question": None})
        diag["disagreement"] = None
    else:
        question, diag["disagreement"] = question_for(valid, state)
        out.update({"confidence": "low", "critique": None, "clarifying_question": question})
    return out


def score_samples(raw, n, K):
    """v1's per-sample validation: JSON, sample schema, mappable target."""
    samples = []
    for idx, r in enumerate(raw):
        rec = {"sample_index": idx, "parse_status": r["parse_status"], "sample": r["parsed"]}
        if r["parse_status"] != "json_ok":
            rec.update(valid=False, reason=r["parse_status"])
        elif errors("localization_sample", r["parsed"]):
            rec.update(valid=False, reason="schema", schema_errors=errors("localization_sample", r["parsed"])[:3])
        else:
            tid = map_target(r["parsed"], n, K)
            rec.update(valid=tid is not None, target=tid, reason=None if tid else "unmappable_or_unknown_object")
        samples.append(rec)
    return samples


def localize(state, complaint, llm, case_id, run, clarification=None):
    data = model_data(state)
    component = "localize_v2_clarified" if clarification else "localize_v2"
    msgs = _messages(state, complaint, clarification)
    raw = [llm.chat(msgs, temperature=TEMPERATURE, seed=derive_seed(case_id, component, run, idx), json_mode=True,
                    meta={"component": component, "case_id": case_id, "run": run, "sample_index": idx})
           for idx in range(N_SAMPLES)]
    return decide(score_samples(raw, data["n"], data["K"]), state, complaint, clarification)
