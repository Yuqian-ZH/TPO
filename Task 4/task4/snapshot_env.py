"""Stage 0: environment record (env.json) plus the list of Task 2 bytecode files that existed before Task 4
started, so the acceptance check can tell that Task 4 added none."""
import datetime
import glob
import importlib.metadata as md
import json
import os
import platform
import sys

sys.dont_write_bytecode = True

from feedback_service.bridge import TASK2_ROOT, TASK3_ROOT, TASK4_ROOT, t2, task3_protocol_check  # noqa: E402

PACKAGES = ("fastapi", "starlette", "uvicorn", "pydantic", "httpx", "openai", "gurobipy", "jsonschema", "pytest")


def pycache_files(root):
    return sorted(os.path.relpath(p, root) for p in glob.glob(os.path.join(root, "**", "__pycache__", "*"),
                                                               recursive=True))


def main():
    env = {"recorded_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "python": sys.version.split()[0], "machine": platform.machine(), "platform": platform.platform(),
           "packages": {p: md.version(p) for p in PACKAGES},
           "installed_for_task4": ["fastapi==0.161.1", "starlette==1.9.0", "uvicorn==0.54.0", "httpx==0.28.1",
                                   "httpcore==1.0.9", "annotated-doc==0.0.5", "opentelemetry-api==1.45.1"],
           "task2_instance_sha256": t2.sha256(t2.INSTANCE),
           "task3_protocol_check": task3_protocol_check(),
           "task2_pycache_before_task4": pycache_files(TASK2_ROOT),
           "task3_pycache_before_task4": pycache_files(TASK3_ROOT)}
    t2.load_frozen_instance()  # raises if the instance hash differs from Task 2's freeze
    with open(os.path.join(TASK4_ROOT, "env.json"), "w") as f:
        json.dump(env, f, indent=1)
    print(json.dumps({k: v for k, v in env.items() if not k.endswith("before_task4")}, indent=1))
    print("task2 pycache files:", len(env["task2_pycache_before_task4"]),
          "task3:", len(env["task3_pycache_before_task4"]))


if __name__ == "__main__":
    main()
