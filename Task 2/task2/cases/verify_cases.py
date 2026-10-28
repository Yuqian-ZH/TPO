"""Section 5.4 acceptance for test and dev cases: checker fails on the initial solution, the reference
modification resolves the complaint (oracle and Gurobi), ground truth matches a fresh oracle run and a
Gurobi cross-check, every ID exists, schemas validate, coverage meets section 5.3.
Run from task2/:  python -m cases.verify_cases"""
import hashlib
import json
import os
import re
from collections import Counter

from cvrp import canon, ids
from cvrp.data import apply_data_mods, load_instance
from cvrp.model import CVRPModel
from cvrp.oracle import oracle_for
from cvrp.validate import errors

from .checkers import CHECKERS, complaint_resolved, run_checker
from .gt import attribution_gt, counterfactual_gt, reference_check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOL = 1e-9
OBJVAL_TOL = 1e-3


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def strip(x):
    """GT dicts carry solver-independent data only; compare via JSON round trip."""
    return json.loads(json.dumps(x))


def gurobi_solve(base, mods, prims):
    m = CVRPModel(base, mods)
    for p in prims:
        m.add_primitive(p, "verify")
    out = m.optimize()
    return m, out


def check_ids(case, n, problems):
    def need(cond, what):
        if not cond:
            problems.append(f"{case['id']}: unknown or out-of-range {what}")
    nodes = range(0, n + 1)
    for t in case["gt"]["localization"]["targets"]:
        need(ids.target_exists(t, n), f"localization target {t}")
    d = case["why_decision"]
    need(d["i"] in nodes and d["j"] in nodes and d["i"] != d["j"], f"decision {d}")
    q = case["what_if"]
    for key in ("i", "j"):
        if key in q:
            need(q[key] in nodes, f"query node {q}")
    if "k" in q:
        need(q["k"] in (1, 2), f"query vehicle {q}")
    for m in case["model_modifications"] + case["reference_modification"] + case["allowed_data_corrections"] + \
            (q["mods"] if q["type"] == "APPLY_MODIFICATIONS" else []):
        tid = m.get("target") or m.get("term") or m.get("field")
        need(ids.target_exists(tid, n) or tid in ids.OBJECTIVE_TERMS, f"modification target {tid}")
    for s in case["gt"]["attribution"]["acceptable_sets"]:
        for a in s:
            need(ids.id_exists(a, n), f"attribution ID {a}")
    p = case["checker"]["params"]
    need(case["checker"]["name"] in CHECKERS, f"checker {case['checker']['name']}")
    for key in ("i", "j"):
        if key in p:
            need(p[key] in nodes, f"checker node {p}")
    for key in ("k", "other"):
        if key in p:
            need(p[key] in (1, 2), f"checker vehicle {p}")


def check_schemas(case, problems):
    for name, obj in [("decision", case["why_decision"]), ("query", case["what_if"])] + \
            [("modification", m) for m in case["model_modifications"] + case["reference_modification"]
             + case["allowed_data_corrections"]]:
        for e in errors(name, obj):
            problems.append(f"{case['id']}: {name} schema: {e}")


