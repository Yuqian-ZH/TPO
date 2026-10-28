"""Stage 3 (plan 5.3): freeze the service code before the test-case end-to-end run. e2e_client.py refuses test
cases unless every hash recorded here still matches; an existing freeze is never overwritten."""
import datetime
import glob
import json
import os
import sys

sys.dont_write_bytecode = True

from feedback_service.bridge import TASK3_PROTOCOL, TASK4_ROOT, t2, task3_protocol_check  # noqa: E402

FREEZE = os.path.join(TASK4_ROOT, "service_freeze.json")
SOURCES = ["feedback_service/*.py", "serve.py", "e2e_client.py"]
TEST_CASES = os.path.join(t2.TASK2_ROOT, "cases", "test_cases.json")


def current():
    hashes = {os.path.relpath(p, TASK4_ROOT): t2.sha256(p) for pat in SOURCES
              for p in sorted(glob.glob(os.path.join(TASK4_ROOT, pat)))}
    hashes["<task3>/protocol.json"] = t2.sha256(TASK3_PROTOCOL)
    hashes["<task2>/cases/test_cases.json"] = t2.sha256(TEST_CASES)
    hashes["<task2>/instance/cvrp_instance.json"] = t2.sha256(t2.INSTANCE)
    return {"hashes": hashes, "task3_protocol_check": task3_protocol_check()}


def read_freeze():
    if not os.path.exists(FREEZE):
        return None
    with open(FREEZE) as f:
        return json.load(f)


def main():
    if os.path.exists(FREEZE):
        sys.exit(f"refused: {FREEZE} exists; keep it (rename it to supersede, and say why in DECISIONS.md)")
    now = current()
    if not now["task3_protocol_check"]["ok"]:
        sys.exit(f"refused: Task 3 files changed: {now['task3_protocol_check']['changed']}")
    t2.load_frozen_instance()
    rec = {"protocol": "task4_v1", "frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           **now, "e2e": {"cases": "Task 2 test cases (10)", "configs": ["A0B0C1", "A1B1C1"], "runs": 1,
                          "restart_at": "A0B0C1:5", "max_requests": 400}}
    with open(FREEZE, "w") as f:
        json.dump(rec, f, indent=1)
    print(json.dumps(rec, indent=1))


if __name__ == "__main__":
    main()
