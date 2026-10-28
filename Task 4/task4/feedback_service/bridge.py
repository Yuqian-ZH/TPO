"""Read-only access to Task 3's TPO loop core and, through Task 3's own bridge, to Task 2.

Nothing is ever written into either directory: bytecode writing is switched off before anything is imported,
and Task 3 is appended (not prepended) to sys.path so that module names here always win."""
import importlib.util
import json
import os
import sys

sys.dont_write_bytecode = True

TASK4_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USC_ROOT = os.path.dirname(os.path.dirname(TASK4_ROOT))
TASK3_ROOT = os.path.join(USC_ROOT, "Task 3", "task3")

if TASK3_ROOT not in sys.path:
    sys.path.append(TASK3_ROOT)

from tpo import task2_bridge as t2  # noqa: E402
from tpo.loop import CONFIGS, MAIN, Settings, Trial, probe_agreement  # noqa: E402
from tpo.proposal import check_modification  # noqa: E402
from tpo.public_case import PublicCase  # noqa: E402
from tpo.user_sim import FEEDBACK_UNRESOLVED, NOTE_NO_PLAN, NOTE_REJECTED  # noqa: E402

TASK2_ROOT = t2.TASK2_ROOT
canon, apply_data_mods, CVRPModel = t2.canon, t2.apply_data_mods, t2.CVRPModel
TASK3_PROTOCOL = os.path.join(TASK3_ROOT, "protocol.json")

__all__ = ["TASK4_ROOT", "TASK3_ROOT", "TASK2_ROOT", "t2", "canon", "apply_data_mods", "CVRPModel", "CONFIGS",
           "MAIN", "Settings", "Trial", "probe_agreement", "check_modification", "PublicCase",
           "FEEDBACK_UNRESOLVED", "NOTE_NO_PLAN", "NOTE_REJECTED", "task3_protocol_check", "load_instance_spec"]


def _task3_freeze_module():
    # loaded by path: Task 2's root has a freeze_protocol.py too, and both roots are on sys.path
    spec = importlib.util.spec_from_file_location("task3_freeze_protocol", os.path.join(TASK3_ROOT,
                                                                                       "freeze_protocol.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def task3_protocol_check():
    """Every hash in Task 3's protocol.json against the files as they are now (the loop the service runs is
    the loop Task 3 measured)."""
    with open(TASK3_PROTOCOL) as f:
        frozen = json.load(f)["hashes"]
    now = _task3_freeze_module().current()
    changed = sorted(f"{g}:{p}" for g in frozen for p in set(frozen[g]) | set(now[g])
                     if frozen[g].get(p) != now[g].get(p))
    return {"ok": not changed, "changed": changed, "files": sum(len(v) for v in frozen.values())}


def load_instance_spec():
    """The public instance specification (coordinates, demands, capacity, objective, conventions)."""
    with open(t2.INSTANCE) as f:
        return json.load(f)
