import os
import sys
import threading

sys.dont_write_bytecode = True

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from feedback_service.app import create_app  # noqa: E402
from feedback_service.bridge import TASK2_ROOT, TASK3_ROOT, t2  # noqa: E402
from feedback_service.service import build_service  # noqa: E402
from tpo.components import ReferenceComponents  # noqa: E402
from tpo.llm import StubLLM  # noqa: E402


def file_snapshot(root):
    out = {}
    for d, _, files in os.walk(root):
        for f in files:
            p = os.path.join(d, f)
            st = os.stat(p)
            out[os.path.relpath(p, root)] = (st.st_size, st.st_mtime_ns)
    return out


# taken at collection time; test_zz_readonly.py compares at the end of the run
BEFORE = {"task2": file_snapshot(TASK2_ROOT), "task3": file_snapshot(TASK3_ROOT)}

REFERENCE = {"routes": [[1, 4, 7, 2], [5, 3, 6, 8]]}   # Task 2 reference optimum, 351

# Same synthetic case as Task 3's tests (not a Task 2 dev or test case); non-public fields carry sentinels.
SENTINELS = ("SENTINEL_GT", "SENTINEL_WHY", "SENTINEL_WHATIF", "SENTINEL_SCENARIO", "SENTINEL_CLARITY",
             "SENTINEL_OBJECT", "987.654", "max_stops")


def synthetic_case(cid="X1", complaint="Vehicle 2 has far too many stops today.", **over):
    case = {"id": cid, "split": "unit", "scenario": "SENTINEL_SCENARIO", "model_modifications": [],
            "solution": {"routes": [list(r) for r in REFERENCE["routes"]]}, "complaint": complaint,
            "clarity": "SENTINEL_CLARITY", "complaint_object": "SENTINEL_OBJECT",
            "clarification_answer": "SENTINEL_CLARIFICATION: it is the number of stops.",
            "why_question": "SENTINEL_WHY", "why_decision": {"type": "ADJ", "i": 1, "j": 4},
            "what_if_question": "SENTINEL_WHATIF", "what_if": {"type": "FIX_ARC", "k": 1, "i": 4, "j": 1},
            "checker": {"name": "max_stops", "params": {"k": 2, "max": 3}}, "allowed_data_corrections": [],
            "reference_modification": [{"op": "add_soft_constraint", "target": "S[2]", "sense": "<=", "rhs": 3,
                                        "penalty": 987.654}],
            "gt": {"localization": "SENTINEL_GT", "attribution": "SENTINEL_GT", "counterfactual": "SENTINEL_GT"}}
    case.update(over)
    return case


HIGH = {"confidence": "high", "target": "S[2]", "aspect": "stops", "direction": "decrease",
        "modification_type": "add_soft_constraint", "evidence": {"S[2]": 4}, "clarification_question": None}
LOW = {"confidence": "low", "target": None, "aspect": None, "direction": None, "modification_type": None,
       "evidence": {}, "clarification_question": "Do you mean distance, load or number of stops?"}

FIX_STOPS = {"rationale": "cap stops of vehicle 2", "modifications": [
    {"op": "add_soft_constraint", "target": "S[2]", "sense": "<=", "rhs": 3, "penalty": 60}]}
MOVE = {"rationale": "break edge 4-7", "modifications": [                     # new plan, vehicle 2 keeps 4 stops
    {"op": "add_soft_constraint", "target": "e[4,7]", "sense": "==", "rhs": 0, "penalty": 100}]}
NO_CHANGE = {"rationale": "mild balance weight", "modifications": [            # same routes as the input plan
    {"op": "set_objective_weight", "term": "balance", "weight": 0.3}]}
BALANCE = {"rationale": "balance the routes", "modifications": [
    {"op": "set_objective_weight", "term": "balance", "weight": 1}]}
INVALID = "this is not JSON"


def by_iteration(plan, choice=1):
    """Stub answers: proposals by iteration (dict t -> answer, last one repeats), selector picks `choice`."""
    def answer(messages, meta):
        if meta.get("role") == "select":
            return {"choice": choice, "reason": "r"}
        if meta.get("role") == "propose":
            return plan[min(meta["iteration"], max(plan))]
        raise AssertionError(f"unexpected LLM call {meta}")
    return answer


class FixedKeyComponents(ReferenceComponents):
    """ReferenceComponents answers localization by case id; the service passes its feedback id instead.
    Also records the thread every component call runs on."""

    def __init__(self, base, localizations, key="X1"):
        super().__init__(base, localizations)
        self.key, self.threads = key, []

    def _mark(self):
        self.threads.append(threading.get_ident())

    def localize(self, case_mods, sol, complaint, clarification, run, case_id):
        self._mark()
        return super().localize(case_mods, sol, complaint, clarification, run, self.key)

    def attribute(self, *a):
        self._mark()
        return super().attribute(*a)

    def probe(self, *a):
        self._mark()
        return super().probe(*a)

    def refresh_critique(self, *a):
        self._mark()
        return super().refresh_critique(*a)


def counter_ids():
    counters = {}

    def new_id(prefix):
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}_{counters[prefix]:04d}"
    return new_id


@pytest.fixture(scope="session")
def base():
    return t2.load_frozen_instance()


@pytest.fixture()
def make(tmp_path):
    """make(script, first=HIGH, clarified=None, ...) -> (client, service, stub llm, components)."""
    opened = []

    def _make(script=None, first=HIGH, clarified=None, data=None, llm=None, components=None, **kw):
        llm = llm or StubLLM(script or by_iteration({1: FIX_STOPS}))
        made = {}

        def factory(b, counting):
            made["c"] = components(b, counting) if components else FixedKeyComponents(
                b, {"X1": {"first": first, "clarified": clarified or first}})
            return made["c"]
        svc = build_service(str(data or tmp_path / "store"), llm=llm, components_factory=factory,
                            new_id=counter_ids(), **kw)
        client = TestClient(create_app(svc))
        client.__enter__()
        opened.append(client)
        return client, svc, llm, made["c"]

    yield _make
    for c in opened:
        try:
            c.__exit__(None, None, None)
        except RuntimeError:   # already shut down by the test (restart scenarios)
            pass


def new_session(client, **body):
    r = client.post("/sessions", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def complain(client, sid, complaint="Vehicle 2 has far too many stops today.", **extra):
    return client.post(f"/sessions/{sid}/feedback", json={"complaint": complaint, **extra})


def proposal_prompts(llm):
    return [c["messages"][1]["content"] for c in llm.calls if c["meta"].get("role") == "propose"]
