"""Stage 1 smoke with the real LLM (<= 7 requests) on a separate random 6-customer instance, so nothing touches
the frozen instance or any Task 2 case. Checks only that prompts are answered with parseable, valid
modifications that the solver can apply; the outcome is not evaluated."""
import json
import os
import random
import sys

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tpo.components import ReferenceComponents  # noqa: E402
from tpo.llm import real_client  # noqa: E402
from tpo.loop import CONFIGS, Settings, localize_with_clarification, run_trial  # noqa: E402
from tpo.task2_bridge import CVRPModel, canon, make_data  # noqa: E402


def toy_instance(seed=20261023, n=6):
    rng = random.Random(seed)
    coords = [(50, 50)]
    while len(coords) < n + 1:
        p = (rng.randint(0, 100), rng.randint(0, 100))
        if p not in coords:
            coords.append(p)
    demand = [0] + [rng.randint(10, 40) for _ in range(n)]
    return make_data(coords, demand, capacity=max(max(demand), (sum(demand) * 3) // 5))


def main():
    base = toy_instance()
    opt = canon.canonical(CVRPModel(base).optimize()["solution"])
    m = canon.metrics(opt, base)
    long_k = 1 if m["L[1]"] >= m["L[2]"] else 2
    case = {"id": "TOY1", "split": "smoke", "model_modifications": [], "solution": opt,
            "complaint": f"Vehicle {long_k} drives much further than the other vehicle; share the driving more evenly.",
            "clarification_answer": "I mean the route length.", "allowed_data_corrections": [],
            "checker": {"name": "balance_max", "params": {"max": max(1, m["balance"] // 2)}}}
    loc = {"confidence": "high", "target": "balance", "aspect": "balance", "direction": "decrease",
           "modification_type": "set_objective_weight", "evidence": {"balance": m["balance"]},
           "clarification_question": None}
    comps = ReferenceComponents(base, {"TOY1": {"first": loc, "clarified": loc}})
    llm = real_client(os.path.join(ROOT, "logs", "smoke_llm.jsonl"))
    shared = localize_with_clarification(case, base, comps, 1)
    out = {"instance": {"n": base["n"], "Q": base["Q"], "demand": base["q"], "coords": base["coords"]},
           "optimum": opt, "metrics": m, "trials": []}
    for config, iters in (("A1B0C0", 3), ("A1B1C1", 1)):
        tr = run_trial(case, base, CONFIGS[config], config, 1, comps, llm, Settings(max_iters=iters), shared)
        out["trials"].append({
            "config": config, "outcome": tr["outcome"], "converged_at": tr["converged_at"],
            "iterations": [{"t": it["t"], "status": it["status"],
                            "candidates": [{"parse_status": c["llm"]["parse_status"], "valid": c["valid"],
                                            "errors": c["errors"], "modifications": c["raw_modifications"],
                                            "rationale": c["rationale"], "returned_model": c["llm"]["returned_model"],
                                            "reasoning_present": c["llm"]["reasoning_present"],
                                            "usage": c["llm"]["usage"]} for c in it["candidates"]],
                            "selection": {k: v for k, v in (it.get("selection") or {}).items() if k != "prompt"},
                            "verdict": it["verdict"], "metrics_after": (it.get("commit") or {}).get("metrics")}
                           for it in tr["iterations"]]})
    with open(os.path.join(ROOT, "smoke", "smoke_result.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    for t in out["trials"]:
        print(t["config"], t["outcome"], [(i["status"], [c["parse_status"] for c in i["candidates"]],
                                          [c["valid"] for c in i["candidates"]]) for i in t["iterations"]])


if __name__ == "__main__":
    main()
