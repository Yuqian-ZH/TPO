"""Mechanism demonstration of the feedback validator (DESIGN.md section 3.4), offline, solver only.

Starting points are real sessions from Task 4's end-to-end run (read-only); the user feedback in each scenario is
illustrative and is given in the structured form the localizer produces. The scenarios were built to exhibit each
check, with controls for false alarms: this demonstrates the mechanism, it does not measure detection rates.

    python -m validator.demo        (from Task 5/task5)"""
import json
import os
import sys

sys.dont_write_bytecode = True

from validator import TASK4_ROOT, TASK5_ROOT  # noqa: E402
from validator.checks import Validator  # noqa: E402
from feedback_service.bridge import t2  # noqa: E402
from tpo.commit import commit_solve  # noqa: E402
from tpo.llm import StubLLM  # noqa: E402
from tpo_v21.components import Task2ComponentsV21  # noqa: E402

STORE = os.path.join(TASK4_ROOT, "results", "e2e_test", "store", "sessions")
OUT = os.path.join(TASK5_ROOT, "results")
UNCONFIRMED = [{"op": "modify_data", "field": "capacity", "value": 130},          # never stated by the user
               {"op": "add_soft_constraint", "target": "S[2]", "sense": "<=", "rhs": 2, "penalty": 100}]
# V9 (audit F6): total demand 202 > 2 x 100, so without the user's capacity entry there is no feasible plan at all
TIGHT_DAY = [{"op": "modify_data", "field": "demand[3]", "value": 62},
             {"op": "modify_data", "field": "capacity", "value": 110}]


def session(label, config="A0B0C1"):
    for name in sorted(os.listdir(STORE)):
        with open(os.path.join(STORE, name, "session.json")) as f:
            s = json.load(f)
        if s["label"] == label and s["config"] == config:
            return s
    raise KeyError(label)


def plan(s, v):
    return {"routes": s["plans"][v]["routes"]}


def scenarios(base):
    t1, t2s, t9 = session("T1"), session("T2"), session("T9")
    acc = t2s["accepted_modifications"]                   # W[1] <= 92, accepted with T2
    v0, v1 = plan(t2s, 0), plan(t2s, 1)
    v5 = commit_solve(base, [], v0, UNCONFIRMED)["solution"]
    v9 = commit_solve(base, TIGHT_DAY, v0, [])["solution"]
    complaint, praise = "complaint", "praise"
    return [
        ("V1", complaint, "T2 session after accepting W[1] <= 92 (plan v1)",
         "Vehicle 1 now drives 235 km; that is too far.", {"target": "L[1]", "direction": "decrease"},
         dict(plan=v1, user_data=t2s["model_modifications"], accepted=acc), "self_imposed"),
        ("V2", complaint, "T9 session, user-entered demand[3] = 54 (plan v0)",
         "Customers 2 and 5 should share a truck.", {"decision": {"type": "SEP", "i": 2, "j": 5}},
         dict(plan=plan(t9, 0), user_data=t9["model_modifications"], accepted=[]), "self_imposed"),
        ("V2b", complaint, "same T9 session (control: a real physical limit)",
         "Customers 1 and 3 should share a truck.", {"decision": {"type": "SEP", "i": 1, "j": 3}},
         dict(plan=plan(t9, 0), user_data=t9["model_modifications"], accepted=[]), "hard_constraint"),
        ("V3", praise, "T2: accepted plan v1 after the W[1] <= 92 fix",
         "Thanks for putting customers 3 and 5 on the same truck.", {"decision": {"type": "SAME", "i": 3, "j": 5}},
         dict(before=v0, after=v1, confirmed_mods=[], mods_before=[], mods_after=acc), "exclude_from_training"),
        ("V4", praise, "T2: accepted plan v1",
         "Great, customer 3 now gets its delivery early.", {"target": "A[3]", "direction": "decrease"},
         dict(before=v0, after=v1, confirmed_mods=[], mods_before=[], mods_after=acc), "exclude_from_training"),
        ("V5", praise, "T2 plan v0 refined with an unstated capacity change (constructed)",
         "Good, the second driver has fewer stops now.", {"target": "S[2]", "direction": "decrease"},
         dict(before=v0, after=v5, confirmed_mods=[], mods_before=[], mods_after=UNCONFIRMED), "incident"),
        ("V6", praise, "T2: accepted plan v1 (control: valid praise)",
         "Good, vehicle 1 is no longer loaded to the limit.", {"target": "W[1]", "direction": "decrease"},
         dict(before=v0, after=v1, confirmed_mods=[], mods_before=[], mods_after=acc), "usable_positive"),
        ("V7", complaint, "T2 session plan v1 (control: user inputs present but not the cause)",
         "Vehicle 2 still has too many stops.", {"target": "S[2]", "direction": "decrease"},
         dict(plan=v1, user_data=t2s["model_modifications"], accepted=acc), "genuine"),
        ("V8", complaint, "T1 session plan v0 (control: no user inputs)",
         "Vehicle 2 is on the road for 211 km.", {"target": "L[2]", "direction": "decrease"},
         dict(plan=plan(t1, 0), user_data=t1["model_modifications"], accepted=[]), "genuine"),
        ("V9", complaint, "constructed day: user entered demand[3] = 62 and capacity 110 (no plan without the "
                          "capacity entry; the v1 validator crashed here)",
         "Vehicle 2 drives too far.", {"target": "L[2]", "direction": "decrease"},
         dict(plan=v9, user_data=TIGHT_DAY, accepted=[]), "self_imposed"),
    ]


