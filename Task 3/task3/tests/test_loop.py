import json

import pytest

from tpo.components import ReferenceComponents
from tpo.llm import StubLLM
from tpo.loop import CONFIGS, MAIN, Settings, localize_with_clarification, run_trial

from conftest import FIX_STOPS, HIGH, LOW, NO_EFFECT, SENTINELS, synthetic_case

FAST = Settings(tie_diagnostic=False)


def script(proposal, choice=1):
    def answer(messages, meta):
        return {"choice": choice, "reason": "r"} if meta["role"] == "select" else proposal
    return answer


def loc_for(case, base, first, clarified=None, run=1):
    comps = ReferenceComponents(base, {case["id"]: {"first": first, "clarified": clarified or first}})
    return comps, localize_with_clarification(case, base, comps, run)


def prompts(llm):
    return [m["content"] for c in llm.calls for m in c["messages"]]


@pytest.mark.parametrize("config", MAIN)
def test_switches_change_only_their_blocks(base, config):
    case = synthetic_case()
    flags = CONFIGS[config]
    comps, loc = loc_for(case, base, HIGH)
    llm = StubLLM(script(NO_EFFECT))
    tr = run_trial(case, base, flags, config, 1, comps, llm, Settings(max_iters=1, tie_diagnostic=False), loc)
    it = tr["iterations"][0]
    assert ("attribution" in it["blocks"]) == flags.A
    assert ("localization" in it["blocks"]) == flags.C
    assert "clarification" not in it["blocks"]            # high confidence: nobody was asked
    assert len(it["candidates"]) == (3 if flags.B else 1)
    proposals = [c for c in llm.calls if c["meta"]["role"] == "propose"]
    assert len({c["messages"][1]["content"] for c in proposals}) == 1   # same prompt for every candidate
    assert len({c["seed"] for c in proposals}) == len(proposals)      # but independent seeds
    if flags.B:
        assert all("probe" in c for c in it["candidates"])
        assert it["selection"]["called"]
        assert "predicted outcome" in it["selection"]["prompt"]


def test_low_confidence_is_never_passed_to_tpo(base):
    case = synthetic_case()
    comps, loc = loc_for(case, base, LOW, LOW)
    assert loc["asked"] and loc["answer"].startswith("SENTINEL_CLARIFICATION")
    llm = StubLLM(script(FIX_STOPS))
    tr = run_trial(case, base, CONFIGS["A1B1C1"], "A1B1C1", 1, comps, llm, FAST, loc)
    assert tr["outcome"] == "stopped_low_confidence" and not tr["iterations"] and not llm.calls


def test_clarified_localization_reaches_tpo_with_the_answer(base):
    case = synthetic_case()
    comps, loc = loc_for(case, base, LOW, HIGH)
    llm = StubLLM(script(FIX_STOPS))
    tr = run_trial(case, base, CONFIGS["A0B0C1"], "A0B0C1", 1, comps, llm, FAST, loc)
    it = tr["iterations"][0]
    assert "clarification" in it["blocks"] and "SENTINEL_CLARIFICATION" in it["proposal_prompt"]
    assert tr["converged"] and tr["converged_at"] == 1


def test_s2_appends_answer_only_when_clarification_was_asked(base):
    case = synthetic_case()
    for first, asked in ((LOW, True), (HIGH, False)):
        comps, loc = loc_for(case, base, first, HIGH)
        llm = StubLLM(script(NO_EFFECT))
        tr = run_trial(case, base, CONFIGS["S2"], "S2", 1, comps, llm, Settings(max_iters=1, tie_diagnostic=False),
                       loc)
        it = tr["iterations"][0]
        assert "localization" not in it["blocks"] and "clarification" not in it["blocks"]
        assert ("The user later added" in it["proposal_prompt"]) == asked


def test_s1_blind_selection_has_no_probes(base):
    case = synthetic_case()
    comps, loc = loc_for(case, base, HIGH)
    llm = StubLLM(script(NO_EFFECT))
    tr = run_trial(case, base, CONFIGS["S1"], "S1", 1, comps, llm, Settings(max_iters=1, tie_diagnostic=False), loc)
    it = tr["iterations"][0]
    assert not any("probe" in c for c in it["candidates"])
    assert it["selection"]["called"] and "predicted outcome" not in it["selection"]["prompt"]


