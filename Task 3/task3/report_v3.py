"""task3_v3 report from saved trials only (no network, no LLM): <out>/task3_v3_results.{json,md}.
Analyses as pre-registered in protocol_v3.json / DESIGN_V3.md section 5.

    python report_v3.py --out results/formal_v3 --cases test
    python report_v3.py --out results/pilot_v3b --cases dev        # the pilot (descriptive only)"""
import argparse
import glob
import json
import os
import sys
from statistics import mean

sys.dont_write_bytecode = True

import stats  # noqa: E402
from report_v2 import cost_table, localization_cost  # noqa: E402
from run_experiment import load_cases, write_json  # noqa: E402
from run_experiment_v3 import CASES  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
STRATA = ("control", "ambiguity", "side")


def load_trials(out):
    return [json.load(open(p)) for p in sorted(glob.glob(os.path.join(out, "trials", "*", "*.json")))]


def at_first(trials):
    return [{**t, "converged": bool(t["converged"] and t["converged_at"] == 1)} for t in trials]


def stratum_effects(trials, strata, B):
    """Main effects within each stratum (case-clustered bootstrap over that stratum's cases)."""
    out = {}
    for s in STRATA:
        ts = [t for t in trials if strata[t["case_id"]] == s and t["config"] in stats.MAIN]
        if len({t["config"] for t in ts}) < len(stats.MAIN):
            continue
        boot = stats.cluster_bootstrap(ts, B=B)
        out[s] = {f: boot[f"main_{f}"] for f in stats.FACTORS}
        out[s]["rate_by_config"] = {g: round(mean(t["converged"] for t in ts if t["config"] == g), 4)
                                    for g in stats.MAIN}
    return out


def build(out, split, B=10000):
    cases = load_cases(CASES[split])
    strata = {c["id"]: c["stratum"] for c in cases}
    trials = load_trials(out)
    res = {"protocol": "task3_v3", "out": os.path.relpath(out, ROOT), "split": split, "trials": len(trials),
           "summary": stats.summarize(trials, B=B, case_labels={"stratum": strata})}
    if all(g in {t["config"] for t in trials} for g in stats.MAIN):
        res["first_iteration"] = {"effects": stats.cluster_bootstrap(at_first(trials), B=B)}
        res["first_iteration"]["verdict"] = stats.verdict_rule(res["first_iteration"]["effects"])
        res["by_stratum"] = stratum_effects(trials, strata, B)
        res["by_stratum_first_iteration"] = stratum_effects(at_first(trials), strata, B)
    runs = len({t["run"] for t in trials})
    for v in [res["summary"].get("verdict"), res.get("first_iteration", {}).get("verdict")]:
        if v:   # stats.verdict_rule's text was written for task3_v1's 3 runs; the rule itself is unchanged
            v["text"] = v["text"].replace("3 runs per configuration", f"{runs} runs per configuration")
    res["cost"] = cost_table(trials, localization_cost(out))
    res["localizations"] = summarize_localizations(out, cases)
    return res


def summarize_localizations(out, cases):
    gt = {c["id"]: c["gt"]["localization"]["targets"] for c in cases}
    rows = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(out, "localization", "*.json")))]
    final_ok = sum(1 for r in rows if r["final"].get("confidence") == "high"
                   and (r["final"].get("critique") or {}).get("target") in gt[r["case_id"]])
    return {"count": len(rows), "asked": sum(r["asked"] for r in rows), "final_high_and_correct": final_ok,
            "final_high_but_wrong": sum(1 for r in rows if r["final"].get("confidence") == "high"
                                        and (r["final"].get("critique") or {}).get("target") not in gt[r["case_id"]]),
            "still_low": sum(1 for r in rows if r["final"].get("confidence") != "high")}


def _ci(e):
    return f"{100 * e['estimate']:+.1f} pp [{100 * e['ci95'][0]:+.1f}, {100 * e['ci95'][1]:+.1f}]"


