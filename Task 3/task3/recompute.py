"""Recompute every metric from saved trial records (plan 6, stage 4). No network, no LLM, no solving:
only the instance and case files are read, to evaluate distances of saved solutions."""
import argparse
import glob
import json
import os
import sys

sys.dont_write_bytecode = True

import stats  # noqa: E402
from run_experiment import load_cases, write_json  # noqa: E402
from tpo.task2_bridge import canon, checkers, load_frozen_instance  # noqa: E402


def load_trials(out_dir):
    trials = []
    for path in sorted(glob.glob(os.path.join(out_dir, "trials", "*", "*.json"))):
        with open(path) as f:
            trials.append(json.load(f))
    return trials


def add_excess_distance(trials, cases, base):
    """Distance of the converged plan minus that of Task 2's reference fix, both on the evaluation data."""
    by_id = {c["id"]: c for c in cases}
    for t in trials:
        case = by_id[t["case_id"]]
        ref = (case.get("reference_check") or {}).get("solution")
        if t["converged"] and ref:
            data = checkers.eval_data(case, base)
            t["excess_distance"] = (canon.metrics(t["final_solution"], data)["total_distance"]
                                    - canon.metrics(ref, data)["total_distance"])
    return trials


def recompute(out_dir, cases, base, B=10000):
    trials = add_excess_distance(load_trials(out_dir), cases, base)
    labels = {k: {c["id"]: c.get(k, "unknown") for c in cases} for k in ("clarity", "complaint_object")}
    return stats.summarize(trials, B=B, case_labels=labels)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--result", default=None, help="default: <out>/task3_results.json")
    args = ap.parse_args()
    res = recompute(args.out, load_cases(args.cases), load_frozen_instance())
    write_json(args.result or os.path.join(args.out, "task3_results.json"), res)
    print(json.dumps({g: v["rate_mean_std_over_runs"] for g, v in res["configs"].items()}, indent=1))
    if "verdict" in res:
        print(res["verdict"]["text"])


if __name__ == "__main__":
    main()
