"""task3_v2: Task 2's v2 attribution inside the loop (audit F1), and the guards of the v2 run."""
import json

import pytest

from tpo.llm import StubLLM
from tpo.loop import CONFIGS, Settings, run_trial
from tpo.task2_bridge import canon, oracle_for
from tpo_v2.components import Task2ComponentsV2

import run_experiment_v2 as rv2
from conftest import NO_EFFECT, synthetic_case

# Task 3 v1, A1B1C0 / T2 / run 2, input plan of iteration 3: v1 put 20,114 into the prompt for ADJ(0,1)
STATE = ([{"op": "add_soft_constraint", "target": "L[1]", "sense": "<=", "rhs": 180, "penalty": 500},
          {"op": "set_objective_weight", "term": "balance", "weight": 5}],
         {"routes": [[1, 2, 4, 7], [5, 3, 6, 8]]})


@pytest.fixture(scope="module")
def comps(base):
    return Task2ComponentsV2(base, StubLLM([]))


def test_prompt_number_matches_brute_force(base, comps):
    mods, sol = STATE
    d = {"type": "ADJ", "i": 0, "j": 1}
    a = comps.attribute(mods, sol, d)
    anchor = {k: a["raw"]["anchor"][k] for k in ("type", "i", "k")}
    assert a["raw"]["anchor"]["current_plan_optimal"]
    gt = oracle_for(base, mods).solve(mods, [canon.forbid_decision(d), anchor])
    cur = canon.objective(sol, base, mods)
    assert cur == 586
    assert a["objective_increase_if_forbidden"] == pytest.approx(gt["objective"] - cur)
    assert 0 <= a["objective_increase_if_forbidden"] < 20114 - 586     # v1 put 20,114 into the prompt


def test_cheaper_without_carries_the_alternative(base, comps):
    mods = [{"op": "add_soft_constraint", "target": "L[2]", "sense": "<=", "rhs": 180, "penalty": 100}]
    a = comps.attribute(mods, {"routes": [[4, 5, 3, 6], [1, 7, 2, 8]]}, {"type": "ADJ", "i": 0, "j": 4})
    assert a["conclusion"] == "cheaper_without"
    assert a["objective_increase_if_forbidden"] < 0 and a["edges_only_in_alternative"]


def test_v2_attribution_reaches_the_prompt(base, comps):
    case = synthetic_case(complaint="Vehicle 1 is doing too much work.")
    llm = StubLLM(lambda messages, meta: NO_EFFECT)
    tr = run_trial(case, base, CONFIGS["A1B0C0"], "A1B0C0", 1, comps, llm, Settings(max_iters=1, tie_diagnostic=False))
    it = tr["iterations"][0]
    assert "attribution" in it["blocks"]
    assert all(item["raw"]["protocol"] == "task2_v2" for item in it["attribution"]["items"])
    assert "## Decision attribution on the current plan" in it["proposal_prompt"]


def test_task3_v1_protocol_still_matches():
    """tpo_v2/ and the v2 scripts sit outside every pattern task3_v1 hashes, so Task 4 still starts."""
    from freeze_protocol import current
    frozen = json.load(open(rv2.ROOT + "/protocol.json"))["hashes"]
    now = current()
    assert all(frozen[g] == now[g] for g in frozen)


def test_reuse_check_detects_a_changed_decision():
    old = {"confidence": "high", "clarifying_question": None,
           "critique": {"target": "balance", "aspect": "distance_balance", "direction": "decrease",
                        "modification_type": "add_soft_constraint", "threshold": 50, "corrected_value": None}}
    assert rv2._same(old, json.loads(json.dumps(old)))
    assert not rv2._same(old, {**old, "critique": {**old["critique"], "threshold": 40}})
    assert not rv2._same(old, {"confidence": "low", "clarifying_question": "?", "critique": None})