def markdown(res):
    s = res["summary"]
    lines = [f"# Task 3 results, protocol task3_v3 ({res['split']} cases)", "",
             f"Trials: {res['trials']} in `{res['out']}`. Design: DESIGN_V3.md; analyses as pre-registered there.", "",
             "## 1. Convergence within 3 iterations (primary)", "",
             "| Config | Mean ± std over runs | Per run | At iteration 1 | Mean iterations | Excess km when converged | "
             "Requests / tokens per trial (localization incl.) |", "|---|---|---|---|---|---|---|"]
    for g, t in s["configs"].items():
        c = res["cost"].get(g, {})
        ms = t["rate_mean_std_over_runs"]
        lines.append(f"| {g} | {100 * ms['mean']:.1f}% ± {100 * (ms['std'] or 0):.1f} | "
                     f"{' / '.join(f'{100 * v:.0f}%' for v in t['rate_per_run'].values())} | "
                     f"{100 * t['cumulative_by_iteration'][0]:.1f}% | {t['mean_iterations_when_converged']} | "
                     f"{t['excess_distance_mean_when_converged']} | {c.get('total_calls')} / {c.get('total_tokens')} |")
    if "effects" in s:
        e = s["effects"]
        lines += ["", "## 2. Mechanism effects (case-clustered bootstrap, 95% CI)", "",
                  "| Effect | Within 3 iterations | At iteration 1 |", "|---|---|---|"]
        fe = res["first_iteration"]["effects"]
        for k in ("main_A", "main_B", "main_C", "interaction_AB", "interaction_AC", "interaction_BC"):
            lines.append(f"| {k} | {_ci(e[k])} | {_ci(fe[k])} |")
        lines += ["", f"**Pre-registered rule (primary):** {s['verdict']['text']}  ",
                  f"**Same rule at iteration 1 (secondary):** {res['first_iteration']['verdict']['text']}", "",
                  "## 3. By stratum (pre-registered, descriptive)", "",
                  "| Stratum | A | B | C | A at t=1 | B at t=1 | C at t=1 |", "|---|---|---|---|---|---|---|"]
        for st, v in res["by_stratum"].items():
            v1 = res["by_stratum_first_iteration"][st]
            lines.append(f"| {st} | {_ci(v['A'])} | {_ci(v['B'])} | {_ci(v['C'])} | {_ci(v1['A'])} | {_ci(v1['B'])} | "
                         f"{_ci(v1['C'])} |")
        lines += ["", "| Stratum | " + " | ".join(stats.MAIN) + " |", "|---" * 9 + "|"]
        for st, v in res["by_stratum"].items():
            lines.append(f"| {st} | " + " | ".join(f"{100 * v['rate_by_config'][g]:.0f}%" for g in stats.MAIN) + " |")
    lines += ["", "## 4. Per case (converged runs)", "", "| Case | Stratum | " + " | ".join(s["configs"]) + " |",
              "|---" * (2 + len(s["configs"])) + "|"]
    case_ids = sorted({c for t in s["configs"].values() for c in t["per_case_converged_runs"]},
                      key=lambda x: int(x[1:]))
    for cid in case_ids:
        lines.append(f"| {cid} | {res['case_strata'][cid]} | " +
                     " | ".join(str(s["configs"][g]["per_case_converged_runs"].get(cid, "-")) for g in s["configs"])
                     + " |")
    if "paired" in s:
        lines += ["", "## 5. Paired comparisons (exact McNemar over (case, run) pairs)", "",
                  "| Slice | Comparison | Pairs | Only first | Only second | p |", "|---|---|---|---|---|---|"]
        for sl, comps in s["paired"].items():
            for name, p in comps.items():
                lines.append(f"| {sl} | {name} | {p['pairs']} | {p['first_only']} | {p['second_only']} | {p['p_value']} |")
    lo = res["localizations"]
    lines += ["", f"Shared localizations: {lo['count']}, asked {lo['asked']}; final high-confidence and correct "
                  f"{lo['final_high_and_correct']}, high but wrong {lo['final_high_but_wrong']}, still low {lo['still_low']}."]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--cases", choices=list(CASES), default="test")
    ap.add_argument("--bootstrap", type=int, default=10000)
    args = ap.parse_args()
    out = os.path.join(ROOT, args.out) if not os.path.isabs(args.out) else args.out
    res = build(out, args.cases, args.bootstrap)
    res["case_strata"] = {c["id"]: c["stratum"] for c in load_cases(CASES[args.cases])}
    write_json(os.path.join(out, "task3_v3_results.json"), res)
    with open(os.path.join(out, "task3_v3_results.md"), "w") as f:
        f.write(markdown(res))
    print(f"wrote {os.path.relpath(out, ROOT)}/task3_v3_results.{{json,md}}")


if __name__ == "__main__":
    main()
