"""Cross-check the instance (oracle vs Gurobi, D1-D5) and write oracle_report.json, instance.md,
instance.png.  Run from task2/:  python -m instance.report_instance"""
import hashlib
import itertools
import json
import math
import os

import gurobipy as gp
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from cvrp import canon  # noqa: E402
from cvrp.data import load_instance, triangle_violations  # noqa: E402
from cvrp.model import CVRPModel  # noqa: E402
from cvrp.oracle import Oracle  # noqa: E402
from instance.generate_instance import check_design  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "cvrp_instance.json")
LIMIT = 2000  # size-limited Gurobi license: variables and linear constraints


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def decisions_of(sol, n):
    out = [{"type": "ADJ", "i": i, "j": j} for i, j in itertools.combinations(range(n + 1), 2)
           if canon.adjacency_count(sol, i, j)]
    out += [{"type": "SAME" if canon.same_vehicle(sol, i, j) else "SEP", "i": i, "j": j}
            for i, j in itertools.combinations(range(1, n + 1), 2)]
    return out


def main():
    inst = json.load(open(PATH))
    data = load_instance(PATH)
    n = data["n"]
    o = Oracle(data)
    ok, design, best = check_design(data, o)
    res = o.solve()
    m = canon.metrics(best, data)

    model = CVRPModel(data)
    g = model.optimize()
    g_canon = canon.canonical(g["solution"])
    size = model.size()

    decs = []
    for d in decisions_of(best, n):
        r = o.solve(prims=[canon.forbid_decision(d)])
        decs.append({**d, "forbidden_feasible": r["feasible"],
                     "delta": None if not r["feasible"] else r["objective"] - res["objective"]})
    W1, W2 = o.rload[o.r1], o.rload[o.r2]
    feas = (W1 <= data["Q"]) & (W2 <= data["Q"])
    parts = sorted({tuple(sorted((tuple(sorted(s["routes"][0])), tuple(sorted(s["routes"][1])))))
                    for s in (o.solution(i) for i in feas.nonzero()[0])})

    report = {
        "instance_file": "instance/cvrp_instance.json", "instance_sha256_at_report": sha256(PATH),
        "gurobi_version": ".".join(map(str, gp.gurobi.version())),
        "optimal": {"objective": res["objective"], "solution": best, "metrics": m,
                    "labeled_directed_optimal_count": len(res["optimal"]),
                    "note": "8 = 2 vehicle labelings x 2 x 2 route directions, i.e. one distinct solution"},
        "second_best": {"objective": design["D1"]["second_best"], "solution": design["D1"]["second_best_solution"],
                        "metrics": canon.metrics(design["D1"]["second_best_solution"], data)},
        "design_goals": {k: v for k, v in design.items()}, "all_design_goals_met": ok,
        "gurobi_check": {"objective": g["objective"], "canonical_solution": g_canon,
                         "objective_equal": abs(g["objective"] - res["objective"]) < 1e-6,
                         "routes_equal": g_canon == best, "runtime_s": g["runtime_s"],
                         "model_size": size, "license_limit": LIMIT,
                         "within_limit": size["num_vars"] <= LIMIT and size["num_constrs"] <= LIMIT},
        "triangle_inequality_violations": triangle_violations(data["c"]),
        "feasible_partitions": {"count": len(parts), "partitions": parts},
        "decisions_in_optimal_solution": decs,
        "capacity_forced_decisions": [d for d in decs if not d["forbidden_feasible"]],
        "solution_counts": {"labeled_directed_total": int(len(o.r1)),
                            "labeled_directed_capacity_feasible": int(feas.sum())},
    }
    with open(os.path.join(HERE, "oracle_report.json"), "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    draw(inst, data, best, m)
    write_md(inst, data, report)
    print(json.dumps({"all_design_goals_met": ok, "gurobi_check": report["gurobi_check"],
                      "capacity_forced": report["capacity_forced_decisions"],
                      "feasible_partitions": len(parts)}, indent=2))


def label_offset(xy, node, nbrs, dist=16):
    """Offset (points) pointing away from every edge incident to the node."""
    angles = [math.atan2(xy[b][1] - xy[node][1], xy[b][0] - xy[node][0]) for b in nbrs]

    def gap(t):
        return min(abs((t - a + math.pi) % (2 * math.pi) - math.pi) for a in angles)
    t = max((k * math.pi / 8 for k in range(16)), key=gap)
    return dist * math.cos(t), dist * math.sin(t)


def draw(inst, data, best, m):
    fig, ax = plt.subplots(figsize=(7.2, 7.2), dpi=150)
    xy = data["coords"]
    colors = ["#2563eb", "#dc2626"]
    nbrs = {i: [] for i in range(data["n"] + 1)}
    for k, r in enumerate(best["routes"]):
        path = [0, *r, 0]
        for a, b in zip(path, path[1:]):
            nbrs[a].append(b)
            nbrs[b].append(a)
            ax.annotate("", xy=xy[b], xytext=xy[a],
                        arrowprops=dict(arrowstyle="-|>", color=colors[k], lw=1.8, shrinkA=7, shrinkB=7))
        ax.plot([], [], color=colors[k], lw=2,
                label=f"Vehicle {k + 1}: 0-{'-'.join(map(str, r))}-0  (L={m[f'L[{k + 1}]']}, load={m[f'W[{k + 1}]']})")
    ax.scatter(*xy[0], marker="s", s=110, color="black", zorder=3)
    ax.annotate("Depot 0", xy[0], xytext=(-9, 5), textcoords="offset points", fontsize=9, fontweight="bold",
                ha="right", va="bottom")
    for i in range(1, data["n"] + 1):
        ax.scatter(*xy[i], s=130, color="white", edgecolor="black", zorder=3)
        ax.annotate(str(i), xy[i], ha="center", va="center", fontsize=8, fontweight="bold", zorder=4)
        dx, dy = label_offset(xy, i, nbrs[i] + ([0] if i == 1 else []), 19)
        ax.annotate(f"q={data['q'][i]}", xy[i], xytext=(dx, dy), textcoords="offset points", fontsize=8,
                    color="#374151", ha="center", va="center")
    ax.set_xlim(-5, 105)
    ax.set_ylim(-5, 105)
    ax.set_aspect("equal")
    ax.grid(alpha=0.25)
    ax.set_title(f"Task 2 CVRP instance: optimal total distance {m['total_distance']} (capacity {data['Q']})",
                 fontsize=10)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.95)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "instance.png"))


