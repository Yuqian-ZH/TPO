"""Stage 1: environment record and smoke tests.  Usage: python smoke.py env|gurobi|llm"""
import importlib.metadata as md
import json
import os
import platform
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
PACKAGES = ["gurobipy", "openai", "pytest", "jsonschema", "numpy", "matplotlib"]


def dump(obj, rel):
    with open(os.path.join(ROOT, rel), "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def gurobi_license():
    import gurobipy as gp
    with tempfile.TemporaryDirectory() as d:
        log = os.path.join(d, "gurobi.log")
        env = gp.Env(empty=True)
        env.setParam("OutputFlag", 1)
        env.setParam("LogToConsole", 0)
        env.setParam("LogFile", log)
        env.start()
        env.dispose()
        text = open(log).read()
    lines = [l.strip() for l in text.splitlines() if "license" in l.lower()]
    return lines


def cmd_env():
    import gurobipy as gp
    pkgs = {p: md.version(p) for p in PACKAGES}
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True).stdout
    cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
    env = {
        "python": platform.python_version(), "python_executable": sys.executable,
        "machine": platform.machine(), "platform": platform.platform(), "cpu": cpu,
        "packages": pkgs, "gurobi_version": ".".join(map(str, gp.gurobi.version())),
        "gurobi_license_log": gurobi_license(),
        "pip_freeze": freeze.splitlines(),
    }
    assert env["machine"] == "arm64", env["machine"]
    dump(env, "env.json")
    print(json.dumps({k: v for k, v in env.items() if k != "pip_freeze"}, indent=2))


def cmd_gurobi():
    import gurobipy as gp
    from gurobipy import GRB
    out = {}
    genv = gp.Env(params={"OutputFlag": 0})
    # (a) 5-variable model
    m = gp.Model("smoke5", env=genv)
    x = m.addVars(5, vtype=GRB.BINARY, name="x")
    m.addConstr(gp.quicksum((i + 1) * x[i] for i in range(5)) <= 7, name="knap")
    m.setObjective(gp.quicksum((5 - i) * x[i] for i in range(5)), GRB.MAXIMIZE)
    m.Params.MIPGap, m.Params.Threads, m.Params.Seed = 0, 1, 0
    m.optimize()
    out["five_var"] = {"status": m.Status, "obj": m.ObjVal, "x": [round(x[i].X) for i in range(5)],
                       "num_vars": m.NumVars, "num_constrs": m.NumConstrs}
    # (b) infeasible model -> IIS
    m2 = gp.Model("infeas", env=genv)
    a, b = m2.addVar(name="a"), m2.addVar(name="b")
    m2.addConstr(a + b >= 10, name="c_ge10")
    m2.addConstr(a <= 3, name="c_a3")
    m2.addConstr(b <= 4, name="c_b4")
    m2.addConstr(a - b <= 100, name="c_loose")
    m2.optimize()
    m2.computeIIS()
    out["iis"] = {"status": m2.Status, "iis_constrs": [c.ConstrName for c in m2.getConstrs() if c.IISConstr]}
    # (c) LP relaxation duals / reduced costs
    r = m.relax()
    r.optimize()
    out["relax"] = {"status": r.Status, "obj": r.ObjVal,
                    "Pi": {c.ConstrName: c.Pi for c in r.getConstrs()},
                    "RC": {v.VarName: v.RC for v in r.getVars()}}
    ok = (out["five_var"]["status"] == GRB.OPTIMAL and m2.Status == GRB.INFEASIBLE
          and sorted(out["iis"]["iis_constrs"]) == ["c_a3", "c_b4", "c_ge10"] and r.Status == GRB.OPTIMAL)
    out["pass"] = ok
    dump(out, "logs/smoke_gurobi.json")
    print(json.dumps(out, indent=2))


def cmd_llm():
    sys.path.insert(0, ROOT)
    from components.llm_client import LLMClient, derive_seed
    cli = LLMClient(os.path.join(ROOT, "logs", "llm_smoke.jsonl"))
    msgs = [{"role": "system", "content": "You are a test endpoint. Reply with JSON only."},
            {"role": "user", "content": 'Return the JSON object {"status": "ok", "sum": <the value of 2+3>}.'}]
    results = []
    seed = derive_seed("smoke", "smoke", 0, 0)
    for i, (temp, s) in enumerate([(0.2, seed), (0.7, seed), (0.7, seed)]):
        r = cli.chat(msgs, temperature=temp, seed=s, json_mode=True, max_tokens=50,
                     meta={"component": "smoke", "case_id": "smoke", "run": 0, "sample_index": i})
        results.append({k: r.get(k) for k in ("ok", "parse_status", "parsed", "content", "returned_model",
                                              "reasoning_present", "usage", "latency_s", "attempts")})
    out = {"seed": seed, "requests": results,
           "json_ok": all(r["parse_status"] == "json_ok" and r["parsed"] == {"status": "ok", "sum": 5}
                          for r in results),
           "thinking_disabled": all(r["ok"] and not r["reasoning_present"] for r in results),
           "seed_accepted_without_error": all(r["ok"] for r in results),
           "same_seed_same_output_at_t0.7": results[1]["content"] == results[2]["content"]}
    out["pass"] = out["json_ok"] and out["thinking_disabled"]
    dump(out, "logs/smoke_llm.json")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    {"env": cmd_env, "gurobi": cmd_gurobi, "llm": cmd_llm}[sys.argv[1]]()
