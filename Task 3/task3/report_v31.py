"""task3_v31 report from saved trials only (no network, no LLM): <out>/task3_v31_results.{json,md}.
Analyses as pre-registered in DESIGN_V31.md section 4; the main and stratum analyses are report_v3's.

    python report_v31.py --out results/formal_v31 --cases test
    python report_v31.py --out results/pilot_v31 --cases dev        # the pilot (descriptive only)"""
import argparse
import math
import os
import random
import sys
from statistics import mean

sys.dont_write_bytecode = True

import report_v3  # noqa: E402
import stats  # noqa: E402
from run_experiment import load_cases, write_json  # noqa: E402
from run_experiment_v3 import CASES  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
V3_OUT = os.path.join(ROOT, "results", "formal_v3")
PAIRS = {
    "probe_vs_blind": [("A0B1C0", "S1a"), ("A1B1C1", "S1b")],
    "blind_vs_single": [("S1a", "A0B0C0"), ("S1b", "A1B0C1")],
    "localization_vs_answer_text": [("A0B0C1", "S2a")],
    "answer_before_vs_after_first_failure": [("S2a", "A0B0C0")],
}


def _ci(draws):
    v = sorted(draws)
    return [round(v[int(0.025 * (len(v) - 1))], 4), round(v[int(math.ceil(0.975 * (len(v) - 1)))], 4)]


def paired_difference(trials, pairs, cases=None, first=False, B=10000, seed=42):
    """Rate(first config) - rate(second config) over (case, run) pairs pooled across `pairs`; case-clustered
    bootstrap interval and exact McNemar."""
    by = {(t["config"], t["case_id"], t["run"]): t for t in trials}

    def ok(t):
        return bool(t["converged"] and (not first or t["converged_at"] == 1))
    rows = {}
    for a, b in pairs:
        for (g, cid, run), t in by.items():
            if g == a and (b, cid, run) in by and (cases is None or cid in cases):
                rows.setdefault(cid, []).append((ok(t), ok(by[(b, cid, run)])))
    if not rows:
        return None
    flat = [p for v in rows.values() for p in v]
    est = mean(x for x, _ in flat) - mean(y for _, y in flat)
    rng, ids, draws = random.Random(seed), sorted(rows), []
    for _ in range(B):
        sample = [p for cid in (rng.choice(ids) for _ in ids) for p in rows[cid]]
        draws.append(mean(x for x, _ in sample) - mean(y for _, y in sample))
    return {"pairs": len(flat), "rate_first": round(mean(x for x, _ in flat), 4),
            "rate_second": round(mean(y for _, y in flat), 4), "estimate": round(est, 4), "ci95": _ci(draws),
            **stats.mcnemar_exact(flat)}


def b_source_verdict(probe, blind):
    """DESIGN_V31.md section 4, question 2: pooled, within 3 iterations, all cases."""
    if probe["ci95"][0] > 0:
        return "B's effect comes at least partly from seeing the predicted consequences (probe vs blind above 0)"
    if blind["ci95"][0] > 0:
        return "B's effect comes mainly from generating more candidates (blind vs single above 0, probe vs blind not)"
    return "cannot be separated (both intervals include 0)"


def a_verdict(side_a):
    lo, hi = side_a["ci95"]
    if hi < 0:
        return "A is still harmful in the side stratum: its harm does not come only from the hidden session modifications"
    if lo > 0:
        return "A helps in the side stratum"
    return "no harm from A detectable in the side stratum (interval includes 0)"


