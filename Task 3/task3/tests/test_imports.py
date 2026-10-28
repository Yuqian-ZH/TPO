"""Task 2 and Task 3 share module names at their roots (freeze_protocol, recompute); Task 3's must win."""
import importlib
import os

from tpo import task2_bridge

TASK3_ROOT = task2_bridge.TASK3_ROOT


def test_task3_modules_shadow_task2_ones():
    for name in ("freeze_protocol", "recompute", "run_experiment", "stats"):
        mod = importlib.import_module(name)
        assert os.path.dirname(os.path.abspath(mod.__file__)) == TASK3_ROOT, (name, mod.__file__)
    assert hasattr(importlib.import_module("freeze_protocol"), "current")


def test_task2_packages_still_importable():
    for name in ("cvrp.canon", "cases.checkers", "components.localization"):
        mod = importlib.import_module(name)
        assert os.path.abspath(mod.__file__).startswith(task2_bridge.TASK2_ROOT), (name, mod.__file__)
