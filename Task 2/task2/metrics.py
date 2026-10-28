"""Metric definitions (section 7.2). Pure functions over saved artifacts: no solver, no LLM, no network.
Shared by evaluate.py (first computation) and recompute.py (re-computation from results/raw)."""
import math
import statistics

OBJ_TOL = 0.01  # 1% relative tolerance for objective agreement


def change_key(cs):
    return (tuple(cs["moved"]), tuple(map(tuple, cs["added_edges"])), tuple(map(tuple, cs["removed_edges"])))


def summary(xs):
    xs = sorted(xs)
    if not xs:
        return None
    p95 = xs[max(0, math.ceil(0.95 * len(xs)) - 1)]  # nearest-rank
    return {"n": len(xs), "median": statistics.median(xs), "mean": statistics.fmean(xs), "p95": p95,
            "min": xs[0], "max": xs[-1]}


def mean_std(xs):
    return {"mean": statistics.fmean(xs), "std": statistics.stdev(xs) if len(xs) > 1 else 0.0, "runs": xs}


def rate(num, den):
    return {"rate": num / den if den else None, "num": num, "den": den}


# ---------------- attribution ----------------

def _prf(returned, gt):
    inter = len(returned & gt)
    p = inter / len(returned) if returned else (1.0 if not gt else 0.0)
    r = inter / len(gt) if gt else 1.0
    return p, r, inter


def attribution_metrics(cases, raw):
    rows, pooled = [], {"all": [0, 0, 0], "constraints": [0, 0, 0], "variables": [0, 0, 0]}
    for case in cases:
        out = raw[case["id"]]["output"]
        ret_c, ret_v = set(out["attribution_set"]["constraints"]), set(out["attribution_set"]["variables"])
        returned = ret_c | ret_v
        best = None
        for g in case["gt"]["attribution"]["acceptable_sets"]:
            g = set(g)
            p, r, inter = _prf(returned, g)
            f = 2 * p * r / (p + r) if p + r else 0.0
            if best is None or f > best[0]:
                best = (f, g, p, r)
        _, g, p, r = best
        g_c = {x for x in g if not x.startswith("e[")}
        g_v = g - g_c
        for part, rs, gs in (("all", returned, g), ("constraints", ret_c, g_c), ("variables", ret_v, g_v)):
            pooled[part][0] += len(rs & gs)
            pooled[part][1] += len(rs)
            pooled[part][2] += len(gs)
        rows.append({"case": case["id"], "decision": out["decision_text"], "conclusion": out["conclusion"],
                     "gt_conclusion": case["gt"]["attribution"]["conclusion"], "returned": sorted(returned),
                     "gt": sorted(g), "contains_gt": g <= returned, "precision": p, "recall": r,
                     "part": "constraints" if g_c else "variables"})
    res = {"per_case": rows, "inclusion_rate": rate(sum(r["contains_gt"] for r in rows), len(rows)),
           "macro": {"precision": statistics.fmean(r["precision"] for r in rows),
                     "recall": statistics.fmean(r["recall"] for r in rows)}}
    for part in ("constraints", "variables"):
        sub = [r for r in rows if r["part"] == part]
        res[f"macro_{part}"] = {"cases": len(sub),
                                "precision": statistics.fmean(r["precision"] for r in sub) if sub else None,
                                "recall": statistics.fmean(r["recall"] for r in sub) if sub else None}
    res["pooled"] = {part: {"precision": v[0] / v[1] if v[1] else None, "recall": v[0] / v[2] if v[2] else None,
                            "intersection": v[0], "returned": v[1], "ground_truth": v[2]}
                     for part, v in pooled.items()}
    return res


def explanation_metrics(cases, raw, runs):
    per_run, first = [], []
    for run in range(runs):
        exps = [raw[c["id"]]["explanations"][run] for c in cases]
        per_run.append(sum(e["valid"] for e in exps) / len(exps))
        first.append(sum(e["attempts"][0]["check"].get("ok", False) for e in exps) / len(exps))
    return {"pass_rate": mean_std(per_run), "first_attempt_pass_rate": mean_std(first),
            "template_fallbacks": sum(not raw[c["id"]]["explanations"][r]["valid"]
                                      for c in cases for r in range(runs))}


# ---------------- counterfactual ----------------

def _agree(a, b):
    """Feasibility / objective (1%) / change-set agreement between two outputs."""
    feas = a["feasible"] == b["feasible"]
    both = a["feasible"] and b["feasible"]
    obj = both and abs(a["objective"] - b["objective"]) <= OBJ_TOL * max(1.0, abs(b["objective"]))
    cs = both and change_key(a["change_set"]) == change_key(b["change_set"])
    return feas, both, obj, cs


def _against_gt(out, gt):
    feas = out["feasible"] == gt["feasible"]
    both = out["feasible"] and gt["feasible"]
    obj = both and abs(out["objective"] - gt["objective"]) <= OBJ_TOL * max(1.0, abs(gt["objective"]))
    cs = both and change_key(out["change_set"]) in [change_key(c) for c in gt["acceptable_change_sets"]]
    return feas, both, obj, cs


