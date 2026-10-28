"""Feedback localization, task2_v2.1: v2/localization.py with two defects fixed.

1. Only the limit that applies counts towards agreement. v2 compared threshold and corrected value on every sample,
   so "forbid e[3,4]" written once with limit 0 and once with null counted as two meanings, and the question asked
   about a limit the user never gave. v2.1: a data target (demand, location, capacity) is settled by its corrected
   value; another target by its threshold when the direction is decrease or increase; forbid and require have no
   limit. A value that does not apply is carried into the critique as the most common one among the agreeing
   samples, which is v2's value whenever v2 was confident.
2. The modification type is one the target admits (modification.schema.json): modify_data for a data target,
   add_soft_constraint or set_objective_weight for balance, makespan, load_balance and sum_arrival, and
   add_soft_constraint for every other target. v2 took the majority among the agreeing samples without that check,
   so a 3:2 split could give set_objective_weight on L[2]. v2.1 takes the majority among the agreeing samples whose
   type is admissible (ties by sample order, as v2), and the target's first admissible type if none is; as in v2
   the type is the system's choice and never a reason to ask.

Prompts, sample schema, target mapping, evidence, critique text and the question wording are v2's."""
import json
from collections import Counter

from components.llm_client import derive_seed
from components.localization import N_SAMPLES, TEMPERATURE, _messages, critique_text, evidence
from components.state import model_data
from v2 import localization as v2
from v2.localization import GENERIC_QUESTION, describe_target, score_samples

RULE = {**v2.RULE, "agree_on": ["target", "direction", "limit"],
        "limit": "corrected value for demand / location / capacity; threshold for other targets when the direction is "
                 "decrease or increase; none for forbid / require"}
PROTOCOL = "task2_v2.1"
DATA_HEADS = ("demand", "coord", "capacity")
WEIGHT_TERMS = ("balance", "makespan", "load_balance", "sum_arrival")
__all__ = ["GENERIC_QUESTION", "RULE", "admissible_types", "decide", "describe_target", "limit_field", "localize",
           "meaning", "question_for", "score_samples", "critique_text", "evidence"]


def limit_field(target, direction):
    """The sample field that states the user's limit for this target and direction, or None."""
    if direction in ("forbid", "require"):
        return None
    if target.split("[")[0] in DATA_HEADS:
        return "corrected_value"
    return "threshold" if direction in ("decrease", "increase") else None


def admissible_types(target):
    head = target.split("[")[0]
    if head in DATA_HEADS:
        return ("modify_data",)
    if head in WEIGHT_TERMS:
        return ("add_soft_constraint", "set_objective_weight")
    return ("add_soft_constraint",)


def _value(s, field):
    return json.dumps(v2._norm(s[field]))


def meaning(rec):
    """(target, direction, limit field, limit) as far as the user can say it; the limit only where it applies."""
    s = rec["sample"]
    field = limit_field(rec["target"], s["direction"])
    return rec["target"], s["direction"], field, _value(s, field) if field else None


def question_for(valid, state):
    """v2's question about the first point the valid samples disagree on (target, direction, then the limit that
    applies), never about the modification type."""
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
        return f"Should {desc} {' or '.join(v2.DIRECTION_WORDS[d] for d in dirs[:2])}?", "direction"
    field = limit_field(tid, dirs[0])
    vals = list(dict.fromkeys(_value(s["sample"], field) for s in valid)) if field else []
    if len(vals) > 1:
        nums = [json.loads(t) for t in vals if t != "null"]
        if field == "threshold":
            if len(nums) == 1:
                return f"Do you have a specific limit in mind for {desc}, for example {v2._values(nums)}?", "threshold"
            return f"Which limit do you want for {desc}: {v2._values(nums[:2])}?", "threshold"
        if nums:
            return f"What is the correct value of {desc}: {v2._values(nums[:2])}?", "corrected_value"
        return f"What is the correct value of {desc}?", "corrected_value"
    return (llm_qs[0] if llm_qs else GENERIC_QUESTION), "none"


def _most_common(agree, field):
    return json.loads(Counter(_value(s["sample"], field) for s in agree).most_common(1)[0][0])


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
    allowed = admissible_types(maj_meaning[0]) if maj_meaning else ()
    ok_types = Counter({t: n for t, n in type_counts.items() if t in allowed})
    maj_type = ok_types.most_common(1)[0][0] if ok_types else (allowed[0] if allowed else None)
    non_amb = sum(1 for s in valid if not s["sample"]["ambiguous"])
    invalid = len(samples) - len(valid)
    high = (maj_count >= RULE["min_agree"] and maj_meaning is not None and non_amb >= RULE["min_non_ambiguous"]
            and invalid <= RULE["max_invalid"])
    diag = {"samples": samples, "valid_samples": len(valid), "invalid_samples": invalid,
            "majority_target": majority_target, "majority_key_target": maj_meaning[0] if maj_meaning else None,
            "majority_modification_type": maj_type, "majority_count": maj_count, "non_ambiguous_count": non_amb,
            "target_counts": dict(target_counts),
            "meaning_counts": {json.dumps(list(k)): v for k, v in meanings.items()},
            "modification_type_counts_among_agreeing": dict(type_counts),
            "modification_type_from": "agreeing samples" if ok_types else "target" if allowed else None,
            "rule": RULE, "protocol": PROTOCOL}
    out = {"complaint": complaint, "clarification": clarification, "diagnostics": diag}
    if high:
        tid, direction, field, _ = maj_meaning
        crit = {"complaint": complaint, "target": tid, "aspect": agree[0]["sample"]["aspect"],
                "direction": direction, "modification_type": maj_type, "confidence": "high",
                "threshold": _most_common(agree, "threshold"),
                "corrected_value": _most_common(agree, "corrected_value"),
                "evidence": evidence(tid, state)}
        crit["critique_text"] = critique_text(crit)
        out.update({"confidence": "high", "critique": crit, "clarifying_question": None})
        diag["disagreement"] = None
    else:
        question, diag["disagreement"] = question_for(valid, state)
        out.update({"confidence": "low", "critique": None, "clarifying_question": question})
    return out


def localize(state, complaint, llm, case_id, run, clarification=None):
    data = model_data(state)
    component = "localize_v2.1_clarified" if clarification else "localize_v2.1"
    msgs = _messages(state, complaint, clarification)
    raw = [llm.chat(msgs, temperature=TEMPERATURE, seed=derive_seed(case_id, component, run, idx), json_mode=True,
                    meta={"component": component, "case_id": case_id, "run": run, "sample_index": idx})
           for idx in range(N_SAMPLES)]
    return decide(score_samples(raw, data["n"], data["K"]), state, complaint, clarification)
