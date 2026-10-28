"""Plan 5.1 items 9-10: one engine thread does all solver and LLM work; an LLM outage fails the job instead of
passing for low confidence or a rejected proposal."""
import threading

from tpo.components import Task2Components
from tpo.llm import StubLLM

from conftest import FIX_STOPS, by_iteration, complain, new_session


class NoResponseLLM(StubLLM):
    """What Task 2's LLMClient returns on a network error or HTTP 403: no exception, an empty result."""

    def __init__(self, script, roles):
        super().__init__(script)
        self.roles = roles

    def chat(self, messages, **kw):
        meta = kw.get("meta") or {}
        if meta.get("role", meta.get("component")) in self.roles:
            self.calls.append({"messages": messages, "meta": meta})
            return {"ok": False, "content": None, "parsed": None, "parse_status": "no_response"}
        return super().chat(messages, **kw)


def test_all_engine_work_runs_on_the_engine_thread(make):
    client, svc, llm, comps = make(by_iteration({1: FIX_STOPS}))
    sids = [new_session(client, config="A1B1C1")["session_id"] for _ in range(3)]
    out = {}

    def send(sid):
        out[sid] = svc.submit_feedback(sid, {"complaint": "Vehicle 2 has far too many stops today."}, True)
    threads = [threading.Thread(target=send, args=(sid,)) for sid in sids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(view["status"] == "awaiting_reply" and done for view, done in out.values())
    assert comps.threads and set(comps.threads) == {svc.worker.ident}
    assert svc.worker.ident != threading.get_ident()


def test_llm_outage_fails_the_feedback_instead_of_rejecting_the_proposal(make):
    client, *_ = make(llm=NoResponseLLM(by_iteration({1: FIX_STOPS}), roles=("propose",)))
    sid = new_session(client)["session_id"]
    v = complain(client, sid).json()
    assert v["status"] == "failed" and v["error"]["kind"] == "llm_unavailable" and v["iteration"] == 0
    s = client.get(f"/sessions/{sid}").json()
    assert s["current_plan"]["version"] == 0 and s["open_feedback"] is None and len(s["plans"]) == 1
    assert not client.get(f"/sessions/{sid}/iterations").json()


def test_llm_outage_during_localization_is_not_mistaken_for_low_confidence(make):
    llm = NoResponseLLM(by_iteration({1: FIX_STOPS}), roles=("localize",))
    client, *_ = make(llm=llm, components=lambda b, counting: Task2Components(b, counting, run_label="t4"))
    sid = new_session(client)["session_id"]
    v = complain(client, sid).json()
    assert v["status"] == "failed" and v["error"]["kind"] == "llm_unavailable"   # not needs_clarification
    assert len(llm.calls) == 5                                                   # Task 2's five samples
