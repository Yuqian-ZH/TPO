"""Plan 5.1 items 2-6: clarification gate, iteration log, replies, automatic continuation, acceptance, rollback."""
import pytest

from feedback_service.bridge import FEEDBACK_UNRESOLVED

from conftest import (BALANCE, FIX_STOPS, HIGH, INVALID, LOW, MOVE, REFERENCE, by_iteration, complain,
                      new_session, proposal_prompts)

COMPLAINT = "Vehicle 2 has far too many stops today."


def test_low_confidence_asks_and_never_reaches_tpo(make):
    client, svc, llm, _ = make(first=LOW, clarified=LOW)
    sid = new_session(client)["session_id"]
    v = complain(client, sid).json()
    assert v["status"] == "needs_clarification"
    assert v["clarification"] == {"question": LOW["clarification_question"], "answer": None}
    assert not proposal_prompts(llm)
    v = client.post(f"/feedback/{v['feedback_id']}/clarification", json={"answer": "I mean the route."}).json()
    assert v["status"] == "stopped_low_confidence" and v["iteration"] == 0
    assert not proposal_prompts(llm) and not client.get(f"/sessions/{sid}/iterations").json()
    s = client.get(f"/sessions/{sid}").json()
    assert s["open_feedback"] is None and s["current_plan"]["version"] == 0
    events = [e["event"] for e in client.get(f"/sessions/{sid}/events").json()]
    assert events[-3:] == ["clarification_requested", "clarification_received", "stopped_low_confidence"]


def test_clarified_complaint_reaches_tpo_with_the_answer(make):
    client, svc, llm, _ = make(first=LOW, clarified=HIGH)
    sid = new_session(client)["session_id"]
    fid = complain(client, sid).json()["feedback_id"]
    v = client.post(f"/feedback/{fid}/clarification", json={"answer": "The number of stops."}).json()
    assert v["status"] == "awaiting_reply" and v["critique"]["clarification"]["answer"] == "The number of stops."
    log = client.get(f"/sessions/{sid}/iterations").json()[0]
    assert log["trigger"] == "clarification"
    assert "## Clarification" in log["critique"]["text"] and "The number of stops." in log["critique"]["text"]
    assert log["critique"]["structured"]["target"] == "S[2]"


@pytest.mark.parametrize("config", ["A0B0C0", "A0B0C1", "A1B1C0", "A1B1C1"])
def test_every_iteration_logs_the_five_required_fields(make, config):
    client, svc, llm, _ = make(by_iteration({1: FIX_STOPS}))
    sid = new_session(client, config=config)["session_id"]
    v = complain(client, sid).json()
    assert v["status"] == "awaiting_reply" and v["plan"]["metrics"]["S[2]"] == 3
    (log,) = client.get(f"/sessions/{sid}/iterations").json()
    assert log["input_solution"]["routes"] == REFERENCE["routes"] and log["input_solution"]["version"] == 0
    assert log["complaint"] == COMPLAINT
    assert log["critique"]["text"].startswith("## User complaint")
    assert (log["critique"]["structured"] is not None) == (config[-1] == "1")
    assert ("## Decision attribution" in log["critique"]["text"]) == (config[1] == "1")
    assert log["refined_solution"]["version"] == 1 and log["refined_solution"]["metrics"]["S[2]"] == 3
    assert log["refined_solution"]["new_plan"] and log["refined_solution"]["changes"]["moved"]
    f = log["feasibility"]
    assert f["solver_status"] == "optimal" and f["feasible"] and f["feasible_on_confirmed_data"]
    assert len(log["candidates"]) == (3 if config[3] == "1" else 1)
    assert log["detail"]["proposal_prompt"] == proposal_prompts(llm)[0]


