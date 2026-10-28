"""task4_v2 (audit F2): a data correction that leaves the optimal routes unchanged is shown and kept, not dropped."""
import pytest
from fastapi.testclient import TestClient

from feedback_service.app import create_app
from feedback_service.service import build_service
from feedback_service_v2.service import DATA_NOTICE, build_service_v2
from tpo.llm import StubLLM

from conftest import HIGH, NO_CHANGE, REFERENCE, FixedKeyComponents, by_iteration, complain, counter_ids, new_session

DEMAND_13 = {"rationale": "the user corrected customer 4's order", "modifications": [
    {"op": "modify_data", "field": "demand[4]", "value": 13}]}
COMPLAINT = "Customer 4 has changed its order: it is 13 units now, not 12. Please update the plan's data."


@pytest.fixture()
def serve(tmp_path):
    opened = []

    def _serve(builder, script):
        svc = builder(str(tmp_path / builder.__name__), llm=StubLLM(script), new_id=counter_ids(),
                      components_factory=lambda b, llm: FixedKeyComponents(b, {"X1": {"first": HIGH,
                                                                                      "clarified": HIGH}}))
        client = TestClient(create_app(svc))
        client.__enter__()
        opened.append(client)
        return client
    yield _serve
    for c in opened:
        c.__exit__(None, None, None)


def test_v1_drops_a_correction_that_leaves_the_routes_unchanged(serve):
    """The defect, kept as a regression record: three iterations, nothing shown, correction rolled back."""
    client = serve(build_service, by_iteration({1: DEMAND_13}))
    sid = new_session(client, config="A0B0C0")["session_id"]
    v = complain(client, sid, COMPLAINT).json()
    assert v["status"] == "not_converged" and v["iteration"] == 3
    s = client.get(f"/sessions/{sid}").json()
    assert s["accepted_modifications"] == [] and s["current_plan"]["version"] == 0


def test_v2_shows_the_corrected_plan_and_keeps_the_correction(serve):
    client = serve(build_service_v2, by_iteration({1: DEMAND_13}))
    sid = new_session(client, config="A0B0C0")["session_id"]
    v = complain(client, sid, COMPLAINT).json()
    assert v["status"] == "awaiting_reply" and v["iteration"] == 1
    assert v["notice"] == DATA_NOTICE
    assert v["plan"]["routes"] == REFERENCE["routes"] and v["plan"]["version"] == 1
    assert v["plan"]["source"]["kind"] == "data_corrected" and v["plan"]["metrics"]["W[1]"] == 100
    assert v["latest_iteration"]["state_change"] == "data"
    log = client.get(f"/sessions/{sid}/iterations").json()[0]
    assert log["refined_solution"]["state_change"] == "data" and log["feasibility"]["feasible"]
    v = client.post(f"/feedback/{v['feedback_id']}/reply", json={"resolved": True}).json()
    assert v["status"] == "resolved" and v["notice"] is None
    s = client.get(f"/sessions/{sid}").json()
    assert [{k: x for k, x in m.items() if k != "id"} for m in s["accepted_modifications"]] == \
        DEMAND_13["modifications"]
    assert s["current_plan"]["version"] == 1 and s["current_plan"]["metrics"]["W[1]"] == 100


def test_v2_still_skips_a_change_that_moves_nothing(serve):
    """Same routes and same data (a weight that changes nothing) is not shown to the user, as in v1."""
    client = serve(build_service_v2, by_iteration({1: NO_CHANGE}))
    sid = new_session(client, config="A0B0C0")["session_id"]
    v = complain(client, sid, "Vehicle 2 has far too many stops today.").json()
    assert v["status"] == "not_converged" and v["iteration"] == 3
    assert [it["state_change"] for it in v["iterations"]] == [None, None, None]


def test_v2_routes_change_is_unchanged_behaviour(serve):
    client = serve(build_service_v2, by_iteration({1: {"rationale": "r", "modifications": [
        {"op": "add_soft_constraint", "target": "S[2]", "sense": "<=", "rhs": 3, "penalty": 60}]}}))
    sid = new_session(client, config="A0B0C0")["session_id"]
    v = complain(client, sid, "Vehicle 2 has far too many stops today.").json()
    assert v["status"] == "awaiting_reply" and v["latest_iteration"]["state_change"] == "routes"
    assert v["plan"]["source"]["kind"] == "refined" and v["notice"] is None
