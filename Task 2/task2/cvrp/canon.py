"""Route bookkeeping shared by every component: metrics recomputed from routes, canonical form,
single anchor, change sets, and compilation of queries / decisions into primitive constraints.

A solution is {"routes": [route_of_vehicle_1, route_of_vehicle_2]}, each route a list of customers
in visiting order (depot 0 implicit at both ends)."""
from collections import Counter

OBJECTIVE_TERMS = ("balance", "makespan", "load_balance", "sum_arrival")


def route_length(route, c):
    path = [0, *route, 0]
    return sum(c[a][b] for a, b in zip(path, path[1:]))


def route_edges(route):
    """Undirected edges as a sorted list (a depot round trip 0-i-0 yields the edge (0, i) twice)."""
    path = [0, *route, 0]
    return sorted(tuple(sorted(e)) for e in zip(path, path[1:]))


def vehicle_of(sol):
    return {i: k + 1 for k, r in enumerate(sol["routes"]) for i in r}


def metrics(sol, data):
    """Every indicator, recomputed from the routes (never read from solver variables)."""
    c, q = data["c"], data["q"]
    m = {}
    arrival = {}
    for k, r in enumerate(sol["routes"], start=1):
        m[f"L[{k}]"] = route_length(r, c)
        m[f"W[{k}]"] = sum(q[i] for i in r)
        m[f"S[{k}]"] = len(r)
        acc, prev = 0, 0
        for i in r:
            acc += c[prev][i]
            arrival[i] = acc
            prev = i
    for i in sorted(arrival):
        m[f"A[{i}]"] = arrival[i]
    L = [m[f"L[{k}]"] for k in (1, 2)]
    W = [m[f"W[{k}]"] for k in (1, 2)]
    m["total_distance"] = sum(L)
    m["balance"] = abs(L[0] - L[1])
    m["makespan"] = max(L)
    m["load_balance"] = abs(W[0] - W[1])
    m["sum_arrival"] = sum(arrival.values())
    return m


def adjacency_count(sol, i, j):
    e = tuple(sorted((i, j)))
    return sum(route_edges(r).count(e) for r in sol["routes"])


def same_vehicle(sol, i, j):
    v = vehicle_of(sol)
    return int(v[i] == v[j])


def target_value(sol, data, target):
    """Value of a soft-constraint target / objective term on a solution."""
    if target.startswith(("e[", "same[", "sep[")):
        i, j = (int(t) for t in target[target.index("[") + 1:-1].split(","))
        if target.startswith("e["):
            return adjacency_count(sol, i, j)
        s = same_vehicle(sol, i, j)
        return s if target.startswith("same[") else 1 - s
    return metrics(sol, data)[target]


def violation(value, sense, rhs):
    if sense == "<=":
        return max(0.0, value - rhs)
    if sense == ">=":
        return max(0.0, rhs - value)
    return abs(value - rhs)


def objective(sol, data, mods):
    """Total distance + weighted objective terms + soft-constraint penalties (data mods already in data)."""
    m = metrics(sol, data)
    val = m["total_distance"]
    weights = objective_weights(mods)
    for t, w in weights.items():
        val += w * m[t]
    for mod in mods:
        if mod["op"] == "add_soft_constraint":
            val += mod["penalty"] * violation(target_value(sol, data, mod["target"]), mod["sense"], mod["rhs"])
    return val


def objective_weights(mods):
    w = {}
    for mod in mods:
        if mod["op"] == "set_objective_weight":
            w[mod["term"]] = mod["weight"]
    return {t: v for t, v in w.items() if v}


def is_feasible(sol, data):
    routes = sol["routes"]
    seen = [i for r in routes for i in r]
    return (len(routes) == data["K"] and all(routes) and sorted(seen) == list(range(1, data["n"] + 1))
            and all(sum(data["q"][i] for i in r) <= data["Q"] for r in routes))


def orient(route):
    return list(route) if len(route) < 2 or route[0] < route[-1] else list(route[::-1])


def canonical(sol):
    """Reference form: the route holding customer 1 is vehicle 1; each route runs so that its first
    customer has a smaller index than its last."""
    routes = [orient(r) for r in sol["routes"]]
    if 1 not in routes[0]:
        routes = routes[::-1]
    return {"routes": routes}


def unlabeled_key(sol):
    """Identity of a solution up to vehicle swap and route reversal."""
    return tuple(sorted(tuple(orient(r)) for r in sol["routes"]))


