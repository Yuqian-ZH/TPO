"""Brute-force CVRP solver: enumerates every labeled, directed solution (both vehicles used).
Independent of model.py: it never builds or calls a MIP; every indicator is evaluated with numpy
from enumerated routes."""
import itertools

import numpy as np

from .data import apply_data_mods

EPS = 1e-6
ONLY_LE = ("balance", "makespan", "load_balance", "sum_arrival")


class Oracle:
    def __init__(self, data):
        self.data = data
        n, c, q = data["n"], data["c"], data["q"]
        self.n = n
        routes, rmask, rlen, rload = [], [], [], []
        arr_rows, arc_rows = [], []
        for size in range(1, n + 1):
            for subset in itertools.combinations(range(1, n + 1), size):
                mask = sum(1 << (i - 1) for i in subset)
                load = sum(q[i] for i in subset)
                for perm in itertools.permutations(subset):
                    arr = np.zeros(n + 1)
                    arcs = np.zeros((n + 1, n + 1), dtype=bool)
                    acc, prev = 0, 0
                    for i in perm:
                        acc += c[prev][i]
                        arr[i] = acc
                        arcs[prev, i] = True
                        prev = i
                    arcs[prev, 0] = True
                    routes.append(perm)
                    rmask.append(mask)
                    rlen.append(acc + c[prev][0])
                    rload.append(load)
                    arr_rows.append(arr)
                    arc_rows.append(arcs)
        self.routes = routes
        self.rmask = np.array(rmask, dtype=np.int64)
        self.rlen = np.array(rlen, dtype=float)
        self.rload = np.array(rload, dtype=float)
        self.rstops = np.array([len(r) for r in routes], dtype=float)
        self.rarr = np.array(arr_rows)
        self.rarc = np.array(arc_rows)
        full = (1 << n) - 1
        by_mask = {}
        for idx, m in enumerate(rmask):
            by_mask.setdefault(m, []).append(idx)
        r1, r2 = [], []
        for m, ids in by_mask.items():
            if m == full:
                continue
            other = by_mask[full ^ m]
            r1.append(np.repeat(ids, len(other)))
            r2.append(np.tile(other, len(ids)))
        self.r1 = np.concatenate(r1)
        self.r2 = np.concatenate(r2)

    # ---------- per-solution quantities ----------
    def _pair(self, a):
        return a[self.r1], a[self.r2]

    def _vehicle_route(self, k):
        return self.r1 if k == 1 else self.r2

    def _on(self, i, k):
        return ((self.rmask[self._vehicle_route(k)] >> (i - 1)) & 1).astype(bool)

    def _adj_count(self, i, j):
        r1, r2 = self.r1, self.r2
        a = self.rarc
        return (a[r1, i, j].astype(int) + a[r1, j, i] + a[r2, i, j] + a[r2, j, i])

    def _same(self, i, j):
        return (self._on(i, 1) & self._on(j, 1)) | (self._on(i, 2) & self._on(j, 2))

    def target(self, name):
        L1, L2 = self._pair(self.rlen)
        W1, W2 = self._pair(self.rload)
        if name in ("L[1]", "L[2]"):
            return L1 if name == "L[1]" else L2
        if name in ("W[1]", "W[2]"):
            return W1 if name == "W[1]" else W2
        if name in ("S[1]", "S[2]"):
            s1, s2 = self._pair(self.rstops)
            return s1 if name == "S[1]" else s2
        if name == "balance":
            return np.abs(L1 - L2)
        if name == "makespan":
            return np.maximum(L1, L2)
        if name == "load_balance":
            return np.abs(W1 - W2)
        if name == "sum_arrival":
            tot = self.rarr.sum(axis=1)
            return tot[self.r1] + tot[self.r2]
        head, idx = name[:name.index("[")], name[name.index("[") + 1:-1]
        if head == "A":
            i = int(idx)
            return self.rarr[self.r1, i] + self.rarr[self.r2, i]
        i, j = (int(t) for t in idx.split(","))
        if head == "e":
            return self._adj_count(i, j).astype(float)
        s = self._same(i, j).astype(float)
        if head == "same":
            return s
        if head == "sep":
            return 1.0 - s
        raise ValueError(name)

    def mask(self, prim):
        t = prim["type"]
        if t == "FIX_ARC":
            return self.rarc[self._vehicle_route(prim["k"]), prim["i"], prim["j"]]
        if t == "MOVE":
            return self._on(prim["i"], prim["k"])
        if t == "FORCE_ADJ":
            return self._adj_count(prim["i"], prim["j"]) > 0
        if t == "FORBID_ADJ":
            return self._adj_count(prim["i"], prim["j"]) == 0
        if t == "FORCE_SAME":
            return self._same(prim["i"], prim["j"])
        if t == "FORCE_SEP":
            return ~self._same(prim["i"], prim["j"])
        raise ValueError(t)

    def evaluate(self, mods=(), prims=(), capacity=True):
        """Objective of every solution; +inf where infeasible. capacity: True, False, or the tuple of
        vehicles whose capacity constraint is kept."""
        L1, L2 = self._pair(self.rlen)
        obj = L1 + L2
        weights = {}
        for m in mods:  # "set" semantics: the last weight given for a term wins
            if m["op"] == "set_objective_weight":
                assert m["weight"] >= 0, m
                weights[m["term"]] = m["weight"]
        for term, w in weights.items():
            if w:
                obj = obj + w * self.target(term)
        for m in mods:
            if m["op"] == "add_soft_constraint":
                assert m["target"].split("[")[0] not in ONLY_LE or m["sense"] == "<=", m
                v = self.target(m["target"])
                if m["sense"] == "<=":
                    viol = np.maximum(0.0, v - m["rhs"])
                elif m["sense"] == ">=":
                    viol = np.maximum(0.0, m["rhs"] - v)
                else:
                    viol = np.abs(v - m["rhs"])
                obj = obj + m["penalty"] * viol
        ok = np.ones(len(obj), dtype=bool)
        keep = (1, 2) if capacity is True else (capacity or ())
        W1, W2 = self._pair(self.rload)
        if 1 in keep:
            ok &= W1 <= self.data["Q"]
        if 2 in keep:
            ok &= W2 <= self.data["Q"]
        for p in prims:
            ok &= self.mask(p)
        return np.where(ok, obj, np.inf)

    def solution(self, idx):
        return {"routes": [list(self.routes[self.r1[idx]]), list(self.routes[self.r2[idx]])]}

    def solve(self, mods=(), prims=(), capacity=True):
        """-> dict(feasible, objective, optimal: [labeled directed solutions], indices)."""
        obj = self.evaluate(mods, prims, capacity)
        best = obj.min()
        if not np.isfinite(best):
            return {"feasible": False, "objective": None, "optimal": [], "obj": obj}
        idx = np.flatnonzero(obj <= best + EPS)
        return {"feasible": True, "objective": float(best), "optimal": [self.solution(i) for i in idx],
                "obj": obj, "idx": idx}


_CACHE = {}


def oracle_for(data, mods=()):
    """Oracle on the data after modify_data ops (cached per effective data)."""
    eff = apply_data_mods(data, mods)
    key = (tuple(eff["coords"]), tuple(eff["q"]), eff["Q"])
    if key not in _CACHE:
        _CACHE[key] = Oracle(eff)
    return _CACHE[key]
