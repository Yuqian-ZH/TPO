"""Instance data: loading, distances, and data modifications (modify_data). No solving logic here."""
import copy
import json
import math
import re

K = 2  # vehicles


def dist(a, b):
    """Rounded Euclidean distance, round half up (exact .5 cannot occur for integer coordinates)."""
    return int(math.floor(math.hypot(a[0] - b[0], a[1] - b[1]) + 0.5))


def make_data(coords, demand, capacity, vehicles=K):
    """coords/demand are indexed by node, node 0 = depot (demand 0)."""
    n = len(coords) - 1
    coords = [tuple(c) for c in coords]
    c = [[dist(coords[i], coords[j]) for j in range(n + 1)] for i in range(n + 1)]
    return {"n": n, "K": vehicles, "Q": capacity, "coords": coords, "q": list(demand), "c": c}


def load_instance(path):
    with open(path) as f:
        inst = json.load(f)
    nodes = sorted(inst["nodes"], key=lambda d: d["id"])
    data = make_data([(d["x"], d["y"]) for d in nodes], [d["demand"] for d in nodes],
                     inst["capacity"], inst["vehicles"])
    assert data["c"] == inst["distance_matrix"], "distance matrix in file does not match coordinates"
    return data


_FIELD = re.compile(r"^(demand|coord)\[(\d+)\]$")


def apply_data_mods(data, mods):
    """Return a new data dict with every modify_data op applied (other ops are ignored)."""
    coords, q, Q = list(data["coords"]), list(data["q"]), data["Q"]
    for m in mods:
        if m["op"] != "modify_data":
            continue
        if m["field"] == "capacity":
            Q = m["value"]
            continue
        kind, i = _FIELD.match(m["field"]).groups()
        i = int(i)
        assert 1 <= i <= data["n"], m
        if kind == "demand":
            q[i] = m["value"]
        else:
            coords[i] = tuple(m["value"])
    return make_data(coords, q, Q, data["K"])


def triangle_violations(c):
    n = len(c)
    return [(i, j, k) for i in range(n) for j in range(n) for k in range(n)
            if len({i, j, k}) == 3 and i < k and c[i][k] > c[i][j] + c[j][k]]


def clone(data):
    return copy.deepcopy(data)
