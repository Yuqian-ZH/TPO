"""Gate G2 interface check (plan 2.1): the adapter over the real Task 2 components agrees with the
brute-force reference. localize() runs on a stub LLM, so no request is sent."""
import random

import pytest

from tpo.components import ReferenceComponents, Task2Components
from tpo.entities import decisions
from tpo.llm import StubLLM
from tpo.loop import CONFIGS, Settings, localize_with_clarification, run_trial

from conftest import FIX_STOPS, REFERENCE, synthetic_case
from test_commit_and_validation import random_mod

SAMPLE = {"object_type": "vehicle", "vehicle": 2, "customers": [], "aspect": "stops", "direction": "decrease",
          "modification_type": "add_soft_constraint", "threshold": 3, "corrected_value": None, "ambiguous": False,
          "clarifying_question": None, "rationale": "stops of vehicle 2"}
AMBIGUOUS = {**SAMPLE, "aspect": "route_length", "ambiguous": True,
             "clarifying_question": "Is it the distance, the load or the number of stops?"}


@pytest.fixture()
def pair(base):
    return Task2Components(base, StubLLM([])), ReferenceComponents(base)


def test_attribution_agrees_with_brute_force(pair):
    real, ref = pair
    for d in decisions(REFERENCE, {"vehicles": [], "customers": []}):
        a, b = real.attribute([], REFERENCE, d), ref.attribute([], REFERENCE, d)
        assert a["decision"] == b["decision"] and a["conclusion"] == b["conclusion"], d
        assert a["constraint_ids"] == b["constraint_ids"], d
        if a["conclusion"] == "objective_preferred":
            assert a["objective_increase_if_forbidden"] == pytest.approx(b["objective_increase_if_forbidden"])
            assert "raw" in a and "lp_relaxation" not in a["raw"]


@pytest.mark.parametrize("probe", ["task2_frozen", "v2"])
@pytest.mark.parametrize("seed", range(15))
def test_probe_is_feasible_and_never_better_than_full(base, probe, seed):
    real, ref = Task2Components(base, StubLLM([]), probe=probe), ReferenceComponents(base)
    rng = random.Random(100 + seed)
    mods = [random_mod(rng, base["n"]) for _ in range(rng.randint(1, 2))]
    a, b = real.probe([], REFERENCE, mods), ref.probe([], REFERENCE, mods)
    assert a["feasible"] == b["feasible"]
    if a["feasible"]:
        assert a["objective"] >= b["objective"] - 1e-6          # local search space is a subset
        assert a["level"] in ("L0", "L1", "L2")
        if probe == "v2":
            assert a["objective"] == pytest.approx(b["objective"], abs=1e-6)


def test_v2_fixes_the_stuck_l0_and_restores_the_resident_model(base):
    stops = [{"op": "add_soft_constraint", "target": "S[2]", "sense": "<=", "rhs": 3, "penalty": 60}]
    frozen = Task2Components(base, StubLLM([]), probe="task2_frozen").probe([], REFERENCE, stops)
    assert frozen["level"] == "L0" and frozen["objective"] == 411 and not frozen["change_set"]["moved"]
    from tpo import counterfactual_v2
    v2 = Task2Components(base, StubLLM([]), probe="v2")
    r = v2.probe([], REFERENCE, stops)
    assert r["objective"] == 397 and r["metric_changes"]["S[2]"] == [4, 3]
    reasons = [t["escalate_reason"] for t in r["raw"]["levels_tried"]]
    assert reasons[0] in ("soft_violation", "unchanged") and reasons[-1] is None
    engine = next(iter(counterfactual_v2._ENGINES.values()))
    size = engine.model.size()
    for _ in range(3):
        v2.probe([], REFERENCE, stops + [{"op": "modify_data", "field": "demand[4]", "value": 30}])
    assert engine.model.size() == size and engine.model.optimize()["objective"] == pytest.approx(351, abs=1e-3)
    data_mod = v2.probe([], REFERENCE, [{"op": "modify_data", "field": "demand[4]", "value": 5}])
    assert data_mod["level"] == "L2"


def test_localize_high_and_clarification_flow(base):
    llm = StubLLM([AMBIGUOUS] * 5 + [SAMPLE] * 5)
    comps = Task2Components(base, llm)
    case = synthetic_case()
    loc = localize_with_clarification(case, base, comps, 1)
    assert loc["initial"]["confidence"] == "low" and loc["asked"]
    assert loc["question"] == AMBIGUOUS["clarifying_question"]
    assert loc["final"]["confidence"] == "high" and loc["final"]["critique"]["target"] == "S[2]"
    clarified_prompt = llm.calls[5]["messages"][-1]["content"]
    assert "SENTINEL_CLARIFICATION" in clarified_prompt         # the user's answer reached Task 2's localizer
    assert {c["meta"]["run"] for c in llm.calls} == {"t3-1"}    # Task 3 seeds differ from Task 2's own runs
    crit = comps.refresh_critique(loc["final"]["critique"], [], {"routes": [[1, 4, 7, 2, 5], [3, 6, 8]]})
    assert crit["evidence"]["S[2]"] == 3 and "S[2] = 3" in crit["critique_text"]


def test_full_trial_on_real_components(base):
    llm = StubLLM(lambda m, meta: {"choice": 1} if meta.get("role") == "select" else
                  SAMPLE if meta.get("component", "").startswith("localize") else FIX_STOPS)
    comps = Task2Components(base, llm)
    case = synthetic_case()
    loc = localize_with_clarification(case, base, comps, 1)
    tr = run_trial(case, base, CONFIGS["A1B1C1"], "A1B1C1", 1, comps, llm, Settings(), loc)
    it = tr["iterations"][0]
    assert tr["converged_at"] == 1 and it["blocks"] == ["instance", "plan", "mods_in_force", "complaint",
                                                       "localization", "attribution"]
    # With the v2 rule (decision ④) the probe no longer stops at the stuck L0: it predicts what the commit does.
    probe = it["candidates"][0]["probe"]
    assert probe["probe_version"] == "v2" and probe["objective"] == pytest.approx(it["commit"]["objective"])
    assert it["probe_vs_commit"] == {"feasible": True, "objective_1pct": True, "change_set": True}
    assert "Critique: User complaint" in it["proposal_prompt"]