def test_no_private_field_reaches_any_prompt(base):
    case = synthetic_case()
    for config in list(MAIN) + ["S1"]:
        comps, loc = loc_for(case, base, HIGH)
        llm = StubLLM(script(NO_EFFECT))
        run_trial(case, base, CONFIGS[config], config, 1, comps, llm, FAST, loc)
        text = "\n".join(prompts(llm))
        assert not any(s in text for s in SENTINELS), config
        assert "SENTINEL_CLARIFICATION" not in text        # nobody was asked in these runs


def test_feedback_never_reveals_threshold_or_value(base):
    case = synthetic_case()
    llm = StubLLM(script(NO_EFFECT))
    tr = run_trial(case, base, CONFIGS["A0B0C0"], "A0B0C0", 1, ReferenceComponents(base), llm, FAST)
    assert not tr["converged"] and len(tr["iterations"]) == 3
    for it in tr["iterations"]:
        assert it["feedback"] == f"The new plan still doesn't fix my complaint: {case['complaint']}"
    last = llm.calls[-1]["messages"][1]["content"]
    assert "Attempt 2:" in last and "still doesn't fix" in last


def test_invalid_proposal_is_rejected_and_reported(base):
    case = synthetic_case()
    bad = {"rationale": "x", "modifications": [{"op": "set_objective_weight", "term": "distance", "weight": 2}]}
    llm = StubLLM([bad, FIX_STOPS])
    tr = run_trial(case, base, CONFIGS["A0B0C0"], "A0B0C0", 1, ReferenceComponents(base), llm, FAST)
    first, second = tr["iterations"]
    assert first["status"] == "rejected" and first["solution_after"] == case["solution"]
    assert "rejected" in second["proposal_prompt"] and "unknown objective term" in second["proposal_prompt"]
    assert tr["converged_at"] == 2


def test_infeasible_commit_keeps_previous_plan(base):
    case = synthetic_case()
    shrink = {"rationale": "x", "modifications": [{"op": "modify_data", "field": "capacity", "value": 50}]}
    llm = StubLLM([shrink, FIX_STOPS])
    tr = run_trial(case, base, CONFIGS["A0B0C0"], "A0B0C0", 1, ReferenceComponents(base), llm, FAST)
    first = tr["iterations"][0]
    assert first["status"] == "no_plan" and first["solution_after"] == case["solution"]
    assert first["illegal_data_mods"] == [{"op": "modify_data", "field": "capacity", "value": 50}]
    assert "No feasible plan exists" in tr["iterations"][1]["proposal_prompt"]


def test_selector_failure_falls_back_to_first_feasible(base):
    case = synthetic_case()
    comps, loc = loc_for(case, base, HIGH)
    llm = StubLLM(script(FIX_STOPS, choice=9))
    tr = run_trial(case, base, CONFIGS["A0B1C0"], "A0B1C0", 1, comps, llm, FAST)
    it = tr["iterations"][0]
    assert not it["selection"]["ok"] and it["chosen_sample"] == 0 and tr["converged"]
    assert it["probe_vs_commit"] == {"feasible": True, "objective_1pct": True, "change_set": True}


def test_attribution_block_contents(base):
    case = synthetic_case(complaint="Customer 3 is always served late.")
    llm = StubLLM(script(NO_EFFECT))
    tr = run_trial(case, base, CONFIGS["A1B0C0"], "A1B0C0", 1, ReferenceComponents(base), llm,
                   Settings(max_iters=1, tie_diagnostic=False))
    attr = tr["iterations"][0]["attribution"]
    assert attr["entities"] == {"vehicles": [], "customers": [3]}
    by = {a["decision"]: a for a in attr["items"]}
    assert by["SEP(1,3)"]["conclusion"] == "hard_constraint_forced"
    assert by["SEP(1,3)"]["constraint_ids"] == ["cap[1]", "cap[2]"]
    assert all(a["objective_increase_if_forbidden"] > 0 for a in attr["items"] if a["conclusion"] == "objective_preferred")
    assert '"SEP(1,3)"' in tr["iterations"][0]["proposal_prompt"]


def test_tie_and_label_diagnostics(base):
    case = synthetic_case()
    llm = StubLLM(script(FIX_STOPS))
    tr = run_trial(case, base, CONFIGS["A0B0C0"], "A0B0C0", 1, ReferenceComponents(base), llm, Settings())
    it = tr["iterations"][0]
    assert it["tie"]["matches_commit"] and it["tie"]["n_optimal"] >= 1
    assert isinstance(it["label_swap_resolved"], bool)
    json.dumps(tr)   # the whole record is serializable