def write_md(inst, data, rep):
    n, c, q = data["n"], data["c"], data["q"]
    opt, d = rep["optimal"], rep["design_goals"]
    g = inst["generator"]
    lines = ["# Task 2 CVRP instance (`task2_cvrp_v1`)", "",
             "Machine-readable spec: `cvrp_instance.json`. Figure: `instance.png`. Oracle report: `oracle_report.json`.",
             "", "## Specification", "",
             f"- 1 depot (node 0), {n} customers (nodes 1-{n}), {inst['vehicles']} identical vehicles, "
             f"capacity Q = {inst['capacity']} each, no time windows.",
             f"- Objective: {inst['objective']}",
             f"- Distance: {inst['distance']}",
             f"- Total demand {sum(q)} > Q, so both vehicles are needed.", "",
             "| Node | x | y | Demand |", "|---|---|---|---|"]
    lines += [f"| {'0 (depot)' if i == 0 else i} | {data['coords'][i][0]} | {data['coords'][i][1]} | {q[i]} |"
              for i in range(n + 1)]
    lines += ["", "Distance matrix:", "", "| | " + " | ".join(map(str, range(n + 1))) + " |",
              "|---" * (n + 2) + "|"]
    lines += [f"| **{i}** | " + " | ".join(map(str, c[i])) + " |" for i in range(n + 1)]
    lines += ["", f"Triangle inequality violations after rounding: {len(rep['triangle_inequality_violations'])}.",
              "", "## Optimal solution", "",
              f"Total distance **{opt['objective']:.0f}**, unique up to vehicle relabeling and route reversal "
              f"(second best {rep['second_best']['objective']:.0f}).", "",
              "| Vehicle | Route | Length | Load | Stops |", "|---|---|---|---|---|"]
    for k, r in enumerate(opt["solution"]["routes"], start=1):
        lines.append(f"| {k} | 0 → {' → '.join(map(str, r))} → 0 | {opt['metrics'][f'L[{k}]']} | "
                     f"{opt['metrics'][f'W[{k}]']} | {opt['metrics'][f'S[{k}]']} |")
    lines += ["", "Arrival mileage A[i] (distance driven from the depot until customer i, in the canonical direction): "
              + ", ".join(f"A[{i}]={opt['metrics'][f'A[{i}]']}" for i in range(1, n + 1)) + ".", "",
              "Conventions: " + inst["conventions"]["vehicle_label"] + " " + inst["conventions"]["route_direction"],
              "", "## Design goals (checked by brute force)", "", "| Goal | Requirement | Result | OK |",
              "|---|---|---|---|",
              f"| D1 | Unique optimum; second best strictly worse | optimum {d['D1']['optimal']:.0f}, "
              f"second best {d['D1']['second_best']:.0f} (gap {d['D1']['gap']:.0f}) | {d['D1']['ok']} |",
              f"| D2 | Some pair of customers exceeds Q together | "
              f"{', '.join(f'{a}+{b}: {s}' for a, b, s in d['D2']['pairs_over_capacity'])} | {d['D2']['ok']} |",
              f"| D3 | Dropping capacity changes the optimal grouping | uncapacitated optimum "
              f"{d['D3']['uncapacitated_optimal']:.0f} with grouping "
              f"{' / '.join(str(list(r)) for r in d['D3']['uncapacitated_solutions'][0])} | {d['D3']['ok']} |",
              f"| D4 | Both loads ≥ 0.8Q | {d['D4']['loads']} | {d['D4']['ok']} |",
              f"| D5 | Route length ratio ≥ 1.2 | {d['D5']['lengths']} → {d['D5']['ratio']} | {d['D5']['ok']} |",
              "", "## Gurobi cross-check", "",
              f"Gurobi {rep['gurobi_version']} (size-limited license): objective {rep['gurobi_check']['objective']:.0f}, "
              f"canonical routes equal to the oracle: {rep['gurobi_check']['routes_equal']}. Model size "
              f"{rep['gurobi_check']['model_size']['num_vars']} variables "
              f"({rep['gurobi_check']['model_size']['num_bin_vars']} binary), "
              f"{rep['gurobi_check']['model_size']['num_constrs']} constraints (limit {LIMIT}).", "",
              "## Generation", "",
              f"`{g['script']}` with seed {g['seed']}: candidate #{g['candidate_index']} is the first meeting D1-D5 "
              f"({g['rejected_candidates']} rejected: {g['rejected_by']['D2_precheck']} by the demand-only D2 "
              f"pre-check, {g['rejected_by']['oracle_D1_D3_D4_D5']} by the oracle {g['oracle_failures_by_goal']}). "
              f"Coordinates are uniform integers in [0, 100] (depot fixed at (50, 50)); demands are uniform "
              f"integers in [{g['demand_range'][0]}, {g['demand_range'][1]}], redrawn until the total is in "
              f"[{g['total_demand_range'][0]}, {g['total_demand_range'][1]}].", "",
              "## Capacity structure", "",
              f"{rep['feasible_partitions']['count']} customer groupings are capacity-feasible. Decisions of the "
              f"optimal solution whose prohibition is infeasible (capacity-forced): "
              + ", ".join(f"{x['type']}({x['i']},{x['j']})" for x in rep["capacity_forced_decisions"])
              + ". Every other decision is preferred by the objective (prohibiting it stays feasible but costs more)."]
    with open(os.path.join(HERE, "instance.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
