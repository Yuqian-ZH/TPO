"""Evidence for the Task 2 issue found at G2: for APPLY_MODIFICATIONS queries, Task 2's local counterfactual
stops at L0 whenever L0 is feasible, which soft constraints always are. How often does the local answer
differ from the full re-solve (objective beyond 1 %, or a different change set)?

Solver only, no LLM. Uses the dev cases' reference modifications and random modification sets on the
reference solution; test cases are not touched."""
import json
import os
import random
import sys

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from run_experiment import DEV_CASES, load_cases  # noqa: E402
from test_commit_and_validation import random_mod  # noqa: E402
from tpo.components import ReferenceComponents, Task2Components  # noqa: E402
from tpo.llm import StubLLM  # noqa: E402
from tpo.task2_bridge import canon, load_frozen_instance  # noqa: E402

REFERENCE = {"routes": [[1, 4, 7, 2], [5, 3, 6, 8]]}


def compare(real, ref, case_mods, sol, mods):
    a, b = real.probe(case_mods, sol, mods), ref.probe(case_mods, sol, mods)
    return {"latency_s": a["raw"]["latency"]["with_model_setup_s"], **_compare(a, b, sol)}


def _compare(a, b, sol):
    if not (a["feasible"] and b["feasible"]):
        return {"feasible_agree": a["feasible"] == b["feasible"], "objective_1pct": None, "change_set": None}
    tol = 0.01 * max(1.0, abs(b["objective"]))
    return {"feasible_agree": True, "level": a["level"],
            "objective_1pct": abs(a["objective"] - b["objective"]) <= tol,
            "change_set": (canon.change_key(canon.change_set(sol, a["solution"])) ==
                           canon.change_key(canon.change_set(sol, b["solution"]))),
            "local_objective": a["objective"], "full_objective": b["objective"],
            "local_unchanged": not a["change_set"]["moved"] and not a["change_set"]["added_edges"],
            "full_unchanged": not b["change_set"]["moved"] and not b["change_set"]["added_edges"]}


def run(base, probe):
    real, ref = Task2Components(base, StubLLM([]), probe=probe), ReferenceComponents(base)
    rows = []
    for c in load_cases(DEV_CASES):
        r = compare(real, ref, c["model_modifications"], c["solution"], c["reference_modification"])
        rows.append({"source": f"dev {c['id']} reference_modification", "mods": c["reference_modification"], **r})
    rng = random.Random(20261023)
    for s in range(200):
        mods = [random_mod(rng, base["n"]) for _ in range(rng.randint(1, 2))]
        rows.append({"source": f"random {s}", "mods": mods, **compare(real, ref, [], REFERENCE, mods)})
    both = [r for r in rows if r["objective_1pct"] is not None]
    summary = {
        "queries": len(rows), "both_feasible": len(both),
        "feasible_agreement": sum(r["feasible_agree"] for r in rows) / len(rows),
        "objective_1pct_agreement": sum(r["objective_1pct"] for r in both) / len(both),
        "change_set_agreement": sum(r["change_set"] for r in both) / len(both),
        "local_says_unchanged_but_full_changes": sum(r["local_unchanged"] and not r["full_unchanged"] for r in both),
        "levels": {lv: sum(r.get("level") == lv for r in both) for lv in ("L0", "L1", "L2")},
        "dev_reference_modifications": [{k: r[k] for k in ("source", "objective_1pct", "change_set", "local_objective",
                                                           "full_objective", "local_unchanged", "full_unchanged")
                                         if k in r} for r in rows[:5]],
    }
    lat = sorted(r["latency_s"] for r in rows)
    summary["latency_ms_median_p95"] = [round(1000 * lat[len(lat) // 2], 1), round(1000 * lat[int(0.95 * len(lat))], 1)]
    return summary, rows


def main():
    base = load_frozen_instance()
    out = {}
    for probe in ("task2_frozen", "v2"):
        summary, rows = run(base, probe)
        out[probe] = {"summary": summary, "rows": rows}
        print(probe, json.dumps({k: v for k, v in summary.items() if k != "dev_reference_modifications"}))
        for r in summary["dev_reference_modifications"]:
            print("   ", r)
    with open(os.path.join(ROOT, "logs", "probe_vs_full.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)


if __name__ == "__main__":
    main()