def run():
    base = t2.load_frozen_instance()
    val = Validator(base, Task2ComponentsV21(base, StubLLM([])))
    rows = []
    for sid, kind, where, says, claim, args, expected in scenarios(base):
        res = val.check_praise(claim, **args) if kind == "praise" else val.check_complaint(claim, **args)
        rows.append({"id": sid, "kind": kind, "situation": where, "user_says": says, "claim": claim,
                     "expected": expected, **res, "as_expected": res["verdict"] == expected})
    return rows


def _evidence(r):
    e = r["evidence"]
    if r["kind"] == "praise":
        parts = [f"{k} {v['before']} -> {v['after']}" for k, v in e.items() if isinstance(v, dict) and "before" in v]
        if "holds_before" in e:
            parts.append(f"held before: {e['holds_before']}, after: {e['holds_after']}")
        if "why_it_held_before" in e:
            w = e["why_it_held_before"]
            parts.append(f"before the fix it was {w['conclusion']}")
        if not e["feasible_on_confirmed_data"]:
            parts.append(f"loads {e['loads_on_confirmed_data']} vs capacity {e['capacity_on_confirmed_data']} "
                         "on confirmed data")
        return "; ".join(parts)
    if "attribution" in e:
        a = e["attribution"]
        parts = [f"attribution: {a['conclusion']} by {a['constraint_ids']}"]
        parts += [f"without {x['input']['field']} = {x['input']['value']}: "
                  f"{x.get('conclusion_without_it', 'no feasible plan')}"
                  for x in e.get("without_each_user_data_item", [])]
        return "; ".join(parts)
    tgt = next(k for k in e if k not in ("total_distance", "without_each_user_input"))
    parts = [f"{tgt} = {e[tgt]}"]
    for x in e.get("without_each_user_input", []):
        m = x["input"]
        name = m.get("target", m.get("field"))
        if x.get("feasible_without_it") is False:
            parts.append(f"without the user's {name} input: no feasible plan")
            continue
        parts.append(f"without the user's {name} input: {tgt} = {x[f'{tgt}_without_it']}, "
                     f"total distance {e['total_distance']} -> {x['total_distance_without_it']}")
    if not e.get("without_each_user_input"):
        parts.append("no user inputs to drop")
    return "; ".join(parts)


def main():
    rows = run()
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "validator_demo.json"), "w") as f:
        json.dump(rows, f, indent=1, default=str)
    lines = ["# Feedback validator: mechanism demonstration", "",
             "Offline, Gurobi only. Starting points are sessions from Task 4's end-to-end run; the feedback text is "
             "illustrative and enters as the structured claim the localizer would extract.", "",
             "| ID | Situation | User says | Claim | Evidence | Verdict | Flags | Expected |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['id']} | {r['situation']} | \"{r['user_says']}\" | `{json.dumps(r['claim'])}` | "
                     f"{_evidence(r)} | **{r['verdict']}** | {', '.join(r['flags']) or 'none'} | "
                     f"{r['expected']}{'' if r['as_expected'] else ' (MISMATCH)'} |")
    with open(os.path.join(OUT, "validator_demo.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if all(r["as_expected"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
