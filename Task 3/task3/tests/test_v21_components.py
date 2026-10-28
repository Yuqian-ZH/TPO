"""task3_v2.1: the tpo_v2 adapter over Task 2's task2_v2.1 components (Task 2 README 8.4)."""
import pytest

from tpo.llm import StubLLM
from tpo_v2.components import Task2ComponentsV2
from tpo_v21.components import Task2ComponentsV21

# Task 2's review example: weight 0.8 on balance and W[1] <= 90; the plan (412.8) is optimal under customer 5's anchor
TOL_MODS = [{"op": "set_objective_weight", "term": "balance", "weight": 0.8},
            {"op": "add_soft_constraint", "target": "W[1]", "sense": "<=", "rhs": 90, "penalty": 1}]
TOL_PLAN = {"routes": [[1, 7, 2, 8], [4, 5, 3, 6]]}


@pytest.fixture(scope="module")
def comps(base):
    return Task2ComponentsV2(base, StubLLM([])), Task2ComponentsV21(base, StubLLM([]))


def test_exact_anchor_reaches_the_prompt(comps):
    v2, v21 = comps
    d = {"type": "SAME", "i": 1, "j": 2}
    old, new = v2.attribute(TOL_MODS, TOL_PLAN, d), v21.attribute(TOL_MODS, TOL_PLAN, d)
    assert old["conclusion"] == "cheaper_without" and old["objective_increase_if_forbidden"] < 0
    assert new["conclusion"] == "objective_preferred" and new["objective_increase_if_forbidden"] > 0
    assert new["raw"]["protocol"] == "task2_v2.1"


def test_plan_over_capacity_gives_no_alternative(comps):
    _, v21 = comps
    a = v21.attribute([{"op": "modify_data", "field": "demand[4]", "value": 20}],
                      {"routes": [[1, 4, 7, 2], [5, 3, 6, 8]]}, {"type": "ADJ", "i": 3, "j": 6})
    assert a["conclusion"] == "current_plan_infeasible"
    assert (a["constraint_ids"], a["variable_ids"]) == ([], [])
    assert "objective_increase_if_forbidden" not in a


def test_localization_is_v21(comps):
    _, v21 = comps
    assert v21.loc.RULE["agree_on"] == ["target", "direction", "limit"]
