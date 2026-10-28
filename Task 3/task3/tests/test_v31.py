"""task3_v31 harness (DESIGN_V31.md): the session's modifications are shown and nothing else in the prompt changes;
S1a/S1b select blind among B's candidates; S2a carries the clarification answer as text (no LLM)."""
import json
import os

import pytest

from tpo import context as ctx
from tpo.components import ReferenceComponents
from tpo.llm import StubLLM, derive_seed
from tpo.loop import MAIN, Settings
from tpo.public_case import public_view
from tpo.task2_bridge import TASK2_ROOT
from tpo_v3.loop import TrialV3
from tpo_v3.user_sim import SimulatedUserV3
from tpo_v31.loop import CONFIGS, RUNS, SUPPLEMENTARY, TrialV31, localize_with_clarification, run_trial

DEV = {c["id"]: c for c in json.load(open(os.path.join(TASK2_ROOT, "v3", "cases", "dev_cases.json")))["cases"]}
HIGH = {"confidence": "high", "target": "x", "aspect": "x", "direction": "decrease",
        "modification_type": "add_soft_constraint", "evidence": {}, "clarification_question": None}
LOW = {"confidence": "low", "clarification_question": "What do you mean?"}
SESSION_SOFT = [{"op": "add_soft_constraint", "target": "same[4,5]", "sense": ">=", "rhs": 1, "penalty": 100}]


def script(case, first):
    def answer(messages, meta):
        if meta.get("role") == "select":
            return {"choice": 1, "reason": "r"}
        mods = first if meta["iteration"] == 1 else case["reference_modification"]
        return {"rationale": "r", "modifications": mods}
    return answer


def comps_for(base, case, flat=None):
    return ReferenceComponents(base, {case["id"]: flat or {"first": HIGH, "clarified": HIGH}})


def prompt(cls, base, case, config):
    comps = comps_for(base, case)
    loc = localize_with_clarification(case, base, comps, 6) if CONFIGS[config].C else None
    tr = cls(public_view(case), base, SimulatedUserV3(case, base), CONFIGS[config], config, 6, comps,
             StubLLM(script(case, [])), Settings(), loc)
    return ctx.user_message(tr.blocks()[0], ctx.TASK_PROPOSAL)


def trial(base, case, config, first, flat=None):
    comps = comps_for(base, case, flat)
    loc = localize_with_clarification(case, base, comps, 6) if (CONFIGS[config].C or CONFIGS[config].clar_text) \
        else None
    return run_trial(case, base, CONFIGS[config], config, 6, comps, StubLLM(script(case, first)), Settings(), loc)


def test_configurations_and_runs():
    assert [g for g in CONFIGS if g not in MAIN] == list(SUPPLEMENTARY)
    s1a, s1b, s2a = (CONFIGS[g] for g in SUPPLEMENTARY)
    assert (s1a.A, s1a.B, s1a.C, s1a.blind, s1a.clar_text) == (False, True, False, True, False)
    assert (s1b.A, s1b.B, s1b.C, s1b.blind, s1b.clar_text) == (True, True, True, True, False)
    assert (s2a.A, s2a.B, s2a.C, s2a.blind, s2a.clar_text) == (False, False, False, False, True)
    assert set(RUNS).isdisjoint({1, 2, 3, 4, 5}) and len(RUNS) == 5
    v3 = {derive_seed("U10", "A1B1C1", r, 1, "propose", 0) for r in (1, 2, 3, 4, 5)}
    assert v3.isdisjoint({derive_seed("U10", "A1B1C1", r, 1, "propose", 0) for r in RUNS})


@pytest.mark.parametrize("config", MAIN)
@pytest.mark.parametrize("cid", [c for c in sorted(DEV) if not DEV[c]["model_modifications"]])
def test_prompt_unchanged_without_session_modifications(base, cid, config):
    case = DEV[cid]
    assert prompt(TrialV31, base, case, config) == prompt(TrialV3, base, case, config)


