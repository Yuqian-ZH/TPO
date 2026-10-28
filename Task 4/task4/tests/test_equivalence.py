"""Plan 5.1 item 7: the service driven over HTTP by Task 3's simulated user reproduces Task 3's run_trial on the
same case, stub script and components: in every iteration the same status, prompt text, candidates, selection,
committed modifications and plan, and the same outcome. Seeds differ (they derive from the case id in Task 3 and
from the feedback id here) and are not compared; the stub's answers do not depend on them."""
import json
import os

import pytest

from e2e_client import drive
from feedback_service.engine import SERVICE_SETTINGS
from tpo.llm import StubLLM
from tpo.loop import CONFIGS, MAIN, localize_with_clarification, run_trial

from conftest import (FIX_STOPS, HIGH, INVALID, LOW, MOVE, NO_CHANGE, SENTINELS, FixedKeyComponents, by_iteration,
                      synthetic_case)

SCENARIOS = {   # proposals by iteration, first localization, localization after clarification
    "fixed_at_1": ({1: FIX_STOPS}, HIGH, None),
    "new_plan_then_fixed": ({1: MOVE, 2: FIX_STOPS}, HIGH, None),
    "rejected_unchanged_fixed": ({1: INVALID, 2: NO_CHANGE, 3: FIX_STOPS}, HIGH, None),
    "never_fixed": ({1: MOVE, 2: NO_CHANGE}, HIGH, None),
    "clarified": ({1: MOVE, 2: FIX_STOPS}, LOW, HIGH),
    "still_unclear": ({1: FIX_STOPS}, LOW, LOW),
}
OUTCOME = {"converged": "resolved", "not_converged": "not_converged",
           "stopped_low_confidence": "stopped_low_confidence"}


def expected(scenario, C):
    """Final status and the trigger of each iteration, so that every branch is known to be exercised."""
    return {"fixed_at_1": ("resolved", ["feedback"]),
            "new_plan_then_fixed": ("resolved", ["feedback", "reply"]),
            "rejected_unchanged_fixed": ("resolved", ["feedback", "auto_continue", "auto_continue"]),
            "never_fixed": ("not_converged", ["feedback", "reply", "reply"]),   # 3rd plan unchanged, budget spent
            "clarified": ("resolved", ["clarification" if C else "feedback", "reply"]),
            "still_unclear": ("stopped_low_confidence", []) if C else ("resolved", ["feedback"])}[scenario]


def view(it):
    sel = it.get("selection") or {}
    return {"t": it["t"], "status": it["status"], "note": it["note"], "committed": it["committed_mods"],
            "after": it["solution_after"], "blocks": it["blocks"], "prompt": it["proposal_prompt"],
            "candidates": [(c["valid"], c["modifications"], c["errors"], (c.get("probe") or {}).get("objective"))
                           for c in it["candidates"]],
            "selection": (sel.get("index"), sel.get("prompt"))}


def norm(x):
    return json.loads(json.dumps(x, default=str))


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("config", MAIN)
def test_service_reproduces_task3_run_trial(make, base, tmp_path, config, scenario):
    plan, first, clarified = SCENARIOS[scenario]
    case = synthetic_case()
    flags = CONFIGS[config]

    comps = FixedKeyComponents(base, {"X1": {"first": first, "clarified": clarified or first}})
    loc = localize_with_clarification(case, base, comps, 1) if flags.C else None
    direct = run_trial(case, base, flags, config, 1, comps, StubLLM(by_iteration(plan, choice=2)),
                       SERVICE_SETTINGS, loc)

    client, svc, llm, _ = make(by_iteration(plan, choice=2), first=first, clarified=clarified)
    res = drive(client, case, base, config)
    logs = client.get(f"/sessions/{res['session_id']}/iterations").json()

    assert (res["status"], [x["trigger"] for x in logs]) == expected(scenario, flags.C)
    assert res["status"] == OUTCOME[direct["outcome"]]
    assert res["clarified"] == bool(loc and loc["asked"])
    assert len(logs) == len(direct["iterations"])
    assert [norm(view(x["detail"])) for x in logs] == [norm(view(it)) for it in direct["iterations"]]
    if direct["converged"]:
        assert res["iterations"] == direct["converged_at"]
        assert res["final_plan"]["routes"] == direct["final_solution"]["routes"]

    # nothing private ever reached the service; the clarification answer only when it was asked for
    stored = ""
    for d, _, files in os.walk(tmp_path / "store"):
        for f in files:
            with open(os.path.join(d, f)) as fh:
                stored += fh.read()
    assert not [s for s in SENTINELS if s in stored]
    assert ("SENTINEL_CLARIFICATION" in stored) == bool(flags.C and loc["asked"])
