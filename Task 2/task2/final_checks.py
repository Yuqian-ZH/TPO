"""Section 13 acceptance checklist -> results/acceptance.json. Needs DASHSCOPE_* in the environment only
to scan for them; their values are never printed or written.   python final_checks.py"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def sha256(rel):
    return hashlib.sha256(open(os.path.join(ROOT, rel), "rb").read()).hexdigest()


def run(args):
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def credential_scan():
    secrets = [v for v in (os.environ.get("DASHSCOPE_API_KEY"), os.environ.get("DASHSCOPE_BASE_URL")) if v]
    if not secrets:
        return {"ok": False, "detail": "credentials not in the environment; scan not performed"}
    hits, scanned = [], 0
    for d, _, files in os.walk(ROOT):
        if "__pycache__" in d:
            continue
        for f in files:
            path = os.path.join(d, f)
            data = open(path, "rb").read()
            scanned += 1
            if any(s.encode() in data for s in secrets):
                hits.append(os.path.relpath(path, ROOT))
    return {"ok": not hits, "files_scanned": scanned, "files_with_credentials": hits,
            "secrets_checked": ["DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL"]}


def main():
    checks = {}
    oracle = json.load(open(os.path.join(ROOT, "instance", "oracle_report.json")))
    frozen = json.load(open(os.path.join(ROOT, "FROZEN.json")))
    proto = json.load(open(os.path.join(ROOT, "protocol.json")))
    checks["gurobi_equals_exhaustive_and_D1_D5"] = {
        "ok": oracle["gurobi_check"]["objective_equal"] and oracle["gurobi_check"]["routes_equal"]
        and oracle["all_design_goals_met"]}
    mism = [p for p, h in proto["file_sha256"].items() if sha256(p) != h]
    checks["hashes_match_freeze_records"] = {
        "ok": sha256(frozen["instance"]["file"]) == frozen["instance"]["sha256"] == proto["instance_sha256"]
        and sha256(frozen["test_cases"]["file"]) == frozen["test_cases"]["sha256"] == proto["test_cases_sha256"]
        and not mism, "protocol_files_changed": mism}
    code, out = run([PY, "-m", "cases.verify_cases"])
    checks["verify_cases"] = {"ok": code == 0}
    res = json.load(open(os.path.join(ROOT, "results", "task2_results.json")))
    checks["component_outputs_pass_schemas"] = {"ok": not res["meta"]["schema_errors"],
                                                "violations": len(res["meta"]["schema_errors"])}
    loc = res["metrics"]["localization"]
    checks["no_low_confidence_critique"] = {"ok": loc["low_with_critique_total"] == 0,
                                            "count": loc["low_with_critique_total"]}
    cf = [res["metrics"]["counterfactual_main"], res["metrics"].get("counterfactual_supplementary", {})]
    before = sum(m.get("local_infeasible_before_L2", 0) for m in cf)
    checks["local_never_infeasible_before_L2"] = {"ok": before == 0, "count": before}
    code, out = run([PY, "recompute.py"])
    checks["recompute_identical"] = {"ok": code == 0, "output": out.strip()[-200:]}
    checks["no_credentials_in_logs_or_artifacts"] = credential_scan()
    code, out = run([PY, "-m", "pytest", "-q"])
    checks["pytest"] = {"ok": code == 0, "summary": out.strip().splitlines()[-1] if out.strip() else ""}
    ok = all(v["ok"] for v in checks.values())
    with open(os.path.join(ROOT, "results", "acceptance.json"), "w") as f:
        json.dump({"all_ok": ok, "checks": checks}, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({k: v["ok"] for k, v in checks.items()} | {"all_ok": ok}, indent=1))


if __name__ == "__main__":
    main()
