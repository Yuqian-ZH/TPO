"""task4_v3: the service runs task3_v3's loop. Driven over HTTP by Task 3's v3 simulated user, it reproduces
tpo_v3.loop.run_trial on Task 2's v3 development cases whenever every iteration produces a plan the user has not
seen; the one remaining difference (an iteration that returns a plan already seen) is pinned down below."""
import json
import os

import pytest
from fastapi.testclient import TestClient

from e2e_client_v3 import drive
from feedback_service.app import create_app
from feedback_service.bridge import TASK2_ROOT
from feedback_service.engine import SERVICE_SETTINGS
from feedback_service_v3.service import build_service_v3
from tpo.llm import StubLLM
from tpo.loop import CONFIGS, MAIN
from tpo_v3.loop import localize_with_clarification, run_trial

from conftest import HIGH, LOW, FixedKeyComponents, counter_ids

DEV = {c["id"]: c for c in json.load(open(os.path.join(TASK2_ROOT, "v3", "cases", "dev_cases.json")))["cases"]}
OTHER = [{"op": "add_soft_constraint", "target": "S[1]", "sense": "<=", "rhs": 3, "penalty": 500}]


def script(plan):
    def answer(messages, meta):
        if meta.get("role") == "select":
            return {"choice": 2, "reason": "r"}
        return {"rationale": "r", "modifications": plan[min(meta["iteration"], max(plan))]}
    return answer


def scenarios():
    p6, p3, p9 = DEV["P6"], DEV["P3"], DEV["P9"]
    return {
        "side_fixed_at_2": (p6, {1: p6["design"]["direct"]["modifications"], 2: p6["reference_modification"]},
                            HIGH, None, ("resolved", 2)),
        "ambiguous_clarified": (p3, {1: p3["design"]["misreading"]["modifications"], 2: p3["reference_modification"]},
                                LOW, HIGH, ("resolved", 2)),
        "never_fixed": (p9, {1: p9["design"]["direct"]["modifications"], 2: OTHER}, HIGH, None,
                        ("not_converged", 3)),
    }


@pytest.fixture()
def serve(tmp_path):
    opened = []

    def _serve(case, plan, first, clarified):
        comps = FixedKeyComponents(None, {}, key=case["id"])

        def factory(b, llm):
            comps.base = b
            comps.localizations = {case["id"]: {"first": first, "clarified": clarified or first}}
            return comps
        svc = build_service_v3(str(tmp_path / f"store{len(opened)}"), llm=StubLLM(script(plan)),
                               new_id=counter_ids(), components_factory=factory)
        client = TestClient(create_app(svc))
        client.__enter__()
        opened.append(client)
        return client
    yield _serve
    for c in opened:
        c.__exit__(None, None, None)


def view(it):
    sel = it.get("selection") or {}
    return {"t": it["t"], "status": it["status"], "committed": it["committed_mods"], "input": it["input_solution"],
            "after": it["solution_after"], "blocks": it["blocks"], "prompt": it["proposal_prompt"],
            "candidates": [(c["valid"], c["modifications"], (c.get("probe") or {}).get("objective"))
                           for c in it["candidates"]],
            "selection": (sel.get("index"), sel.get("prompt"))}


def norm(x):
    return json.loads(json.dumps(x, default=str))


@pytest.mark.parametrize("name", list(scenarios()))
@pytest.mark.parametrize("config", MAIN)
def test_service_reproduces_task3_v3(serve, base, config, name):
    case, plan, first, clarified, expected = scenarios()[name]
    flags = CONFIGS[config]
    comps = FixedKeyComponents(base, {case["id"]: {"first": first, "clarified": clarified or first}}, key=case["id"])
    loc = localize_with_clarification(case, base, comps, 1) if flags.C else None
    direct = run_trial(case, base, flags, config, 1, comps, StubLLM(script(plan)), SERVICE_SETTINGS, loc)

    client = serve(case, plan, first, clarified)
    res = drive(client, case, base, config)
    logs = client.get(f"/sessions/{res['session_id']}/iterations").json()
    assert (res["status"], res["iterations"]) == expected
    assert len(logs) == len(direct["iterations"])
    assert [norm(view(x["detail"])) for x in logs] == [norm(view(it)) for it in direct["iterations"]]
    assert all(x["detail"]["input_solution"] == case["solution"] for x in logs)     # task3_v3's loop
    if direct["converged"]:
        assert res["final_plan"]["routes"] == direct["final_solution"]["routes"]
        assert res["excess_distance"] == direct["excess_distance"]


def test_plan_already_seen_is_not_shown(serve, base):
    """The remaining difference: an iteration that returns the plan complained about is not shown to the user, so
    the service runs on with the user's last words, where Task 3's simulated user comments on that plan."""
    case = DEV["P9"]
    nothing = [{"op": "add_soft_constraint", "target": "same[5,7]", "sense": ">=", "rhs": 1, "penalty": 0.5}]
    plan = {1: nothing, 2: case["reference_modification"]}
    comps = FixedKeyComponents(base, {case["id"]: {"first": HIGH, "clarified": HIGH}}, key=case["id"])
    direct = run_trial(case, base, CONFIGS["A0B0C0"], "A0B0C0", 1, comps, StubLLM(script(plan)), SERVICE_SETTINGS)
    client = serve(case, plan, HIGH, None)
    res = drive(client, case, base, "A0B0C0")
    logs = client.get(f"/sessions/{res['session_id']}/iterations").json()
    assert direct["converged_at"] == 2 and res["status"] == "resolved" and res["iterations"] == 2
    assert [x["trigger"] for x in logs] == ["feedback", "auto_continue"]
    t3_feedback = direct["iterations"][0]["feedback"]
    service_feedback = logs[1]["detail"]["proposal_prompt"].split("- user feedback: ")[1].split("\n")[0]
    assert t3_feedback.startswith("That does not solve it. What I mean is:")
    assert service_feedback == json.dumps(f"The new plan still doesn't fix my complaint: {case['complaint']}")


def test_accepting_keeps_the_shown_plan_and_its_modifications(serve, base):
    case = DEV["P6"]
    plan = {1: case["reference_modification"]}
    client = serve(case, plan, HIGH, None)
    res = drive(client, case, base, "A0B0C0")
    s = client.get(f"/sessions/{res['session_id']}").json()
    assert res["status"] == "resolved" and s["current_plan"]["routes"] == res["final_plan"]["routes"]
    assert [{k: v for k, v in m.items() if k != "id"} for m in s["accepted_modifications"]] == \
        case["reference_modification"]
