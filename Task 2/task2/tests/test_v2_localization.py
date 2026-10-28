"""task2_v2 localization rule (audit finding F5, Task 4's T7): agreement is counted on what the user can answer;
the clarifying question names the point of disagreement and never the modification type."""
import json
import os
import re

from components.state import make_state, state_for_case
from cvrp.validate import errors
from v2.localization import decide, describe_target

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST = {c["id"]: c for c in json.load(open(os.path.join(ROOT, "cases", "test_cases.json")))["cases"]}
REF = make_state({"routes": [[1, 4, 7, 2], [5, 3, 6, 8]]})
INTERNAL_WORDS = ("soft", "objective weight", "modification", "penalty", "W[", "L[", "A[")


def sample(target, aspect, mtype, direction="decrease", threshold=None, corrected=None, ambiguous=False, q=None,
           object_type="global", vehicle=None, customers=()):
    return {"valid": True, "target": target, "parse_status": "json_ok",
            "sample": {"object_type": object_type, "vehicle": vehicle, "customers": list(customers),
                       "aspect": aspect, "direction": direction, "modification_type": mtype, "threshold": threshold,
                       "corrected_value": corrected, "ambiguous": ambiguous, "clarifying_question": q,
                       "rationale": "test"}}


def _ok(out):
    assert errors("localization_output", out) == []
    if out["confidence"] == "low":
        assert not any(w in out["clarifying_question"] for w in INTERNAL_WORDS), out["clarifying_question"]


def test_t7_type_split_is_high_confidence():
    """Task 4's T7: five samples agree on balance <= 50 and split 3:2 on the modification type. v1: low, the user
    was asked about the target, the second pass split 3:2 again and the complaint stopped."""
    st = state_for_case(TEST["T7"])
    s = [sample("balance", "distance_balance", t, threshold=50)
         for t in ("add_soft_constraint", "set_objective_weight", "add_soft_constraint", "set_objective_weight",
                   "add_soft_constraint")]
    out = decide(s, st, TEST["T7"]["complaint"])
    _ok(out)
    assert out["confidence"] == "high"
    assert out["critique"]["modification_type"] == "add_soft_constraint"
    assert out["critique"]["threshold"] == 50
    assert out["diagnostics"]["modification_type_counts_among_agreeing"] == {"add_soft_constraint": 3,
                                                                             "set_objective_weight": 2}


def test_threshold_disagreement_asks_for_the_limit():
    s = [sample("L[2]", "route_length", "add_soft_constraint", threshold=t, object_type="vehicle", vehicle=2)
         for t in (180, 180, 150, 150, 180)]
    out = decide(s, REF, "Vehicle 2 drives too far.")
    _ok(out)
    assert out["confidence"] == "low" and out["diagnostics"]["disagreement"] == "threshold"
    assert "vehicle 2's route (211 km now)" in out["clarifying_question"]
    assert "180" in out["clarifying_question"] and "150" in out["clarifying_question"]


def test_missing_limit_in_some_samples():
    s = [sample("A[6]", "detour", "add_soft_constraint", threshold=t, object_type="customer", customers=[6])
         for t in (None, None, None, 70.5, 70.5)]
    out = decide(s, REF, "Customer 6 is on a long detour.")
    _ok(out)
    assert out["confidence"] == "low" and out["diagnostics"]["disagreement"] == "threshold"
    assert "for example 70.5" in out["clarifying_question"]


def test_same_limit_written_differently_agrees():
    s = [sample("balance", "distance_balance", "add_soft_constraint", threshold=t) for t in (50, 50.0, 50, 50, 50.0)]
    assert decide(s, REF, "x")["confidence"] == "high"


def test_target_disagreement_prefers_the_llm_question():
    q = "Do you mean vehicle 1's load (99 units), its route length (140 km), or its number of stops (4)?"
    s = [sample("W[1]", "load", "add_soft_constraint", ambiguous=True, q=q, object_type="vehicle", vehicle=1),
         sample("L[1]", "route_length", "add_soft_constraint", ambiguous=True, q=q, object_type="vehicle", vehicle=1),
         sample("W[1]", "load", "add_soft_constraint", object_type="vehicle", vehicle=1),
         sample("L[1]", "route_length", "add_soft_constraint", object_type="vehicle", vehicle=1),
         sample("W[1]", "load", "add_soft_constraint", object_type="vehicle", vehicle=1)]
    out = decide(s, REF, "Vehicle 1 is doing too much work.")
    _ok(out)
    assert (out["confidence"], out["clarifying_question"], out["diagnostics"]["disagreement"]) == ("low", q, "target")


def test_target_disagreement_without_llm_question():
    s = [sample("W[1]", "load", "add_soft_constraint", object_type="vehicle", vehicle=1)] * 3 + \
        [sample("L[1]", "route_length", "add_soft_constraint", object_type="vehicle", vehicle=1)] * 2
    out = decide(s, REF, "Vehicle 1 is doing too much work.")
    _ok(out)
    assert out["clarifying_question"] == ("Do you mean vehicle 1's load (99 units now) or the length of vehicle 1's "
                                          "route (140 km now)?")


def test_direction_disagreement():
    s = [sample("S[2]", "stops", "add_soft_constraint", direction=d, object_type="vehicle", vehicle=2)
         for d in ("decrease", "decrease", "increase", "increase", "decrease")]
    out = decide(s, REF, "Vehicle 2's stops are wrong.")
    _ok(out)
    assert out["diagnostics"]["disagreement"] == "direction"
    assert out["clarifying_question"] == "Should the number of stops of vehicle 2 (4 now) be lower or be higher?"


def test_ambiguous_but_agreeing_keeps_v1_behaviour():
    """T2's first pass: all five read W[1] but call the complaint ambiguous; the LLM's question is asked."""
    q = "Do you mean the load, the route length or the number of stops of vehicle 1?"
    s = [sample("W[1]", "load", "add_soft_constraint", ambiguous=True, q=q, object_type="vehicle", vehicle=1)] * 5
    out = decide(s, REF, "Vehicle 1 is doing too much work.")
    _ok(out)
    assert (out["confidence"], out["clarifying_question"], out["diagnostics"]["disagreement"]) == ("low", q, "none")


def test_invalid_samples_still_count():
    s = [sample("L[2]", "route_length", "add_soft_constraint", threshold=180, object_type="vehicle", vehicle=2)] * 3
    s += [{"valid": False, "reason": "json_error", "parse_status": "json_error", "sample": None}] * 2
    out = decide(s, REF, "Vehicle 2 drives too far.")
    _ok(out)
    assert out["confidence"] == "low"


def test_describe_every_target_kind():
    """Questions use the user's words, never internal IDs such as W[1]."""
    for tid in ("L[1]", "W[2]", "S[1]", "A[6]", "balance", "load_balance", "makespan", "sum_arrival", "e[0,8]",
                "same[4,5]", "sep[2,5]", "demand[7]", "coord[3]", "capacity"):
        text = describe_target(tid, REF)
        assert not re.search(r"[A-Za-z_]\[\d", text), (tid, text)
