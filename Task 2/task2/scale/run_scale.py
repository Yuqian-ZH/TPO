"""Stage 7 (optional): latency of local re-optimization vs full re-solve on larger random instances
(12 / 16 / 20 customers, 3 vehicles). Uses its own K-vehicle model; the frozen Task 2 code is not touched
and nothing here feeds back into the main experiment.
  python -m scale.run_scale [--sizes 12 16 20] [--queries 20] [--repeats 3] [--time-limit 300]"""
import argparse
import json
import math
import os
import random
import time

import gurobipy as gp
from gurobipy import GRB

from cvrp.data import make_data

HERE = os.path.dirname(os.path.abspath(__file__))
SEED, K, LICENSE_LIMIT = 20261022, 3, 2000


def instance(n):
    rng = random.Random(SEED + n)
    pts = []
    while len(pts) < n:
        p = (rng.randint(0, 100), rng.randint(0, 100))
        if p != (50, 50) and p not in pts:
            pts.append(p)
    q = [0] + [rng.randint(10, 55) for _ in range(n)]
    cap = math.ceil(sum(q) / (K * 0.85))  # average load 85% of capacity
    return make_data([(50, 50)] + pts, q, max(cap, max(q)), K)


class KModel:
    """Three-index CVRP with K vehicles (each used once), load-based MTZ, distance objective."""

    def __init__(self, data, env, time_limit):
        n, c, q, Q = data["n"], data["c"], data["q"], data["Q"]
        self.data, self.N, self.C, self.Ks = data, range(n + 1), range(1, n + 1), range(1, K + 1)
        m = self.m = gp.Model(env=env)
        for k, v in {"MIPGap": 0, "Threads": 1, "Seed": 0, "OutputFlag": 0, "TimeLimit": time_limit}.items():
            m.setParam(k, v)
        N, C, Ks = self.N, self.C, self.Ks
        x = self.x = {(k, i, j): m.addVar(vtype=GRB.BINARY, obj=c[i][j]) for k in Ks for i in N for j in N if i != j}
        y = self.y = {(k, i): m.addVar(vtype=GRB.BINARY) for k in Ks for i in C}
        usum = sum(q)
        u = {i: m.addVar(lb=q[i], ub=usum) for i in C}
        for i in C:
            m.addConstr(gp.quicksum(y[k, i] for k in Ks) == 1)
        for k in Ks:
            m.addConstr(gp.quicksum(q[i] * y[k, i] for i in C) <= Q)
            m.addConstr(gp.quicksum(x[k, 0, j] for j in C) == 1)
            for i in C:
                m.addConstr(gp.quicksum(x[k, i, j] for j in N if j != i) == y[k, i])
                m.addConstr(gp.quicksum(x[k, j, i] for j in N if j != i) == y[k, i])
        for i in C:
            for j in C:
                if i != j:
                    m.addConstr(u[j] >= u[i] + q[j] - usum * (1 - gp.quicksum(x[k, i, j] for k in Ks)))
        m.update()

    def size(self):
        return {"vars": self.m.NumVars, "constrs": self.m.NumConstrs}

    def solve(self):
        t0 = time.perf_counter()
        self.m.optimize()
        st = {GRB.OPTIMAL: "optimal", GRB.INFEASIBLE: "infeasible", GRB.TIME_LIMIT: "time_limit"}.get(
            self.m.Status, str(self.m.Status))
        out = {"status": st, "runtime_s": self.m.Runtime, "wall_s": time.perf_counter() - t0}
        if self.m.SolCount:
            out["objective"] = self.m.ObjVal
            out["gap"] = self.m.MIPGap
            out["routes"] = self.routes()
        return out

    def routes(self):
        rs = []
        for k in self.Ks:
            r, cur = [], 0
            while True:
                cur = next(j for j in self.N if j != cur and self.x[k, cur, j].X > 0.5)
                if cur == 0:
                    break
                r.append(cur)
            rs.append(r)
        return rs

    def add(self, query, anchors):
        x, y, cons = self.x, self.y, []
        if query["type"] == "MOVE":
            cons.append(self.m.addConstr(y[query["k"], query["i"]] >= 1))
        else:
            cons.append(self.m.addConstr(x[query["k"], query["i"], query["j"]] >= 1))
        for i, k in anchors:
            cons.append(self.m.addConstr(y[k, i] >= 1))
        self.m.update()
        return cons

    def start(self, routes):
        for v in self.x.values():
            v.Start = 0
        for v in self.y.values():
            v.Start = 0
        for k, r in enumerate(routes, start=1):
            path = [0, *r, 0]
            for a, b in zip(path, path[1:]):
                self.x[k, a, b].Start = 1
            for i in r:
                self.y[k, i].Start = 1


