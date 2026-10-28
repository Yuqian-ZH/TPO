"""task2_v2 evaluation, run from the Task 2 root:  python -m v2.evaluate --part <part>

Parts without the LLM (solver and brute force only):
  attribution           v2 on the 10 test cases (same ground truth and metrics as v1), and v1 vs v2 against
                        brute force on states with soft constraints and weights: the 10 reference-fix plans
                        (every decision) and the 14 Task 3 loop states where condition A ran at iteration 2 or 3
  counterfactual        test-case and supplementary queries; local_v1 / local_v2 / full, warm and cold set-up
  localization_rescore  the v2 confidence rule applied to the samples saved by the v1 run (results/raw)
Parts with the LLM (qwen3.8-max, enable_thinking=false; seeds use new component names, so they are new samples):
  explanation           v2 explanation of the test-case attributions, 3 runs
  localization          v2 localization of the test complaints, 3 runs, then again with the clarification answer

Each part writes results_v2/raw/<part>.json once and refuses to overwrite it. LLM parts refuse to run unless
v2/protocol_v2.json matches the files on disk."""
import argparse
import datetime
import glob
import hashlib
import json
import os
import platform
import subprocess
import sys

from cases.gt import attribution_gt, counterfactual_gt
from components.attribution import attribute as attribute_v1
from components.state import make_state, model_data, state_for_case
from cvrp import canon
from cvrp.data import load_instance
from cvrp.oracle import oracle_for

from . import attribution as att2
from . import localization as loc2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2 = os.path.join(ROOT, "v2")
OUT = os.path.join(ROOT, "results_v2", "raw")
LOGS = os.path.join(ROOT, "logs", "eval_v2")
TASK3_TRIALS = os.path.normpath(os.path.join(ROOT, "..", "..", "Task 3", "task3", "results", "formal", "trials"))
PROTOCOL = os.path.join(V2, "protocol_v2.json")
LLM_PARTS = ("explanation", "localization")
RUNS = 3
REPEATS = 20


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def frozen_files():
    pats = ["v2/__init__.py", "v2/attribution.py", "v2/localization.py", "v2/timing.py", "v2/evaluate.py",
            "v2/freeze.py", "v2/prompts/*.txt", "tests/test_v2_*.py", "cases/test_cases.json",
            "instance/cvrp_instance.json", "components/*.py", "components/prompts/*.txt", "cvrp/*.py"]
    return sorted({os.path.relpath(p, ROOT) for pat in pats for p in glob.glob(os.path.join(ROOT, pat))})


def check_protocol():
    if not os.path.exists(PROTOCOL):
        sys.exit("refused: LLM parts need v2/protocol_v2.json (python -m v2.freeze)")
    proto = json.load(open(PROTOCOL))
    now = {f: sha256(os.path.join(ROOT, f)) for f in frozen_files()}
    changed = sorted(f for f in set(now) | set(proto["file_sha256"]) if now.get(f) != proto["file_sha256"].get(f))
    if changed:
        sys.exit(f"refused: files changed since protocol_v2.json was frozen: {changed}")
    return proto


def load_cases(split="test"):
    return json.load(open(os.path.join(ROOT, "cases", f"{split}_cases.json")))["cases"]


def all_decisions(sol):
    """Every ADJ, SAME and SEP decision of a plan."""
    out = []
    routes = sol["routes"]
    for r in routes:
        path = [0, *r, 0]
        out += [{"type": "ADJ", "i": min(a, b), "j": max(a, b)} for a, b in zip(path, path[1:])]
        out += [{"type": "SAME", "i": min(a, b), "j": max(a, b)} for x, a in enumerate(r) for b in r[x + 1:]]
    out += [{"type": "SEP", "i": min(a, b), "j": max(a, b)} for a in routes[0] for b in routes[1]]
    seen, uniq = set(), []
    for d in out:
        key = (d["type"], d["i"], d["j"])
        if key not in seen:
            seen.add(key)
            uniq.append(d)
    return uniq


def soft_states(base, cases):
    """(source, plan, modifications) where the objective has soft constraints, weights or corrected data."""
    states = []
    for c in cases:
        mods = list(c["model_modifications"]) + list(c["reference_modification"])
        states.append((f"reference_fix/{c['id']}", c["reference_check"]["solution"], mods))
    for p in sorted(glob.glob(os.path.join(TASK3_TRIALS, "A1*", "*.json"))):
        r = json.load(open(p))
        for it in r["iterations"]:
            if it.get("attribution") and it["t"] >= 2:
                states.append((f"task3_loop/{r['config']}/{r['case_id']}/r{r['run']}/t{it['t']}",
                               it["input_solution"], list(it["mods_before"])))
    return states


def _brute(base, sol, mods, d, anchor=None):
    """Brute force of the forbidden model: labels free (v1's semantics) or under the anchor v2 chose, whose claim
    that the current plan is optimal under it is checked as well."""
    o = oracle_for(base, mods)
    prims = [canon.forbid_decision(d)]
    out = {}
    if anchor is not None:
        a = {k: anchor[k] for k in ("type", "i", "k")}
        prims.append(a)
        cur = canon.objective(sol, model_data(make_state(sol, mods)), mods)
        out["current_plan_optimal_under_anchor"] = o.solve(mods, [a])["objective"] >= cur - 1e-6
    r = o.solve(mods, prims)
    out.update(feasible=r["feasible"], objective=r["objective"])
    if r["feasible"]:
        out["acceptable_sets"] = sorted({tuple(sorted({f"e[{a},{b}]" for a, b in
                                                       canon.change_set(sol, s)["added_edges"] +
                                                       canon.change_set(sol, s)["removed_edges"]}))
                                         for s in r["optimal"]})
    return out


