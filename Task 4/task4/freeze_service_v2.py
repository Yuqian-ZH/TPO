"""Freeze the task4_v2 service before its test-case end-to-end run. e2e_client_v2.py refuses test cases unless every
hash recorded here still matches; an existing freeze is never overwritten. service_freeze.json (task4_v1) stays."""
import datetime
import glob
import json
import os
import sys

sys.dont_write_bytecode = True

from feedback_service.bridge import TASK3_ROOT, TASK4_ROOT, t2  # noqa: E402
from feedback_service_v2.checks import TASK3_PROTOCOL_V2, startup_checks  # noqa: E402

FREEZE = os.path.join(TASK4_ROOT, "service_freeze_v2.json")
SOURCES = ["feedback_service/*.py", "feedback_service_v2/*.py", "serve_v2.py", "e2e_client.py", "e2e_client_v2.py",
           "scenarios/*.json"]
TEST_CASES = os.path.join(t2.TASK2_ROOT, "cases", "test_cases.json")


def current():
    hashes = {os.path.relpath(p, TASK4_ROOT): t2.sha256(p) for pat in SOURCES
              for p in sorted(glob.glob(os.path.join(TASK4_ROOT, pat)))}
    hashes["<task3>/protocol.json"] = t2.sha256(os.path.join(TASK3_ROOT, "protocol.json"))
    hashes["<task3>/protocol_v2.json"] = t2.sha256(TASK3_PROTOCOL_V2) if os.path.exists(TASK3_PROTOCOL_V2) else None
    hashes["<task2>/cases/test_cases.json"] = t2.sha256(TEST_CASES)
    hashes["<task2>/instance/cvrp_instance.json"] = t2.sha256(t2.INSTANCE)
    return {"hashes": hashes, "startup_checks": startup_checks()}


def read_freeze():
    if not os.path.exists(FREEZE):
        return None
    with open(FREEZE) as f:
        return json.load(f)


def main():
    if os.path.exists(FREEZE):
        sys.exit(f"refused: {FREEZE} exists; keep it (rename it to supersede, and say why in DECISIONS.md)")
    now = current()
    if not now["startup_checks"]["ok"]:
        sys.exit(f"refused: Task 3 files differ from its protocols: {now['startup_checks']}")
    t2.load_frozen_instance()
    rec = {"protocol": "task4_v2", "frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "why": "audit F2 (state change judged by routes alone) and the v2 components (F1 attribution, F5 / T7 "
                  "localization); task4_v1 and its results stay as frozen",
           **now, "e2e": {"cases": "Task 2 test cases (10)", "configs": ["A0B0C1", "A1B1C1"], "runs": 1,
                          "restart_at": "A0B0C1:5", "max_requests": 400,
                          "audit_scenario": "scenarios/audit_cases.json, both configurations, v1 and v2 services"}}
    with open(FREEZE, "w") as f:
        json.dump(rec, f, indent=1)
    print(json.dumps({k: rec[k] for k in ("protocol", "frozen_at")}, indent=1))


if __name__ == "__main__":
    main()