def involved(q):
    return {q["i"]} if q["type"] == "MOVE" else {q["i"], q["j"]}


def anchors_for(q, veh, n):
    """One anchor per vehicle: its smallest customer not involved in the query (fixes all K labels)."""
    out = []
    for k in range(1, K + 1):
        free = [i for i in range(1, n + 1) if veh[i] == k and i not in involved(q)]
        if free:
            out.append((min(free), k))
    return out


def local(model, q, ref, anchors, n, c):
    veh = {i: k for k, r in enumerate(ref, start=1) for i in r}
    t0 = time.perf_counter()
    cons = model.add(q, anchors)
    model.start(ref)
    solve_only, tried, res = 0.0, [], None
    for level in ("L0", "L1", "L2"):
        free = set(involved(q))
        if level == "L1":
            for i in involved(q):
                free.update(sorted((j for j in range(1, n + 1) if j != i), key=lambda j: (c[i][j], j))[:2])
        if level == "L2":
            free = set(range(1, n + 1))
        fixed = [model.y[veh[i], i] for i in range(1, n + 1) if i not in free]
        for v in fixed:
            v.LB = 1
        model.m.update()
        res = model.solve()
        solve_only += res["runtime_s"]
        tried.append((level, res["status"]))
        for v in fixed:
            v.LB = 0
        model.m.update()
        if "objective" in res:
            break
    for con in cons:
        model.m.remove(con)
    for v in model.m.getVars():
        v.Start = GRB.UNDEFINED
    model.m.update()
    return {**res, "level": tried[-1][0], "levels_tried": tried, "with_setup_s": time.perf_counter() - t0,
            "solve_only_s": solve_only}


def full(data, env, tl, q, anchors):
    t0 = time.perf_counter()
    m = KModel(data, env, tl)
    m.add(q, anchors)
    res = m.solve()
    return {**res, "with_setup_s": time.perf_counter() - t0, "solve_only_s": res["runtime_s"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[12, 16, 20])
    ap.add_argument("--queries", type=int, default=20)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--time-limit", type=float, default=300)
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    env = gp.Env(params={"OutputFlag": 0})
    summary = {"seed": SEED, "vehicles": K, "repeats": args.repeats, "time_limit_s": args.time_limit, "sizes": {}}
    for n in args.sizes:
        data = instance(n)
        ref_model = KModel(data, env, args.time_limit)
        size = ref_model.size()
        assert size["vars"] <= LICENSE_LIMIT and size["constrs"] <= LICENSE_LIMIT, size
        ref = ref_model.solve()
        print(f"n={n}: size {size}, reference {ref['status']} obj {ref.get('objective')} in {ref['runtime_s']:.1f}s",
              flush=True)
        routes = ref["routes"]
        veh = {i: k for k, r in enumerate(routes, start=1) for i in r}
        rng = random.Random(SEED * 31 + n)
        queries = []
        while len(queries) < args.queries:
            if len(queries) % 2 == 0:
                i = rng.randint(1, n)
                q = {"type": "MOVE", "i": i, "k": rng.choice([k for k in range(1, K + 1) if k != veh[i]])}
            else:
                i, j = rng.sample(range(1, n + 1), 2)
                q = {"type": "FIX_ARC", "k": rng.randint(1, K), "i": i, "j": j}
            if q not in queries:
                queries.append(q)
        resident = KModel(data, env, args.time_limit)
        rows = []
        for q in queries:
            anchors = anchors_for(q, veh, n)
            loc = [local(resident, q, routes, anchors, n, data["c"]) for _ in range(args.repeats)]
            fl = [full(data, env, args.time_limit, q, anchors) for _ in range(args.repeats)]
            rows.append({"query": q, "anchors": anchors, "local": loc, "full": fl})
            print(f"  {q} local {loc[0]['status']}/{loc[0]['level']} {loc[0].get('objective')} "
                  f"{loc[0]['with_setup_s']:.2f}s | full {fl[0]['status']} {fl[0].get('objective')} "
                  f"{fl[0]['with_setup_s']:.2f}s", flush=True)
        summary["sizes"][str(n)] = {"capacity": data["Q"], "total_demand": sum(data["q"]), "model_size": size,
                                    "reference": {k: ref[k] for k in ("status", "objective", "gap", "runtime_s")},
                                    "rows": rows}
        with open(os.path.join(args.out, "scale_raw.json"), "w") as f:
            json.dump(summary, f, indent=1)


if __name__ == "__main__":
    main()