def verify_case(case, base):
    problems, notes = [], []
    cid, mm, sol = case["id"], case["model_modifications"], case["solution"]
    # 0. structure first: a malformed case cannot be recomputed
    check_schemas(case, problems)
    check_ids(case, base["n"], problems)
    if case["clarity"] == "ambiguous" and case["gt"]["localization"]["confidence"] != "low":
        problems.append(f"{cid}: ambiguous complaint should expect low confidence")
    if problems:
        return problems, notes
    data = apply_data_mods(base, mm)
    # the case solution is the unique optimum of the case model, and Gurobi agrees
    r = oracle_for(base, mm).solve(mm)
    keys = {canon.unlabeled_key(s) for s in r["optimal"]}
    if keys != {canon.unlabeled_key(sol)} or abs(r["objective"] - case["solution_objective"]) > TOL:
        problems.append(f"{cid}: solution is not the unique optimum of the case model")
    _, g = gurobi_solve(base, mm, [])
    if canon.canonical(g["solution"]) != sol:
        problems.append(f"{cid}: Gurobi optimum differs from the case solution")
    # 1. the initial solution fails its checker
    init = run_checker(case, sol, base)
    if init["passed"]:
        problems.append(f"{cid}: initial solution already passes its checker")
    # 2. the reference modification resolves the complaint (oracle: every optimum; Gurobi: its optimum)
    ref = reference_check(base, case)
    if not (ref["feasible"] and ref["all_optimal_resolve"]):
        problems.append(f"{cid}: reference modification does not resolve the complaint (oracle)")
    q = {"type": "APPLY_MODIFICATIONS", "mods": case["reference_modification"]}
    _, qmods, inv = canon.compile_query(q, sol)
    anchor = canon.anchor(inv, sol, base["n"])
    _, g = gurobi_solve(base, mm + qmods, [anchor])
    if g["status"] != "optimal" or not complaint_resolved(case, g["solution"], base)["resolved"]:
        problems.append(f"{cid}: reference modification does not resolve the complaint (Gurobi)")
    elif abs(canon.objective(g["solution"], apply_data_mods(base, mm + qmods), mm + qmods) - ref["objective"]) > TOL:
        problems.append(f"{cid}: Gurobi and oracle disagree on the reference-modification optimum")
    # 3. ground truth equals a fresh oracle computation
    att = attribution_gt(base, mm, sol, case["why_decision"])
    att["part"] = case["gt"]["attribution"]["part"]
    if strip(att) != case["gt"]["attribution"]:
        problems.append(f"{cid}: stored attribution GT differs from the oracle")
    cf = counterfactual_gt(base, mm, sol, case["what_if"])
    if strip(cf) != case["gt"]["counterfactual"]:
        problems.append(f"{cid}: stored counterfactual GT differs from the oracle")
    # ... and with a Gurobi cross-check
    forbid = canon.forbid_decision(case["why_decision"])
    m, g = gurobi_solve(base, mm, [forbid])
    if att["conclusion"] == "objective_preferred":
        if g["status"] != "optimal":
            problems.append(f"{cid}: Gurobi finds the forbidden-decision model infeasible")
        else:
            delta = canon.objective(g["solution"], data, mm) - canon.objective(sol, data, mm)
            cs = canon.change_set(sol, g["solution"])
            edges = sorted({f"e[{a},{b}]" for a, b in cs["added_edges"] + cs["removed_edges"]})
            if abs(delta - att["delta"]) > TOL or edges not in att["acceptable_sets"]:
                problems.append(f"{cid}: Gurobi attribution cross-check failed ({delta}, {edges})")
    else:
        if g["status"] != "infeasible":
            problems.append(f"{cid}: Gurobi finds the forbidden-decision model feasible")
        else:
            iis = m.iis()["constraints"]
            biz = sorted(c for c in iis if ids.category(c) == "business_specific")
            notes.append(f"{cid}: Gurobi IIS business-specific constraints {biz}")
            if biz != sorted(att["acceptable_sets"][0]):
                problems.append(f"{cid}: Gurobi IIS business constraints {biz} != GT")
    prims, qmods, inv = canon.compile_query(case["what_if"], sol)
    anchor = canon.anchor(inv, sol, base["n"])
    _, g = gurobi_solve(base, mm + qmods, prims + [anchor])
    if (g["status"] == "optimal") != cf["feasible"]:
        problems.append(f"{cid}: Gurobi counterfactual feasibility differs from GT")
    elif cf["feasible"]:
        d2 = apply_data_mods(base, mm + qmods)
        if abs(canon.objective(g["solution"], d2, mm + qmods) - cf["objective"]) > TOL or \
                abs(g["objective"] - cf["objective"]) > OBJVAL_TOL:
            problems.append(f"{cid}: Gurobi counterfactual objective differs from GT")
        if canon.change_key(canon.change_set(sol, g["solution"])) not in \
                [canon.change_key(c) for c in cf["acceptable_change_sets"]]:
            problems.append(f"{cid}: Gurobi counterfactual change set not among the acceptable ones")
    return problems, notes


