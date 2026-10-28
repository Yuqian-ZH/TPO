"""Start-up check of the task4_v2 service: the Task 3 code it runs is the code both Task 3 protocols froze
(protocol.json for tpo/, protocol_v2.json for tpo_v2/ and Task 2's v2 package)."""
import importlib.util
import json
import os

from feedback_service.bridge import TASK3_ROOT, task3_protocol_check

TASK3_PROTOCOL_V2 = os.path.join(TASK3_ROOT, "protocol_v2.json")


def _task3_freeze_v2_module():
    # loaded by path, like bridge._task3_freeze_module: several roots on sys.path have a freeze_protocol.py
    spec = importlib.util.spec_from_file_location("task3_freeze_protocol_v2",
                                                  os.path.join(TASK3_ROOT, "freeze_protocol_v2.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def task3_v2_protocol_check():
    if not os.path.exists(TASK3_PROTOCOL_V2):
        return {"ok": False, "changed": ["protocol_v2.json missing"], "files": 0}
    with open(TASK3_PROTOCOL_V2) as f:
        frozen = json.load(f)["hashes"]
    now = _task3_freeze_v2_module().current()
    changed = sorted(f"{g}:{p}" for g in frozen for p in set(frozen[g]) | set(now[g])
                     if frozen[g].get(p) != now[g].get(p))
    return {"ok": not changed, "changed": changed, "files": sum(len(v) for v in frozen.values())}


def startup_checks():
    v1, v2 = task3_protocol_check(), task3_v2_protocol_check()
    return {"ok": v1["ok"] and v2["ok"], "task3_v1": v1, "task3_v2": v2}
