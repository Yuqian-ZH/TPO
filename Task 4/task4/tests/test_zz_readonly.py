"""Plan 5.1 item 11, run last: Task 2 and Task 3 are exactly as they were when the test run started, and
nothing wrote bytecode or caches into Task 4."""
import glob
import os

from feedback_service.bridge import TASK2_ROOT, TASK3_ROOT, TASK4_ROOT

from conftest import BEFORE, file_snapshot


def test_task2_and_task3_untouched():
    assert file_snapshot(TASK2_ROOT) == BEFORE["task2"]
    assert file_snapshot(TASK3_ROOT) == BEFORE["task3"]


def test_no_bytecode_or_caches_in_task4():
    found = [p for p in glob.glob(os.path.join(TASK4_ROOT, "**"), recursive=True)
             if os.path.basename(p) in ("__pycache__", ".pytest_cache")]
    assert not found
