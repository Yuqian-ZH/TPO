"""What a task2_v3 case asks for, as conditions on a plan, and what the simulated user says when one fails.

Every requirement the user has is a condition, stated in the complaint or in the explanation the user gives when
asked or when a plan misses the point (task2_v1 kept the limit of its ambiguous complaints for the clarification
answer only, which only condition C ever received). A plan resolves the complaint when it is feasible on the real
data (instance, session data, and the corrections the user stated) and every condition holds. Vehicle k is the same
physical vehicle as in the plan complained about; max_moved and route_kept compare with that plan."""
from cvrp import canon
from cvrp.data import apply_data_mods

KINDS = ("max", "same", "separate", "not_adjacent", "max_moved", "total_max", "route_kept")


def real_data(case, base):
    return apply_data_mods(base, list(case.get("model_modifications", [])) +
                           list(case.get("allowed_data_corrections", [])))


def _value(target, sol, data):
    if target == "avg_arrival":
        return round(canon.metrics(sol, data)["sum_arrival"] / data["n"], 4)
    return canon.target_value(sol, data, target)


def _edges(route):
    return canon.route_edges(route)


def evaluate(cond, sol, start, data):
    """{"passed", "value", "limit"} of one condition."""
    k, p = cond["kind"], cond["params"]
    if k == "max":
        v = _value(p["target"], sol, data)
        return {"passed": v <= p["max"] + 1e-9, "value": v, "limit": p["max"]}
    if k in ("same", "separate"):
        v = canon.same_vehicle(sol, p["i"], p["j"])
        return {"passed": bool(v) == (k == "same"), "value": v, "limit": 1 if k == "same" else 0}
    if k == "not_adjacent":
        v = canon.adjacency_count(sol, p["i"], p["j"])
        return {"passed": v == 0, "value": v, "limit": 0}
    if k == "max_moved":
        moved = canon.change_set(start, sol)["moved"]
        return {"passed": len(moved) <= p["max"], "value": moved, "limit": p["max"]}
    if k == "total_max":
        v = canon.metrics(sol, data)["total_distance"]
        return {"passed": v <= p["max"] + 1e-9, "value": v, "limit": p["max"]}
    if k == "route_kept":
        r0, r1 = start["routes"][p["k"] - 1], sol["routes"][p["k"] - 1]
        return {"passed": _edges(r0) == _edges(r1), "value": r1, "limit": r0}
    raise ValueError(f"unknown condition kind {k}")


def _node(i):
    return "the depot" if i == 0 else f"customer {i}"


def _path(route):
    return " -> ".join(map(str, [0, *route, 0]))


def unmet_text(cond, res):
    """The user's words for a failed condition, with the value the plan shows."""
    k, p, v = cond["kind"], cond["params"], res["value"]
    if k == "max":
        t, lim = p["target"], p["max"]
        head = t.split("[")[0]
        idx = t[t.index("[") + 1:-1] if "[" in t else None
        return {"L": f"vehicle {idx}'s route is {v} km long, and it must be at most {lim:g} km",
                "W": f"vehicle {idx} carries {v} units, and it must carry at most {lim:g}",
                "S": f"vehicle {idx} has {v} stops, and it must have at most {lim:g}",
                "A": f"customer {idx} is reached only after {v} km, and it must be reached within {lim:g} km",
                "balance": f"the two routes differ by {v} km, and they may differ by at most {lim:g} km",
                "load_balance": f"the two loads differ by {v} units, and they may differ by at most {lim:g}",
                "makespan": f"the longer route is {v} km, and it must be at most {lim:g} km",
                "avg_arrival": f"customers are reached after {v:g} km on average, and it must be at most {lim:g} km"
                }[head]
    if k == "same":
        return f"customers {p['i']} and {p['j']} are on different trucks, and they must share one"
    if k == "separate":
        return f"customers {p['i']} and {p['j']} are on the same truck, and they must not be"
    if k == "not_adjacent":
        return f"a truck still drives directly between {_node(p['i'])} and {_node(p['j'])}"
    if k == "max_moved":
        return (f"{len(v)} customers changed trucks ({', '.join(map(str, v))}), and at most {p['max']} may change "
                f"trucks")
    if k == "total_max":
        return f"the total distance is {v} km, and I can accept at most {p['max']:g} km"
    if k == "route_kept":
        return f"vehicle {p['k']}'s route was changed to {_path(v)}; it has to stay {_path(res['limit'])}"
    raise ValueError(k)


def infeasible_text(sol, data):
    over = [(k, sum(data["q"][i] for i in r)) for k, r in enumerate(sol["routes"], 1)]
    over = [f"vehicle {k} would carry {w} units, more than its capacity of {data['Q']}" for k, w in over
            if w > data["Q"]]
    return "this plan can't be used: with the real orders " + " and ".join(over)


def verdict(case, sol, base):
    """Is the complaint resolved by this plan? With every condition's result and the user's words for the failures."""
    data = real_data(case, base)
    feasible = canon.is_feasible(sol, data)
    results = [{**c, **evaluate(c, sol, case["solution"], data)} for c in case["conditions"]]
    unmet = ([] if feasible else [infeasible_text(sol, data)]) + \
        [unmet_text(c, r) for c, r in zip(case["conditions"], results) if not r["passed"]]
    return {"resolved": feasible and all(r["passed"] for r in results), "feasible": feasible,
            "conditions": results, "unmet": unmet}


def feedback(case, v, explained):
    """What the user says about a plan that does not resolve the complaint. The first time in a conversation the
    user also explains what they meant (the same words a clarifying question gets)."""
    now = "In the new plan " + "; ".join(v["unmet"]) + "."
    if explained:
        return "That does not solve it yet. " + now
    return f"That does not solve it. What I mean is: {case['explanation']} {now}"