def _compact(a):
    keep = ("decision_text", "conclusion", "attribution_set", "current_objective", "objective_increase_if_forbidden",
            "alternative_objective", "solver_objective", "alternative_solution", "anchor", "solve_time_s")
    return {k: a[k] for k in keep if k in a}


def part_attribution(base):
    cases = load_cases()
    test = {c["id"]: {"output": att2.attribute(state_for_case(c), c["why_decision"])} for c in cases}
    rows = []
    for source, sol, mods in soft_states(base, cases):
        st = make_state(sol, mods)
        cur = canon.objective(sol, model_data(st), mods)
        for d in all_decisions(sol):
            a1, a2 = attribute_v1(st, d), att2.attribute(st, d)
            rows.append({"source": source, "routes": sol["routes"], "mods": mods, "decision": d,
                         "current_objective": cur, "v1": _compact(a1), "v2": _compact(a2),
                         "brute_force_v1_semantics": _brute(base, sol, mods, d),
                         "brute_force_v2_semantics": _brute(base, sol, mods, d, a2["anchor"])})
        print(f"attribution {source}: {len(all_decisions(sol))} decisions", flush=True)
    return {"test_cases": test, "soft_states": rows}


def part_counterfactual(base):
    from .timing import METHODS, SETUPS, Runner
    from evaluate import supplementary_queries
    cases = load_cases()
    run = Runner()
    jobs = [(c["id"], state_for_case(c), c["what_if"], c["gt"]["counterfactual"]) for c in cases]
    ref = next(c for c in cases if not c["model_modifications"])["solution"]
    st = make_state(ref)
    for q in supplementary_queries(ref):
        qid = "S:" + q["type"] + "(" + ",".join(str(q[k]) for k in ("k", "i", "j") if k in q) + ")"
        jobs.append((qid, st, q, counterfactual_gt(base, [], ref, q)))
    for method in METHODS:          # resident models are built before any timed call
        for _, state, _, _ in jobs:
            run.engine(method, state)
    entries = []
    for qid, state, q, gt in jobs:
        e = {"id": qid, "query": q, "gt": gt, "main": not qid.startswith("S:")}
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


def part_localization_rescore(base):
    cases = load_cases()
    v1 = json.load(open(os.path.join(ROOT, "results", "raw", "localization.json")))
    out = []
    for run, per in enumerate(v1):
        rec = {}
        for c in cases:
            st = state_for_case(c)
            r = {}
            for phase in ("initial", "clarified"):
                old = per[c["id"]][phase]
                new = loc2.decide(old["diagnostics"]["samples"], st, c["complaint"], old["clarification"])
                r[phase] = {"v1_confidence": old["confidence"], "v1_question": old["clarifying_question"],
                            "v2": new}
            rec[c["id"]] = r
        out.append(rec)
    return {"source": "results/raw/localization.json (task2_v1 samples, unchanged)", "runs": out}


def part_explanation(base, llm):
    cases = load_cases()
    out = {}
    for c in cases:
        a = att2.attribute(state_for_case(c), c["why_decision"])
        exps = [att2.explain(a, llm, c["id"], run) for run in range(RUNS)]
        out[c["id"]] = {"output": a, "explanations": exps}
        print(f"explanation {c['id']}: valid {[e['valid'] for e in exps]}", flush=True)
    return out


def part_localization(base, llm):
    cases = load_cases()
    runs = []
    for run in range(RUNS):
        per = {}
        for c in cases:
            st = state_for_case(c)
            r = loc2.localize(st, c["complaint"], llm, c["id"], run)
            q = r["clarifying_question"] or loc2.GENERIC_QUESTION
            r2 = loc2.localize(st, c["complaint"], llm, c["id"], run,
                               clarification={"question": q, "answer": c["clarification_answer"]})
            per[c["id"]] = {"initial": r, "clarified": r2}
            print(f"localize run {run} {c['id']}: {r['confidence']} {r['diagnostics']['majority_key_target']} -> "
                  f"{r2['confidence']} {r2['diagnostics']['majority_key_target']}", flush=True)
        runs.append(per)
    return runs


PARTS = {"attribution": part_attribution, "counterfactual": part_counterfactual,
         "localization_rescore": part_localization_rescore, "explanation": part_explanation,
         "localization": part_localization}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=list(PARTS), required=True)
    args = ap.parse_args()
    path = os.path.join(OUT, f"{args.part}.json")
    if os.path.exists(path):
        sys.exit(f"refused: {path} exists; each part runs once")
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LOGS, exist_ok=True)
    base = load_instance(os.path.join(ROOT, "instance", "cvrp_instance.json"))
    meta = {"protocol": "task2_v2", "part": args.part,
            "started": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "python": platform.python_version(), "machine": platform.machine(),
            "cpu": subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                                  text=True).stdout.strip(),
            "source_sha256": {f: sha256(os.path.join(ROOT, f)) for f in frozen_files()}}
    if args.part in LLM_PARTS:
        proto = check_protocol()
        meta["protocol_sha256"] = sha256(PROTOCOL)
        from components.llm_client import MODEL, LLMClient
        meta["llm_model"] = MODEL
        llm = LLMClient(os.path.join(LOGS, f"llm_{args.part}.jsonl"))
        data = PARTS[args.part](base, llm)
        meta["frozen_at"] = proto["frozen_at"]
    else:
        data = PARTS[args.part](base)
    meta["finished"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    with open(path, "w") as f:
        json.dump({"meta": meta, "data": data}, f, indent=1, default=str)
    print(f"wrote {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
