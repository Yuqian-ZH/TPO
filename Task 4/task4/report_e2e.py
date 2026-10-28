"""End-to-end report (plan 5.3 item 4): e2e_summary.json and e2e_report.md from a run directory, offline.

    python report_e2e.py --out results/e2e_test"""
import argparse
import json
import os
import statistics
import sys

sys.dont_write_bytecode = True

from feedback_service.bridge import TASK3_ROOT  # noqa: E402
from feedback_service.store import _read_jsonl  # noqa: E402

REQUIRED = ("input_solution", "complaint", "critique", "refined_solution", "feasibility")


def load(out):
    with open(os.path.join(out, "e2e_results.json")) as f:
        run = json.load(f)
    store = os.path.join(out, "store", "sessions")
    for r in run["results"]:
        d = os.path.join(store, r["session_id"])
        r["iteration_log"] = _read_jsonl(os.path.join(d, "iterations.jsonl"))
        r["events"] = _read_jsonl(os.path.join(d, "events.jsonl"))
        with open(os.path.join(d, "feedback", f"{r['feedback_id']}.json")) as f:
            r["record"] = json.load(f)
    return run


def task3_reference(config, case_ids):
    """Task 3's formal trials of the same configuration (30 = 10 cases x 3 runs), for a consistency check."""
    d = os.path.join(TASK3_ROOT, "results", "formal", "trials", config)
    trials = []
    for cid in case_ids:
        for run in (1, 2, 3):
            p = os.path.join(d, f"{cid}__r{run}.json")
            if os.path.exists(p):
                with open(p) as f:
                    t = json.load(f)
                trials.append((t["converged"], t["converged_at"]))
    return {"trials": len(trials), "converged": sum(c for c, _ in trials),
            "converged_at_1": sum(1 for c, a in trials if c and a == 1)} if trials else None


