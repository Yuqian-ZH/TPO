"""One-shot evaluation (section 7.2). Writes raw artifacts to <out>/raw/ and metrics to
<out>/task2_results.json.  The test split refuses to run unless protocol.json matches the files on disk,
and no split overwrites an existing <out>/raw/.
  python evaluate.py --split test
  python evaluate.py --split dev --out results_dev --repeats 3 --runs 1 --no-supplementary   (dry run)"""
import argparse
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

import gurobipy as gp

import metrics
from cases.gt import counterfactual_gt
from components.attribution import attribute, explain
from components.counterfactual import counterfactual, engine_for
from components.llm_client import MODEL, LLMClient
from components.localization import localize
from components.state import make_state, state_for_case
from cvrp import canon
from cvrp.data import load_instance
from cvrp.validate import errors

ROOT = os.path.dirname(os.path.abspath(__file__))
GENERIC_QUESTION = "Could you state precisely what should change?"


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def check_protocol():
    proto = json.load(open(os.path.join(ROOT, "protocol.json")))
    bad = [p for p, h in proto["file_sha256"].items() if sha256(os.path.join(ROOT, p)) != h]
    if bad:
        sys.exit(f"protocol.json does not match files on disk: {bad}")
    return proto


def power_state():
    batt = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout.splitlines()
    low = subprocess.run(["pmset", "-g"], capture_output=True, text=True).stdout
    lowpower = [ln.split()[-1] for ln in low.splitlines() if "lowpowermode" in ln]
    return {"source": batt[0] if batt else None, "lowpowermode": lowpower[0] if lowpower else None}


def supplementary_queries(sol):
    veh = canon.vehicle_of(sol)
    qs = [{"type": "MOVE", "i": i, "k": 3 - veh[i]} for i in sorted(veh)]
    qs += [{"type": "FIX_ARC", "k": k, "i": i, "j": j} for k in (1, 2) for i in sorted(veh) for j in sorted(veh) if i != j]
    return qs


