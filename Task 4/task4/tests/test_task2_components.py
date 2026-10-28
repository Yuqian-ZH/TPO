"""The service on the real Task 2 components (localization, attribution) and Task 3's v2 probe; only the LLM is
a stub. Localization samples follow Task 2's sample schema (same as Task 3's tests)."""
from tpo.components import Task2Components

from conftest import FIX_STOPS, complain, new_session

SAMPLE = {"object_type": "vehicle", "vehicle": 2, "customers": [], "aspect": "stops", "direction": "decrease",
          "modification_type": "add_soft_constraint", "threshold": 3, "corrected_value": None, "ambiguous": False,
          "clarifying_question": None, "rationale": "stops of vehicle 2"}
AMBIGUOUS = {**SAMPLE, "aspect": "route_length", "ambiguous": True,
             "clarifying_question": "Is it the distance, the load or the number of stops?"}


def script(first):
    def answer(messages, meta):
        if meta.get("component") == "localize":
            return first
        if meta.get("component") == "localize_clarified":
            return SAMPLE
        return {"choice": 1, "reason": "r"} if meta.get("role") == "select" else FIX_STOPS
    return answer


def real(b, counting):
    return Task2Components(b, counting, run_label="t4")


def test_full_system_on_the_real_components(make):
    client, svc, llm, _ = make(script(SAMPLE), components=real)
    sid = new_session(client, config="A1B1C1")["session_id"]
    v = complain(client, sid).json()
    assert v["status"] == "awaiting_reply" and v["plan"]["metrics"]["S[2]"] == 3
    assert v["critique"]["structured"]["target"] == "S[2]" and v["critique"]["structured"]["threshold"] == 3
    (log,) = client.get(f"/sessions/{sid}/iterations").json()
    assert "## Structured localization" in log["critique"]["text"]
    assert "## Decision attribution" in log["critique"]["text"]
    assert log["critique"]["structured"]["evidence"]["S[2]"] == 4         # evidence on the input plan
    assert all(c["probe"]["feasible"] and c["probe"]["level"] in ("L0", "L1", "L2") for c in log["candidates"])
    assert log["detail"]["probe_vs_commit"]["objective_1pct"]
    seeds = {c["seed"] for c in llm.calls if c["meta"].get("component") == "localize"}
    assert len(seeds) == 5


def test_real_localization_asks_about_an_ambiguous_complaint(make):
    client, svc, llm, _ = make(script(AMBIGUOUS), components=real)
    sid = new_session(client)["session_id"]
    v = complain(client, sid, complaint="Vehicle 2 is doing too much.").json()
    assert v["status"] == "needs_clarification"
    assert v["clarification"]["question"] == AMBIGUOUS["clarifying_question"]
    v = client.post(f"/feedback/{v['feedback_id']}/clarification", json={"answer": "Too many stops."}).json()
    assert v["status"] == "awaiting_reply" and v["localization"]["target"] == "S[2]"