def counterfactual_metrics(entries):
    """entries: [{"id", "local", "full", "local_latency": [...], "full_latency": [...], "gt": optional}]"""
    n = len(entries)
    f = b = o = c = 0
    rows = []
    for e in entries:
        feas, both, obj, cs = _agree(e["local"], e["full"])
        f, b, o, c = f + feas, b + both, o + obj, c + cs
        rows.append({"id": e["id"], "query": e["local"]["query"], "local_feasible": e["local"]["feasible"],
                     "full_feasible": e["full"]["feasible"], "local_objective": e["local"].get("objective"),
                     "full_objective": e["full"].get("objective"), "level": e["local"].get("level"),
                     "feasibility_agree": feas, "objective_agree": obj, "change_set_agree": cs,
                     "local_median_ms": 1000 * statistics.median(x["with_model_setup_s"] for x in e["local_latency"]),
                     "full_median_ms": 1000 * statistics.median(x["with_model_setup_s"] for x in e["full_latency"])})
    res = {"queries": n, "local_vs_full": {"feasibility": rate(f, n), "objective_1pct": rate(o, b),
                                           "change_set": rate(c, b), "both_feasible": b},
           "levels": {lv: sum(1 for e in entries if e["local"].get("level") == lv) for lv in ("L0", "L1", "L2")},
           "local_infeasible": sum(1 for e in entries if not e["local"]["feasible"]),
           "local_infeasible_before_L2": sum(1 for e in entries if not e["local"]["feasible"]
                                             and len(e["local"].get("levels_tried", [])) < 3),
           "per_query": rows}
    for method in ("local", "full"):
        lat = [x for e in entries for x in e[f"{method}_latency"]]
        res[f"latency_{method}_ms"] = {
            "with_model_setup": summary([1000 * x["with_model_setup_s"] for x in lat]),
            "solve_only": summary([1000 * x["solve_only_s"] for x in lat])}
    if all("gt" in e for e in entries):
        for method in ("local", "full"):
            vals = [_against_gt(e[method], e["gt"]) for e in entries]
            both = sum(v[1] for v in vals)
            res[f"{method}_vs_exhaustive"] = {"feasibility": rate(sum(v[0] for v in vals), n),
                                              "objective_1pct": rate(sum(v[2] for v in vals), both),
                                              "change_set": rate(sum(v[3] for v in vals), both)}
    return res


# ---------------- localization ----------------

def _loc_run(cases, outs, key):
    rows = []
    for case in cases:
        out = outs[case["id"]][key]
        d = out["diagnostics"]
        gt = case["gt"]["localization"]
        rows.append({"case": case["id"], "expected": gt["confidence"], "predicted": out["confidence"],
                     "majority_target": d["majority_target"], "correct": d["majority_target"] in gt["targets"],
                     "type_correct": d["majority_modification_type"] in gt["modification_types"],
                     "invalid_samples": d["invalid_samples"], "critique_present": out["critique"] is not None})
    hi = [r for r in rows if r["predicted"] == "high"]
    lo = [r for r in rows if r["predicted"] == "low"]
    cross = {f"expected_{e}": {f"predicted_{p}": sum(1 for r in rows if r["expected"] == e and r["predicted"] == p)
                               for p in ("high", "low")} for e in ("high", "low")}
    return {"rows": rows, "accuracy": sum(r["correct"] for r in rows) / len(rows),
            "accuracy_high": (sum(r["correct"] for r in hi) / len(hi)) if hi else None, "n_high": len(hi),
            "accuracy_low": (sum(r["correct"] for r in lo) / len(lo)) if lo else None, "n_low": len(lo),
            "clarification_rate": len(lo) / len(rows),
            "invalid_output_rate": sum(r["invalid_samples"] for r in rows) / (5 * len(rows)),
            "modification_type_accuracy": sum(r["type_correct"] for r in rows) / len(rows),
            "low_with_critique": sum(1 for r in lo if r["critique_present"]), "confidence_crosstab": cross}


def localization_metrics(cases, raw, runs):
    per_run = [_loc_run(cases, raw[run], "initial") for run in range(runs)]
    clar = [_loc_run(cases, raw[run], "clarified") for run in range(runs)]

    def agg(rs, k):
        vals = [r[k] for r in rs if r[k] is not None]
        return mean_std(vals) if vals else None
    out = {k: agg(per_run, k) for k in ("accuracy", "accuracy_high", "accuracy_low", "clarification_rate",
                                         "invalid_output_rate", "modification_type_accuracy")}
    out["n_high_per_run"] = [r["n_high"] for r in per_run]
    out["n_low_per_run"] = [r["n_low"] for r in per_run]
    out["low_with_critique_total"] = sum(r["low_with_critique"] for r in per_run + clar)
    out["confidence_crosstab_per_run"] = [r["confidence_crosstab"] for r in per_run]
    out["after_clarification"] = {k: agg(clar, k) for k in ("accuracy", "accuracy_high", "accuracy_low",
                                                            "clarification_rate", "invalid_output_rate")}
    out["after_clarification"]["n_high_per_run"] = [r["n_high"] for r in clar]
    out["per_run"] = per_run
    out["per_run_after_clarification"] = clar
    return out


def compute_all(cases, raw, runs):
    res = {"attribution": attribution_metrics(cases, raw["attribution"]),
           "explanation": explanation_metrics(cases, raw["attribution"], runs),
           "counterfactual_main": counterfactual_metrics(raw["counterfactual_main"]),
           "localization": localization_metrics(cases, raw["localization"], runs)}
    if raw.get("counterfactual_supplementary"):
        res["counterfactual_supplementary"] = counterfactual_metrics(raw["counterfactual_supplementary"])
    return res
