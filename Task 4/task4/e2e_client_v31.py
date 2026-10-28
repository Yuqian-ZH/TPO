"""End-to-end run of the task4_v31 service (serve_v31.py) on Task 2's task2_v3 test cases (DESIGN_V31.md section 6):
e2e_client_v3.py's client and simulated user against the v3.1 server.

    source ~/.dashscope_env
    PYTHONDONTWRITEBYTECODE=1 python freeze_service_v31.py
    PYTHONDONTWRITEBYTECODE=1 python e2e_client_v31.py --configs A1B1C1 --out results/e2e_test_v31"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

sys.dont_write_bytecode = True

import httpx  # noqa: E402

from e2e_client import Server, count_llm_requests, load_cases  # noqa: E402
from e2e_client_v3 import CASES, drive  # noqa: E402
from feedback_service.bridge import TASK4_ROOT, t2  # noqa: E402

PORT = 8008


class ServerV31(Server):
    """Server running serve_v31.py instead of serve.py."""

    def start(self, timeout=90):
        self.log = open(self.log_path, "a")
        self.log.write(f"--- start {datetime.datetime.now().astimezone().isoformat(timespec='seconds')}\n")
        self.log.flush()
        self.proc = subprocess.Popen([sys.executable, os.path.join(TASK4_ROOT, "serve_v31.py"), "--data",
                                      self.data, "--port", str(self.port)], cwd=TASK4_ROOT, stdout=self.log,
                                     stderr=subprocess.STDOUT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(f"serve_v31.py exited with {self.proc.returncode}; see {self.log_path}")
            try:
                h = httpx.get(self.url + "/health", timeout=2)
                if h.status_code == 200:
                    return h.json()
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        raise RuntimeError("serve_v31.py did not become healthy in time")


def require_freeze_v31():
    from freeze_service_v31 import current, read_freeze
    frozen, now = read_freeze(), current()
    if frozen is None:
        sys.exit("refused: test cases need service_freeze_v31.json")
    changed = sorted(k for k in set(frozen["hashes"]) | set(now["hashes"])
                     if frozen["hashes"].get(k) != now["hashes"].get(k))
    if changed or not now["startup_checks"]["ok"]:
        sys.exit(f"refused: files changed since service_freeze_v31.json: {changed or now['startup_checks']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="test", choices=list(CASES))
    ap.add_argument("--configs", default="A1B1C1")
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--max-requests", type=int, default=400)
    args = ap.parse_args()
    path = CASES[args.cases]
    cases = load_cases(path)
    if args.cases == "test":
        require_freeze_v31()
    configs = args.configs.split(",")
    base = t2.load_frozen_instance()
    out = os.path.abspath(args.out)
    store = os.path.join(out, "store")
    if os.path.exists(os.path.join(out, "e2e_results.json")):
        sys.exit(f"refused: {out} already has results")
    os.makedirs(out, exist_ok=True)
    server = ServerV31(store, args.port, os.path.join(out, "server.log"))
    run = {"protocol": "task4_v31", "started_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "cases_file": os.path.relpath(path, os.path.dirname(os.path.dirname(TASK4_ROOT))),
           "cases_sha256": t2.sha256(path), "configs": configs, "max_requests": args.max_requests, "results": []}
    run["health_at_start"] = server.start()
    http = httpx.Client(base_url=server.url, timeout=900, limits=httpx.Limits(max_keepalive_connections=0))
    aborted = None
    try:
        for config in configs:
            for case in cases:
                res = drive(http, case, base, config)
                res["llm_requests_total_so_far"] = count_llm_requests(store)
                run["results"].append(res)
                with open(os.path.join(out, "client_log.jsonl"), "a") as f:
                    f.write(json.dumps(res, ensure_ascii=False) + "\n")
                print(config, case["id"], res["status"], "iterations", res["iterations"],
                      "clarified" if res["clarified"] else "", "requests", res["llm_requests_total_so_far"], flush=True)
                if res["llm_requests_total_so_far"] > args.max_requests:
                    aborted = f"more than {args.max_requests} LLM requests"
                    raise RuntimeError(aborted)
        listed = {s["session_id"]: s for s in http.get("/sessions").json()}
        run["final_check"] = {"sessions_listed": len(listed),
                              "all_sessions_present": all(r["session_id"] in listed for r in run["results"]),
                              "none_open": all(listed[r["session_id"]]["open_feedback"] is None
                                               for r in run["results"])}
    except Exception as e:
        aborted = aborted or f"{type(e).__name__}: {e}"
        raise
    finally:
        http.close()
        server.stop()
        run.update(aborted=aborted, llm_requests=count_llm_requests(store),
                   finished_at=datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
        with open(os.path.join(out, "e2e_results.json"), "w") as f:
            json.dump(run, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
