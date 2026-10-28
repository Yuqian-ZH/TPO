"""The validator's verdicts on the demonstration scenarios, its determinism, and that Tasks 1 to 4 stay untouched."""
import glob
import os
import sys

sys.dont_write_bytecode = True

from validator import TASK4_ROOT, TASK5_ROOT  # noqa: E402
from validator.demo import run  # noqa: E402

USC = os.path.dirname(os.path.dirname(TASK5_ROOT))


def snapshot():
    out = {}
    for task in ("Task 1", "Task 2", "Task 3", "Task 4"):
        for d, _, files in os.walk(os.path.join(USC, task)):
            for f in files:
                st = os.stat(os.path.join(d, f))
                out[os.path.join(d, f)] = (st.st_size, st.st_mtime_ns)
    return out


BEFORE = snapshot()
ROWS = run()


def test_every_scenario_gets_its_expected_verdict():
    assert [(r["id"], r["verdict"]) for r in ROWS] == [(r["id"], r["expected"]) for r in ROWS]


def test_the_binding_input_is_named():
    by_id = {r["id"]: r for r in ROWS}
    assert [m["target"] for m in by_id["V1"]["binding_user_inputs"]] == ["W[1]"]
    assert by_id["V2"]["binding_user_inputs"] == [{"op": "modify_data", "field": "demand[3]", "value": 54}]
    assert by_id["V2b"]["binding_user_inputs"] == [] and by_id["V7"]["binding_user_inputs"] == []


def test_an_input_without_which_there_is_no_plan_is_evidence_not_a_crash():
    """Audit F6: the v1 validator raised KeyError when dropping a user input left no feasible plan."""
    r = {x["id"]: x for x in ROWS}["V9"]
    rec = {m["input"]["field"]: m for m in r["evidence"]["without_each_user_input"]}
    assert rec["capacity"]["feasible_without_it"] is False
    assert r["binding_user_inputs"] == [{"op": "modify_data", "field": "demand[3]", "value": 62}]


def test_controls_raise_no_flags():
    assert all(not r["flags"] for r in ROWS if r["id"] in ("V6", "V7", "V8"))


def test_deterministic():
    assert run() == ROWS


def test_tasks_1_to_4_untouched_and_no_bytecode():
    assert snapshot() == BEFORE
    assert not [p for p in glob.glob(os.path.join(TASK5_ROOT, "**"), recursive=True)
                if os.path.basename(p) in ("__pycache__", ".pytest_cache")]
    assert os.path.isdir(TASK4_ROOT)