def repeats_session(trials, cases):
    """Share of valid proposals on cases with session modifications that write one of them again, by A."""
    out = {}
    for t in trials:
        sess = cases[t["case_id"]].get("model_modifications") or []
        if not sess or t["config"] not in stats.MAIN:
            continue
        keys = {(m["op"], m.get("target") or m.get("field"), m.get("sense")) for m in sess}
        a = f"A{stats.level(t['config'], 'A')}"
        for it in t["iterations"]:
            for c in it["candidates"]:
                if c["valid"]:
                    hit = any((m["op"], m.get("target") or m.get("field"), m.get("sense")) in keys
                              for m in c["modifications"])
                    k = out.setdefault(t["case_id"], {}).setdefault(a, [0, 0])
                    k[0] += hit
                    k[1] += 1
    return {cid: {a: f"{k}/{n} ({100 * k / n:.0f}%)" for a, (k, n) in sorted(v.items())}
            for cid, v in sorted(out.items(), key=lambda kv: int(kv[0][1:]))}


def a_by_case(trials, strata):
    out = {}
    for t in trials:
        if t["config"] in stats.MAIN and strata[t["case_id"]] == "side":
            k = out.setdefault(t["case_id"], {}).setdefault(f"A{stats.level(t['config'], 'A')}", [0, 0])
            k[0] += bool(t["converged"])
            k[1] += 1
    return {cid: {a: f"{k}/{n}" for a, (k, n) in sorted(v.items())}
            for cid, v in sorted(out.items(), key=lambda kv: int(kv[0][1:]))}


def per_config_cases(trials, keep):
    out = {}
    for t in trials:
        if t["config"] in stats.MAIN and t["case_id"] in keep:
            k = out.setdefault(t["config"], [0, 0])
            k[0] += bool(t["converged"])
            k[1] += 1
    return {g: f"{k}/{n}" for g, (k, n) in sorted(out.items())}


def build(out, split, B=10000):
    res = report_v3.build(out, split, B)
    res["protocol"] = "task3_v31"
    cases = {c["id"]: c for c in load_cases(CASES[split])}
    strata = {cid: c["stratum"] for cid, c in cases.items()}
    trials = report_v3.load_trials(out)
    side = {cid for cid, s in strata.items() if s == "side"}
    amb = {cid for cid, s in strata.items() if s == "ambiguity"}
    sup = {}
    for name, pairs in PAIRS.items():
        present = [(a, b) for a, b in pairs if any(t["config"] == a for t in trials)
                   and any(t["config"] == b for t in trials)]
        if not present:
            continue
        sup[name] = {}
        for label, sel in (("pooled", present), *((f"{a} vs {b}", [(a, b)]) for a, b in present)):
            sup[name][label] = {f"{scope}{'_t1' if first else ''}": paired_difference(trials, sel, keep, first, B)
                                for scope, keep in (("all", None), ("side", side), ("ambiguity", amb))
                                for first in (False, True)}
    res["supplementary"] = sup
    if "probe_vs_blind" in sup and "blind_vs_single" in sup:
        res["b_source_verdict"] = b_source_verdict(sup["probe_vs_blind"]["pooled"]["all"],
                                                   sup["blind_vs_single"]["pooled"]["all"])
    if "by_stratum" in res and "side" in res["by_stratum"]:
        res["a_verdict"] = a_verdict(res["by_stratum"]["side"]["A"])
    res["a_by_side_case"] = a_by_case(trials, strata)
    res["session_repeats"] = repeats_session(trials, cases)
    if split == "test" and os.path.isdir(V3_OUT):
        v3 = report_v3.load_trials(V3_OUT)
        res["v3_side_by_side"] = {
            "a_by_side_case": a_by_case(v3, strata), "session_repeats": repeats_session(v3, cases),
            "U1_U8_by_config": {"v3": per_config_cases(v3, set(cases) - {"U9", "U10"}),
                                "v31": per_config_cases(trials, set(cases) - {"U9", "U10"})},
            "U9_U10_by_config": {"v3": per_config_cases(v3, {"U9", "U10"}),
                                 "v31": per_config_cases(trials, {"U9", "U10"})}}
    return res


