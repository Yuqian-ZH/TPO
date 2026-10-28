"""Metrics of plan 5.3 and the decision rule of 5.4, computed from saved trial records only."""
import math
import random
from statistics import mean, stdev

FACTORS = ("A", "B", "C")
MAIN = tuple(f"A{a}B{b}C{c}" for a in (0, 1) for b in (0, 1) for c in (0, 1))
Z95 = 1.959963984540054


def level(config, factor):
    return int(config[config.index(factor) + 1])


def wilson(k, n, z=Z95):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def mean_std(values):
    return {"mean": round(mean(values), 4) if values else None,
            "std": round(stdev(values), 4) if len(values) > 1 else None}


def mcnemar_exact(pairs):
    """Two-sided exact McNemar on paired booleans (a, b)."""
    b10 = sum(1 for a, b in pairs if a and not b)
    b01 = sum(1 for a, b in pairs if b and not a)
    n = b10 + b01
    p = 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, k) for k in range(min(b10, b01) + 1)) / 2 ** n)
    return {"first_only": b10, "second_only": b01, "p_value": round(p, 4)}


# ---------- effects on per-case counts (fast cluster bootstrap) ----------

def case_counts(trials):
    """case_id -> config -> [converged, total]."""
    out = {}
    for tr in trials:
        c = out.setdefault(tr["case_id"], {}).setdefault(tr["config"], [0, 0])
        c[0] += bool(tr["converged"])
        c[1] += 1
    return out


def _rate(counts, cases, configs):
    k = sum(counts[c].get(g, [0, 0])[0] for c in cases for g in configs)
    n = sum(counts[c].get(g, [0, 0])[1] for c in cases for g in configs)
    return k / n if n else float("nan")


def effects(counts, cases):
    """Main effects (rate with − rate without, over the 8 main configs) and difference-of-differences
    interactions (effect of f1 with f2 on − effect of f1 with f2 off)."""
    out = {}
    for f in FACTORS:
        on = [g for g in MAIN if level(g, f) == 1]
        off = [g for g in MAIN if level(g, f) == 0]
        out[f"main_{f}"] = _rate(counts, cases, on) - _rate(counts, cases, off)
    for i, f1 in enumerate(FACTORS):
        for f2 in FACTORS[i + 1:]:
            def eff(v):
                on = [g for g in MAIN if level(g, f1) == 1 and level(g, f2) == v]
                off = [g for g in MAIN if level(g, f1) == 0 and level(g, f2) == v]
                return _rate(counts, cases, on) - _rate(counts, cases, off)
            out[f"interaction_{f1}{f2}"] = eff(1) - eff(0)
    mains = sorted(FACTORS, key=lambda f: -out[f"main_{f}"])
    out["top_minus_second"] = out[f"main_{mains[0]}"] - out[f"main_{mains[1]}"]
    return out


def cluster_bootstrap(trials, B=10000, seed=42):
    counts = case_counts(trials)
    cases = sorted(counts)
    point = effects(counts, cases)
    top = max(FACTORS, key=lambda f: point[f"main_{f}"])
    second = sorted(FACTORS, key=lambda f: -point[f"main_{f}"])[1]
    rng = random.Random(seed)
    draws = {k: [] for k in point}
    draws["top_minus_second"] = []
    for _ in range(B):
        sample = [rng.choice(cases) for _ in cases]
        e = effects(counts, sample)
        for k in point:
            if k != "top_minus_second":
                draws[k].append(e[k])
        draws["top_minus_second"].append(e[f"main_{top}"] - e[f"main_{second}"])   # fixed pair from the point estimate

    def ci(v):
        v = sorted(x for x in v if not math.isnan(x))
        return [round(v[int(0.025 * (len(v) - 1))], 4), round(v[int(math.ceil(0.975 * (len(v) - 1)))], 4)]
    res = {k: {"estimate": round(point[k], 4), "ci95": ci(draws[k])} for k in point}
    res["top"], res["second"] = top, second
    return res


def verdict_rule(boot):
    """Plan 5.4."""
    top = boot["top"]
    main_ci = boot[f"main_{top}"]["ci95"]
    gap_ci = boot["top_minus_second"]["ci95"]
    excl0 = main_ci[0] > 0          # a helpful mechanism: the whole interval above 0
    gap_excl0 = gap_ci[0] > 0
    if excl0 and gap_excl0:
        return {"finding": "clear", "mechanism": top,
                "text": f"{top} contributes most: its main effect excludes 0 and exceeds the runner-up's."}
    if excl0:
        return {"finding": "largest_not_separable", "mechanism": top,
                "text": f"{top} has the largest main effect (excludes 0) but cannot be separated from {boot['second']}."}
    return {"finding": "undetermined", "mechanism": None,
            "text": "At 10 cases and 3 runs per configuration, no mechanism can be singled out."}


# ---------- per-configuration tables ----------

def llm_calls(tr):
    calls, tokens = 0, 0
    for it in tr["iterations"]:
        reqs = [c["llm"] for c in it["candidates"]]
        if it.get("selection") and it["selection"].get("called"):
            reqs.append(it["selection"]["llm"])
        for r in reqs:
            calls += 1
            u = r.get("usage") or {}
            tokens += (u.get("prompt_tokens") or 0) + (u.get("completion_tokens") or 0)
    return calls, tokens


