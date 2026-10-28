"""Render results_v2/task2_v2_results.{json,md} from results_v2/raw/*.json, beside task2_v1's results/. Pure
function of saved artifacts (no solver, no LLM); parts that have not run yet are listed as missing.
    python -m v2.report"""
import glob
import json
import os
from collections import Counter

import metrics

from .evaluate import OUT, ROOT, load_cases
from .localization import decide

USC = os.path.dirname(os.path.dirname(ROOT))
TASK4_STORE = os.path.join(USC, "Task 4", "task4", "results", "e2e_test", "store", "sessions")


def load(part):
    path = os.path.join(OUT, f"{part}.json")
    return json.load(open(path)) if os.path.exists(path) else None


def pct(k, n):
    return f"{100 * k / n:.1f}% ({k}/{n})" if n else "n/a"


# ---------------- attribution ----------------

def soft_state_metrics(rows):
    out = {}
    for ver, gt_key in (("v1", "brute_force_v1_semantics"), ("v2", "brute_force_v2_semantics")):
        forced = [r for r in rows if not r[gt_key]["feasible"]]
        feas = [r for r in rows if r[gt_key]["feasible"]]
        wrong = [r for r in feas if "alternative_objective" not in r[ver]
                 or abs(r[ver]["alternative_objective"] - r[gt_key]["objective"]) > 1e-6]
        sets_ok = sum(tuple(r[ver]["attribution_set"]["variables"]) in map(tuple, r[gt_key]["acceptable_sets"])
                      for r in feas)
        cheaper = [r for r in feas if r[gt_key]["objective"] < r["current_objective"] - 1e-6]
        labelled_preferred = sum(r[ver]["conclusion"] == "objective_preferred" for r in cheaper)
        out[ver] = {"decisions": len(rows), "forced": len(forced),
                    "forced_correct": sum(r[ver]["conclusion"] == "hard_constraint_forced" for r in forced),
                    "feasible": len(feas), "number_correct": len(feas) - len(wrong), "set_correct": sets_ok,
                    "cheaper_alternative_exists": len(cheaper), "cheaper_but_called_preferred": labelled_preferred,
                    "wrong_by_source": dict(Counter(r["source"] for r in wrong)),
                    "worst": max(((abs(r[ver]["alternative_objective"] - r[gt_key]["objective"]), r["source"],
                                   r["decision"], r[ver]["alternative_objective"], r[gt_key]["objective"])
                                  for r in wrong if "alternative_objective" in r[ver]), default=None, key=lambda x: x[0])}
    out["v2"]["anchor_claims_checked"] = sum(1 for r in rows if "current_plan_optimal_under_anchor" in
                                             r["brute_force_v2_semantics"])
    out["v2"]["anchor_claims_correct"] = sum(1 for r in rows if r["brute_force_v2_semantics"].get(
        "current_plan_optimal_under_anchor") == r["v2"]["anchor"]["current_plan_optimal"])
    out["states"] = sorted({r["source"] for r in rows})
    return out


# ---------------- counterfactual ----------------

def cf_metrics(entries):
    methods = sorted({k for e in entries for k in e if "/" in k})
    res = {}
    for key in methods:
        n = len(entries)
        vals = [metrics._against_gt(e[key], e["gt"]) for e in entries]
        both = sum(v[1] for v in vals)
        lat = [x for e in entries for x in e[key]["latency"]]
        res[key] = {"feasibility": [sum(v[0] for v in vals), n], "objective_1pct": [sum(v[2] for v in vals), both],
                    "change_set": [sum(v[3] for v in vals), both],
                    "levels": dict(Counter(e[key].get("level") for e in entries if e[key].get("level"))),
                    "latency_ms": metrics.summary([1000 * x["with_model_setup_s"] for x in lat]),
                    "solve_only_ms": metrics.summary([1000 * x["solve_only_s"] for x in lat]),
                    "nondeterministic": sum(e[key]["nondeterministic"] for e in entries)}
    return res


