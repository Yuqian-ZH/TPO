"""task2_v3 evaluation on the v3 test cases, with task2_v2.1's components. Run from the Task 2 root:
    python -m v3.evaluate --part <part>          then  python -m v3.report

Parts without the LLM:
  attribution     each case's why-decision, against the brute-force ground truth (same metrics as task2_v1)
  counterfactual  each case's what-if query, plus its reference fix and its direct (or misread) encoding as
                  APPLY_MODIFICATIONS queries (the kind of query condition B probes in the loop); local_v1,
                  local_v2 (the loop's probe) and full re-solve, warm and cold, against brute force
Parts with the LLM (qwen3.8-max, enable_thinking=false), refused unless v3/protocol_v3.json matches:
  explanation     the v2.1 explanation of each attribution, 3 runs
  localization    the v2.1 localization of each complaint, 3 runs, then again with the user's explanation as the
                  answer to the clarifying question

Each part writes results_v3/raw/<part>.json once and refuses to overwrite it."""
import argparse
import datetime
import json
import os
import platform
import subprocess
import sys

from cases.gt import counterfactual_gt
from components.state import state_for_case
from cvrp.data import load_instance
from v2.evaluate import sha256
from v21 import attribution as att21
from v21 import localization as loc21

from .freeze import PROTOCOL, ROOT, check, frozen_files

OUT = os.path.join(ROOT, "results_v3", "raw")
LOGS = os.path.join(ROOT, "logs", "eval_v3")
CASES = os.path.join(ROOT, "v3", "cases", "test_cases.json")
LLM_PARTS = ("explanation", "localization")
RUNS = 3
REPEATS = 20


def load_cases():
    return json.load(open(CASES))["cases"]


def part_attribution(base):
    return {c["id"]: {"output": att21.attribute(state_for_case(c), c["why_decision"])} for c in load_cases()}


def cf_queries(cases):
    """(id, case, query, kind): the what-if, the reference fix and the direct / misread encoding of every case."""
    out = []
    for c in cases:
        probe = c["design"].get("direct") or c["design"].get("misreading")
        out += [(f"{c['id']}:what_if", c, c["what_if"], "what_if"),
                (f"{c['id']}:reference", c, {"type": "APPLY_MODIFICATIONS", "mods": c["reference_modification"]},
                 "reference_fix"),
                (f"{c['id']}:direct", c, {"type": "APPLY_MODIFICATIONS", "mods": probe["modifications"]},
                 "direct_or_misreading")]
    return out


def part_counterfactual(base):
    from v2.timing import METHODS, SETUPS, Runner
    run = Runner()
    jobs = [(qid, state_for_case(c), q, kind, counterfactual_gt(base, c["model_modifications"], c["solution"], q))
            for qid, c, q, kind in cf_queries(load_cases())]
    for method in METHODS:                  # resident models are built before any timed call
        for _, state, _, _, _ in jobs:
            run.engine(method, state)
    entries = []
    for qid, state, q, kind, gt in jobs:
        e = {"id": qid, "kind": kind, "query": q, "gt": gt}
        for method in METHODS:
            for setup in SETUPS:
                outs = [run.query(state, q, method, setup) for _ in range(REPEATS)]
                first = outs[0]
                e[f"{method}/{setup}"] = {**{k: v for k, v in first.items() if k != "latency"},
                                          "latency": [o["latency"] for o in outs],
                                          "nondeterministic": any(o["feasible"] != first["feasible"] or
                                                                  o.get("objective") != first.get("objective")
                                                                  for o in outs)}
        entries.append(e)
        print(f"counterfactual {qid}", flush=True)
    return {"repeats": REPEATS, "entries": entries}


def part_explanation(base, llm):
    out = {}
    for c in load_cases():
        a = att21.attribute(state_for_case(c), c["why_decision"])
        exps = [att21.explain(a, llm, c["id"], run, component="explain_v3") for run in range(RUNS)]
        out[c["id"]] = {"output": a, "explanations": exps}
        print(f"explanation {c['id']}: valid {[e['valid'] for e in exps]}", flush=True)
    return out


def part_localization(base, llm):
    runs = []
    for run in range(RUNS):
        per = {}
        for c in load_cases():
            st = state_for_case(c)
            r = loc21.localize(st, c["complaint"], llm, c["id"], f"v3-{run}")
            q = r["clarifying_question"] or loc21.GENERIC_QUESTION
            r2 = loc21.localize(st, c["complaint"], llm, c["id"], f"v3-{run}",
                                clarification={"question": q, "answer": c["explanation"]})
            per[c["id"]] = {"initial": r, "clarified": r2}
            print(f"localize run {run} {c['id']}: {r['confidence']} {r['diagnostics']['majority_target']} -> "
                  f"{r2['confidence']} {r2['diagnostics']['majority_target']}", flush=True)
        runs.append(per)
    return runs


PARTS = {"attribution": part_attribution, "counterfactual": part_counterfactual, "explanation": part_explanation,
         "localization": part_localization}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=list(PARTS), required=True)
    args = ap.parse_args()
    path = os.path.join(OUT, f"{args.part}.json")
    if os.path.exists(path):
        sys.exit(f"refused: {path} exists; each part runs once")
    proto = check()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LOGS, exist_ok=True)
    base = load_instance(os.path.join(ROOT, "instance", "cvrp_instance.json"))
    meta = {"protocol": "task2_v3", "part": args.part, "frozen_at": proto["frozen_at"],
            "protocol_sha256": sha256(PROTOCOL),
            "started": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "python": platform.python_version(), "machine": platform.machine(),
            "cpu": subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                                  text=True).stdout.strip(),
            "source_sha256": {f: sha256(os.path.join(ROOT, f)) for f in frozen_files()}}
    if args.part in LLM_PARTS:
        from components.llm_client import MODEL, LLMClient
        meta["llm_model"] = MODEL
        data = PARTS[args.part](base, LLMClient(os.path.join(LOGS, f"llm_{args.part}.jsonl")))
    else:
        data = PARTS[args.part](base)
    meta["finished"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    with open(path, "w") as f:
        json.dump({"meta": meta, "data": data}, f, indent=1, default=str)
    print(f"wrote {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
