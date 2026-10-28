"""Stage 2 pilot report (dev cases only): what each configuration did, where it failed, what it cost.
Reads saved trials, localizations and LLM logs; no network, no LLM."""
import argparse
import glob
import json
import os
import sys
from collections import Counter

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from recompute import load_trials, recompute  # noqa: E402
from run_experiment import DEV_CASES, load_cases  # noqa: E402
from tpo.task2_bridge import load_frozen_instance  # noqa: E402


def llm_usage(out_dir):
    calls, prompt, completion, by_role = 0, 0, 0, Counter()
    for path in glob.glob(os.path.join(out_dir, "logs", "llm_*.jsonl")):
        for line in open(path):
            r = json.loads(line)
            calls += 1
            u = r.get("usage") or {}
            prompt += u.get("prompt_tokens") or 0
            completion += u.get("completion_tokens") or 0
            by_role[r.get("role") or r.get("component") or "?"] += 1
    return {"requests": calls, "prompt_tokens": prompt, "completion_tokens": completion, "by_role": dict(by_role)}


def localization_accuracy(out_dir, cases):
    gt = {c["id"]: c["gt"]["localization"] for c in cases}
    rows = []
    for path in sorted(glob.glob(os.path.join(out_dir, "localization", "*.json"))):
        loc = json.load(open(path))
        cid = loc["case_id"]
        first, final = loc["initial"], loc["final"]
        tgt = (final.get("critique") or {}).get("target")
        rows.append({"case": cid, "expected_confidence": gt[cid]["confidence"],
                     "first_confidence": first["confidence"], "asked": loc["asked"],
                     "final_confidence": final["confidence"], "final_target": tgt,
                     "target_ok": tgt in gt[cid]["targets"],
                     "majority_first": first["raw"]["diagnostics"]["majority_target"]})
    return rows


def proposal_stats(trials):
    ops, weights, errors = Counter(), [], Counter()
    for t in trials:
        for it in t["iterations"]:
            for c in it["candidates"]:
                for m in c.get("raw_modifications") or []:
                    if isinstance(m, dict):
                        ops[(m.get("op"), (m.get("target") or m.get("term") or m.get("field") or "?").split("[")[0])] += 1
                        if m.get("op") == "set_objective_weight":
                            weights.append((m.get("term"), m.get("weight")))
                for e in c["errors"]:
                    errors[e.split(":")[-1].strip()[:80]] += 1
    big = [w for w in weights if isinstance(w[1], (int, float)) and w[0] in ("balance", "load_balance") and w[1] > 1]
    return {"ops": {f"{a}:{b}": n for (a, b), n in ops.most_common()}, "weights": weights,
            "balance_or_load_balance_weight_above_1": len(big), "errors": dict(errors)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    cases = load_cases(DEV_CASES)
    trials = load_trials(args.out)
    res = recompute(args.out, cases, load_frozen_instance(), B=2000)
    report = {"summary": {g: {k: v[k] for k in ("converged", "trials", "cumulative_by_iteration", "stopped_low_confidence",
                                                 "invalid_candidate_rate", "rejected_iterations", "no_plan_iterations",
                                                 "illegal_data_mods", "probe_commit_agreement",
                                                 "excess_distance_mean_when_converged", "llm_calls_mean",
                                                 "tokens_mean", "converged_label_sensitive",
                                                 "converged_with_ties_not_all_resolving")}
                          for g, v in res["configs"].items()},
              "matrix": {t["case_id"]: {} for t in trials},
              "localization": localization_accuracy(args.out, cases),
              "proposals": proposal_stats(trials),
              "llm_usage": llm_usage(args.out),
              "wall_s_per_trial": {g: round(sum(it["wall_s"] for t in trials if t["config"] == g
                                                 for it in t["iterations"]) / max(1, sum(t["config"] == g for t in trials)), 1)
                                   for g in res["configs"]}}
    for t in trials:
        report["matrix"][t["case_id"]][t["config"]] = (f"t{t['converged_at']}" if t["converged"] else
                                                        "low" if t["outcome"] == "stopped_low_confidence" else "x")
    with open(os.path.join(args.out, "pilot_report.json"), "w") as f:
        json.dump({"report": report, "recompute": res}, f, indent=1, default=str)
    configs = sorted(res["configs"])
    print("case  " + " ".join(f"{g:>7}" for g in configs))
    for cid in sorted(report["matrix"]):
        print(f"{cid:5} " + " ".join(f"{report['matrix'][cid].get(g, '-'):>7}" for g in configs))
    print(json.dumps({k: v for k, v in report.items() if k != "matrix"}, indent=1, default=str))


if __name__ == "__main__":
    main()
