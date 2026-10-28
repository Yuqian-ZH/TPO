"""Plan section 8 acceptance checklist, run after the test-case end-to-end run. Writes results/acceptance.json.
Reads the credential from the environment only to search for it; it is never printed or written."""
import glob
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True

from e2e_client import TERMINAL, load_cases  # noqa: E402
from feedback_service.bridge import TASK2_ROOT, TASK3_ROOT, TASK4_ROOT, t2, task3_protocol_check  # noqa: E402
from freeze_service import TEST_CASES, current, read_freeze  # noqa: E402
from report_e2e import REQUIRED, load  # noqa: E402
from snapshot_env import pycache_files  # noqa: E402

OUT = os.path.join(TASK4_ROOT, "results", "e2e_test")
INBOUND = ("session_created", "feedback_received", "clarification_received", "reply_received")


def main():
    checks, notes = {}, {}
    t3 = task3_protocol_check()
    try:
        t2.load_frozen_instance()
        inst_ok = True
    except RuntimeError:
        inst_ok = False
    checks["task3_frozen_hashes_and_task2_instance"] = t3["ok"] and inst_ok
    frozen, now = read_freeze(), current()
    checks["service_code_matches_freeze"] = bool(frozen) and frozen["hashes"] == now["hashes"]

    run = load(OUT)
    cases = load_cases(TEST_CASES)
    expected = {(g, c["id"]) for g in ("A0B0C1", "A1B1C1") for c in cases}
    got = [(r["config"], r["case_id"]) for r in run["results"]]
    checks["e2e_all_cases_reached_a_final_state"] = (set(got) == expected and len(got) == len(expected)
                                                     and all(r["status"] in TERMINAL for r in run["results"])
                                                     and not run["aborted"]
                                                     and run["final_check"]["all_sessions_present"]
                                                     and run["final_check"]["none_open"])
    checks["feedback_stored_with_complaint_solution_session"] = all(
        r["record"]["complaint"] and r["record"]["session_id"] == r["session_id"]
        and r["record"]["solution"]["routes"] and "version" in r["record"]["solution"] for r in run["results"])
    logs = [x for r in run["results"] for x in r["iteration_log"]]
    checks["iteration_log_complete"] = bool(logs) and all(
        all(k in x for k in REQUIRED) and x["feasibility"]["solver_status"] and "feasible" in x["feasibility"]
        and x["critique"]["text"] for x in logs)
    notes["iteration_records"] = len(logs)
    rs = run["restart"] or {}
    checks["restart_check"] = (rs.get("status_before") == rs.get("status_after_restart") == "awaiting_reply"
                               and rs.get("plan_version_before") == rs.get("plan_version_after_restart")
                               and not rs.get("recovered_at_startup"))

    by_id = {c["id"]: c for c in cases}
    leaks = []
    for r in run["results"]:
        c = by_id[r["case_id"]]
        d = os.path.join(OUT, "store", "sessions", r["session_id"])
        everything = ""
        for p in glob.glob(os.path.join(d, "**", "*"), recursive=True):
            if os.path.isfile(p):
                with open(p) as f:
                    everything += f.read()
        for s in (json.dumps(c["checker"]), f'"name": "{c["checker"]["name"]}"', c["why_question"],
                  c["what_if_question"], c["scenario"]):
            if s in everything:
                leaks.append((r["config"], r["case_id"], s[:40]))
        inbound = json.dumps([e for e in r["events"] if e["event"] in INBOUND], ensure_ascii=False)
        ref = json.dumps(c["reference_modification"][0], separators=(", ", ": "))
        if ref in inbound or ref.replace(", ", ",") in inbound:
            leaks.append((r["config"], r["case_id"], "reference_modification sent by the client"))
        if not r["clarified"] and c["clarification_answer"] in inbound:
            leaks.append((r["config"], r["case_id"], "clarification answer sent without being asked"))
    checks["no_private_case_fields_reached_the_service"] = not leaks

    key = os.environ.get("DASHSCOPE_API_KEY")
    hits = []
    if key:
        for p in glob.glob(os.path.join(os.path.dirname(TASK4_ROOT), "**", "*"), recursive=True):
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    if key.encode() in f.read():
                        hits.append(os.path.relpath(p, TASK4_ROOT))
    checks["no_credential_in_task4"] = bool(key) and not hits
    with open(os.path.join(TASK4_ROOT, "env.json")) as f:
        env = json.load(f)
    caches = [p for root in (TASK4_ROOT, TASK3_ROOT) for p in glob.glob(os.path.join(root, "**"), recursive=True)
              if os.path.basename(p) in ("__pycache__", ".pytest_cache")]
    checks["no_bytecode_written_by_task4"] = (not caches and pycache_files(TASK2_ROOT) ==
                                              env["task2_pycache_before_task4"])
    py = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=TASK4_ROOT, capture_output=True, text=True,
                        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    checks["pytest"] = py.returncode == 0
    report = {"checks": checks, "all_passed": all(checks.values()), "notes": notes,
              "pytest_tail": py.stdout.strip().splitlines()[-1:], "task3_changed": t3["changed"],
              "private_field_hits": leaks, "credential_hits": hits, "caches": caches}
    with open(os.path.join(TASK4_ROOT, "results", "acceptance.json"), "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
