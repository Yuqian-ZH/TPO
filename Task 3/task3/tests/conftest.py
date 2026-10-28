import sys

sys.dont_write_bytecode = True

import pytest  # noqa: E402

from tpo.task2_bridge import load_frozen_instance  # noqa: E402

REFERENCE = {"routes": [[1, 4, 7, 2], [5, 3, 6, 8]]}   # Task 2 reference optimum, 351
SENTINELS = ("SENTINEL_GT", "SENTINEL_WHY", "SENTINEL_WHATIF", "SENTINEL_SCENARIO", "SENTINEL_CLARITY",
             "SENTINEL_OBJECT", "987.654", "max_stops")


@pytest.fixture(scope="session")
def base():
    return load_frozen_instance()


def synthetic_case(cid="X1", complaint="Vehicle 2 has far too many stops today.", **over):
    """Unit-test case in Task 2's format (not a Task 2 dev or test case). Every non-public field carries a
    sentinel so that leaks into prompts are detectable."""
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
NO_EFFECT = {"rationale": "tiny nudge", "modifications": [
    {"op": "add_soft_constraint", "target": "S[2]", "sense": "<=", "rhs": 3, "penalty": 0.5}]}
