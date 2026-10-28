"""task4_v3 end-to-end report: e2e_summary.json and e2e_report.md from a run directory, offline.
Same summary as report_e2e.py, compared with Task 3's task3_v3 trials of the same configuration (5 runs).

    python report_e2e_v3.py --out results/e2e_test_v3"""
import argparse
import json
import os
import sys

sys.dont_write_bytecode = True

import report_e2e  # noqa: E402
from feedback_service.bridge import TASK3_ROOT  # noqa: E402


def task3_v3_reference(config, case_ids):
    d = os.path.join(TASK3_ROOT, "results", "formal_v3", "trials", config)
    trials = []
    for cid in case_ids:
        for run in range(1, 6):
            p = os.path.join(d, f"{cid}__r{run}.json")
            if os.path.exists(p):
                with open(p) as f:
                    t = json.load(f)
                trials.append((t["converged"], t["converged_at"]))
    return {"trials": len(trials), "converged": sum(c for c, _ in trials),
            "converged_at_1": sum(1 for c, a in trials if c and a == 1)} if trials else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    report_e2e.task3_reference = task3_v3_reference
    run = report_e2e.load(out)
    run.setdefault("restart", None)
    s = report_e2e.summarize(run)
    by_case = {(r["config"], r["case_id"]): r for r in run["results"]}
    for c in s["cases"]:
        r = by_case[(c["config"], c["case_id"])]
        c.update(stratum=r["stratum"], excess_distance=r["excess_distance"],
                 plans_shown_unmet=[p["unmet"] for p in r["shown_plans"]])
    for config, v in s["configs"].items():
        rs = [c for c in s["cases"] if c["config"] == config]
        v["by_stratum"] = {st: f"{sum(c['status'] == 'resolved' for c in rs if c['stratum'] == st)}/"
                               f"{sum(1 for c in rs if c['stratum'] == st)}" for st in ("control", "ambiguity", "side")}
    with open(os.path.join(out, "e2e_summary.json"), "w") as f:
        json.dump(s, f, indent=1, ensure_ascii=False)
    lines = ["# End-to-end run, task4_v3", "",
             f"Cases: Task 2 v3 test cases (10), configurations {', '.join(run['configs'])}, one run each; "
             f"{run['started_at']} to {run['finished_at']}. LLM requests in the service log: {run['llm_requests']}.", "",
             "| Config | Resolved | At iteration 1 | By stratum (control / ambiguity / side) | Clarified | LLM requests | "
             "Tokens | POST /feedback median s | Task 3 v3 same config (50 trials) |", "|---|---|---|---|---|---|---|---|---|"]
    for config, v in s["configs"].items():
        t3 = v["task3_same_config"] or {}
        fb = (v["http_latency_s"].get("/feedback") or {}).get("median")
        lines.append(f"| {config} | {v['resolved']}/{v['cases']} | {v['resolved_at_iteration_1']} | "
                     f"{v['by_stratum']['control']} / {v['by_stratum']['ambiguity']} / {v['by_stratum']['side']} | "
                     f"{v['clarified']} | {v['llm_requests']} | {v['prompt_tokens']:,} + {v['completion_tokens']:,} | "
                     f"{fb} | {t3.get('converged')}/{t3.get('trials')} converged, {t3.get('converged_at_1')} at 1 |")
    lines += ["", "| Config | Case | Stratum | Status | Iterations | Clarified | Plans shown | Excess km | Requests | "
                  "Triggers |", "|---|---|---|---|---|---|---|---|---|---|"]
    for c in s["cases"]:
        lines.append(f"| {c['config']} | {c['case_id']} | {c['stratum']} | {c['status']} | {c['iterations']} | "
                     f"{'yes' if c['clarified'] else ''} | {c['plans_shown']} | {c['excess_distance']} | "
                     f"{c['llm_requests']} | {', '.join(c['triggers'])} |")
    fc = s.get("final_check") or {}
    lines += ["", f"Final check: {json.dumps(fc)}. Iteration records complete: "
                  f"{sum(c['iteration_records_complete'] for c in s['cases'])}/{len(s['cases'])}."]
    with open(os.path.join(out, "e2e_report.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {out}/e2e_report.md")


if __name__ == "__main__":
    main()
