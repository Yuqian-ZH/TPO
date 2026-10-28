"""Plan 5.1 item 8: the files are the source of truth; a restarted service continues where the last one stopped."""
from conftest import FIX_STOPS, MOVE, by_iteration, complain, new_session, proposal_prompts


def test_a_complaint_awaiting_its_reply_survives_a_restart(make, tmp_path):
    data = tmp_path / "shared"
    first, *_ = make(by_iteration({1: MOVE, 2: FIX_STOPS}), data=data)
    sid = new_session(first)["session_id"]
    fid = complain(first, sid).json()["feedback_id"]
    first.__exit__(None, None, None)

    second, svc, llm, _ = make(by_iteration({1: MOVE, 2: FIX_STOPS}), data=data)
    v = second.get(f"/feedback/{fid}").json()
    assert v["status"] == "awaiting_reply" and v["plan"]["version"] == 1 and v["iteration"] == 1
    v = second.post(f"/feedback/{fid}/reply", json={"resolved": False, "comment": "SENTINEL_AFTER_RESTART"}).json()
    assert v["status"] == "awaiting_reply" and v["iteration"] == 2 and v["plan"]["metrics"]["S[2]"] == 3
    (prompt,) = proposal_prompts(llm)
    assert "Attempt 1:" in prompt and "SENTINEL_AFTER_RESTART" in prompt
    assert [x["iteration"] for x in second.get(f"/sessions/{sid}/iterations").json()] == [1, 2]
    assert new_session(second)["session_id"] != sid          # ids stay unique across restarts


def test_a_job_interrupted_by_a_restart_fails_and_rolls_back(make, tmp_path):
    data = tmp_path / "shared"
    first, svc, *_ = make(by_iteration({1: MOVE}), data=data)
    sid = new_session(first)["session_id"]
    fid = complain(first, sid).json()["feedback_id"]
    fb = svc.store.get_feedback(fid)                         # as if the process died inside the next job
    fb["status"] = "processing"
    svc.store.save_feedback(fb)
    first.__exit__(None, None, None)

    second, *_ = make(data=data)
    assert second.get("/health").json()["recovered_at_startup"] == [fid]
    v = second.get(f"/feedback/{fid}").json()
    assert v["status"] == "failed" and v["error"]["kind"] == "interrupted_by_restart"
    s = second.get(f"/sessions/{sid}").json()
    assert s["current_plan"]["version"] == 0 and s["open_feedback"] is None
    assert complain(second, sid, solution_version=0).status_code == 200
