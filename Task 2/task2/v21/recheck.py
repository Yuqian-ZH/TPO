"""task2_v2.1 re-check, no LLM: v2.1 re-computed on every state and sample set Task 2's v2 evaluation recorded, and
compared with what v2 produced there. Run from the Task 2 root after python -m v21.freeze:

    python -m v21.recheck          # writes results_v21/recheck.json and recheck.md once

Attribution: the 10 test cases (the outputs the explanation prompts were built from) and the 912 decisions on plans
with soft constraints and weights; where v2.1 picks another anchor than v2, its claim and alternative are checked by
brute force again. Localization: the 60 sample sets of the v1 run (re-scored by v2) and the 60 of the v2 run.
compare_attribution() and compare_localization() are also used by the Task 3 and Task 4 re-checks."""
import datetime
import json
import os
import sys

from components.state import make_state, model_data, state_for_case
from cvrp import canon
from cvrp.data import load_instance
from cvrp.oracle import oracle_for
from v2 import localization as loc2
from v2.evaluate import load_cases, sha256

from . import attribution as att21
from . import localization as loc21
from .freeze import PROTOCOL, ROOT, check

OUT = os.path.join(ROOT, "results_v21")
NUM_TOL = 1e-6
ANCHOR_KEYS = ("type", "i", "k", "current_plan_optimal", "dropped_for_iis")
NOT_COMPARED = ("protocol", "solve_time_s", "tried")


def _differs(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) > NUM_TOL
    return a != b


def compare_attribution(old, new):
    """Fields of a recorded v2 attribution (full or compacted) that v2.1 changes; the anchor by customer, vehicle
    and claim (v2.1 also records the exact optimum of each anchor it tried)."""
    diffs = []
    for k, v in old.items():
        if k in NOT_COMPARED:
            continue
        if k == "anchor":
            if any(v.get(x) != new.get("anchor", {}).get(x) for x in ANCHOR_KEYS):
                diffs.append(k)
        elif k not in new or _differs(v, new[k]):
            diffs.append(k)
    return diffs


def compare_localization(old, new):
    """Whether v2.1 reaches v2's decision on the same samples: confidence, the whole critique and the question."""
    keys = ("confidence", "critique", "clarifying_question")
    return [k for k in keys if old.get(k) != new.get(k)]


def _brute_check(base, sol, mods, d, a):
    """v2.1's anchor claim and alternative objective against brute force under its anchor."""
    o = oracle_for(base, mods)
    anchor = {k: a["anchor"][k] for k in ("type", "i", "k")}
    cur = canon.objective(sol, model_data(make_state(sol, mods)), mods)
    claim_ok = (o.solve(mods, [anchor])["objective"] >= cur - NUM_TOL) == a["anchor"]["current_plan_optimal"]
    r = o.solve(mods, [canon.forbid_decision(d), anchor])
    alt_ok = (a["conclusion"] == att21.FORCED) if not r["feasible"] else \
        abs(a.get("alternative_objective", float("nan")) - r["objective"]) <= NUM_TOL
    return claim_ok and alt_ok


def part_attribution(base):
    cases = {c["id"]: c for c in load_cases()}
    rec = json.load(open(os.path.join(ROOT, "results_v2", "raw", "attribution.json")))["data"]
    exp = json.load(open(os.path.join(ROOT, "results_v2", "raw", "explanation.json")))["data"]
    rows = []
    for source, recorded in (("test_cases", rec["test_cases"]), ("explanation_inputs", exp)):
        for cid, r in recorded.items():
            c = cases[cid]
            new = att21.attribute(state_for_case(c), c["why_decision"])
            rows.append({"source": source, "id": cid, "diffs": compare_attribution(r["output"], new)})
    for r in rec["soft_states"]:
        sol, mods, d = {"routes": r["routes"]}, r["mods"], r["decision"]
        new = att21.attribute(make_state(sol, mods), d)
        diffs = compare_attribution(r["v2"], new)
        row = {"source": r["source"], "id": new["decision_text"], "diffs": diffs}
        if "anchor" in diffs:
            row["brute_force_ok"] = _brute_check(base, sol, mods, d, new)
        rows.append(row)
    return rows


def part_localization():
    cases = {c["id"]: c for c in load_cases()}
    rows = []
    for label, path in (("task2_v1 samples", "results/raw/localization.json"),
                        ("task2_v2 samples", "results_v2/raw/localization.json")):
        d = json.load(open(os.path.join(ROOT, path)))
        for run, per in enumerate(d["data"] if isinstance(d, dict) else d):
            for cid, r in per.items():
                st = state_for_case(cases[cid])
                for phase in ("initial", "clarified"):
                    old = r[phase]
                    args = (old["diagnostics"]["samples"], st, old["complaint"], old["clarification"])
                    # v2's decision re-computed (the v1 file holds v1's decision, not v2's)
                    rows.append({"source": label, "id": f"{cid}/run{run}/{phase}",
                                 "diffs": compare_localization(loc2.decide(*args), loc21.decide(*args))})
    return rows


def summary(rows):
    by = {}
    for r in rows:
        s = by.setdefault(r["source"].split("/")[0], {"checked": 0, "changed": 0, "changed_ids": []})
        s["checked"] += 1
        if r["diffs"]:
            s["changed"] += 1
            s["changed_ids"].append(r["id"])
    return by


def markdown(res):
    lines = ["# task2_v2.1 re-check (no LLM)", "", f"Frozen protocol: `v21/protocol_v21.json` ({res['meta']['frozen_at']}).",
             "", "| Records | Checked | v2.1 differs from v2 |", "|---|---:|---:|"]
    for part in ("attribution", "localization"):
        for src, s in res["summary"][part].items():
            lines.append(f"| {part}: {src} | {s['checked']} | {s['changed']} |")
    bf = [r for r in res["attribution"] if "brute_force_ok" in r]
    lines += ["", f"Attribution rows where v2.1 chose another anchor: {len(bf)}, of which brute force confirms "
                  f"{sum(r['brute_force_ok'] for r in bf)}."]
    return "\n".join(lines) + "\n"


def main():
    path = os.path.join(OUT, "recheck.json")
    if os.path.exists(path):
        sys.exit(f"refused: {path} exists; the re-check runs once")
    proto = check()
    base = load_instance(os.path.join(ROOT, "instance", "cvrp_instance.json"))
    started = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    att, loc = part_attribution(base), part_localization()
    res = {"meta": {"protocol": proto["protocol"], "frozen_at": proto["frozen_at"], "protocol_sha256": sha256(PROTOCOL),
                    "started": started,
                    "finished": datetime.datetime.now().astimezone().isoformat(timespec="seconds")},
           "summary": {"attribution": summary(att), "localization": summary(loc)},
           "attribution": att, "localization": loc}
    os.makedirs(OUT, exist_ok=True)
    with open(path, "w") as f:
        json.dump(res, f, indent=1)
    with open(os.path.join(OUT, "recheck.md"), "w") as f:
        f.write(markdown(res))
    print(json.dumps(res["summary"], indent=1))


if __name__ == "__main__":
    main()
