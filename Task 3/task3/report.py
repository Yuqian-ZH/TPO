"""Stage 4: results/task3_results.{json,md} and figures from saved trials only (no network, no LLM, no solver
beyond re-evaluating saved solutions in recompute.py)."""
import argparse
import glob
import json
import os
import sys
from collections import Counter

sys.dont_write_bytecode = True

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import stats  # noqa: E402
from freeze_protocol import TEST_CASES  # noqa: E402
from recompute import load_trials, recompute  # noqa: E402
from run_experiment import load_cases, write_json  # noqa: E402
from tpo.task2_bridge import load_frozen_instance  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
ORDER = list(stats.MAIN) + ["S1", "S2"]
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
MAIN_C, SUPP_C = "#2a78d6", "#eb6834"
LABEL = {"A": "A attribution", "B": "B counterfactual probing", "C": "C feedback localization"}


def first_iteration(trials):
    return [{**t, "converged": bool(t["converged"] and t["converged_at"] == 1),
             "converged_at": 1 if t["converged"] and t["converged_at"] == 1 else None} for t in trials]


def localization_table(out_dir, cases):
    gt = {c["id"]: c["gt"]["localization"] for c in cases}
    rows = []
    for path in sorted(glob.glob(os.path.join(out_dir, "localization", "*.json"))):
        loc = json.load(open(path))
        g = gt[loc["case_id"]]
        first_t = (loc["initial"].get("critique") or {}).get("target")
        final_t = (loc["final"].get("critique") or {}).get("target")
        rows.append({"case": loc["case_id"], "run": loc["run"], "expected": g["confidence"],
                     "first": loc["initial"]["confidence"], "asked": loc["asked"],
                     "final": loc["final"]["confidence"],
                     "first_target_ok": first_t in g["targets"] if first_t else None,
                     "final_target_ok": final_t in g["targets"] if final_t else False})
    n = len(rows)
    return {"rows": rows, "n": n,
            "final_high_and_correct": sum(r["final"] == "high" and r["final_target_ok"] for r in rows),
            "final_high_but_wrong": sum(r["final"] == "high" and not r["final_target_ok"] for r in rows),
            "still_low_after_clarification": sum(r["final"] == "low" for r in rows),
            "asked": sum(r["asked"] for r in rows),
            "confidence_crosstab": dict(Counter(f"expected {r['expected']} / first {r['first']}" for r in rows))}


def llm_cost(out_dir):
    calls, ptok, ctok, times = 0, 0, 0, []
    for path in glob.glob(os.path.join(out_dir, "logs", "llm_*.jsonl")):
        for line in open(path):
            r = json.loads(line)
            calls += 1
            u = r.get("usage") or {}
            ptok += u.get("prompt_tokens") or 0
            ctok += u.get("completion_tokens") or 0
            times.append(r["time"])
    return {"requests": calls, "prompt_tokens": ptok, "completion_tokens": ctok,
            "first_request": min(times) if times else None, "last_request": max(times) if times else None}


def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def fig_convergence(res, path):
    fig, ax = plt.subplots(figsize=(9, 3.6), facecolor=SURFACE)
    _style(ax)
    for x, g in enumerate(ORDER):
        v = res["configs"].get(g)
        if not v:
            continue
        col = MAIN_C if g in stats.MAIN else SUPP_C
        runs = [100 * r for r in v["rate_per_run"].values()]
        ms = v["rate_mean_std_over_runs"]
        ax.scatter([x] * len(runs), runs, s=22, facecolors="none", edgecolors=col, linewidths=1.2, zorder=2)
        ax.errorbar(x, 100 * ms["mean"], yerr=100 * (ms["std"] or 0), fmt="o", color=col, ms=8, elinewidth=2,
                    capsize=0, zorder=3)
        ax.annotate(f"{100 * ms['mean']:.0f}", (x, 100 * ms["mean"]), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=8, color=INK2)
    ax.set_xticks(range(len(ORDER)), ORDER, fontsize=9, color=INK)
    ax.set_ylim(-5, 116)
    ax.set_yticks(range(0, 101, 20))
    ax.set_ylabel("Converged within 3 iterations (%)", color=INK2, fontsize=9)
    ax.axvline(7.5, color=GRID, linewidth=1)
    ax.text(3.5, 111, "2³ factorial (main)", ha="center", fontsize=9, color=MAIN_C)
    ax.text(8.5, 111, "supplementary", ha="center", fontsize=9, color=SUPP_C)
    ax.set_title("Convergence rate per configuration: mean ± std over 3 runs (filled), each run (hollow)",
                 fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)