def coverage(cases):
    att = Counter(c["gt"]["attribution"]["conclusion"] for c in cases)
    cf = Counter(c["gt"]["counterfactual"]["outcome"] for c in cases)
    clarity = Counter(c["clarity"] for c in cases)
    mtype = Counter(c["reference_modification"][0]["op"] for c in cases)
    obj = Counter(c["complaint_object"] for c in cases)
    modified = sum(1 for c in cases if c["model_modifications"])
    checks = {
        "attribution capacity_forced >= 2": att["capacity_forced"] >= 2,
        "attribution objective_preferred >= 6": att["objective_preferred"] >= 6,
        "counterfactual feasible_worse >= 4": cf["feasible_worse"] >= 4,
        "counterfactual feasible_unchanged >= 1": cf["feasible_unchanged"] >= 1,
        "counterfactual infeasible_capacity >= 2": cf["infeasible_capacity"] >= 2,
        "clear 6-7": 6 <= clarity["clear"] <= 7,
        "ambiguous 3-4": 3 <= clarity["ambiguous"] <= 4,
        "soft >= 2": mtype["add_soft_constraint"] >= 2,
        "weight >= 2": mtype["set_objective_weight"] >= 2,
        "data >= 2": mtype["modify_data"] >= 2,
        "objects vehicle/customer/data present": all(obj[o] for o in ("vehicle", "customer", "data")),
        "modified-model solutions <= 2": modified <= 2,
        "all complaints": all(c["complaint"] for c in cases),
        "every case has a clarification answer": all(c["clarification_answer"] for c in cases),
    }
    counts = {"attribution": dict(att), "counterfactual": dict(cf), "clarity": dict(clarity),
              "modification_type": dict(mtype), "complaint_object": dict(obj), "modified_model_cases": modified}
    return counts, checks


def main():
    frozen = json.load(open(os.path.join(ROOT, "FROZEN.json")))
    inst_path = os.path.join(ROOT, "instance", "cvrp_instance.json")
    problems = []
    if sha256(inst_path) != frozen["instance"]["sha256"]:
        problems.append("instance hash differs from FROZEN.json")
    base = load_instance(inst_path)
    report = {}
    for split in ("test", "dev"):
        doc = json.load(open(os.path.join(ROOT, "cases", f"{split}_cases.json")))
        if doc["instance_sha256"] != frozen["instance"]["sha256"]:
            problems.append(f"{split}_cases.json was built on a different instance")
        per_case = {}
        for case in doc["cases"]:
            p, notes = verify_case(case, base)
            problems += p
            per_case[case["id"]] = {"ok": not p, "problems": p, "notes": notes}
        report[split] = {"cases": per_case}
        if split == "test":
            counts, checks = coverage(doc["cases"])
            report[split]["coverage"] = counts
            report[split]["coverage_checks"] = checks
            problems += [f"coverage: {k}" for k, ok in checks.items() if not ok]
            if len(doc["cases"]) != 10:
                problems.append("test set must have exactly 10 cases")
    tests = json.load(open(os.path.join(ROOT, "cases", "test_cases.json")))["cases"]
    devs = json.load(open(os.path.join(ROOT, "cases", "dev_cases.json")))["cases"]
    if not 3 <= len(devs) <= 5:
        problems.append("dev set must have 3-5 cases")
    norm = lambda s: re.sub(r"\W+", " ", s.lower()).strip()  # noqa: E731
    for d in devs:
        for t in tests:
            if norm(d["complaint"]) == norm(t["complaint"]) or \
                    (d["why_decision"] == t["why_decision"] and d["what_if"] == t["what_if"]):
                problems.append(f"dev case {d['id']} duplicates test case {t['id']}")
        if set(d["gt"]["localization"]["targets"]) & {x for t in tests for x in t["gt"]["localization"]["targets"]}:
            problems.append(f"dev case {d['id']} shares a localization target with a test case")
    report["problems"] = problems
    report["ok"] = not problems
    with open(os.path.join(ROOT, "cases", "verify_report.json"), "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    print(json.dumps({"ok": report["ok"], "problems": problems, "coverage": report["test"]["coverage"],
                      "coverage_checks": report["test"]["coverage_checks"],
                      "notes": [n for s in ("test", "dev") for c in report[s]["cases"].values() for n in c["notes"]]},
                     indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