def _fmt(e):
    if not e:
        return "-"
    return (f"{100 * e['rate_first']:.0f}% vs {100 * e['rate_second']:.0f}% ({e['pairs']} pairs): "
            f"{100 * e['estimate']:+.1f} pp [{100 * e['ci95'][0]:+.1f}, {100 * e['ci95'][1]:+.1f}], "
            f"{e['first_only']} vs {e['second_only']}, p = {e['p_value']}")


def markdown(res):
    lines = report_v3.markdown(res).replace("protocol task3_v3", "protocol task3_v31", 1).replace(
        "Design: DESIGN_V3.md; analyses as pre-registered there.",
        "Design: DESIGN_V31.md (main and stratum analyses as DESIGN_V3.md section 5).", 1).rstrip("\n").split("\n")
    lines += ["", "## 6. Pre-registered v3.1 questions (DESIGN_V31.md section 4)", ""]
    if "a_verdict" in res:
        lines += [f"**Question 1 (A):** {res['a_verdict']}.", ""]
    lines += ["A by side case (converged / trials over the 8 main configurations):", "",
              "| Case | A0 | A1 |" + (" v3 A0 | v3 A1 |" if "v3_side_by_side" in res else ""),
              "|---|---|---|" + ("---|---|" if "v3_side_by_side" in res else "")]
    v3a = (res.get("v3_side_by_side") or {}).get("a_by_side_case", {})
    for cid, v in res["a_by_side_case"].items():
        row = f"| {cid} | {v.get('A0')} | {v.get('A1')} |"
        if v3a:
            row += f" {v3a.get(cid, {}).get('A0')} | {v3a.get(cid, {}).get('A1')} |"
        lines.append(row)
    lines += ["", "Valid proposals that write a session modification again (cases with session modifications): "
              + "; ".join(f"{cid} {v}" for cid, v in res["session_repeats"].items())]
    if v3a:
        lines.append("v3 for comparison: " + "; ".join(f"{cid} {v}" for cid, v in
                                                        res["v3_side_by_side"]["session_repeats"].items()))
    if "b_source_verdict" in res:
        lines += ["", f"**Question 2 (where B's effect comes from):** {res['b_source_verdict']}."]
    names = {"probe_vs_blind": "Probe vs blind", "blind_vs_single": "Blind vs single candidate",
             "localization_vs_answer_text": "Structured localization vs answer as text (question 3)",
             "answer_before_vs_after_first_failure": "Answer before iteration 1 vs after the first failure (question 3)"}
    for name, comps in res["supplementary"].items():
        lines += ["", f"### {names[name]}", "",
                  "| Pairs | Scope | Within 3 iterations | At iteration 1 |", "|---|---|---|---|"]
        for label, v in comps.items():
            for scope in ("all", "side", "ambiguity"):
                lines.append(f"| {label} | {scope} | {_fmt(v[scope])} | {_fmt(v[scope + '_t1'])} |")
    if "v3_side_by_side" in res:
        s = res["v3_side_by_side"]
        lines += ["", "## 7. Beside task3_v3 (not pooled, not tested)", "",
                  "| Config | U1-U8 v3 (runs 1-5) | U1-U8 v3.1 (runs 6-10) | U9-U10 v3 | U9-U10 v3.1 |",
                  "|---|---|---|---|---|"]
        for g in stats.MAIN:
            lines.append(f"| {g} | {s['U1_U8_by_config']['v3'].get(g)} | {s['U1_U8_by_config']['v31'].get(g)} | "
                         f"{s['U9_U10_by_config']['v3'].get(g)} | {s['U9_U10_by_config']['v31'].get(g)} |")
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
    write_json(os.path.join(out, "task3_v31_results.json"), res)
    with open(os.path.join(out, "task3_v31_results.md"), "w") as f:
        f.write(markdown(res))
    print(f"wrote {os.path.relpath(out, ROOT)}/task3_v31_results.{{json,md}}")


if __name__ == "__main__":
    main()