# ---------------- localization ----------------

def rescore_metrics(runs, cases):
    same, changed = 0, []
    for run, per in enumerate(runs):
        for c in cases:
            for phase, r in per[c["id"]].items():
                if r["v1_confidence"] == r["v2"]["confidence"]:
                    same += 1
                else:
                    changed.append({"run": run, "case": c["id"], "phase": phase, "v1": r["v1_confidence"],
                                    "v2": r["v2"]["confidence"]})
    return {"compared": same + len(changed), "same_confidence": same, "changed": changed}


def task4_t7():
    """Task 4's T7 (A1B1C1, task4_v1 end-to-end run): the frozen rule stopped it; the v2 rule on the same samples."""
    from components.state import make_state
    out = []
    for path in sorted(glob.glob(os.path.join(TASK4_STORE, "*", "feedback", "*.json"))):
        fb = json.load(open(path))
        if fb["status"] != "stopped_low_confidence":
            continue
        loc = fb["localization"]
        st = make_state({"routes": fb["solution"]["routes"]}, fb["session_modifications"])
        for phase, clar in (("initial", None), ("after_clarification",
                                                {"question": loc["question"], "answer": loc["answer"]})):
            raw = loc[phase]["raw"]
            new = decide(raw["diagnostics"]["samples"], st, fb["complaint"], clar)
            out.append({"feedback_id": fb["feedback_id"], "phase": phase, "v1_confidence": raw["confidence"],
                        "v1_type_counts": dict(Counter(s["sample"]["modification_type"]
                                                       for s in raw["diagnostics"]["samples"] if s["valid"])),
                        "v2_confidence": new["confidence"],
                        "v2_critique": {k: (new["critique"] or {}).get(k) for k in
                                        ("target", "modification_type", "threshold")}})
    return out


def build():
    cases = load_cases()
    v1 = json.load(open(os.path.join(ROOT, "results", "task2_results.json")))["metrics"]
    res = {"missing_parts": []}
    att = load("attribution")
    if att:
        res["attribution_test_cases"] = metrics.attribution_metrics(cases, att["data"]["test_cases"])
        res["attribution_soft_states"] = soft_state_metrics(att["data"]["soft_states"])
    exp = load("explanation")
    if exp:
        res["explanation"] = metrics.explanation_metrics(cases, exp["data"], 3)
    cf = load("counterfactual")
    if cf:
        ents = cf["data"]["entries"]
        res["counterfactual_main"] = cf_metrics([e for e in ents if e["main"]])
        res["counterfactual_supplementary"] = cf_metrics([e for e in ents if not e["main"]])
    rs = load("localization_rescore")
    if rs:
        res["localization_rescore"] = rescore_metrics(rs["data"]["runs"], cases)
    res["task4_t7_rescored"] = task4_t7()
    loc = load("localization")
    if loc:
        res["localization"] = metrics.localization_metrics(cases, loc["data"], 3)
        res["localization_questions"] = [{"run": run, "case": c["id"],
                                          "question": per[c["id"]]["initial"]["clarifying_question"],
                                          "disagreement": per[c["id"]]["initial"]["diagnostics"].get("disagreement")}
                                         for run, per in enumerate(loc["data"]) for c in cases
                                         if per[c["id"]]["initial"]["confidence"] == "low"]
    for part in ("attribution", "explanation", "counterfactual", "localization_rescore", "localization"):
        if load(part) is None:
            res["missing_parts"].append(part)
    return res, v1


