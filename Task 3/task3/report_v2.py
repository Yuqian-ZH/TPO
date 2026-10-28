"""task3_v2 report: results/formal_v2/task3_v2_results.{json,md} and figures, from saved trials only (no network,
no LLM; the brute-force oracle re-checks every attribution that reached a prompt at iteration 2 or 3).

Beside the v2 batch it reports task3_v1 (results/formal) for the same 8 configurations, and the cost of each
configuration with the shared localization counted (audit F3: task3_v1 counted only the TPO calls).

    python report_v2.py"""
import argparse
import glob
import json
import os
import sys
from collections import defaultdict
from statistics import mean

sys.dont_write_bytecode = True

import report  # noqa: E402
import stats  # noqa: E402
from freeze_protocol import TEST_CASES  # noqa: E402
from recompute import load_trials, recompute  # noqa: E402
from run_experiment import load_cases, write_json  # noqa: E402
from tpo.task2_bridge import apply_data_mods, canon, load_frozen_instance, oracle_for  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.join(ROOT, "results", "formal")
V2 = os.path.join(ROOT, "results", "formal_v2")


def localization_cost(v1_dir):
    """(case, run) -> [calls, tokens] of the shared localization, from task3_v1's request logs."""
    out = defaultdict(lambda: [0, 0])
    for path in glob.glob(os.path.join(v1_dir, "logs", "llm_*.jsonl")):
        for line in open(path):
            r = json.loads(line)
            if str(r.get("component", "")).startswith("localize"):
                u = r.get("usage") or {}
                k = out[(r["case_id"], int(str(r["run"]).split("-")[-1]))]
                k[0] += 1
                k[1] += (u.get("prompt_tokens") or 0) + (u.get("completion_tokens") or 0)
    return out


def cost_table(trials, loc):
    rows = {}
    for g in sorted({t["config"] for t in trials}):
        ts = [t for t in trials if t["config"] == g]
        tpo = [stats.llm_calls(t) for t in ts]
        shared = [loc[(t["case_id"], t["run"])] if t.get("localization") else [0, 0] for t in ts]
        rows[g] = {"tpo_calls": round(mean(c for c, _ in tpo), 2), "tpo_tokens": round(mean(x for _, x in tpo)),
                   "localization_calls": round(mean(c for c, _ in shared), 2),
                   "localization_tokens": round(mean(x for _, x in shared)),
                   "total_calls": round(mean(c for c, _ in tpo) + mean(c for c, _ in shared), 2),
                   "total_tokens": round(mean(x for _, x in tpo) + mean(x for _, x in shared))}
    return rows


def attribution_check(trials, base, cases):
    """Every attribution item shown at iteration >= 2: its number against brute force under the anchor it used
    (none for task2_v1, so on task3_v1's trials this finds the audit's 18)."""
    items, wrong, cheaper, per_trial = 0, [], 0, {}
    for t in trials:
        for it in t["iterations"]:
            a = it.get("attribution")
            if not a or it["t"] < 2:
                continue
            per_trial[(t["config"], t["case_id"], t["run"])] = it["t"]
            mods = list(cases[t["case_id"]].get("model_modifications", [])) + it["mods_before"]
            sol = it["input_solution"]
            cur = canon.objective(sol, apply_data_mods(base, mods), mods)
            o = oracle_for(base, mods)
            for x in a["items"]:
                items += 1
                raw = x["raw"]
                if x["conclusion"] == "cheaper_without":
                    cheaper += 1
                if "alternative_objective" not in raw:
                    continue
                prims = [canon.forbid_decision(raw["decision"])]
                if "anchor" in raw:                       # task2_v1 attribution had no anchor
                    prims.append({k: raw["anchor"][k] for k in ("type", "i", "k")})
                gt = o.solve(mods, prims)
                if abs(gt["objective"] - raw["alternative_objective"]) > 1e-6 or \
                        abs(x["objective_increase_if_forbidden"] - (gt["objective"] - cur)) > 1e-6:
                    wrong.append({"trial": [t["config"], t["case_id"], t["run"], it["t"]], "decision": x["decision"]})
    return {"items_at_iteration_2_or_3": items, "trials": len(per_trial), "wrong_numbers": wrong,
            "cheaper_without": cheaper}


