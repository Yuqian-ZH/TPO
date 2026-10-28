"""Freeze the task4_v31 service before its test-case run (e2e_client_v31.py refuses unless every hash here still
matches); an existing freeze is never overwritten. Earlier freezes stay as they are."""
import datetime
import glob
import json
import os
import sys

sys.dont_write_bytecode = True

from feedback_service.bridge import TASK3_ROOT, TASK4_ROOT, t2  # noqa: E402
from feedback_service_v21.checks import startup_checks  # noqa: E402
from freeze_service_v3 import current as current_v3  # noqa: E402

FREEZE = os.path.join(TASK4_ROOT, "service_freeze_v31.json")
SOURCES = ["feedback_service_v31/*.py", "serve_v31.py", "e2e_client_v31.py", "freeze_service_v31.py",
           "tests/test_v31_service.py"]


def current():
    hashes = {os.path.relpath(p, TASK4_ROOT): t2.sha256(p) for pat in SOURCES
              for p in sorted(glob.glob(os.path.join(TASK4_ROOT, pat)))}
    hashes.update({f"v3:{k}": v for k, v in current_v3()["hashes"].items()})
    hashes["<task3>/protocol_v31.json"] = t2.sha256(os.path.join(TASK3_ROOT, "protocol_v31.json"))
    return {"hashes": hashes, "startup_checks": startup_checks()}


def read_freeze():
    if not os.path.exists(FREEZE):
        return None
    with open(FREEZE) as f:
        return json.load(f)


def main():
    if os.path.exists(FREEZE):
        sys.exit(f"refused: {FREEZE} exists; keep it (rename it to supersede, and say why in DECISIONS.md)")
    if not os.path.exists(os.path.join(TASK3_ROOT, "protocol_v31.json")):
        sys.exit("refused: freeze Task 3's protocol_v31.json first")
    now = current()
    if not now["startup_checks"]["ok"]:
        sys.exit(f"refused: Task 2 / Task 3 files differ from their protocols: {now['startup_checks']}")
    rec = {"protocol": "task4_v31", "frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "why": "DESIGN_V31.md: task3_v31's prompt (the session's own modifications are shown); otherwise task4_v3",
           **now, "e2e": {"cases": "Task 2 v3 test cases (10)", "configs": ["A1B1C1"], "runs": 1}}
    with open(FREEZE, "w") as f:
        json.dump(rec, f, indent=1)
    print(json.dumps({k: rec[k] for k in ("protocol", "frozen_at")}, indent=1))


if __name__ == "__main__":
    main()
