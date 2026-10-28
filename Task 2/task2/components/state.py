"""state = {"instance": <cvrp_instance.json content>, "modifications": [...], "solution": {"routes": [...]}}.
Everything a component needs travels in the state; nothing is read from globals."""
import hashlib
import json
import os

from cvrp import canon
from cvrp.data import apply_data_mods, make_data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTANCE = os.path.join(ROOT, "instance", "cvrp_instance.json")


def make_state(solution, modifications=(), instance_path=INSTANCE):
    return {"instance": json.load(open(instance_path)), "modifications": list(modifications), "solution": solution}


def state_for_case(case, instance_path=INSTANCE):
    return make_state(case["solution"], case["model_modifications"], instance_path)


def base_data(state):
    nodes = sorted(state["instance"]["nodes"], key=lambda d: d["id"])
    return make_data([(d["x"], d["y"]) for d in nodes], [d["demand"] for d in nodes],
                     state["instance"]["capacity"], state["instance"]["vehicles"])


def model_data(state):
    """Data after the state's modify_data operations."""
    return apply_data_mods(base_data(state), state["modifications"])


def model_key(state):
    """Identifies the model (instance + modifications), not the current solution."""
    blob = json.dumps({"i": state["instance"], "m": state["modifications"]}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def solution_summary(state):
    data = model_data(state)
    sol = state["solution"]
    m = canon.metrics(sol, data)
    return {"routes": {f"vehicle {k}": [0, *r, 0] for k, r in enumerate(sol["routes"], start=1)},
            "metrics": m, "objective": canon.objective(sol, data, state["modifications"])}
