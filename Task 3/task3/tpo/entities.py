"""Condition A: which decisions to attribute, from the complaint text alone (plan 3.5).
No hand labels are read; nothing mentioned means every decision of the current solution."""
import re

from .task2_bridge import canon

VEHICLE = re.compile(r"\b(?:vehicle|van|truck|driver|route)s?\s*(?:#|no\.?|number)?\s*(\d+)", re.I)
CUSTOMER = re.compile(r"\b(?:customer|client|stop)s?\s*(?:#|no\.?|number)?\s*"
                      r"(\d+(?:\s*(?:,\s*(?:and\s+|or\s+)?|and|&|or)\s*\d+)*)", re.I)
MAX_DECISIONS = 40


def extract(text, n, K):
    vehicles = sorted({int(m) for m in VEHICLE.findall(text) if 1 <= int(m) <= K})
    customers = set()
    for group in CUSTOMER.findall(text):
        customers |= {int(v) for v in re.findall(r"\d+", group) if 1 <= int(v) <= n}
    return {"vehicles": vehicles, "customers": sorted(customers)}


def _adj(a, b):
    return {"type": "ADJ", "i": min(a, b), "j": max(a, b)}


def _pair(t, a, b):
    return {"type": t, "i": min(a, b), "j": max(a, b)}


def decisions(sol, ent):
    routes = sol["routes"]
    veh = canon.vehicle_of(sol)
    out = []

    def add(d):
        if d not in out:
            out.append(d)

    def route_decisions(k):
        path = [0, *routes[k - 1], 0]
        for a, b in zip(path, path[1:]):
            add(_adj(a, b))
        r = routes[k - 1]
        for x in range(len(r)):
            for y in range(x + 1, len(r)):
                add(_pair("SAME", r[x], r[y]))

    for i in ent["customers"]:
        r = routes[veh[i] - 1]
        path = [0, *r, 0]
        pos = path.index(i)
        add(_adj(path[pos - 1], i))
        add(_adj(i, path[pos + 1]))
        for j in r:
            if j != i:
                add(_pair("SAME", i, j))
        for j in routes[2 - veh[i]]:
            add(_pair("SEP", i, j))
    for k in ent["vehicles"]:
        route_decisions(k)
    if not ent["customers"] and not ent["vehicles"]:
        for k in range(1, len(routes) + 1):
            route_decisions(k)
        for i in routes[0]:
            for j in routes[1]:
                add(_pair("SEP", i, j))
    return out[:MAX_DECISIONS]