class Evaluator:
    def __init__(self, args, logs):
        self.args = args
        self.solve_log = open(os.path.join(logs, "solves.jsonl"), "a")
        self.schema_errors = []

    def log_solve(self, rec):
        rec["time"] = datetime.datetime.now().astimezone().isoformat(timespec="milliseconds")
        self.solve_log.write(json.dumps(rec) + "\n")

    def check(self, schema, obj, where):
        e = errors(schema, obj)
        if e:
            self.schema_errors.append({"where": where, "schema": schema, "errors": e[:5]})

    def run_cf(self, state, query, qid, gt=None):
        eng = engine_for(state)  # the resident model is built at start-up, outside the timed calls
        entry = {"id": qid, "engine_build_s": eng.build_s}
        for method in ("local", "full"):
            lat = []
            for rep in range(self.args.repeats):
                out = counterfactual(state, query, method)
                lat.append(out["latency"])
                self.log_solve({"component": "counterfactual", "id": qid, "method": method, "rep": rep,
                                "query": query, "level": out.get("level"),
                                "levels_tried": [(t["level"], t["status"]) for t in out.get("levels_tried", [])],
                                "feasible": out["feasible"], "objective": out.get("objective"),
                                "latency": out["latency"]})
                if rep == 0:
                    self.check("counterfactual_output", out, f"{qid}/{method}")
                    entry[method] = out
                elif out["feasible"] != entry[method]["feasible"] or out.get("objective") != entry[method].get("objective"):
                    entry.setdefault("nondeterministic", []).append({"method": method, "rep": rep})
            entry[f"{method}_latency"] = lat
        if gt is not None:
            entry["gt"] = gt
        return entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["test", "dev"], required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--repeats", type=int, default=20)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--no-supplementary", action="store_true")
    args = ap.parse_args()
    out_dir = os.path.join(ROOT, args.out)
    raw_dir = os.path.join(out_dir, "raw")
    if os.path.exists(raw_dir):
        sys.exit(f"{raw_dir} exists: the evaluation is one-shot and is not re-run over saved results")
    proto = check_protocol() if args.split == "test" else None
    logs = os.path.join(ROOT, "logs", "eval" if args.split == "test" else "dev_eval")
    os.makedirs(logs, exist_ok=True)
    os.makedirs(raw_dir)
    started = datetime.datetime.now().astimezone()
    meta = {"split": args.split, "started": started.isoformat(timespec="seconds"), "repeats": args.repeats,
            "runs": args.runs, "power": power_state(), "python": platform.python_version(),
            "machine": platform.machine(),
            "cpu": subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip(),
            "gurobi": ".".join(map(str, gp.gurobi.version())), "llm_model": MODEL,
            "protocol_sha256": sha256(os.path.join(ROOT, "protocol.json")) if proto else None}
    print(json.dumps(meta, indent=1), flush=True)
    ev = Evaluator(args, logs)
    llm = LLMClient(os.path.join(logs, "llm_eval.jsonl"))
    cases = json.load(open(os.path.join(ROOT, "cases", f"{args.split}_cases.json")))["cases"]
    base = load_instance(os.path.join(ROOT, "instance", "cvrp_instance.json"))

    # 1. attribution (deterministic, once) + LLM explanation (runs)
    att = {}
    for c in cases:
        a = attribute(state_for_case(c), c["why_decision"])
        ev.check("attribution_output", a, f"{c['id']}/attribution")
        ev.log_solve({"component": "attribution", "id": c["id"], "decision": c["why_decision"],
                      "conclusion": a["conclusion"], "solve_time_s": a["solve_time_s"]})
        exps = []
        for run in range(args.runs):
            e = explain(a, llm, c["id"], run)
            ev.check("explanation_output", e, f"{c['id']}/explain/{run}")
            exps.append(e)
        att[c["id"]] = {"output": a, "explanations": exps}
        print(f"attribution {c['id']}: {a['conclusion']}, explanations valid {[e['valid'] for e in exps]}", flush=True)

    # 2. counterfactual on the cases' what-if queries
    t0 = time.perf_counter()
    main_entries = [ev.run_cf(state_for_case(c), c["what_if"], c["id"], c["gt"]["counterfactual"]) for c in cases]
    print(f"counterfactual main: {len(main_entries)} queries in {time.perf_counter() - t0:.1f}s", flush=True)

    # 3. supplementary: every MOVE and FIX_ARC query on the reference optimum
    supp = []
    if not args.no_supplementary:
        ref = next(c for c in cases if not c["model_modifications"])["solution"]
        st = make_state(ref)
        t0 = time.perf_counter()
        for q in supplementary_queries(ref):
            qid = "S:" + q["type"] + "(" + ",".join(str(q[k]) for k in ("k", "i", "j") if k in q) + ")"
            supp.append(ev.run_cf(st, q, qid, counterfactual_gt(base, [], ref, q)))
        print(f"counterfactual supplementary: {len(supp)} queries in {time.perf_counter() - t0:.1f}s", flush=True)

    # 4. localization (runs), then again with the simulated clarification answer
    loc = []
    for run in range(args.runs):
        per = {}
        for c in cases:
            st = state_for_case(c)
            r = localize(st, c["complaint"], llm, c["id"], run)
            ev.check("localization_output", r, f"{c['id']}/localize/{run}")
            q = r["clarifying_question"] or GENERIC_QUESTION
            r2 = localize(st, c["complaint"], llm, c["id"], run, clarification={"question": q, "answer": c["clarification_answer"]})
            ev.check("localization_output", r2, f"{c['id']}/localize_clarified/{run}")
            per[c["id"]] = {"initial": r, "clarified": r2}
            print(f"localize run {run} {c['id']}: {r['confidence']} {r['diagnostics']['majority_target']} -> "
                  f"{r2['confidence']} {r2['diagnostics']['majority_target']}", flush=True)
        loc.append(per)

    raw = {"attribution": att, "counterfactual_main": main_entries, "counterfactual_supplementary": supp,
           "localization": loc}
    meta["finished"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    meta["schema_errors"] = ev.schema_errors
    for name, obj in list(raw.items()) + [("meta", meta)]:
        with open(os.path.join(raw_dir, f"{name}.json"), "w") as f:
            json.dump(obj, f, indent=1)
    results = {"meta": meta, "metrics": metrics.compute_all(cases, raw, args.runs)}
    with open(os.path.join(out_dir, "task2_results.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps({"schema_errors": len(ev.schema_errors)}, indent=1))


if __name__ == "__main__":
    main()