def stats(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return {"n": len(xs), "median": round(statistics.median(xs), 2), "mean": round(statistics.mean(xs), 2),
            "max": round(max(xs), 2)}


def summarize(run):
    out = {"configs": {}, "cases": [], "llm_requests_total": run["llm_requests"], "restart": run["restart"],
           "aborted": run["aborted"], "final_check": run.get("final_check")}
    for config in run["configs"]:
        rs = [r for r in run["results"] if r["config"] == config]
        calls = {k: [c["elapsed_s"] for r in rs for c in r["calls"] if c["call"].endswith(k) and
                     c["call"].startswith("POST")] for k in ("/feedback", "/clarification", "/reply")}
        usage = [r["record"]["usage"] for r in rs]
        out["configs"][config] = {
            "cases": len(rs), "resolved": sum(r["status"] == "resolved" for r in rs),
            "resolved_at_iteration_1": sum(r["status"] == "resolved" and r["iterations"] == 1 for r in rs),
            "statuses": {s: sum(r["status"] == s for r in rs) for s in sorted({r["status"] for r in rs})},
            "clarified": sum(r["clarified"] for r in rs),
            "iterations": sum(r["iterations"] for r in rs),
            "llm_requests": sum(u.get("requests", 0) for u in usage),
            "prompt_tokens": sum(u.get("prompt_tokens", 0) for u in usage),
            "completion_tokens": sum(u.get("completion_tokens", 0) for u in usage),
            "http_latency_s": {k: stats(v) for k, v in calls.items()},
            "task3_same_config": task3_reference(config, [r["case_id"] for r in rs])}
    for r in run["results"]:
        logs = r["iteration_log"]
        out["cases"].append({
            "config": r["config"], "case_id": r["case_id"], "status": r["status"], "iterations": r["iterations"],
            "clarified": r["clarified"], "plans_shown": len(r["shown_plans"]),
            "final_total_distance": r["final_plan"]["metrics"]["total_distance"] if r["final_plan"] else None,
            "committed_modifications": logs[-1]["committed_modifications"] if logs else None,
            "llm_requests": r["record"]["usage"].get("requests"),
            "tokens": r["record"]["usage"].get("prompt_tokens", 0) + r["record"]["usage"].get("completion_tokens", 0),
            "feedback_call_s": next((c["elapsed_s"] for c in r["calls"] if c["call"].endswith("/feedback")), None),
            "iteration_records": len(logs),
            "iteration_records_complete": all(all(k in x for k in REQUIRED) for x in logs),
            "triggers": [x["trigger"] for x in logs]})
    return out


def transcript(r):
    """A readable account of one complaint, rebuilt from the service's own event and iteration logs."""
    lines = [f"Session `{r['session_id']}`, feedback `{r['feedback_id']}`, config {r['config']}, case {r['case_id']}.",
             ""]
    its = {x["iteration"]: x for x in r["iteration_log"]}
    for e in r["events"]:
        ev = e["event"]
        if ev == "session_created":
            lines.append(f"1. Session created with plan v0 `{e['routes']}`.")
        elif ev == "feedback_received":
            lines.append(f"1. Complaint received about plan v{e['solution']['version']}: \"{e['complaint']}\"")
        elif ev == "clarification_requested":
            loc = e["localization"]
            lines.append(f"1. Localization not confident ({e['llm']['requests']} LLM requests); the service asks: "
                         f"\"{loc['question']}\"")
        elif ev == "clarification_received":
            lines.append(f"1. User answers: \"{e['answer']}\"")
        elif ev == "critique_ready":
            c = e["critique"]
            if c["structured"]:
                s = c["structured"]
                lines.append(f"1. Critique: target `{s['target']}` ({s['aspect']}, {s['direction']}), "
                             f"{s['modification_type']}, threshold {s['threshold']}, evidence {s['evidence']}.")
            else:
                lines.append("1. Critique: the raw complaint (localization switched off).")
        elif ev in ("refined", "not_converged") and "iterations" in e:
            for t in e["iterations"]:
                x = its[t]
                rs = x["refined_solution"]
                if x["status"] != "committed":
                    lines.append(f"1. TPO iteration {t} ({x['trigger']}): {x['status']}. {x['note']}")
                    continue
                lines.append(f"1. TPO iteration {t} (trigger: {x['trigger']}): the LLM proposed "
                             f"`{json.dumps(x['committed_modifications'])}`; Gurobi re-solved to plan v{rs['version']} "
                             f"`{rs['routes']}`, total distance {rs['metrics']['total_distance']}, feasible "
                             f"{x['feasibility']['feasible']}. Proposer's rationale: \"{x['rationale']}\"")
        elif ev == "reply_received":
            lines.append(f"1. User reply: resolved={e['resolved']}"
                         + (f", \"{e['comment']}\"" if e.get("comment") else ""))
        elif ev in ("resolved", "stopped_by_user", "stopped_low_confidence", "failed"):
            lines.append(f"1. Final status: {ev}.")
        elif ev == "reverted":
            lines.append(f"1. Plan reverted from v{e['from_version']} to v{e['to_version']}.")
    return "\n".join(lines)


def markdown(run, s):
    L = ["# End-to-end run", "",
         f"Cases: `{run['cases_file']}` ({len({r['case_id'] for r in run['results']})}), configurations "
         f"{', '.join(run['configs'])}, one run each; {run['started_at']} to {run['finished_at']}. "
         f"LLM requests in the service log: {run['llm_requests']}." + (f" ABORTED: {run['aborted']}"
                                                                      if run["aborted"] else ""), "",
         "| Config | Resolved | At iteration 1 | Clarified | LLM requests | Tokens (prompt + completion) | "
         "POST /feedback median s | POST /reply median s | Task 3 same config (30 trials) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for g, c in s["configs"].items():
        t3 = c["task3_same_config"]
        fb, rp = c["http_latency_s"]["/feedback"], c["http_latency_s"]["/reply"]
        L.append(f"| {g} | {c['resolved']}/{c['cases']} | {c['resolved_at_iteration_1']}/{c['cases']} | "
                 f"{c['clarified']} | {c['llm_requests']} | {c['prompt_tokens']:,} + {c['completion_tokens']:,} | "
                 f"{fb['median'] if fb else '-'} | {rp['median'] if rp else '-'} | "
                 + (f"{t3['converged']}/{t3['trials']} converged, {t3['converged_at_1']} at iteration 1 |" if t3
                    else "- |"))
    L += ["", "| Config | Case | Status | Iterations | Clarified | Final distance | LLM requests | "
              "POST /feedback s | Triggers |", "|---|---|---|---|---|---|---|---|---|"]
    for c in s["cases"]:
        L.append(f"| {c['config']} | {c['case_id']} | {c['status']} | {c['iterations']} | "
                 f"{'yes' if c['clarified'] else ''} | {c['final_total_distance']} | {c['llm_requests']} | "
                 f"{c['feedback_call_s']} | {', '.join(c['triggers'])} |")
    if run["restart"]:
        r = run["restart"]
        L += ["", f"Restart: the server process was stopped and started again while {r['case_id']} ({r['config']}) "
                  f"waited for its first reply; after the restart the complaint was `{r['status_after_restart']}` "
                  f"with plan v{r['plan_version_after_restart']} (before: `{r['status_before']}`, "
                  f"v{r['plan_version_before']}), {r['sessions_after_restart']} sessions were reloaded, and the "
                  "reply was handled by the new process."]
    if run.get("final_check"):
        L += ["", f"Final check after the run: {json.dumps(run['final_check'])}."]
    pick = next((r for r in run["results"] if r["clarified"] and r["status"] == "resolved"), None)
    if pick:
        L += ["", "## Example: an ambiguous complaint, end to end", "", transcript(pick)]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    run = load(args.out)
    s = summarize(run)
    with open(os.path.join(args.out, "e2e_summary.json"), "w") as f:
        json.dump(s, f, indent=1, ensure_ascii=False)
    with open(os.path.join(args.out, "e2e_report.md"), "w") as f:
        f.write(markdown(run, s))
    print(json.dumps(s["configs"], indent=1))


if __name__ == "__main__":
    main()
