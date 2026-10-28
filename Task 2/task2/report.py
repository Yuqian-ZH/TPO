"""Render results/task2_results.md from results/task2_results.json and the saved artifacts.
python report.py [--out results]"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def pct(r):
    if r is None:
        return "n/a"
    if isinstance(r, dict) and "rate" in r:
        return "n/a" if r["rate"] is None else f"{100 * r['rate']:.1f}% ({r['num']}/{r['den']})"
    if isinstance(r, dict) and "mean" in r:
        return f"{100 * r['mean']:.1f}% ± {100 * r['std']:.1f}"
    return f"{100 * r:.1f}%"


def ms(s):
    return f"{s['median']:.1f} / {s['mean']:.1f} / {s['p95']:.1f}"


def qstr(q):
    t = q["type"]
    if t == "FIX_ARC":
        return f"FIX_ARC(v{q['k']}: {q['i']}→{q['j']})"
    if t == "MOVE":
        return f"MOVE({q['i']}→v{q['k']})"
    if t == "APPLY_MODIFICATIONS":
        m = q["mods"][0]
        return "APPLY(" + (f"{m['target']} {m['sense']} {m['rhs']}" if m["op"] == "add_soft_constraint" else
                           f"w[{m['term']}]={m['weight']}" if m["op"] == "set_objective_weight" else
                           f"{m['field']}={m['value']}") + ")"
    return f"{t}({q['i']},{q['j']})"


def cf_section(title, m, per_query=True):
    lv = m["local_vs_full"]
    lines = [f"### {title}", "",
             f"{m['queries']} queries. Local re-optimization vs full re-solve:", "",
             "| Agreement | Rate |", "|---|---|",
             f"| Feasibility | {pct(lv['feasibility'])} |",
             f"| Objective within 1% (both feasible) | {pct(lv['objective_1pct'])} |",
             f"| Change set (both feasible) | {pct(lv['change_set'])} |", ""]
    if "local_vs_exhaustive" in m:
        lines += ["Each method against the exhaustive ground truth:", "",
                  "| Method | Feasibility | Objective within 1% | Change set |", "|---|---|---|---|"]
        for meth in ("local", "full"):
            g = m[f"{meth}_vs_exhaustive"]
            lines.append(f"| {meth} | {pct(g['feasibility'])} | {pct(g['objective_1pct'])} | {pct(g['change_set'])} |")
        lines.append("")
    lines += [f"Levels where the local method stopped: L0 {m['levels']['L0']}, L1 {m['levels']['L1']}, "
              f"L2 {m['levels']['L2']}; infeasible after L2: {m['local_infeasible']} "
              f"(infeasible reported before L2: {m['local_infeasible_before_L2']}).", "",
              "Latency in ms over all repeats (median / mean / p95):", "",
              "| Method | Including model setup | Solver only |", "|---|---|---|"]
    for meth in ("local", "full"):
        lat = m[f"latency_{meth}_ms"]
        lines.append(f"| {meth} | {ms(lat['with_model_setup'])} | {ms(lat['solve_only'])} |")
    lines.append("")
    if per_query:
        lines += ["| Case | Query | Local (level) | Full | Feasible / objective / change set agree | "
                  "Median ms local / full |", "|---|---|---|---|---|---|"]
        for r in m["per_query"]:
            loc = f"{r['local_objective']:g} ({r['level']})" if r["local_feasible"] else "infeasible"
            full = f"{r['full_objective']:g}" if r["full_feasible"] else "infeasible"
            agree = " / ".join("yes" if r[k] else ("n/a" if not (r["local_feasible"] and r["full_feasible"])
                                                   and k != "feasibility_agree" else "no")
                               for k in ("feasibility_agree", "objective_agree", "change_set_agree"))
            lines.append(f"| {r['id']} | {qstr(r['query'])} | {loc} | {full} | {agree} | "
                         f"{r['local_median_ms']:.1f} / {r['full_median_ms']:.1f} |")
        lines.append("")
    else:
        bad = [r for r in m["per_query"] if not (r["feasibility_agree"] and (r["objective_agree"] or not
                                                                             (r["local_feasible"] and r["full_feasible"])))]
        lines += [f"Queries where local and full disagree on feasibility or objective: {len(bad)}."]
        if bad:
            lines += ["", "| Query | Local (level) | Full |", "|---|---|---|"]
            for r in bad:
                loc = f"{r['local_objective']:g} ({r['level']})" if r["local_feasible"] else "infeasible"
                full = f"{r['full_objective']:g}" if r["full_feasible"] else "infeasible"
                lines.append(f"| {qstr(r['query'])} | {loc} | {full} |")
        lines.append("")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results")
    args = ap.parse_args()
    out_dir = os.path.join(ROOT, args.out)
    res = json.load(open(os.path.join(out_dir, "task2_results.json")))
    meta, m = res["meta"], res["metrics"]
    cases = {c["id"]: c for c in json.load(open(os.path.join(ROOT, "cases", f"{meta['split']}_cases.json")))["cases"]}
    att_raw = json.load(open(os.path.join(out_dir, "raw", "attribution.json")))
    a, e, loc = m["attribution"], m["explanation"], m["localization"]
    L = ["# Task 2 results", "",
         f"Split `{meta['split']}`, run {meta['started']} to {meta['finished']} on {meta['cpu']} ({meta['machine']}), "
         f"Python {meta['python']}, Gurobi {meta['gurobi']}, LLM `{meta['llm_model']}` (alias; no fixed snapshot), "
         f"power: {meta['power']['source']}, low-power mode {meta['power']['lowpowermode']}. "
         f"LLM parts: {meta['runs']} independent runs (mean ± sample std); deterministic parts once; "
         f"{meta['repeats']} timing repeats per query and method. Protocol `protocol.json` sha256 "
         f"`{meta['protocol_sha256']}`. Schema violations in component outputs: {len(meta['schema_errors'])}.", "",
         "## 1. Decision attribution", "",
         f"- Inclusion rate (returned set contains every ground-truth element): {pct(a['inclusion_rate'])}",
         f"- Precision / recall, per-case mean: {a['macro']['precision']:.3f} / {a['macro']['recall']:.3f}",
         f"- Pooled precision / recall: {a['pooled']['all']['precision']:.3f} / {a['pooled']['all']['recall']:.3f} "
         f"({a['pooled']['all']['intersection']} of {a['pooled']['all']['returned']} returned, "
         f"{a['pooled']['all']['ground_truth']} in ground truth)",
         f"- Constraint part ({a['macro_constraints']['cases']} cases): pooled precision "
         f"{a['pooled']['constraints']['precision']:.3f}, recall {a['pooled']['constraints']['recall']:.3f}",
         f"- Variable part ({a['macro_variables']['cases']} cases): pooled precision "
         f"{a['pooled']['variables']['precision']:.3f}, recall {a['pooled']['variables']['recall']:.3f}",
         f"- LLM explanation passes the number/entity checks: {pct(e['pass_rate'])} "
         f"(first attempt {pct(e['first_attempt_pass_rate'])}; template fallbacks {e['template_fallbacks']})", "",
         "| Case | Decision | Conclusion (GT) | Returned set | Contains GT | P / R |", "|---|---|---|---|---|---|"]
    for r in a["per_case"]:
        rs = ", ".join(r["returned"]) if len(r["returned"]) <= 4 else f"{len(r['returned'])} edges"
        L.append(f"| {r['case']} | {r['decision']} | {r['conclusion']} ({r['gt_conclusion']}) | {rs} | "
                 f"{'yes' if r['contains_gt'] else 'no'} | {r['precision']:.2f} / {r['recall']:.2f} |")
    L += ["", "Example explanation (run 0, first case of each conclusion type):", ""]
    seen = set()
    for cid, v in att_raw.items():
        concl = v["output"]["conclusion"]
        if concl in seen:
            continue
        seen.add(concl)
        L += [f"> **{cid}, {v['output']['decision_text']}** ({v['explanations'][0]['source']}): "
              f"{v['explanations'][0]['text']}", ""]
    L += ["## 2. Counterfactual explanation", ""]
    L += cf_section("2.1 The 10 test-case queries", m["counterfactual_main"])
    if "counterfactual_supplementary" in m:
        L += cf_section("2.2 Supplementary: every MOVE and FIX_ARC query on the reference optimum",
                        m["counterfactual_supplementary"], per_query=False)
    L += ["## 3. Feedback localization", "",
          "| Metric | First pass | After the clarification answer |", "|---|---|---|",
          f"| Accuracy (majority target in GT list) | {pct(loc['accuracy'])} | {pct(loc['after_clarification']['accuracy'])} |",
          f"| Accuracy, predicted high | {pct(loc['accuracy_high'])} | {pct(loc['after_clarification']['accuracy_high'])} |",
          f"| Accuracy, predicted low | {pct(loc['accuracy_low'])} | {pct(loc['after_clarification']['accuracy_low'])} |",
          f"| Predicted high / low per run | {loc['n_high_per_run']} / {loc['n_low_per_run']} | "
          f"{loc['after_clarification']['n_high_per_run']} high |",
          f"| Clarifying-question rate | {pct(loc['clarification_rate'])} | {pct(loc['after_clarification']['clarification_rate'])} |",
          f"| Invalid samples | {pct(loc['invalid_output_rate'])} | {pct(loc['after_clarification']['invalid_output_rate'])} |",
          f"| Modification type correct | {pct(loc['modification_type_accuracy'])} | |", "",
          f"Low-confidence results that carried a critique: {loc['low_with_critique_total']} (must be 0).", "",
          "Expected vs predicted confidence (first pass, per run):", ""]
    for run, ct in enumerate(loc["confidence_crosstab_per_run"]):
        L.append(f"- run {run}: expected high → high {ct['expected_high']['predicted_high']}, low "
                 f"{ct['expected_high']['predicted_low']}; expected low → high {ct['expected_low']['predicted_high']}, "
                 f"low {ct['expected_low']['predicted_low']}")
    L += ["", "| Case | Clarity | GT targets | Run 0 / 1 / 2: confidence, majority target | After clarification |",
          "|---|---|---|---|---|"]
    for cid, c in cases.items():
        runs = [next(r for r in pr["rows"] if r["case"] == cid) for pr in loc["per_run"]]
        clar = [next(r for r in pr["rows"] if r["case"] == cid) for pr in loc["per_run_after_clarification"]]
        fmt = lambda rr: " / ".join(f"{r['predicted']}, {r['majority_target']}{'' if r['correct'] else ' ✗'}" for r in rr)  # noqa: E731
        L.append(f"| {cid} | {c['clarity']} | {', '.join(c['gt']['localization']['targets'])} | {fmt(runs)} | {fmt(clar)} |")
    L.append("")
    with open(os.path.join(out_dir, "task2_results.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    print("written", os.path.join(args.out, "task2_results.md"))


if __name__ == "__main__":
    main()
