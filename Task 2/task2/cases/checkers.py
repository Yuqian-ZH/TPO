"""Programmatic "is the complaint gone?" checks. Every checker takes a solution and the evaluation data
(original instance + the case's model data modifications + allowed data corrections) and returns
{"passed", "value", "threshold"}.  Task 3 uses complaint_resolved() as its convergence test."""
from cvrp import canon
from cvrp.data import apply_data_mods


def _m(sol, data):
    return canon.metrics(sol, data)


def _le(value, limit):
    return {"passed": value <= limit + 1e-9, "value": value, "threshold": limit}


def route_length_max(sol, data, k, max):
    return _le(_m(sol, data)[f"L[{k}]"], max)


def route_length_ratio(sol, data, k, other, max_ratio):
    m = _m(sol, data)
    return _le(round(m[f"L[{k}]"] / m[f"L[{other}]"], 4), max_ratio)


def max_load(sol, data, k, max):
    return _le(_m(sol, data)[f"W[{k}]"], max)


def max_stops(sol, data, k, max):
    return _le(_m(sol, data)[f"S[{k}]"], max)


def detour_ratio(sol, data, i, max_ratio):
    """Arrival mileage of customer i divided by its straight-line distance from the depot."""
    return _le(round(_m(sol, data)[f"A[{i}]"] / data["c"][0][i], 4), max_ratio)


def arrival_max(sol, data, i, max):
    return _le(_m(sol, data)[f"A[{i}]"], max)


def balance_max(sol, data, max):
    return _le(_m(sol, data)["balance"], max)


def makespan_max(sol, data, max):
    return _le(_m(sol, data)["makespan"], max)


def load_balance_max(sol, data, max):
    return _le(_m(sol, data)["load_balance"], max)


def avg_arrival_max(sol, data, max):
    return _le(round(_m(sol, data)["sum_arrival"] / data["n"], 4), max)


def not_adjacent(sol, data, i, j):
    v = canon.adjacency_count(sol, i, j)
    return {"passed": v == 0, "value": v, "threshold": 0}


def same_vehicle(sol, data, i, j):
    v = canon.same_vehicle(sol, i, j)
    return {"passed": v == 1, "value": v, "threshold": 1}


def separate(sol, data, i, j):
    v = canon.same_vehicle(sol, i, j)
    return {"passed": v == 0, "value": v, "threshold": 0}


def feasible_under(sol, data, corrections):
    """The corrections are already part of the evaluation data; they are listed for the record."""
    loads = [sum(data["q"][i] for i in r) for r in sol["routes"]]
    return {"passed": canon.is_feasible(sol, data), "value": loads, "threshold": data["Q"]}


CHECKERS = {f.__name__: f for f in (route_length_max, route_length_ratio, max_load, max_stops, detour_ratio,
                                     arrival_max, balance_max, makespan_max, load_balance_max, avg_arrival_max,
                                     not_adjacent, same_vehicle, separate, feasible_under)}


def eval_data(case, base):
    return apply_data_mods(base, list(case.get("model_modifications", [])) + list(case["allowed_data_corrections"]))


def run_checker(case, sol, base):
    spec = case["checker"]
    return CHECKERS[spec["name"]](sol, eval_data(case, base), **spec["params"])


def complaint_resolved(case, sol, base):
    """Convergence test: feasible under the evaluation data and the case's checker passes."""
    data = eval_data(case, base)
    res = run_checker(case, sol, base)
    feasible = canon.is_feasible(sol, data)
    return {"resolved": feasible and res["passed"], "feasible": feasible, "checker": res}
