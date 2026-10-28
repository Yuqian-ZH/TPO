"""task4_v2.1: a plan is shown only if its (routes, data) is new to the user in this complaint, and a data change is
listed, not called the user's correction. Each v2 defect is kept as a regression record next to the v2.1 behaviour."""
import pytest
from fastapi.testclient import TestClient

from feedback_service.app import create_app
from feedback_service_v2.service import DATA_NOTICE, build_service_v2
from feedback_service_v21.service import build_service_v21
from tpo.llm import StubLLM

from conftest import FIX_STOPS, HIGH, NO_CHANGE, REFERENCE, FixedKeyComponents, by_iteration, complain, counter_ids, \
    new_session

DEMAND_13 = {"rationale": "the user corrected customer 4's order", "modifications": [
    {"op": "modify_data", "field": "demand[4]", "value": 13}]}
DEMAND_5 = {"rationale": "r", "modifications": [{"op": "modify_data", "field": "demand[5]", "value": 13},
                                                {"op": "set_objective_weight", "term": "balance", "weight": 0.3}]}
CAPACITY = {"rationale": "r", "modifications": [{"op": "modify_data", "field": "capacity", "value": 120},
                                                FIX_STOPS["modifications"][0]]}
CORRECTION = "Customer 4 has changed its order: it is 13 units now, not 12. Please update the plan's data."
STOPS = "Vehicle 2 has far too many stops today."


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


def _start(serve, builder, script, complaint):
    client = serve(builder, by_iteration(script))
    sid = new_session(client, config="A0B0C0")["session_id"]
    return client, sid, complain(client, sid, complaint).json()


def test_correction_is_shown_with_the_changed_value(serve):
    client, sid, v = _start(serve, build_service_v21, {1: DEMAND_13}, CORRECTION)
    assert v["status"] == "awaiting_reply" and v["iteration"] == 1
    assert v["plan"]["routes"] == REFERENCE["routes"] and v["plan"]["source"]["kind"] == "data_corrected"
    assert v["plan"]["source"]["data_changes"] == ["customer 4's order size 12 -> 13"]
    assert "customer 4's order size 12 -> 13" in v["notice"] and "correction is applied" not in v["notice"]
    v = client.post(f"/feedback/{v['feedback_id']}/reply", json={"resolved": True}).json()
    assert v["status"] == "resolved" and v["notice"] is None
    s = client.get(f"/sessions/{sid}").json()
    assert [{k: x for k, x in m.items() if k != "id"} for m in s["accepted_modifications"]] == \
        DEMAND_13["modifications"]


@pytest.mark.parametrize("builder", [build_service_v2, build_service_v21])
def test_rejected_correction_that_reverts(serve, builder):
    """The user rejects the corrected plan; the next proposal drops the correction, so routes and data are the plan
    the user complained about. v2 showed it again, claiming the correction is in force; v2.1 runs on."""
    client, sid, v = _start(serve, builder, {1: DEMAND_13, 2: NO_CHANGE}, CORRECTION)
    assert v["plan"]["source"]["kind"] == "data_corrected"
    v = client.post(f"/feedback/{v['feedback_id']}/reply", json={"resolved": False, "comment": "no"}).json()
    if builder is build_service_v2:
        assert v["status"] == "awaiting_reply" and v["iteration"] == 2 and v["notice"] == DATA_NOTICE
        assert v["modifications_in_force"] == NO_CHANGE["modifications"]       # the correction is gone
        assert v["plan"]["metrics"]["W[1]"] == 99
    else:
        assert v["status"] == "not_converged" and v["iteration"] == 3
        assert [it["state_change"] for it in v["iterations"]] == ["data", None, None]
        assert client.get(f"/sessions/{sid}").json()["current_plan"]["version"] == 0


@pytest.mark.parametrize("builder", [build_service_v2, build_service_v21])
def test_unrequested_data_change(serve, builder):
    """A stops complaint; the LLM changes customer 5's demand and the routes stay. v2 called it the user's
    correction; v2.1 lists it and asks the user to check it."""
    _, _, v = _start(serve, builder, {1: DEMAND_5}, STOPS)
    assert v["status"] == "awaiting_reply" and v["latest_iteration"]["state_change"] == "data"
    if builder is build_service_v2:
        assert v["notice"] == DATA_NOTICE
    else:
        changes = v["plan"]["source"]["data_changes"]
        assert len(changes) == 1 and changes[0].startswith("customer 5's order size ")
        assert changes[0] in v["notice"] and "check" in v["notice"]


def test_new_routes_on_changed_data_list_the_change(serve):
    """v2 showed new routes on silently changed data without a notice."""
    _, _, v = _start(serve, build_service_v21, {1: CAPACITY}, STOPS)
    assert v["latest_iteration"]["state_change"] == "routes" and v["plan"]["source"]["kind"] == "refined"
    assert v["plan"]["source"]["data_changes"] == ["vehicle capacity 100 -> 120"]
    assert v["notice"].startswith("The data the plan uses also changed: vehicle capacity 100 -> 120.")


def test_new_routes_on_the_same_data_have_no_notice(serve):
    _, _, v = _start(serve, build_service_v21, {1: FIX_STOPS}, STOPS)
    assert v["latest_iteration"]["state_change"] == "routes"
    assert v["plan"]["source"]["data_changes"] == [] and v["notice"] is None


def test_change_that_moves_nothing_is_still_skipped(serve):
    _, _, v = _start(serve, build_service_v21, {1: NO_CHANGE}, STOPS)
    assert v["status"] == "not_converged" and v["iteration"] == 3
    assert [it["state_change"] for it in v["iterations"]] == [None, None, None]


def test_health_names_the_protocol(serve):
    client = serve(build_service_v21, by_iteration({1: NO_CHANGE}))
    assert client.get("/health").json()["protocol"] == "task4_v2.1"
