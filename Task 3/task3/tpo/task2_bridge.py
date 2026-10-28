"""Read-only access to the Task 2 code base (another session is still writing it).

Task 3 never writes into Task 2: bytecode writing is switched off before anything from Task 2 is imported."""
import hashlib
import json
import os
import sys

sys.dont_write_bytecode = True

TASK3_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK2_ROOT = os.path.normpath(os.path.join(TASK3_ROOT, "..", "..", "Task 2", "task2"))
INSTANCE = os.path.join(TASK2_ROOT, "instance", "cvrp_instance.json")
FROZEN = os.path.join(TASK2_ROOT, "FROZEN.json")

if TASK2_ROOT not in sys.path:
    # appended, not prepended: Task 2 also has freeze_protocol.py / recompute.py at its root, and Task 3's own
    # modules of the same name must win (2026-10-23 the prepended path made the protocol check import Task 2's)
    sys.path.append(TASK2_ROOT)

from cases import checkers  # noqa: E402
from cvrp import canon, ids  # noqa: E402
from cvrp.data import apply_data_mods, load_instance, make_data  # noqa: E402
from cvrp.model import CVRPModel  # noqa: E402
from cvrp.oracle import oracle_for  # noqa: E402

__all__ = ["checkers", "canon", "ids", "apply_data_mods", "load_instance", "make_data", "CVRPModel", "oracle_for",
           "TASK2_ROOT", "TASK3_ROOT", "INSTANCE", "FROZEN", "sha256", "load_frozen_instance"]


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_frozen_instance():
    """The Task 2 instance, after checking its hash against Task 2's freeze record."""
    with open(FROZEN) as f:
        expected = json.load(f)["instance"]["sha256"]
    actual = sha256(INSTANCE)
    if actual != expected:
        raise RuntimeError(f"Task 2 instance hash {actual} does not match FROZEN.json {expected}")
    return load_instance(INSTANCE)