def test_unresolved_reply_reaches_the_next_prompt_then_the_budget_ends_and_the_plan_reverts(make):
    client, svc, llm, _ = make(by_iteration({1: MOVE}))
    sid = new_session(client)["session_id"]
    v = complain(client, sid).json()
    assert v["status"] == "awaiting_reply" and v["plan"]["version"] == 1
    v = client.post(f"/feedback/{v['feedback_id']}/reply",
                    json={"resolved": False, "comment": "SENTINEL_COMMENT still four stops"}).json()
    # iteration 2 proposes the same list, gets the same routes, so iteration 3 runs without asking the user
    assert v["status"] == "not_converged" and v["iteration"] == 3
    logs = client.get(f"/sessions/{sid}/iterations").json()
    assert [x["trigger"] for x in logs] == ["feedback", "reply", "auto_continue"]
    assert [x["refined_solution"]["new_plan"] for x in logs] == [True, False, False]
    p = proposal_prompts(llm)
    assert "SENTINEL_COMMENT" not in p[0]
    assert p[1].count("SENTINEL_COMMENT") == 1 and p[2].count("SENTINEL_COMMENT") == 2   # attempts 1 and 2
    s = client.get(f"/sessions/{sid}").json()
    assert s["current_plan"]["version"] == 0 and s["open_feedback"] is None and len(s["plans"]) == 2
    assert "reverted" in [e["event"] for e in client.get(f"/sessions/{sid}/events").json()]


def test_rejected_proposal_continues_without_asking_the_user(make):
    client, svc, llm, _ = make(by_iteration({1: INVALID, 2: FIX_STOPS}))
    sid = new_session(client)["session_id"]
    v = complain(client, sid).json()
    assert v["status"] == "awaiting_reply" and v["iteration"] == 2 and not v["replies"]
    logs = client.get(f"/sessions/{sid}/iterations").json()
    assert [(x["status"], x["trigger"]) for x in logs] == [("rejected", "feedback"), ("committed", "auto_continue")]
    assert logs[0]["feasibility"]["solver_status"] == "not_solved" and logs[0]["feasibility"]["feasible"]
    second = proposal_prompts(llm)[1]
    assert "The proposed modifications were rejected" in second
    assert FEEDBACK_UNRESOLVED.format(complaint=COMPLAINT) in second


def test_an_accepted_fix_stays_in_force_for_the_next_complaint(make):
    def answer(messages, meta):
        return BALANCE if "unbalanced" in messages[1]["content"] else FIX_STOPS
    client, svc, llm, _ = make(answer, first=HIGH)
    sid = new_session(client)["session_id"]
    v = complain(client, sid).json()
    v = client.post(f"/feedback/{v['feedback_id']}/reply", json={"resolved": True}).json()
    assert v["status"] == "resolved"
    s = client.get(f"/sessions/{sid}").json()
    assert s["current_plan"]["version"] == 1 and s["accepted_modifications"] == [
        {**FIX_STOPS["modifications"][0], "id": "acc1_1"}]
    v = complain(client, sid, complaint="The two routes are unbalanced.", solution_version=1).json()
    prompt = proposal_prompts(llm)[-1]
    assert "## Modifications accepted earlier (kept in force)" in prompt and '"target": "S[2]"' in prompt
    assert proposal_prompts(llm)[0].count("accepted earlier") == 0
    assert v["modifications_in_force"] == [BALANCE["modifications"][0]]
    assert v["plan"]["metrics"]["S[2]"] <= 3           # the accepted cap still holds


def test_stop_returns_to_the_plan_complained_about(make):
    client, *_ = make(by_iteration({1: FIX_STOPS}))
    sid = new_session(client)["session_id"]
    v = complain(client, sid).json()
    v = client.post(f"/feedback/{v['feedback_id']}/reply", json={"resolved": False, "stop": True}).json()
    assert v["status"] == "stopped_by_user"
    s = client.get(f"/sessions/{sid}").json()
    assert s["current_plan"]["version"] == 0 and s["accepted_modifications"] == []
    assert complain(client, sid, solution_version=0).status_code == 200