def fig_effects(res, sec, path):
    fig, ax = plt.subplots(figsize=(7, 3.2), facecolor=SURFACE)
    _style(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ys = []
    for i, f in enumerate("ABC"):
        for off, (eff, col, name) in enumerate(((res["effects"], MAIN_C, "within 3 iterations"),
                                                 (sec, SUPP_C, "at iteration 1"))):
            e = eff[f"main_{f}"]
            y = i - 0.15 + 0.3 * off
            ax.plot(e["ci95"], [y, y], color=col, linewidth=2)
            ax.plot(e["estimate"], y, "o", color=col, ms=8, label=name if i == 0 else None)
            ax.annotate(f"{100 * e['estimate']:+.0f} pp", (e["ci95"][1], y), xytext=(6, 0),
                        textcoords="offset points", va="center", fontsize=8, color=INK2)
        ys.append(i)
    ax.axvline(0, color=INK2, linewidth=1)
    ax.set_yticks(ys, [LABEL[f] for f in "ABC"], fontsize=9, color=INK)
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{100 * v:+.0f}"))
    ax.set_xlabel("Main effect on convergence rate, with − without (pp), 95% case-clustered bootstrap CI",
                  color=INK2, fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=2, labelcolor=INK2)
    ax.set_title("Which mechanism moves convergence?", fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def fig_by_iteration(res, path):
    """Cumulative convergence after iteration 1, 2, 3 per configuration (pooled over 30 trials)."""
    cols = {1: "#2a78d6", 2: "#eb6834", 3: "#1baf7a"}
    fig, ax = plt.subplots(figsize=(9, 3.6), facecolor=SURFACE)
    _style(ax)
    for x, g in enumerate(ORDER):
        v = res["configs"].get(g)
        if not v:
            continue
        cum = [100 * c for c in v["cumulative_by_iteration"]]
        ax.plot([x - 0.18, x, x + 0.18], cum, color=GRID, linewidth=1.5, zorder=1)
        for t, (dx, c) in enumerate(zip((-0.18, 0, 0.18), cum), start=1):
            ax.plot(x + dx, c, "o", color=cols[t], ms=7, zorder=2, label=f"after iteration {t}" if x == 0 else None)
        ax.annotate(f"{cum[0]:.0f}", (x - 0.18, cum[0]), xytext=(0, -13), textcoords="offset points", ha="center",
                    fontsize=8, color=INK2)
    ax.set_xticks(range(len(ORDER)), ORDER, fontsize=9, color=INK)
    ax.set_ylim(60, 106)
    ax.set_ylabel("Cumulative converged (%)", color=INK2, fontsize=9)
    ax.axvline(7.5, color=GRID, linewidth=1)
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12), labelcolor=INK2)
    ax.set_title("How fast each configuration converges (30 trials each; y-axis starts at 60%)", fontsize=10,
                 color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def pct(v):
    return "n/a" if v is None else f"{100 * v:.1f}%"


def markdown(res, sec, loc, cost, proto, trials):
    L = ["# Task 3 results", ""]
    L.append(f"Protocol `protocol.json` frozen {proto['frozen_at']} (sha256 of test cases `{proto['test_cases']['sha256'][:12]}…`, "
             f"Task 2 protocol `{proto['task2_protocol_sha256'][:12]}…`). LLM `qwen3.8-max` (alias, no fixed snapshot), "
             f"requests {cost['first_request']} to {cost['last_request']}: {cost['requests']} requests, "
             f"{cost['prompt_tokens']:,} prompt + {cost['completion_tokens']:,} completion tokens. "
             f"{len(trials)} trials = 10 configurations × 3 runs × 10 test cases.")
    L += ["", "## 1. Convergence rate per configuration", "",
          "Converged = feasible and complaint-free (Task 2 checker) within 3 TPO iterations. Mean and sample std over 3 runs of the 10-case rate.", "",
          "| Config | A | B | C | Mean ± std | Runs | Pooled (95% Wilson) | Cum. at t=1/2/3 | All 3 runs | Low-conf. stops | LLM calls / trial | Tokens / trial |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for g in ORDER:
        v = res["configs"].get(g)
        if not v:
            continue
        flags = proto["configs"][g]
        ms = v["rate_mean_std_over_runs"]
        L.append(f"| {g} | {int(flags['A'])} | {int(flags['B'])}{' blind' if flags['blind'] else ''} | "
                 f"{int(flags['C'])}{' +clar. text' if flags['clar_text'] else ''} | "
                 f"{pct(ms['mean'])} ± {100 * (ms['std'] or 0):.1f} | "
                 f"{' / '.join(pct(r) for r in v['rate_per_run'].values())} | {pct(v['pooled_rate'])} "
                 f"[{pct(v['pooled_wilson95'][0])}, {pct(v['pooled_wilson95'][1])}] | "
                 f"{' / '.join(pct(r) for r in v['cumulative_by_iteration'])} | {v['cases_converged_all_runs']}/10 | "
                 f"{v['stopped_low_confidence']} | {v['llm_calls_mean']} | {v['tokens_mean']:,.0f} |")
    L += ["", "![Convergence per configuration](fig_convergence.png)", "", "![Convergence by iteration](fig_by_iteration.png)", ""]
    L += ["## 2. Mechanism effects", "",
          "Main effect = rate of the 4 factorial configurations with the mechanism minus the 4 without (120 vs 120 trials). "
          "Interaction = effect of the first factor with the second on, minus with it off. 95% CI: case-clustered bootstrap, 10,000 resamples, seed 42.", "",
          "| Effect | Within 3 iterations | 95% CI | At iteration 1 (secondary) | 95% CI |", "|---|---|---|---|---|"]
    for k in [f"main_{f}" for f in "ABC"] + ["interaction_AB", "interaction_AC", "interaction_BC"]:
        a, b = res["effects"][k], sec[k]
        L.append(f"| {k} | {100 * a['estimate']:+.1f} pp | [{100 * a['ci95'][0]:+.1f}, {100 * a['ci95'][1]:+.1f}] | "
                 f"{100 * b['estimate']:+.1f} pp | [{100 * b['ci95'][0]:+.1f}, {100 * b['ci95'][1]:+.1f}] |")
    L += ["", f"**Pre-registered rule (primary):** {res['verdict']['text']}  ",
          f"**Same rule on convergence at iteration 1 (secondary):** {stats.verdict_rule(sec)['text']}", "",
          "![Main effects](fig_effects.png)", "", "### Paired comparisons (exact McNemar over (case, run) pairs)", "",
          "| Slice | Comparison | Pairs | Only first converged | Only second converged | p |", "|---|---|---|---|---|---|"]
    for name, comps in res["paired"].items():
        for cmp_, r in comps.items():
            L.append(f"| {name} | {cmp_} | {r['pairs']} | {r['first_only']} | {r['second_only']} | {r['p_value']} |")
    L += ["", "## 3. Per case (converged runs out of 3)", "", "| Case | Clarity | Object | " + " | ".join(ORDER) + " |",
          "|---|---|---|" + "---|" * len(ORDER)]
    labels = res.get("by_clarity", {})
    cases = sorted({t["case_id"] for t in trials}, key=lambda c: int(c[1:]))
    for c in cases:
        clar = next(t for t in trials if t["case_id"] == c)
        row = [str(res["configs"][g]["per_case_converged_runs"].get(c, "-")) if g in res["configs"] else "-" for g in ORDER]
        L.append(f"| {c} | {CASE_LABELS[c]['clarity']} | {CASE_LABELS[c]['complaint_object']} | " + " | ".join(row) + " |")
    L += ["", "By clarity: " + "; ".join(f"{g}: {v}" for g, v in labels.items() if g in ("A0B0C0", "A1B1C1", "A0B0C1", "A1B1C0")), ""]
    L += ["## 4. Diagnostics", "",
          f"- Shared localization ({loc['n']} = 10 cases × 3 runs, Task 2's frozen localizer, run labels t3-1..3): "
          f"clarification asked {loc['asked']}×; final high-confidence and correct {loc['final_high_and_correct']}, "
          f"high-confidence but wrong target {loc['final_high_but_wrong']}, still low after clarification "
          f"{loc['still_low_after_clarification']}. Expected vs first-pass confidence: {loc['confidence_crosstab']}."]
    probed = [(it["candidates"][it["chosen_sample"]]["probe"], it["commit"]) for t in trials for it in t["iterations"]
              if it.get("probe_vs_commit")]
    exact = sum(abs(p["objective"] - c["objective"]) < 1e-6 for p, c in probed)
    gaps = sorted({p["distance_after"] - c["metrics"]["total_distance"] for p, c in probed
                   if abs(p["objective"] - c["objective"]) >= 1e-6})
    L.append(f"- Probe (Task 3's v2 local counterfactual) vs commit (full re-solve) on the {len(probed)} committed, probed "
             f"candidates: feasibility and objective within 1% agree in all; objective exactly equal in {exact}; the other "
             f"{len(probed) - exact} predict a plan longer by {gaps} km (the local search stopped at L0/L1 once the soft "
             f"constraint was met), so their change sets differ.")
    for g in ORDER:
        v = res["configs"].get(g)
        if v and v.get("probe_commit_agreement"):
            L.append(f"- {g}: probe vs commit agreement {v['probe_commit_agreement']}")
    for g in ORDER:
        v = res["configs"].get(g)
        if v:
            L.append(f"- {g}: invalid candidates {pct(v['invalid_candidate_rate'])}, rejected iterations "
                     f"{v['rejected_iterations']}, no-plan iterations {v['no_plan_iterations']}, illegal data modifications "
                     f"{v['illegal_data_mods']}, selector failures {v['selector_failures']}, mean iterations when converged "
                     f"{v['mean_iterations_when_converged']}, excess distance vs Task 2 reference fix "
                     f"{v['excess_distance_mean_when_converged']}, converged with ties not all resolving "
                     f"{v['converged_with_ties_not_all_resolving']}, converged trials whose checker names a vehicle (verdict "
                     f"would flip if the labels were swapped) {v['converged_label_sensitive']}")
    return "\n".join(L) + "\n"


CASE_LABELS = {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "formal"))
    ap.add_argument("--cases", default=TEST_CASES)
    args = ap.parse_args()
    cases = load_cases(args.cases)
    CASE_LABELS.update({c["id"]: {"clarity": c["clarity"], "complaint_object": c["complaint_object"]} for c in cases})
    base = load_frozen_instance()
    res = recompute(args.out, cases, base)
    trials = load_trials(args.out)
    sec = stats.cluster_bootstrap(first_iteration([t for t in trials if t["config"] in stats.MAIN]))
    loc = localization_table(args.out, cases)
    cost = llm_cost(args.out)
    proto = json.load(open(os.path.join(ROOT, "protocol.json")))
    write_json(os.path.join(args.out, "task3_results.json"),
               {"recompute": res, "first_iteration_effects": sec, "localization": loc, "cost": cost})
    fig_convergence(res, os.path.join(args.out, "fig_convergence.png"))
    fig_effects(res, sec, os.path.join(args.out, "fig_effects.png"))
    fig_by_iteration(res, os.path.join(args.out, "fig_by_iteration.png"))
    with open(os.path.join(args.out, "task3_results.md"), "w") as f:
        f.write(markdown(res, sec, loc, cost, proto, trials))
    print(res["verdict"]["text"])
    print("secondary:", stats.verdict_rule(sec)["text"])


if __name__ == "__main__":
    main()
