"""Feedback validator (DESIGN.md section 3.4): solver-backed checks that decide whether a piece of user feedback
may become training data. Importing the package puts Task 4 (and through it Tasks 3 and 2) on sys.path read-only."""
import os
import sys

sys.dont_write_bytecode = True

TASK5_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK4_ROOT = os.path.join(os.path.dirname(os.path.dirname(TASK5_ROOT)), "Task 4", "task4")
if TASK4_ROOT not in sys.path:
    sys.path.append(TASK4_ROOT)

from feedback_service import bridge  # noqa: E402,F401
