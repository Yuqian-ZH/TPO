"""Plan 5.1 item 1: API contract, ingestion storage, validation and conflicts."""
import json
import os
import time

from conftest import FIX_STOPS, MOVE, REFERENCE, by_iteration, complain, new_session


def test_health_instance_and_docs(make):
    client, *_ = make()
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["engine_thread_alive"] and h["default_config"] == "A0B0C1"
    inst = client.get("/instance").json()
    assert inst["capacity"] == 100 and len(inst["nodes"]) == 9
    assert client.get("/openapi.json").status_code == 200


def test_session_defaults_to_the_optimal_plan_in_reference_form(make):
    client, *_ = make()
    s = new_session(client)
    assert s["config"] == "A0B0C1" and s["max_iterations"] == 3
    assert s["current_plan"]["routes"] == REFERENCE["routes"] and s["current_plan"]["version"] == 0
    assert s["initial_plan"] == {"provided_by_client": False, "optimal_objective": 351.0, "is_optimal": True}


def test_session_validation(make):
    client, *_ = make()
    bad = [{"config": "S1"},                                                       # experiment arm, not offered
           {"model_modifications": [{"op": "add_soft_constraint", "target": "Z[9]", "sense": "<=", "rhs": 1,
                                     "penalty": 1}]},
           {"solution": {"routes": [[1, 2, 3, 4, 5, 6, 7, 8], []]}},                # empty route, over capacity
           {"solution": {"routes": [[1, 4, 7], [5, 3, 6, 8]]}},                     # customer 2 missing
           {"checker": {"name": "max_stops"}},                                     # unknown field
           {"max_iterations": 4}]
    for body in bad:
        assert client.post("/sessions", json=body).status_code == 422, body
    s = new_session(client, solution={"routes": [[1, 7, 4, 2], [5, 3, 6, 8]]}, label="mine")
    assert s["initial_plan"]["provided_by_client"] and not s["initial_plan"]["is_optimal"]
    t9 = new_session(client, model_modifications=[{"op": "modify_data", "field": "demand[3]", "value": 54}])
    assert t9["model_modifications"][0]["value"] == 54


def test_feedback_is_stored_with_its_solution_and_session(make, tmp_path):
    client, svc, *_ = make()
    s = new_session(client)
    r = complain(client, s["session_id"], solution_version=0)
    assert r.status_code == 200
    v = r.json()
    path = os.path.join(tmp_path, "store", "sessions", s["session_id"], "feedback", f"{v['feedback_id']}.json")
    with open(path) as f:
        stored = json.load(f)
    assert stored["complaint"] == "Vehicle 2 has far too many stops today."
    assert stored["session_id"] == s["session_id"]
    assert stored["solution"] == {"version": 0, "routes": REFERENCE["routes"]}
    events = [e["event"] for e in client.get(f"/sessions/{s['session_id']}/events").json()]
    assert events[:2] == ["session_created", "feedback_received"]


def test_conflicts_and_bad_requests(make):
    client, *_ = make(by_iteration({1: MOVE}))
    assert complain(client, "s_nope").status_code == 404
    assert client.get("/feedback/f_nope").status_code == 404
    sid = new_session(client)["session_id"]
    assert complain(client, sid, complaint="   ").status_code == 422
    assert complain(client, sid, solution_version=3).status_code == 409
    assert complain(client, sid, solution={"routes": [[2, 7, 4, 1], [5, 3, 6, 8]]}).status_code == 409
    v = complain(client, sid, solution={"routes": REFERENCE["routes"]}).json()
    assert v["status"] == "awaiting_reply"
    second = complain(client, sid, solution_version=v["plan"]["version"])
    assert second.status_code == 409 and second.json()["error"] == "feedback_open"
    assert client.post(f"/feedback/{v['feedback_id']}/clarification", json={"answer": "x"}).status_code == 409
    assert client.post(f"/feedback/{v['feedback_id']}/reply", json={"resolved": True}).json()["status"] == "resolved"
    assert client.post(f"/feedback/{v['feedback_id']}/reply", json={"resolved": True}).status_code == 409


def test_wait_false_returns_202_and_polling_reaches_the_result(make):
    client, *_ = make(by_iteration({1: FIX_STOPS}))
    sid = new_session(client)["session_id"]
    r = client.post(f"/sessions/{sid}/feedback?wait=false", json={"complaint": "Vehicle 2 has too many stops."})
    assert r.status_code in (200, 202)
    fid = r.json()["feedback_id"]
    for _ in range(200):
        v = client.get(f"/feedback/{fid}").json()
        if v["status"] == "awaiting_reply":
            break
        time.sleep(0.05)
    assert v["status"] == "awaiting_reply" and v["plan"]["metrics"]["S[2]"] == 3
