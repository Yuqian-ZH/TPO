"""task2_v3 results from results_v3/raw: results_v3/task2_v3_results.{json,md}. Run from the Task 2 root:
    python -m v3.report
Pure function of the saved raw files (task2_v1's metric definitions); no solver, no LLM."""
import json
import os
from collections import Counter

import metrics
from v2.report import cf_metrics

from .evaluate import CASES, OUT, RUNS

RES = os.path.dirname(OUT)


def load(part):
    p = os.path.join(OUT, f"{part}.json")
    return json.load(open(p))["data"] if os.path.exists(p) else None


def by_stratum_localization(cases, runs):
    """First-pass and after-clarification accuracy per stratum, pooled over runs."""
    out = {}
    for c in cases:
        s = out.setdefault(c["stratum"], {"first": [0, 0], "high_first": [0, 0], "after": [0, 0]})
        for per in runs:
            for phase, key in (("initial", "first"), ("clarified", "after")):
                r = per[c["id"]][phase]
                ok = r["diagnostics"]["majority_target"] in c["gt"]["localization"]["targets"]
                s[key][0] += ok
                s[key][1] += 1
                if phase == "initial" and r["confidence"] == "high":
                    s["high_first"][0] += ok
                    s["high_first"][1] += 1
    return out


def build():
    cases = json.load(open(CASES))["cases"]
    res = {"protocol": "task2_v3", "cases": len(cases), "strata": dict(Counter(c["stratum"] for c in cases))}
    att = load("attribution")
    if att:
        res["attribution"] = metrics.attribution_metrics(cases, att)
    exp = load("explanation")
    if exp:
        res["explanation"] = metrics.explanation_metrics(cases, exp, RUNS)
    cf = load("counterfactual")
    if cf:
        ents = cf["entries"]
        res["counterfactual"] = {kind: cf_metrics([e for e in ents if e["kind"] == kind])
                                 for kind in ("what_if", "reference_fix", "direct_or_misreading")}
        res["counterfactual"]["all"] = cf_metrics(ents)
    loc = load("localization")
    if loc:
        res["localization"] = metrics.localization_metrics(cases, loc, RUNS)
        res["localization_by_stratum"] = by_stratum_localization(cases, loc)
    return res


def _r(pair):
    k, n = pair
    return f"{k}/{n}" if n else "-"


def markdown(res):
    lines = ["# Task 2 results, protocol task2_v3", "",
             "The 10 test cases of DESIGN_V3.md (2 control, 3 ambiguity, 5 side), task2_v2.1's components. "
             "Ground truth by brute force.", ""]
    if "attribution" in res:
        a = res["attribution"]
        lines += ["## 1. Decision attribution", "",
                  f"- Returned set contains the ground truth: {a['inclusion_rate']['num']}/{a['inclusion_rate']['den']}",
                  f"- Pooled precision / recall: {a['pooled']['all']['precision']:.3f} / "
                  f"{a['pooled']['all']['recall']:.3f}; macro {a['macro']['precision']:.3f} / {a['macro']['recall']:.3f}",
                  "", "| Case | Decision | Conclusion | GT conclusion | Contains GT | P | R |", "|---|---|---|---|---|---|---|"]
        lines += [f"| {r['case']} | {r['decision']} | {r['conclusion']} | {r['gt_conclusion']} | {r['contains_gt']} | "
                  f"{r['precision']:.2f} | {r['recall']:.2f} |" for r in a["per_case"]]
    if "explanation" in res:
        e = res["explanation"]
        lines += ["", f"LLM explanation passes the number and entity checks: {100 * e['pass_rate']['mean']:.1f}% ± "
                      f"{100 * e['pass_rate']['std']:.1f} (first attempt {100 * e['first_attempt_pass_rate']['mean']:.1f}%; "
                      f"template fallbacks {e['template_fallbacks']})."]
    if "counterfactual" in res:
        lines += ["", "## 2. Counterfactual", "",
                  "Per case: the what-if query, the reference fix and the direct (or misread) encoding as "
                  "APPLY_MODIFICATIONS queries. Against brute force under the same anchor.", ""]
        for kind in ("what_if", "reference_fix", "direct_or_misreading", "all"):
            lines += [f"### {kind}", "", "| Method / set-up | Feasibility | Objective within 1% | Change set | Levels | "
                      "Median / mean / p95 ms |", "|---|---|---|---|---|---|"]
            for key, m in res["counterfactual"][kind].items():
                lat = m["latency_ms"]
                lines.append(f"| {key} | {_r(m['feasibility'])} | {_r(m['objective_1pct'])} | {_r(m['change_set'])} | "
                             f"{m['levels'] or '-'} | {lat['median']:.1f} / {lat['mean']:.1f} / {lat['p95']:.1f} |")
            lines.append("")
    if "localization" in res:
        lo = res["localization"]
        ac = lo["after_clarification"]

        def pct(x):
            return f"{100 * x['mean']:.1f}% ± {100 * x['std']:.1f}" if x else "-"
        lines += ["## 3. Feedback localization", "",
                  "| Metric | Value |", "|---|---|",
                  f"| Accuracy, first pass | {pct(lo['accuracy'])} |",
                  f"| Accuracy, predicted high | {pct(lo['accuracy_high'])} |",
                  f"| Accuracy, predicted low (first pass, before the question) | {pct(lo['accuracy_low'])} |",
                  f"| Predicted high / low per run | {lo['n_high_per_run']} / {lo['n_low_per_run']} |",
                  f"| Clarifying-question rate | {pct(lo['clarification_rate'])} |",
                  f"| Accuracy after the clarification answer | {pct(ac['accuracy'])} |",
                  f"| Modification type correct | {pct(lo['modification_type_accuracy'])} |",
                  f"| Low-confidence results that carried a critique | {lo['low_with_critique_total']} |", "",
                  "| Stratum | First pass correct | Correct when high | After clarification |", "|---|---|---|---|"]
        lines += [f"| {s} | {_r(v['first'])} | {_r(v['high_first'])} | {_r(v['after'])} |"
                  for s, v in res["localization_by_stratum"].items()]
    return "\n".join(lines) + "\n"


def main():
    res = build()
    with open(os.path.join(RES, "task2_v3_results.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    with open(os.path.join(RES, "task2_v3_results.md"), "w") as f:
        f.write(markdown(res))
    print(f"wrote {os.path.relpath(RES)}/task2_v3_results.{{json,md}}")


if __name__ == "__main__":
    main()
