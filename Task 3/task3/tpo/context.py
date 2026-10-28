"""Prompt blocks (plan 3.3 step 2.1, 3.8). Blocks are concatenated in a fixed order; a switched-off block is
omitted. Every input here is either public case data or computed by the system; no ground truth."""
import json
import os

from .task2_bridge import canon

PROMPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")
ORDER = ("instance", "plan", "mods_in_force", "complaint", "clarification", "localization", "attribution",
         "history")
TASK_PROPOSAL = "## Task\nPropose the complete list of modifications for the next plan."
TASK_SELECTOR = "## Task\nChoose the candidate to commit."


def system_prompt(name):
    with open(os.path.join(PROMPTS, f"system_{name}.txt")) as f:
        return f.read().strip()


def _j(obj):
    return json.dumps(obj, separators=(", ", ": "))


def instance_block(data):
    n = data["n"]
    rows = ["| node | x | y | demand |", "|---|---|---|---|"]
    for i in range(n + 1):
        x, y = data["coords"][i]
        rows.append(f"| {i}{' (depot)' if i == 0 else ''} | {x} | {y} | {data['q'][i]} |")
    w = max(len(str(v)) for row in data["c"] for v in row) + 1
    mat = [" " * 3 + "".join(f"{j:>{w}}" for j in range(n + 1))]
    mat += [f"{i:>3}" + "".join(f"{data['c'][i][j]:>{w}}" for j in range(n + 1)) for i in range(n + 1)]
    return ("## Instance\n"
            f"Depot = node 0, customers 1-{n}, {data['K']} identical vehicles with capacity {data['Q']} each. "
            "Distances are rounded Euclidean distances (symmetric integers).\n" + "\n".join(rows) +
            "\n\nDistance matrix (row i, column j):\n" + "\n".join(mat))


def plan_lines(sol, data):
    m = canon.metrics(sol, data)
    lines = []
    for k, r in enumerate(sol["routes"], start=1):
        path = " -> ".join(map(str, [0, *r, 0]))
        lines.append(f"- Vehicle {k}: {path} | length {m[f'L[{k}]']} | load {m[f'W[{k}]']} / {data['Q']} | "
                     f"stops {m[f'S[{k}]']}")
    arr = ", ".join(f"A[{i}]={m[f'A[{i}]']}" for i in range(1, data["n"] + 1))
    lines.append(f"- Arrival distances: {arr}")
    lines.append(f"- total distance {m['total_distance']}, balance {m['balance']}, makespan {m['makespan']}, "
                 f"load_balance {m['load_balance']}, sum_arrival {m['sum_arrival']}")
    return lines


def plan_block(sol, data):
    return "## Current plan\n" + "\n".join(plan_lines(sol, data))


def mods_block(mods):
    body = "\n".join(f"- {_j(m)}" for m in mods) if mods else "none"
    return "## Modifications currently in force (your answer replaces this list)\n" + body


def complaint_block(complaint, extra=None):
    text = f"## User complaint\n\"{complaint}\""
    if extra:
        text += f"\nThe user later added: \"{extra}\""
    return text


def clarification_block(question, answer):
    return f"## Clarification\nThe system asked: \"{question}\"\nThe user answered: \"{answer}\""


def localization_block(crit):
    """Structured critique of Task 2's localization, evidence already recomputed on the current plan."""
    fields = {k: crit.get(k) for k in ("target", "aspect", "direction", "modification_type", "confidence",
                                       "threshold", "corrected_value") if crit.get(k) is not None}
    fields["evidence_on_current_plan"] = crit.get("evidence") or {}
    text = "## Structured localization of the complaint\n" + _j(fields)
    if crit.get("critique_text"):
        text += "\nCritique: " + crit["critique_text"]
    return text


def attribution_block(items, sol, data):
    m = canon.metrics(sol, data)
    slack = {f"vehicle {k}": data["Q"] - m[f"W[{k}]"] for k in range(1, data["K"] + 1)}
    lines = ["## Decision attribution on the current plan",
             "For each decision: whether hard constraints force it (and which), or how much the objective "
             "prefers it (change if the decision were forbidden, and the edges that would change).",
             f"Remaining capacity: {_j(slack)}"]
    lines += [f"- {_j(a)}" for a in items]
    return "\n".join(lines)


def history_block(history):
    if not history:
        return None
    out = ["## Previous attempts"]
    for h in history:
        out.append(f"Attempt {h['t']}:")
        if h["status"] == "rejected":
            out.append("- " + h["note"])
        else:
            out.append(f"- modifications: {_j(h['mods'])}")
            if h["status"] == "no_plan":
                out.append("- " + h["note"])
            else:
                out += ["- resulting plan:"] + ["  " + line for line in h["plan_lines"]]
        out.append(f"- user feedback: \"{h['feedback']}\"")
    return "\n".join(out)


def candidates_block(cands, blind):
    out = ["## Candidates"]
    for idx, c in enumerate(cands, start=1):
        out.append(f"Candidate {idx}: {_j(c['modifications'])}")
        if c.get("rationale"):
            out.append(f"  proposer's rationale: {c['rationale']}")
        if blind:
            continue
        p = c["probe"]
        if not p["feasible"]:
            out.append("  predicted outcome: infeasible (no plan satisfies the hard constraints)")
            continue
        changed = [f"{k} {b}->{a}" for k, (b, a) in p["metric_changes"].items() if k != "total_distance"]
        cs = p["change_set"]
        out.append(f"  predicted outcome: total distance {p['distance_before']} -> {p['distance_after']}; "
                   f"customers changing vehicle: {cs['moved']}; edges removed: {cs['removed_edges']}; "
                   f"edges added: {cs['added_edges']}")
        out.append(f"  changed indicators: {', '.join(changed) if changed else 'none'}")
    return "\n".join(out)


def user_message(blocks, task):
    return "\n\n".join([blocks[k] for k in ORDER if blocks.get(k)] + [task])