@pytest.mark.parametrize("config", ["A0B0C0", "A1B1C1"])
def test_session_soft_constraint_is_shown(base, config):
    case = {**DEV["P6"], "id": "P6s", "model_modifications": SESSION_SOFT}
    new, old = prompt(TrialV31, base, case, config), prompt(TrialV3, base, case, config)
    block = ("## Modifications set earlier in this session (kept in force)\n"
             "They were in the model before this complaint. They stay in force whatever you answer; do not repeat "
             "them. An empty answer returns the plan to the optimum of the model with them.\n"
             '- {"op": "add_soft_constraint", "target": "same[4,5]", "sense": ">=", "rhs": 1, "penalty": 100}')
    assert block not in old and new == old.replace("## Modifications currently in force", block +
                                                   "\n\n## Modifications currently in force")


def test_session_data_correction_is_shown(base):
    case = DEV["P10"]
    p = prompt(TrialV31, base, case, "A0B0C0")
    assert '- {"op": "modify_data", "field": "demand[4]", "value": 20}' in p
    assert p.index("## Modifications set earlier") < p.index("## Modifications currently in force")


def test_selector_sees_session_block(base):
    case = {**DEV["P6"], "id": "P6s", "model_modifications": SESSION_SOFT}
    rec = trial(base, case, "A0B1C0", case["design"]["direct"]["modifications"])
    sel = rec["iterations"][0]["selection"]
    assert sel["called"] and "## Modifications set earlier in this session" in sel["prompt"]


@pytest.mark.parametrize("config,probe", [("A0B1C0", True), ("S1a", False), ("A1B1C1", True), ("S1b", False)])
def test_blind_selection_does_not_probe(base, config, probe):
    case = DEV["P6"]
    rec = trial(base, case, config, case["design"]["direct"]["modifications"])
    it = rec["iterations"][0]
    assert len(it["candidates"]) == 3 and it["selection"]["called"]
    assert all(("probe" in c) == probe for c in it["candidates"])
    assert ("predicted outcome" in it["selection"]["prompt"]) == probe
    assert rec["converged"] and rec["converged_at"] == 2


def test_s2a_carries_the_answer_as_text(base):
    case = DEV["P3"]
    rec = trial(base, case, "S2a", case["design"]["misreading"]["modifications"], {"first": LOW, "clarified": HIGH})
    assert rec["localization"]["asked"] and rec["user_explained_at_start"]
    p = rec["iterations"][0]["proposal_prompt"]
    assert f'The user later added: "{case["explanation"]}"' in p
    assert "## Structured localization" not in p and "## Clarification" not in p
    assert len(rec["iterations"][0]["candidates"]) == 1 and rec["iterations"][0]["selection"] is None
    fb = rec["iterations"][0]["feedback"]
    assert fb.startswith("That does not solve it yet.") and case["explanation"] not in fb
    assert rec["converged_at"] == 2


def test_s2a_without_a_question_is_the_bare_loop(base):
    case = DEV["P6"]
    s2a = trial(base, case, "S2a", case["design"]["direct"]["modifications"])
    bare = trial(base, case, "A0B0C0", case["design"]["direct"]["modifications"])
    assert not s2a["localization"]["asked"] and not s2a["user_explained_at_start"]
    assert [it["proposal_prompt"] for it in s2a["iterations"]] == [it["proposal_prompt"] for it in bare["iterations"]]


@pytest.mark.parametrize("config", ["A1B1C1", *SUPPLEMENTARY])
@pytest.mark.parametrize("cid", sorted(DEV))
def test_reference_fix_converges_at_once(base, cid, config):
    case = DEV[cid]
    rec = trial(base, case, config, case["reference_modification"])
    assert rec["protocol"] == "task3_v31" and rec["converged"] and rec["converged_at"] == 1


def test_low_confidence_stops_c_but_not_s2a(base):
    case = DEV["P3"]
    flat = {"first": LOW, "clarified": LOW}
    assert trial(base, case, "A0B0C1", case["reference_modification"], flat)["outcome"] == "stopped_low_confidence"
    assert trial(base, case, "S2a", case["reference_modification"], flat)["converged_at"] == 1