def change_set(old, new):
    vo, vn = vehicle_of(old), vehicle_of(new)
    moved = sorted(i for i in vo if vo[i] != vn[i])
    eo = Counter(e for r in old["routes"] for e in route_edges(r))
    en = Counter(e for r in new["routes"] for e in route_edges(r))
    added = sorted((en - eo).elements())
    removed = sorted((eo - en).elements())
    reversed_ = [k + 1 for k, (a, b) in enumerate(zip(old["routes"], new["routes"]))
                 if len(a) >= 2 and list(b) == list(a)[::-1]]
    return {"moved": moved, "added_edges": [list(e) for e in added],
            "removed_edges": [list(e) for e in removed], "reversed": reversed_}


def change_key(cs):
    """Comparison key for change-set agreement; the reversal flag is reported but not compared."""
    return (tuple(cs["moved"]), tuple(map(tuple, cs["added_edges"])), tuple(map(tuple, cs["removed_edges"])))


# ---------- queries, decisions and the single anchor ----------

def _custs(*nodes):
    return {v for v in nodes if v != 0}


def _target_customers(target, sol):
    """Customers on the route(s) of the indicator a modification touches."""
    v = vehicle_of(sol)
    routes = sol["routes"]
    everyone = set(v)
    if target in OBJECTIVE_TERMS or target == "capacity":
        return everyone
    head, idx = target[:target.index("[")], target[target.index("[") + 1:-1]
    if head in ("L", "W", "S"):
        return set(routes[int(idx) - 1])
    nodes = [int(t) for t in idx.split(",")]
    out = set()
    for i in nodes:
        if i != 0:
            out |= set(routes[v[i] - 1])
    return out


def mod_customers(mod, sol):
    if mod["op"] == "add_soft_constraint":
        return _target_customers(mod["target"], sol)
    if mod["op"] == "set_objective_weight":
        return _target_customers(mod["term"], sol)
    return _target_customers(mod["field"], sol)


def compile_query(query, sol):
    """-> (primitive constraints, modifications, involved customers)."""
    t = query["type"]
    if t == "FIX_ARC":
        return [dict(query)], [], _custs(query["i"], query["j"])
    if t == "MOVE":
        return [dict(query)], [], {query["i"]}
    if t == "SWAP":
        v = vehicle_of(sol)
        i, j = query["i"], query["j"]
        if v[i] == v[j]:
            raise ValueError(f"SWAP({i},{j}): customers are already on the same vehicle")
        return [{"type": "MOVE", "i": i, "k": v[j]}, {"type": "MOVE", "i": j, "k": v[i]}], [], {i, j}
    if t in ("FORCE_ADJ", "FORBID_ADJ", "FORCE_SAME", "FORCE_SEP"):
        return [dict(query)], [], _custs(query["i"], query["j"])
    if t == "APPLY_MODIFICATIONS":
        inv = set()
        for m in query["mods"]:
            inv |= mod_customers(m, sol)
        return [], list(query["mods"]), inv
    raise ValueError(f"unknown query type {t}")


def anchor(involved, sol, n):
    """Smallest customer not involved in the query, fixed to its current vehicle (customer 1 if every
    customer is involved).  Convention constraint: excluded from attribution sets."""
    free = [i for i in range(1, n + 1) if i not in involved]
    a = free[0] if free else 1
    return {"type": "MOVE", "i": a, "k": vehicle_of(sol)[a], "role": "anchor"}


FORBID = {"ADJ": "FORBID_ADJ", "SAME": "FORCE_SEP", "SEP": "FORCE_SAME"}


def forbid_decision(decision):
    return {"type": FORBID[decision["type"]], "i": decision["i"], "j": decision["j"], "role": "perturbation"}


def decision_holds(sol, decision):
    i, j = decision["i"], decision["j"]
    if decision["type"] == "ADJ":
        return adjacency_count(sol, i, j) > 0
    s = same_vehicle(sol, i, j)
    return bool(s) if decision["type"] == "SAME" else not s


def satisfies(sol, prim):
    """Does a labeled, directed solution satisfy a primitive constraint?"""
    t, v = prim["type"], vehicle_of(sol)
    if t == "FIX_ARC":
        path = [0, *sol["routes"][prim["k"] - 1], 0]
        return (prim["i"], prim["j"]) in set(zip(path, path[1:]))
    if t == "MOVE":
        return v[prim["i"]] == prim["k"]
    if t == "FORCE_ADJ":
        return adjacency_count(sol, prim["i"], prim["j"]) > 0
    if t == "FORBID_ADJ":
        return adjacency_count(sol, prim["i"], prim["j"]) == 0
    if t == "FORCE_SAME":
        return v[prim["i"]] == v[prim["j"]]
    if t == "FORCE_SEP":
        return v[prim["i"]] != v[prim["j"]]
    raise ValueError(t)
