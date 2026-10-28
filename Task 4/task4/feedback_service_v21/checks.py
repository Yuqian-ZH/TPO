"""Start-up check of the task4_v2.1 service: v2's checks (the Task 3 code both Task 3 protocols froze) and the Task 2
files Task 2's protocol_v21.json froze (the v2.1 components)."""
import json
import os

from feedback_service.bridge import TASK2_ROOT, t2
from feedback_service_v2.checks import startup_checks as startup_checks_v2

TASK2_PROTOCOL_V21 = os.path.join(TASK2_ROOT, "v21", "protocol_v21.json")


def task2_v21_protocol_check():
    if not os.path.exists(TASK2_PROTOCOL_V21):
        return {"ok": False, "changed": ["v21/protocol_v21.json missing"], "files": 0}
    from v21.freeze import frozen_files        # Task 2's package, on sys.path through the bridge
    with open(TASK2_PROTOCOL_V21) as f:
        frozen = json.load(f)["file_sha256"]
    now = {p: t2.sha256(os.path.join(TASK2_ROOT, p)) for p in frozen_files()}
    changed = sorted(p for p in set(frozen) | set(now) if frozen.get(p) != now.get(p))
    return {"ok": not changed, "changed": changed, "files": len(frozen)}


def startup_checks():
    v2, v21 = startup_checks_v2(), task2_v21_protocol_check()
    return {"ok": v2["ok"] and v21["ok"], "task3_v1": v2["task3_v1"], "task3_v2": v2["task3_v2"], "task2_v21": v21}
