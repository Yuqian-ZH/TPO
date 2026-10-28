"""task4_v31: the service runs task3_v31's loop. Driven over HTTP by Task 3's v3 simulated user, it reproduces
tpo_v31.loop.run_trial on Task 2's v3 development cases, including sessions created with modifications, which are
now shown in the prompt as Task 3 v3.1 shows them."""
import json
import os

import pytest
from fastapi.testclient import TestClient

from e2e_client_v3 import drive
from feedback_service.app import create_app
from feedback_service.bridge import TASK2_ROOT
from feedback_service.engine import SERVICE_SETTINGS
from feedback_service_v3.service import build_service_v3
from feedback_service_v31.service import build_service_v31
from tpo.llm import StubLLM
from tpo.loop import CONFIGS, MAIN
from tpo_v31.loop import TrialV31, localize_with_clarification, run_trial

from conftest import HIGH, LOW, FixedKeyComponents, counter_ids

DEV = {c["id"]: c for c in json.load(open(os.path.join(TASK2_ROOT, "v3", "cases", "dev_cases.json")))["cases"]}
SESSION_SOFT = [{"op": "add_soft_constraint", "target": "same[3,6]", "sense": ">=", "rhs": 1, "penalty": 100}]
P6S = {**DEV["P6"], "id": "P6s", "model_modifications": SESSION_SOFT}
OTHER = [{"op": "add_soft_constraint", "target": "S[1]", "sense": "<=", "rhs": 3, "penalty": 500}]
HEADING = "## Modifications set earlier in this session (kept in force)"


def script(plan):
    def answer(messages, meta):
        if meta.get("role") == "select":
            return {"choice": 2, "reason": "r"}
        return {"rationale": "r", "modifications": plan[min(meta["iteration"], max(plan))]}
    return answer


def scenarios():
    p6, p3, p10 = DEV["P6"], DEV["P3"], DEV["P10"]
    return {
        "side_fixed_at_2": (p6, {1: p6["design"]["direct"]["modifications"], 2: p6["reference_modification"]},
                            HIGH, None),
        "ambiguous_clarified": (p3, {1: p3["design"]["misreading"]["modifications"], 2: p3["reference_modification"]},
                                LOW, HIGH),
        "session_data_correction": (p10, {1: p10["design"]["direct"]["modifications"],
                                          2: p10["reference_modification"]}, HIGH, None),
        "session_soft_constraint": (P6S, {1: P6S["design"]["direct"]["modifications"], 2: OTHER}, HIGH, None),
    }


def _factory(case, first, clarified):
    comps = FixedKeyComponents(None, {}, key=case["id"])

    def factory(b, llm):
        comps.base = b
        comps.localizations = {case["id"]: {"first": first, "clarified": clarified or first}}
        return comps
    return factory


@pytest.fixture()
def serve(tmp_path):
    opened = []

    def _serve(case, plan, first, clarified, build=build_service_v31):
        svc = build(str(tmp_path / f"store{len(opened)}"), llm=StubLLM(script(plan)), new_id=counter_ids(),
                    components_factory=_factory(case, first, clarified))
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
def test_service_reproduces_task3_v31(serve, base, config, name):
    case, plan, first, clarified = scenarios()[name]
    flags = CONFIGS[config]
    comps = FixedKeyComponents(base, {case["id"]: {"first": first, "clarified": clarified or first}}, key=case["id"])
    loc = localize_with_clarification(case, base, comps, 1) if flags.C else None
    direct = run_trial(case, base, flags, config, 1, comps, StubLLM(script(plan)), SERVICE_SETTINGS, loc)

    client = serve(case, plan, first, clarified)
    res = drive(client, case, base, config)
    logs = client.get(f"/sessions/{res['session_id']}/iterations").json()
    assert res["status"] == ("resolved" if direct["converged"] else "not_converged")
    assert len(logs) == len(direct["iterations"])
    assert [norm(view(x["detail"])) for x in logs] == [norm(view(it)) for it in direct["iterations"]]
    assert all((HEADING in x["detail"]["proposal_prompt"]) == bool(case["model_modifications"]) for x in logs)
    if direct["converged"]:
        assert res["final_plan"]["routes"] == direct["final_solution"]["routes"]


@pytest.mark.parametrize("name", ["side_fixed_at_2", "ambiguous_clarified"])
def test_without_session_modifications_the_prompt_is_task4_v3s(serve, base, name):
    case, plan, first, clarified = scenarios()[name]
    out = []
    for build in (build_service_v31, build_service_v3):
        client = serve(case, plan, first, clarified, build)
        res = drive(client, case, base, "A1B1C1")
        out.append([x["detail"]["proposal_prompt"] for x in
                    client.get(f"/sessions/{res['session_id']}/iterations").json()])
    assert out[0] == out[1]


def test_session_block_comes_before_the_accepted_block(serve, base):
    """A second complaint in the same session: the session's modifications, then the accepted fix."""
    case = P6S
    plan = {1: case["reference_modification"]}
    client = serve(case, plan, HIGH, None)
    res = drive(client, case, base, "A0B0C0")
    assert res["status"] == "resolved"
    sid = res["session_id"]
    v = client.post(f"/sessions/{sid}/feedback", json={"complaint": "Customer 8 is served too late."}).json()
    while v["status"] not in ("awaiting_reply", "not_converged", "failed"):
        v = client.get(f"/feedback/{v['feedback_id']}").json()
    logs = client.get(f"/sessions/{sid}/iterations").json()
    p = logs[-1]["detail"]["proposal_prompt"]
    i, j, k = (p.index(h) for h in (HEADING, "## Modifications accepted earlier",
                                    "## Modifications currently in force"))
    assert i < j < k
    assert '"target": "same[3,6]"' in p[i:j] and '"target": "e[3,5]"' not in p[i:j]
    assert all(m["target"] in p[j:k] for m in case["reference_modification"])


def test_trial_class_is_task3s(base):
    """The block the service adds is Task 3's, from the same function."""
    from feedback_service_v31.service import ServiceTrialV31
    from tpo.public_case import public_view
    from tpo_v3.user_sim import SimulatedUserV3
    comps = FixedKeyComponents(base, {"P6s": {"first": HIGH, "clarified": HIGH}}, key="P6s")
    pc = public_view(P6S)
    t3 = TrialV31(pc, base, SimulatedUserV3(P6S, base), CONFIGS["A0B0C0"], "A0B0C0", 1, comps, None,
                  SERVICE_SETTINGS)
    t4 = ServiceTrialV31(pc, base, SimulatedUserV3(P6S, base), CONFIGS["A0B0C0"], "A0B0C0", 1, comps, None,
                         SERVICE_SETTINGS, session=P6S["model_modifications"])
    assert t3.blocks()[0] == t4.blocks()[0]
