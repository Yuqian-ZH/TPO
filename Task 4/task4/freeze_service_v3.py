"""Freeze the task4_v3 service before its test-case run (e2e_client_v3.py refuses unless every hash here still
matches); an existing freeze is never overwritten. Earlier freezes stay as they are."""
import datetime
import glob
import json
import os
import sys

sys.dont_write_bytecode = True

from feedback_service.bridge import TASK3_ROOT, TASK4_ROOT, t2  # noqa: E402
from feedback_service_v21.checks import startup_checks  # noqa: E402
from freeze_service_v21 import current as current_v21  # noqa: E402

FREEZE = os.path.join(TASK4_ROOT, "service_freeze_v3.json")
SOURCES = ["feedback_service_v3/*.py", "serve_v3.py", "e2e_client_v3.py", "freeze_service_v3.py",
           "tests/test_v3_service.py"]


def current():
    hashes = {os.path.relpath(p, TASK4_ROOT): t2.sha256(p) for pat in SOURCES
              for p in sorted(glob.glob(os.path.join(TASK4_ROOT, pat)))}
    hashes.update({f"v21:{k}": v for k, v in current_v21()["hashes"].items()})
    hashes["<task3>/protocol_v3.json"] = t2.sha256(os.path.join(TASK3_ROOT, "protocol_v3.json"))
    hashes["<task2>/v3/protocol_v3.json"] = t2.sha256(os.path.join(t2.TASK2_ROOT, "v3", "protocol_v3.json"))
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
        sys.exit(f"refused: Task 2 / Task 3 files differ from their protocols: {now['startup_checks']}")
    rec = {"protocol": "task4_v3", "frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "why": "DESIGN_V3.md: task3_v3's loop (every iteration from the plan complained about) and Task 2's v3 "
                  "test cases with the v3 simulated user",
           **now, "e2e": {"cases": "Task 2 v3 test cases (10)", "configs": ["A0B0C1", "A1B1C1"], "runs": 1}}
    with open(FREEZE, "w") as f:
        json.dump(rec, f, indent=1)
    print(json.dumps({k: rec[k] for k in ("protocol", "frozen_at")}, indent=1))


if __name__ == "__main__":
    main()
