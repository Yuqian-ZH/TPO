"""task3_v3 harness (DESIGN_V3.md): the v3 simulated user gives every configuration the same words, and a trial on a
Task 2 v3 case runs end to end with scripted components (no LLM)."""
import json
import os

import pytest

from tpo.components import ReferenceComponents
from tpo.llm import StubLLM
from tpo.loop import CONFIGS, Settings
from tpo.task2_bridge import TASK2_ROOT
from tpo_v3.loop import localize_with_clarification, run_trial
from tpo_v3.user_sim import SimulatedUserV3

DEV = {c["id"]: c for c in json.load(open(os.path.join(TASK2_ROOT, "v3", "cases", "dev_cases.json")))["cases"]}
HIGH = {"confidence": "high", "target": "x", "aspect": "x", "direction": "decrease",
        "modification_type": "add_soft_constraint", "evidence": {}, "clarification_question": None}
LOW = {"confidence": "low", "clarification_question": "What do you mean?"}


def script(case, first):
    """Iteration 1 proposes `first`, later iterations the case's reference fix; the selector takes candidate 1."""
    def answer(messages, meta):
        if meta.get("role") == "select":
            return {"choice": 1, "reason": "r"}
        mods = first if meta["iteration"] == 1 else case["reference_modification"]
        return {"rationale": "r", "modifications": mods}
    return answer


def trial(base, case, config, first, loc_flat=None):
    comps = ReferenceComponents(base, {case["id"]: loc_flat or {"first": HIGH, "clarified": HIGH}})
    loc = localize_with_clarification(case, base, comps, 1) if CONFIGS[config].C else None
    return run_trial(case, base, CONFIGS[config], config, 1, comps, StubLLM(script(case, first)), Settings(), loc)


def test_side_case_direct_fix_fails_then_reference_converges(base):
    case = DEV["P6"]
    rec = trial(base, case, "A0B0C0", case["design"]["direct"]["modifications"])
    assert rec["converged"] and rec["converged_at"] == 2
    fb = rec["iterations"][0]["feedback"]
    assert fb.startswith("That does not solve it. What I mean is: " + case["explanation"])
    assert "vehicle 1's route was changed" in fb
    assert rec["excess_distance"] == 0


def test_explanation_is_given_once(base):
    case = DEV["P9"]
    nothing = [{"op": "add_soft_constraint", "target": "same[5,7]", "sense": ">=", "rhs": 1, "penalty": 0.5}]
    comps = ReferenceComponents(base, {case["id"]: {"first": HIGH, "clarified": HIGH}})
    llm = StubLLM(lambda m, meta: {"rationale": "r", "modifications": nothing})
    rec = run_trial(case, base, CONFIGS["A0B0C0"], "A0B0C0", 1, comps, llm, Settings())
    fbs = [it["feedback"] for it in rec["iterations"]]
    assert not rec["converged"] and len(fbs) == 3
    assert case["explanation"] in fbs[0] and all(case["explanation"] not in f for f in fbs[1:])
    assert all("customers 5 and 7 are on different trucks" in f for f in fbs)


def test_clarified_trial_starts_explained(base):
    case = DEV["P3"]
    rec = trial(base, case, "A0B0C1", case["design"]["misreading"]["modifications"],
                {"first": LOW, "clarified": HIGH})
    assert rec["localization"]["asked"] and rec["localization"]["answer"] == case["explanation"]
    assert rec["user_explained_at_start"]
    fb = rec["iterations"][0]["feedback"]
    assert fb.startswith("That does not solve it yet.") and case["explanation"] not in fb
    assert rec["converged_at"] == 2


def test_no_clarification_in_the_prompt_without_c(base):
    case = DEV["P3"]
    rec = trial(base, case, "A1B1C0", case["design"]["misreading"]["modifications"])
    assert rec["localization"] is None and not rec["user_explained_at_start"]
    assert case["explanation"] not in rec["iterations"][0]["proposal_prompt"]
    assert case["explanation"] in rec["iterations"][1]["proposal_prompt"]       # through the user's feedback


@pytest.mark.parametrize("cid", sorted(DEV))
def test_reference_fix_converges_at_once(base, cid):
    case = DEV[cid]
    rec = trial(base, case, "A1B1C1", case["reference_modification"])
    assert rec["converged"] and rec["converged_at"] == 1


@pytest.mark.parametrize("cid", sorted(DEV))
def test_prompts_carry_no_hidden_field(base, cid):
    case = DEV[cid]
    rec = trial(base, case, "A1B1C1", case["reference_modification"])
    prompt = rec["iterations"][0]["proposal_prompt"]
    for key in ("explanation", "scenario", "why_question", "what_if_question"):
        assert case[key] not in prompt or case[key] in case["complaint"], key
    assert "conditions" not in prompt and "min_compliant" not in prompt


def test_user_words_do_not_depend_on_the_configuration(base):
    case = DEV["P7"]
    sol = {"routes": [[1, 4, 6, 8], [2, 7, 5, 3]]}
    a, b = SimulatedUserV3(case, base), SimulatedUserV3(case, base)
    assert a.feedback(a.verdict(sol)) == b.feedback(b.verdict(sol))


def test_every_iteration_starts_from_the_plan_complained_about(base):
    """The user's conditions refer to that plan, and so must the prompt, A's decisions, B's probe and the anchor."""
    case = DEV["P9"]
    rec = trial(base, case, "A1B1C0", case["design"]["direct"]["modifications"])
    first, second = rec["iterations"][0], rec["iterations"][1]
    assert first["solution_after"] != case["solution"]
    assert second["input_solution"] == case["solution"] and second["mods_before"] == []
    assert "Previous attempts" in second["proposal_prompt"] and "Attempt 1:" in second["proposal_prompt"]
    probe = second["candidates"][0]["probe"]
    assert probe["change_set"]["moved"] == [2, 5]          # the reference fix, relative to the plan complained about
    assert rec["final_solution"] == second["solution_after"] and rec["converged_at"] == 2