def markdown(res, v1):
    L = ["# Task 2 results, protocol task2_v2", "",
         "Fixed attribution (audit F1), fair counterfactual timing (F4) and the localization rule that counts only what "
         "the user can answer (F5, Task 4's T7). task2_v1's results (`results/`) are unchanged and quoted beside v2.", ""]
    if res["missing_parts"]:
        L += [f"Parts not run yet: {', '.join(res['missing_parts'])}.", ""]
    if "attribution_test_cases" in res:
        a, a1 = res["attribution_test_cases"], v1["attribution"]
        L += ["## 1. Decision attribution", "", "### 1.1 The 10 test cases (same ground truth as v1)", "",
              "| | v1 | v2 |", "|---|---|---|",
              f"| Returned set contains the ground truth | {a1['inclusion_rate']['num']}/10 | {a['inclusion_rate']['num']}/10 |",
              f"| Pooled precision / recall | {a1['pooled']['all']['precision']:.3f} / {a1['pooled']['all']['recall']:.3f} | "
              f"{a['pooled']['all']['precision']:.3f} / {a['pooled']['all']['recall']:.3f} |", ""]
        if "explanation" in res:
            e, e1 = res["explanation"], v1["explanation"]
            L += [f"LLM explanation passes the number and entity checks: v1 {100 * e1['pass_rate']['mean']:.1f}% ± "
                  f"{100 * e1['pass_rate']['std']:.1f}, v2 {100 * e['pass_rate']['mean']:.1f}% ± {100 * e['pass_rate']['std']:.1f} "
                  f"(first attempt {100 * e['first_attempt_pass_rate']['mean']:.1f}%; template fallbacks {e['template_fallbacks']}).", ""]
        s = res["attribution_soft_states"]
        L += ["### 1.2 Where v1 was wrong: plans under soft constraints and weights", "",
              f"The 10 test cases are optimal plans of the unmodified model, where vehicle labels and driving direction "
              f"do not change the objective; the 10/10 above says nothing about other plans. Here every ADJ, SAME and "
              f"SEP decision is attributed on {len(s['states'])} plans that carry soft constraints, weights or corrected "
              "data: the 10 reference-fix plans and the 14 Task 3 loop states where condition A ran at iteration 2 or 3. "
              "Ground truth: brute force (no Gurobi), with labels free for v1 (what v1 solves) and under the anchor v2 "
              "chose for v2.", "",
              "| | v1 | v2 |", "|---|---|---|",
              f"| Decisions | {s['v1']['decisions']} | {s['v2']['decisions']} |",
              f"| Forced by capacity, conclusion correct | {s['v1']['forced_correct']}/{s['v1']['forced']} | "
              f"{s['v2']['forced_correct']}/{s['v2']['forced']} |",
              f"| Objective of the alternative correct | {pct(s['v1']['number_correct'], s['v1']['feasible'])} | "
              f"{pct(s['v2']['number_correct'], s['v2']['feasible'])} |",
              f"| Edge set correct | {s['v1']['set_correct']}/{s['v1']['feasible']} | {s['v2']['set_correct']}/{s['v2']['feasible']} |",
              f"| A cheaper plan exists without the decision | {s['v1']['cheaper_alternative_exists']} (all called "
              f"objective_preferred: {s['v1']['cheaper_but_called_preferred']}) | {s['v2']['cheaper_alternative_exists']} |",
              "", f"v1's wrong numbers by plan: {s['v1']['wrong_by_source']}. Largest error: {s['v1']['worst']}.",
              f"v2's anchor claim (the current plan is optimal under the chosen anchor) checked by brute force: "
              f"{s['v2']['anchor_claims_correct']}/{s['v2']['anchor_claims_checked']}.", ""]
    if "counterfactual_main" in res:
        L += ["## 2. Counterfactual: escalation rule and timing with equal set-up", "",
              "warm: the model of the state is built once, before the timed calls; cold: built inside every call. "
              "local_v1 is the frozen rule, local_v2 is Task 3's (the probe the TPO loop uses), full frees every customer "
              "and has no MIP start. task2_v1 timed local warm against full cold.", ""]
        for title, key in (("10 test-case queries", "counterfactual_main"),
                           ("120 supplementary queries (every MOVE and FIX_ARC on the reference optimum)",
                            "counterfactual_supplementary")):
            m = res[key]
            L += [f"### {title}", "", "| Method / set-up | Feasibility | Objective within 1% | Change set | Levels | "
                  "Median / mean / p95 ms |", "|---|---|---|---|---|---|"]
            for k, v in m.items():
                lat = v["latency_ms"]
                L.append(f"| {k} | {v['feasibility'][0]}/{v['feasibility'][1]} | {v['objective_1pct'][0]}/{v['objective_1pct'][1]} | "
                         f"{v['change_set'][0]}/{v['change_set'][1]} | {v['levels'] or '-'} | "
                         f"{lat['median']:.1f} / {lat['mean']:.1f} / {lat['p95']:.1f} |")
            L.append("")
    if "localization_rescore" in res:
        r = res["localization_rescore"]
        L += ["## 3. Feedback localization", "", "### 3.1 The v2 rule on v1's samples", "",
              f"Same 5 samples per complaint, only the rule changes: {r['same_confidence']}/{r['compared']} decisions "
              f"(10 cases x 3 runs x first pass and clarified pass) are the same as v1's; changed: {r['changed'] or 'none'}.", ""]
    if res.get("task4_t7_rescored"):
        L += ["Task 4's T7 (`A1B1C1`, task4_v1 end-to-end run), the complaint the frozen rule stopped:", "",
              "| Pass | v1 | Modification types in the samples | v2 | v2 critique |", "|---|---|---|---|---|"]
        for t in res["task4_t7_rescored"]:
            L.append(f"| {t['phase']} | {t['v1_confidence']} | {t['v1_type_counts']} | {t['v2_confidence']} | "
                     f"{t['v2_critique']} |")
        L.append("")
    if "localization" in res:
        lo, lo1 = res["localization"], v1["localization"]
        L += ["### 3.2 Fresh v2 run (3 runs, new samples)", "",
              "| Metric | v1 | v2 |", "|---|---|---|",
              f"| Accuracy, first pass | {100 * lo1['accuracy']['mean']:.1f}% ± {100 * lo1['accuracy']['std']:.1f} | "
              f"{100 * lo['accuracy']['mean']:.1f}% ± {100 * lo['accuracy']['std']:.1f} |",
              f"| Accuracy, predicted high | {100 * lo1['accuracy_high']['mean']:.1f}% | {100 * lo['accuracy_high']['mean']:.1f}% |",
              f"| Predicted high / low per run | {lo1['n_high_per_run']} / {lo1['n_low_per_run']} | "
              f"{lo['n_high_per_run']} / {lo['n_low_per_run']} |",
              f"| Clarifying-question rate | {100 * lo1['clarification_rate']['mean']:.1f}% | {100 * lo['clarification_rate']['mean']:.1f}% |",
              f"| Accuracy after the clarification answer | {100 * lo1['after_clarification']['accuracy']['mean']:.1f}% | "
              f"{100 * lo['after_clarification']['accuracy']['mean']:.1f}% |",
              f"| Modification type correct | {100 * lo1['modification_type_accuracy']['mean']:.1f}% | "
              f"{100 * lo['modification_type_accuracy']['mean']:.1f}% |",
              f"| Low-confidence results that carried a critique | {lo1['low_with_critique_total']} | {lo['low_with_critique_total']} |", "",
              "Questions asked in the v2 run:", ""]
        L += [f"- run {q['run']} {q['case']} ({q['disagreement']}): {q['question']}" for q in res["localization_questions"]]
        L.append("")
    return "\n".join(L) + "\n"


def main():
    res, v1 = build()
    with open(os.path.join(ROOT, "results_v2", "task2_v2_results.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    with open(os.path.join(ROOT, "results_v2", "task2_v2_results.md"), "w") as f:
        f.write(markdown(res, v1))
    print(f"missing parts: {res['missing_parts'] or 'none'}")


if __name__ == "__main__":
    main()
