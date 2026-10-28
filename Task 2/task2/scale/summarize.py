"""Summarize the stage-7 run: scale/results/scale_summary.json, scale_summary.md and scale/latency_curve.png.
python -m scale.summarize"""
import json
import math
import os
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
COLORS = {"local": "#2a78d6", "full": "#eb6834"}  # categorical slots 1-2 (validated, light surface)
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3df"


def stats(xs):
    xs = sorted(xs)
    return {"median": statistics.median(xs), "mean": statistics.fmean(xs),
            "p95": xs[max(0, math.ceil(0.95 * len(xs)) - 1)], "n": len(xs)}


def main():
    raw = json.load(open(os.path.join(RES, "scale_raw.json")))
    out = {"vehicles": raw["vehicles"], "repeats": raw["repeats"], "time_limit_s": raw["time_limit_s"], "sizes": {}}
    for n, s in raw["sizes"].items():
        rows = s["rows"]
        entry = {"capacity": s["capacity"], "model_size": s["model_size"], "reference": s["reference"],
                 "queries": len(rows)}
        for m in ("local", "full"):
            runs = [r for row in rows for r in row[m]]
            entry[m] = {"with_setup_ms": stats([1000 * r["with_setup_s"] for r in runs]),
                        "solve_only_ms": stats([1000 * r["solve_only_s"] for r in runs]),
                        "time_limit_hits": sum(1 for r in runs if r["status"] == "time_limit"),
                        "no_solution": sum(1 for r in runs if "objective" not in r)}
        both = [(row["local"][0], row["full"][0]) for row in rows
                if "objective" in row["local"][0] and "objective" in row["full"][0]]
        entry["objective_within_1pct"] = {"num": sum(abs(a["objective"] - b["objective"]) <= 0.01 * b["objective"]
                                                     for a, b in both), "den": len(both)}
        entry["local_better_than_full_incumbent"] = sum(a["objective"] < b["objective"] - 1e-6 for a, b in both)
        entry["local_levels"] = {lv: sum(1 for row in rows if row["local"][0]["level"] == lv) for lv in ("L0", "L1", "L2")}
        out["sizes"][n] = entry
    with open(os.path.join(RES, "scale_summary.json"), "w") as f:
        json.dump(out, f, indent=2)

    sizes = sorted(out["sizes"], key=int)
    xs = [int(n) for n in sizes]
    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=160)
    for m, label in (("local", "Local re-optimization"), ("full", "Full re-solve")):
        ys = [out["sizes"][n][m]["with_setup_ms"]["median"] for n in sizes]
        ax.plot(xs, ys, color=COLORS[m], lw=2, marker="o", ms=7, mec="white", mew=1.5, label=label, zorder=3)
        ax.annotate(label, (xs[-1], ys[-1]), xytext=(8, 0), textcoords="offset points", va="center",
                    fontsize=8.5, color=INK)
    ax.set_yscale("log")
    ax.set_xticks(xs)
    ax.set_xlabel("Customers (3 vehicles)", color=MUTED, fontsize=9)
    ax.set_ylabel("Median query latency, ms (log scale)", color=MUTED, fontsize=9)
    ax.set_title(f"Counterfactual query latency, {raw['repeats']} repeats x {out['sizes'][sizes[0]]['queries']} queries "
                 f"per size", fontsize=10, color=INK, loc="left")
    ax.grid(axis="y", color=GRID, lw=0.8, which="major")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    ax.set_xlim(xs[0] - 1, xs[-1] + 4.5)
    ax.legend(loc="upper left", fontsize=8.5, frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "latency_curve.png"))

    lines = ["| Customers | Model vars / constraints | Reference solve | Local median / p95 ms | Full median / p95 ms | "
             "Full hit 300 s | Local stopped L0/L1/L2 | Objective within 1% |", "|---|---|---|---|---|---|---|---|"]
    for n in sizes:
        e = out["sizes"][n]
        ref = e["reference"]
        refs = f"{ref['status']}, {ref['runtime_s']:.1f} s" + (f", gap {100 * ref['gap']:.1f}%" if ref.get("gap") else "")
        lines.append(f"| {n} | {e['model_size']['vars']} / {e['model_size']['constrs']} | {refs} | "
                     f"{e['local']['with_setup_ms']['median']:.0f} / {e['local']['with_setup_ms']['p95']:.0f} | "
                     f"{e['full']['with_setup_ms']['median']:.0f} / {e['full']['with_setup_ms']['p95']:.0f} | "
                     f"{e['full']['time_limit_hits']}/{e['full']['with_setup_ms']['n']} | "
                     f"{e['local_levels']['L0']}/{e['local_levels']['L1']}/{e['local_levels']['L2']} | "
                     f"{e['objective_within_1pct']['num']}/{e['objective_within_1pct']['den']} |")
    with open(os.path.join(RES, "scale_summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
