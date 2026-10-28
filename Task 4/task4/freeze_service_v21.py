"""Freeze the task4_v2.1 service before its re-check (recheck_v21.py refuses unless every hash here still matches);
an existing freeze is never overwritten. service_freeze.json (task4_v1) and service_freeze_v2.json (task4_v2) stay."""
import datetime
import glob
import json
import os
import sys

sys.dont_write_bytecode = True

from feedback_service.bridge import TASK3_ROOT, TASK4_ROOT, t2  # noqa: E402
from feedback_service_v21.checks import TASK2_PROTOCOL_V21, startup_checks  # noqa: E402

FREEZE = os.path.join(TASK4_ROOT, "service_freeze_v21.json")
SOURCES = ["feedback_service/*.py", "feedback_service_v2/*.py", "feedback_service_v21/*.py", "serve_v21.py",
           "recheck_v21.py", "freeze_service_v21.py", "tests/test_v21_service.py"]
TASK3_SOURCES = ["tpo_v21/*.py", "recheck_v21.py"]


def current():
    hashes = {os.path.relpath(p, TASK4_ROOT): t2.sha256(p) for pat in SOURCES
              for p in sorted(glob.glob(os.path.join(TASK4_ROOT, pat)))}
    hashes.update({"<task3>/" + os.path.relpath(p, TASK3_ROOT): t2.sha256(p) for pat in TASK3_SOURCES
                   for p in sorted(glob.glob(os.path.join(TASK3_ROOT, pat)))})
    hashes["<task3>/protocol.json"] = t2.sha256(os.path.join(TASK3_ROOT, "protocol.json"))
    hashes["<task3>/protocol_v2.json"] = t2.sha256(os.path.join(TASK3_ROOT, "protocol_v2.json"))
    hashes["<task2>/v21/protocol_v21.json"] = t2.sha256(TASK2_PROTOCOL_V21) if os.path.exists(TASK2_PROTOCOL_V21) \
        else None
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
    rec = {"protocol": "task4_v2.1", "frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "why": "review of task4_v2 after its runs: a data change was always shown as the user's applied "
                  "correction (wrong after a rejection that reverts it, and for data the LLM changed on its own); "
                  "the v2.1 components (Task 2 README 8.4)",
           **now, "check": "recheck_v21.py re-computes the v2.1 rule and components on the records of e2e_dev_v2, "
                           "e2e_test_v2 and audit_v2; no LLM, no new end-to-end run"}
    with open(FREEZE, "w") as f:
        json.dump(rec, f, indent=1)
    print(json.dumps({k: rec[k] for k in ("protocol", "frozen_at")}, indent=1))


if __name__ == "__main__":
    main()