def side_by_side(r1, r2):
    out = {}
    for g in stats.MAIN:
        a, b = r1["configs"][g], r2["configs"][g]
        out[g] = {v: {"mean": x["rate_mean_std_over_runs"]["mean"], "std": x["rate_mean_std_over_runs"]["std"],
                      "per_run": x["rate_per_run"], "at_iteration_1": x["cumulative_by_iteration"][0],
                      "failures": x["trials"] - x["converged"], "per_case": x["per_case_converged_runs"]}
                  for v, x in (("v1", a), ("v2", b))}
    return out


def pct(v):
    return "n/a" if v is None else f"{100 * v:.1f}%"


def markdown(res2, sec2, res1, sec1, sbs, cost1, cost2, att, loc2, batch, proto, trials2):
    L = ["# Task 3 results, protocol task3_v2", "",
         f"Protocol `protocol_v2.json` frozen {proto['frozen_at']}. Change against task3_v1: condition A uses Task 2's "
         "task2_v2 attribution (audit F1). Everything else is task3_v1's frozen loop, prompts and seeds. "
         f"{len(trials2)} trials = 8 configurations x 3 runs x 10 test cases; S1 and S2 were not re-run. The "
         f"{batch['localizations_reused']} shared localizations are task3_v1's, re-used after checking that the "
         "v2 confidence rule reaches the same decision and question on their samples.", "",
         "## 1. Convergence, v1 and v2 batches", "",
         "| Config | v1 mean ± std | v1 runs | v1 at t=1 | v1 failures | v2 mean ± std | v2 runs | v2 at t=1 | v2 failures |",
         "|---|---|---|---|---|---|---|---|---|"]
    for g, v in sbs.items():
        a, b = v["v1"], v["v2"]
        L.append(f"| {g} | {pct(a['mean'])} ± {100 * (a['std'] or 0):.1f} | "
                 f"{' / '.join(pct(x) for x in a['per_run'].values())} | {pct(a['at_iteration_1'])} | {a['failures']} | "
                 f"{pct(b['mean'])} ± {100 * (b['std'] or 0):.1f} | {' / '.join(pct(x) for x in b['per_run'].values())} "
                 f"| {pct(b['at_iteration_1'])} | {b['failures']} |")
    L += ["", "![Convergence per configuration](fig_convergence.png)", "", "![Convergence by iteration](fig_by_iteration.png)",
          "", "## 2. Mechanism effects (v2 batch; v1 for reference)", "",
          "| Effect | v2 within 3 iterations [95% CI] | v2 at iteration 1 [95% CI] | v1 within 3 iterations | v1 at iteration 1 |",
          "|---|---|---|---|---|"]
    for k in [f"main_{f}" for f in "ABC"] + ["interaction_AB", "interaction_AC", "interaction_BC"]:
        a, b, c, d = res2["effects"][k], sec2[k], res1["effects"][k], sec1[k]
        L.append(f"| {k} | {100 * a['estimate']:+.1f} pp [{100 * a['ci95'][0]:+.1f}, {100 * a['ci95'][1]:+.1f}] | "
                 f"{100 * b['estimate']:+.1f} pp [{100 * b['ci95'][0]:+.1f}, {100 * b['ci95'][1]:+.1f}] | "
                 f"{100 * c['estimate']:+.1f} pp | {100 * d['estimate']:+.1f} pp |")
    L += ["", f"**Pre-registered rule, v2 (primary):** {res2['verdict']['text']}  ",
          f"**Same rule on convergence at iteration 1, v2 (secondary):** {stats.verdict_rule(sec2)['text']}", "",
          "### Paired comparisons in the v2 batch (exact McNemar over (case, run) pairs)", "",
          "| Slice | Comparison | Pairs | Only first converged | Only second converged | p |", "|---|---|---|---|---|---|"]
    for name, comps in res2["paired"].items():
        for cmp_, r in comps.items():
            L.append(f"| {name} | {cmp_} | {r['pairs']} | {r['first_only']} | {r['second_only']} | {r['p_value']} |")
    L += ["", "## 3. Per case (converged runs out of 3), v1 / v2", "", "| Case | " + " | ".join(stats.MAIN) + " |",
          "|---|" + "---|" * len(stats.MAIN)]
    for c in sorted({t["case_id"] for t in trials2}, key=lambda c: int(c[1:])):
        L.append(f"| {c} | " + " | ".join(f"{sbs[g]['v1']['per_case'].get(c, '-')} / {sbs[g]['v2']['per_case'].get(c, '-')}"
                                          for g in stats.MAIN) + " |")
    L += ["", "## 4. Attribution in the prompt (the reason for v2)", "",
          f"- Attribution items shown at iteration 2 or 3 in the v2 batch: {att['items_at_iteration_2_or_3']} in "
          f"{att['trials']} trials. Numbers that disagree with brute force under the anchor the component used: "
          f"{len(att['wrong_numbers'])} (task3_v1: 18 in 2 of 11 such trials). Conclusions `cheaper_without`: "
          f"{att['cheaper_without']}.", "",
          "## 5. Cost per trial, shared localization included (audit F3)", "",
          "task3_v1's README counted only the TPO calls, so configurations with C looked cheapest. Each trial with C "
          "(and S2) also needs the shared localization of its (case, run): 5 samples, plus 5 more after a "
          "clarification. Its cost is taken from task3_v1's logs for both batches, because v2 re-used those "
          "localizations.", "",
          "| Config | v1 TPO calls | v1 total calls | v1 total tokens | v2 TPO calls | v2 total calls | v2 total tokens |",
          "|---|---|---|---|---|---|---|"]
    for g in report.ORDER:
        a, b = cost1.get(g), cost2.get(g)
        if a is None:
            continue
        L.append(f"| {g} | {a['tpo_calls']} | {a['total_calls']} | {a['total_tokens']:,} | "
                 + (f"{b['tpo_calls']} | {b['total_calls']} | {b['total_tokens']:,} |" if b else "not re-run | | |"))
    L += ["", "## 6. Shared localization (v2 batch)", "",
          f"- {loc2['n']} localizations: asked {loc2['asked']}x; final high-confidence and correct "
          f"{loc2['final_high_and_correct']}, high-confidence but wrong {loc2['final_high_but_wrong']}, still low "
          f"{loc2['still_low_after_clarification']}."]
    for g in stats.MAIN:
        v = res2["configs"][g]
        L.append(f"- {g}: invalid candidates {pct(v['invalid_candidate_rate'])}, rejected iterations "
                 f"{v['rejected_iterations']}, no-plan iterations {v['no_plan_iterations']}, illegal data modifications "
                 f"{v['illegal_data_mods']}, mean iterations when converged {v['mean_iterations_when_converged']}, "
                 f"excess distance vs Task 2 reference fix {v['excess_distance_mean_when_converged']}, probe vs commit "
                 f"{v['probe_commit_agreement']}")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=V2)
    args = ap.parse_args()
    cases = load_cases(TEST_CASES)
    report.CASE_LABELS.update({c["id"]: {"clarity": c["clarity"], "complaint_object": c["complaint_object"]}
                               for c in cases})
    base = load_frozen_instance()
    res2 = recompute(args.out, cases, base)
    trials2 = load_trials(args.out)
    trials1 = [t for t in load_trials(V1) if t["config"] in stats.MAIN]
    res1 = stats.summarize(trials1, case_labels=None)
    sec2 = stats.cluster_bootstrap(report.first_iteration(trials2))
    sec1 = stats.cluster_bootstrap(report.first_iteration(trials1))
    loc = localization_cost(V1)
    cost1 = cost_table(load_trials(V1), loc)
    cost2 = cost_table(trials2, loc)
    att = attribution_check(trials2, base, {c["id"]: c for c in cases})
    loc2 = report.localization_table(args.out, cases)
    batch = json.load(open(os.path.join(args.out, "batch.json")))
    proto = json.load(open(os.path.join(ROOT, "protocol_v2.json")))
    sbs = side_by_side(res1, res2)
    write_json(os.path.join(args.out, "task3_v2_results.json"),
               {"recompute": res2, "first_iteration_effects": sec2, "v1_same_configs": {"recompute": res1,
                                                                                       "first_iteration_effects": sec1},
                "side_by_side": sbs, "cost_v1": cost1, "cost_v2": cost2, "attribution_check": att,
                "localization": loc2, "llm_requests_v2": report.llm_cost(args.out)})
    report.fig_convergence(res2, os.path.join(args.out, "fig_convergence.png"))
    report.fig_by_iteration(res2, os.path.join(args.out, "fig_by_iteration.png"))
    with open(os.path.join(args.out, "task3_v2_results.md"), "w") as f:
        f.write(markdown(res2, sec2, res1, sec1, sbs, cost1, cost2, att, loc2, batch, proto, trials2))
    print(res2["verdict"]["text"])
    print("secondary:", stats.verdict_rule(sec2)["text"])


if __name__ == "__main__":
    main()