def config_table(trials, config, max_iters=3):
    ts = [t for t in trials if t["config"] == config]
    runs = sorted({t["run"] for t in ts})
    per_run = {r: sum(t["converged"] for t in ts if t["run"] == r) / max(1, sum(1 for t in ts if t["run"] == r))
               for r in runs}
    k, n = sum(t["converged"] for t in ts), len(ts)
    its = [it for t in ts for it in t["iterations"]]
    cands = [c for it in its for c in it["candidates"]]
    probes = [it["probe_vs_commit"] for it in its if it.get("probe_vs_commit")]
    ties = [it["tie"] for it in its if it.get("tie") and it["verdict"]["resolved"]]
    calls_tokens = [llm_calls(t) for t in ts]
    by_case = {}
    for t in ts:
        by_case.setdefault(t["case_id"], []).append(t["converged"])
    return {
        "trials": n, "converged": k,
        "rate_per_run": {str(r): round(v, 4) for r, v in per_run.items()},
        "rate_mean_std_over_runs": mean_std(list(per_run.values())),
        "pooled_rate": round(k / n, 4) if n else None, "pooled_wilson95": wilson(k, n),
        "cumulative_by_iteration": [round(sum(1 for t in ts if t["converged"] and t["converged_at"] <= i) / n, 4)
                                    if n else None for i in range(1, max_iters + 1)],
        "mean_iterations_when_converged": round(mean(t["converged_at"] for t in ts if t["converged"]), 4) if k else None,
        "cases_converged_all_runs": sum(1 for v in by_case.values() if all(v) and len(v) == len(runs)),
        "stopped_low_confidence": sum(1 for t in ts if t["outcome"] == "stopped_low_confidence"),
        "invalid_candidate_rate": round(sum(not c["valid"] for c in cands) / len(cands), 4) if cands else None,
        "rejected_iterations": sum(1 for it in its if it["status"] == "rejected"),
        "no_plan_iterations": sum(1 for it in its if it["status"] == "no_plan"),
        "illegal_data_mods": sum(len(it.get("illegal_data_mods") or []) for it in its),
        "selector_failures": sum(1 for it in its if (it.get("selection") or {}).get("called")
                                 and not it["selection"]["ok"]),
        "probe_commit_agreement": ({k2: round(sum(bool(p[k2]) for p in probes) / len(probes), 4)
                                    for k2 in ("feasible", "objective_1pct", "change_set")} if probes else None),
        "converged_with_ties_not_all_resolving": sum(1 for d in ties if d.get("n_optimal_resolving", 0)
                                                     < d.get("n_optimal", 0)),
        "converged_label_sensitive": sum(1 for t in ts for it in t["iterations"]
                                         if it["verdict"]["resolved"] and it.get("label_swap_resolved") is False),
        "excess_distance_mean_when_converged": (round(mean(t["excess_distance"] for t in ts if t["converged"]), 2)
                                                if k and all("excess_distance" in t for t in ts if t["converged"])
                                                else None),
        "llm_calls_mean": round(mean(c for c, _ in calls_tokens), 2) if ts else None,
        "tokens_mean": round(mean(tok for _, tok in calls_tokens), 1) if ts else None,
        "per_case_converged_runs": {c: sum(v) for c, v in sorted(by_case.items())},
    }


def paired(trials, cfg_a, cfg_b):
    a = {(t["case_id"], t["run"]): t["converged"] for t in trials if t["config"] == cfg_a}
    b = {(t["case_id"], t["run"]): t["converged"] for t in trials if t["config"] == cfg_b}
    keys = sorted(set(a) & set(b))
    return {"pairs": len(keys), **mcnemar_exact([(a[k], b[k]) for k in keys])}


SLICES = {"full_minus": [("A1B1C1", "A0B1C1"), ("A1B1C1", "A1B0C1"), ("A1B1C1", "A1B1C0")],
          "bare_plus": [("A1B0C0", "A0B0C0"), ("A0B1C0", "A0B0C0"), ("A0B0C1", "A0B0C0")],
          "supplementary": [("A1B1C1", "S1"), ("S1", "A1B0C1"), ("A1B1C1", "S2"), ("S2", "A1B1C0")]}


def by_group(trials, labels):
    """Descriptive convergence by a case label (clarity, complaint_object); no tests."""
    out = {}
    for t in trials:
        g = out.setdefault(t["config"], {}).setdefault(labels.get(t["case_id"], "unknown"), [0, 0])
        g[0] += bool(t["converged"])
        g[1] += 1
    return {cfg: {lab: f"{k}/{n}" for lab, (k, n) in sorted(v.items())} for cfg, v in sorted(out.items())}


def summarize(trials, B=10000, seed=42, case_labels=None):
    configs = sorted({t["config"] for t in trials})
    out = {"configs": {g: config_table(trials, g) for g in configs}}
    for name, labels in (case_labels or {}).items():
        out[f"by_{name}"] = by_group(trials, labels)
    if all(g in configs for g in MAIN):
        boot = cluster_bootstrap([t for t in trials if t["config"] in MAIN], B=B, seed=seed)
        out["effects"] = boot
        out["verdict"] = verdict_rule(boot)
    out["paired"] = {name: {f"{a} vs {b}": paired(trials, a, b) for a, b in pairs if a in configs and b in configs}
                     for name, pairs in SLICES.items()}
    return out
