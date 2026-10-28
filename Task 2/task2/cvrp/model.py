"""Three-index CVRP MIP in Gurobi, plus modifications (section 10 format) and primitive query
constraints, all reversible so one resident model can serve many queries."""
import time

import gurobipy as gp
from gurobipy import GRB

from .data import apply_data_mods, clone

PARAMS = {"MIPGap": 0, "Threads": 1, "Seed": 0, "OutputFlag": 0}
ONLY_LE = ("A", "balance", "makespan", "load_balance", "sum_arrival")
_ENV = None


def gurobi_env():
    global _ENV
    if _ENV is None:
        _ENV = gp.Env(params={"OutputFlag": 0})
    return _ENV


class CVRPModel:
    def __init__(self, data, mods=()):
        self.data = clone(data)
        self.m = gp.Model("cvrp", env=gurobi_env())
        for k, v in PARAMS.items():
            self.m.setParam(k, v)
        self._build()
        self._set_data(self.data)
        self.weights = {}
        self._soft_count = 0
        for mod in mods:
            self.apply_modification(mod)

    # ---------- construction ----------
    def _build(self):
        n, K, m = self.data["n"], self.data["K"], self.m
        self.N, self.C, self.Ks = range(n + 1), range(1, n + 1), range(1, K + 1)
        N, C, Ks = self.N, self.C, self.Ks
        self.x = {(k, i, j): m.addVar(vtype=GRB.BINARY, name=f"x[{k},{i},{j}]")
                  for k in Ks for i in N for j in N if i != j}
        self.y = {(k, i): m.addVar(vtype=GRB.BINARY, name=f"y[{k},{i}]") for k in Ks for i in C}
        self.u = {i: m.addVar(name=f"u[{i}]") for i in C}
        self.L = {k: m.addVar(name=f"L[{k}]", obj=1.0) for k in Ks}
        self.W = {k: m.addVar(name=f"W[{k}]") for k in Ks}
        self.S = {k: m.addVar(name=f"S[{k}]") for k in Ks}
        self.A = {i: m.addVar(name=f"A[{i}]") for i in C}
        self.aux = {t: m.addVar(name=t) for t in ("balance", "makespan", "load_balance")}
        x, y = self.x, self.y
        self.con = {}

        def add(name, expr):
            self.con[name] = m.addConstr(expr, name=name)

        for i in C:
            add(f"visit[{i}]", gp.quicksum(y[k, i] for k in Ks) == 1)
        for k in Ks:
            add(f"cap[{k}]", gp.quicksum(y[k, i] for i in C) <= 0)  # coefficients set in _set_data
            add(f"depot_out[{k}]", gp.quicksum(x[k, 0, j] for j in C) == 1)
            for i in C:
                add(f"flow_out[{k},{i}]", gp.quicksum(x[k, i, j] for j in N if j != i) == y[k, i])
                add(f"flow_in[{k},{i}]", gp.quicksum(x[k, j, i] for j in N if j != i) == y[k, i])
        for i in C:
            for j in C:
                if i != j:
                    used = gp.quicksum(x[k, i, j] for k in Ks)
                    add(f"mtz[{i},{j}]", self.u[j] - self.u[i] - used >= 0)
        for i in N:
            for j in C:
                if i != j:
                    used = gp.quicksum(x[k, i, j] for k in Ks)
                    lhs = self.A[j] - (self.A[i] if i else 0)
                    add(f"arr[{i},{j}]", lhs - used >= 0)
        for k in Ks:
            add(f"def_L[{k}]", self.L[k] - gp.quicksum(x[k, i, j] for i in N for j in N if i != j) == 0)
            add(f"def_W[{k}]", self.W[k] - gp.quicksum(y[k, i] for i in C) == 0)
            add(f"def_S[{k}]", self.S[k] - gp.quicksum(y[k, i] for i in C) == 0)
            add(f"def_makespan[{k}]", self.aux["makespan"] - self.L[k] >= 0)
        add("def_balance[1]", self.aux["balance"] - self.L[1] + self.L[2] >= 0)
        add("def_balance[2]", self.aux["balance"] - self.L[2] + self.L[1] >= 0)
        add("def_load_balance[1]", self.aux["load_balance"] - self.W[1] + self.W[2] >= 0)
        add("def_load_balance[2]", self.aux["load_balance"] - self.W[2] + self.W[1] >= 0)
        self.m.update()

    def _set_data(self, data):
        """(Re)write every data-dependent coefficient, bound and right-hand side."""
        self.data = data
        c, q, Q, m = data["c"], data["q"], data["Q"], self.m
        N, C, Ks, x = self.N, self.C, self.Ks, self.x
        usum = sum(q[i] for i in C)                     # u is cumulative load, bounded by total demand,
        a_ub = sum(max(row) for row in c)               # so MTZ never implies capacity
        big_a = a_ub + max(max(row) for row in c)
        for i in C:
            self.u[i].LB, self.u[i].UB = q[i], usum
            self.A[i].UB = a_ub
        for k in Ks:
            self.con[f"cap[{k}]"].RHS = Q
            for i in C:
                m.chgCoeff(self.con[f"cap[{k}]"], self.y[k, i], q[i])
                m.chgCoeff(self.con[f"def_W[{k}]"], self.y[k, i], -q[i])
            for i in N:
                for j in N:
                    if i != j:
                        m.chgCoeff(self.con[f"def_L[{k}]"], x[k, i, j], -c[i][j])
        for i in C:
            for j in C:
                if i != j:
                    con = self.con[f"mtz[{i},{j}]"]
                    for k in Ks:
                        m.chgCoeff(con, x[k, i, j], -usum)
                    con.RHS = q[j] - usum
        for i in N:
            for j in C:
                if i != j:
                    con = self.con[f"arr[{i},{j}]"]
                    if i == 0:
                        for k in Ks:
                            m.chgCoeff(con, x[k, 0, j], -c[0][j])
                        con.RHS = 0
                    else:
                        for k in Ks:
                            m.chgCoeff(con, x[k, i, j], -big_a)
                        con.RHS = c[i][j] - big_a
        m.update()

    # ---------- modifications (section 10) ----------
    def _target_expr(self, target):
        head = target.split("[", 1)[0]
        idx = target[target.index("[") + 1:-1] if "[" in target else ""
        if head == "L":
            return self.L[int(idx)], []
        if head == "W":
            return self.W[int(idx)], []
        if head == "S":
            return self.S[int(idx)], []
        if head == "A":
            return self.A[int(idx)], []
        if head in self.aux:
            return self.aux[head], []
        if head == "sum_arrival":
            return gp.quicksum(self.A.values()), []
        i, j = (int(t) for t in idx.split(","))
        if head == "e":
            return gp.quicksum(self.x[k, i, j] + self.x[k, j, i] for k in self.Ks), []
        # same[i,j] / sep[i,j]: z_k = y[k,i] * y[k,j]
        tag = self._soft_count
        z = {k: self.m.addVar(vtype=GRB.BINARY, name=f"soft_aux[{tag},z,{k}]") for k in self.Ks}
        extra = list(z.values())
        for k in self.Ks:
            extra.append(self.m.addConstr(z[k] <= self.y[k, i], name=f"soft_aux[{tag},a,{k}]"))
            extra.append(self.m.addConstr(z[k] <= self.y[k, j], name=f"soft_aux[{tag},b,{k}]"))
            extra.append(self.m.addConstr(z[k] >= self.y[k, i] + self.y[k, j] - 1, name=f"soft_aux[{tag},c,{k}]"))
        same = gp.quicksum(z.values())
        if head == "same":
            return same, extra
        if head == "sep":
            return 1 - same, extra
        raise ValueError(target)

    def apply_modification(self, mod):
        """Apply one modification in place; returns a callable that undoes it."""
        op = mod["op"]
        if op == "modify_data":
            old = self.data
            self._set_data(apply_data_mods(old, [mod]))
            return lambda: self._set_data(old)
        if op == "set_objective_weight":
            term, w = mod["term"], float(mod["weight"])
            assert w >= 0, mod
            old = self.weights.get(term, 0.0)
            self._set_weight(term, w)
            return lambda: self._set_weight(term, old)
        if op == "add_soft_constraint":
            target, sense, rhs, pen = mod["target"], mod["sense"], mod["rhs"], float(mod["penalty"])
            assert target.split("[")[0] not in ONLY_LE or sense == "<=", mod
            self._soft_count += 1
            sid = mod.get("id", f"soft_{self._soft_count}")
            expr, extra = self._target_expr(target)
            v = self.m.addVar(obj=pen, name=f"soft[{sid}],viol")
            if sense == "<=":
                cons = [self.m.addConstr(expr - v <= rhs, name=f"soft[{sid}]")]
            elif sense == ">=":
                cons = [self.m.addConstr(expr + v >= rhs, name=f"soft[{sid}]")]
            else:
                cons = [self.m.addConstr(v >= expr - rhs, name=f"soft[{sid},+]"),
                        self.m.addConstr(v >= rhs - expr, name=f"soft[{sid},-]")]
            self.m.update()
            items = [v, *cons, *extra]

            def undo():
                for it in items:
                    self.m.remove(it)
                self.m.update()
            return undo
        raise ValueError(f"unknown modification op {op}")

    def _set_weight(self, term, w):
        self.weights[term] = w
        if term == "sum_arrival":
            for a in self.A.values():
                a.Obj = w
        else:
            self.aux[term].Obj = w
        self.m.update()

    # ---------- primitive query constraints ----------
    def add_primitive(self, prim, tag):
        """Add one primitive constraint (see canon.compile_query); returns the list of constraints."""
        t, x, y, Ks, m = prim["type"], self.x, self.y, self.Ks, self.m
        role = prim.get("role", "query")
        name = f"{role}[{tag},{t}," + ",".join(str(prim[a]) for a in ("k", "i", "j") if a in prim) + "]"
        if t == "FIX_ARC":
            cons = [m.addConstr(x[prim["k"], prim["i"], prim["j"]] >= 1, name=name)]
        elif t == "MOVE":
            cons = [m.addConstr(y[prim["k"], prim["i"]] >= 1, name=name)]
        elif t in ("FORCE_ADJ", "FORBID_ADJ"):
            i, j = prim["i"], prim["j"]
            adj = gp.quicksum(x[k, i, j] + x[k, j, i] for k in Ks)
            cons = [m.addConstr(adj >= 1 if t == "FORCE_ADJ" else adj <= 0, name=name)]
        elif t == "FORCE_SAME":
            i, j = prim["i"], prim["j"]
            cons = [m.addConstr(y[k, i] - y[k, j] == 0, name=f"{name}[{k}]") for k in Ks]
        elif t == "FORCE_SEP":
            i, j = prim["i"], prim["j"]
            cons = [m.addConstr(y[k, i] + y[k, j] <= 1, name=f"{name}[{k}]") for k in Ks]
        else:
            raise ValueError(t)
        m.update()
        return cons

    def remove(self, items):
        for it in items:
            self.m.remove(it)
        self.m.update()

    # ---------- solving ----------
    def set_start(self, sol):
        """MIP start from a solution (integer variables only; Gurobi completes the rest)."""
        for v in self.x.values():
            v.Start = 0
        for v in self.y.values():
            v.Start = 0
        for k, r in enumerate(sol["routes"], start=1):
            path = [0, *r, 0]
            for a, b in zip(path, path[1:]):
                self.x[k, a, b].Start = 1
            for i in r:
                self.y[k, i].Start = 1
        self.m.update()

    def clear_start(self):
        for v in self.m.getVars():
            v.Start = GRB.UNDEFINED
        self.m.update()

    def optimize(self):
        t0 = time.perf_counter()
        self.m.optimize()
        wall = time.perf_counter() - t0
        st = self.m.Status
        out = {"status": {GRB.OPTIMAL: "optimal", GRB.INFEASIBLE: "infeasible"}.get(st, f"status_{st}"),
               "runtime_s": self.m.Runtime, "wall_s": wall}
        if st == GRB.OPTIMAL:
            out["objective"] = self.m.ObjVal
            out["solution"] = self.extract()
        return out

    def extract(self):
        routes = []
        for k in self.Ks:
            r, cur = [], 0
            for _ in range(self.data["n"] + 1):
                nxt = [j for j in self.N if j != cur and self.x[k, cur, j].X > 0.5]
                assert len(nxt) == 1, (k, cur, nxt)
                cur = nxt[0]
                if cur == 0:
                    break
                r.append(cur)
            assert cur == 0, f"vehicle {k} route does not return to depot"
            routes.append(r)
        return {"routes": routes}

    def iis(self):
        self.m.computeIIS()
        cons = [c.ConstrName for c in self.m.getConstrs() if c.IISConstr]
        lbs = [v.VarName for v in self.m.getVars() if v.IISLB]
        ubs = [v.VarName for v in self.m.getVars() if v.IISUB]
        return {"constraints": cons, "var_lower_bounds": lbs, "var_upper_bounds": ubs}

    def size(self):
        self.m.update()
        return {"num_vars": self.m.NumVars, "num_bin_vars": self.m.NumBinVars, "num_constrs": self.m.NumConstrs}
