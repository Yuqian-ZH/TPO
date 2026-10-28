"""Stage 0: env.json and task2_snapshot.json (hashes and mtimes of the Task 2 files Task 3 depends on)."""
import datetime
import json
import os
import platform
import subprocess
import sys
from importlib import metadata

sys.dont_write_bytecode = True

from tpo import task2_bridge as t2  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
DEPENDS = ["instance/cvrp_instance.json", "FROZEN.json", "cvrp/data.py", "cvrp/canon.py", "cvrp/ids.py",
           "cvrp/model.py", "cvrp/oracle.py", "cases/checkers.py", "cases/gt.py", "components/llm_client.py"]


def env():
    import gurobipy as gp
    cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
    pkgs = {p: metadata.version(p) for p in ("gurobipy", "openai", "pytest", "jsonschema", "numpy", "matplotlib")}
    return {"python": platform.python_version(), "python_executable": sys.executable,
            "machine": platform.machine(), "platform": platform.platform(), "cpu": cpu, "packages": pkgs,
            "gurobi_version": ".".join(map(str, gp.gurobi.version()))}


def task2_snapshot():
    files = {}
    for rel in DEPENDS:
        path = os.path.join(t2.TASK2_ROOT, rel)
        if os.path.exists(path):
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path)).astimezone()
            files[rel] = {"sha256": t2.sha256(path), "mtime": mtime.isoformat(timespec="seconds")}
        else:
            files[rel] = None
    data = t2.load_frozen_instance()  # raises if the instance hash differs from FROZEN.json
    return {"taken_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "task2_root": t2.TASK2_ROOT, "instance_hash_matches_frozen": True,
            "instance": {"n": data["n"], "K": data["K"], "Q": data["Q"]}, "files": files}


if __name__ == "__main__":
    e = env()
    assert e["machine"] == "arm64", e["machine"]
    with open(os.path.join(ROOT, "env.json"), "w") as f:
        json.dump(e, f, indent=2)
    with open(os.path.join(ROOT, "task2_snapshot.json"), "w") as f:
        json.dump(task2_snapshot(), f, indent=2)
    print(json.dumps(e, indent=2))
