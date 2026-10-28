"""End-to-end run (plan 5.2, 5.3): a real service process (serve.py), real HTTP, real LLM and Gurobi, with
Task 3's simulated user as the client.

The client sends only public fields: the case's plan, complaint and model modifications, the clarification
answer when the service asks, and Task 3's fixed reply templates. Checkers and thresholds stay here.

    source ~/.dashscope_env
    PYTHONDONTWRITEBYTECODE=1 python e2e_client.py --cases dev --configs A0B0C1 --out results/e2e_dev
    PYTHONDONTWRITEBYTECODE=1 python e2e_client.py --cases test --configs A0B0C1,A1B1C1 --restart-at A0B0C1:5 \\
        --out results/e2e_test        # refused unless service_freeze.json matches"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

sys.dont_write_bytecode = True

import httpx  # noqa: E402

from feedback_service.bridge import TASK4_ROOT, t2  # noqa: E402
from tpo.user_sim import SimulatedUser  # noqa: E402

CASES = {"dev": os.path.join(t2.TASK2_ROOT, "cases", "dev_cases.json"),
         "test": os.path.join(t2.TASK2_ROOT, "cases", "test_cases.json")}
TERMINAL = ("resolved", "not_converged", "stopped_low_confidence", "stopped_by_user", "failed")


def load_cases(path):
    with open(path) as f:
        d = json.load(f)
    return d["cases"] if isinstance(d, dict) else d


def drive(http, case, base, config, on_awaiting=None, poll_s=1.0):
    """One case through the API. http is anything with httpx's request() (httpx.Client, FastAPI TestClient)."""
    user = SimulatedUser(case, base)
    calls = []

    def call(method, path, body=None):
        t0 = time.perf_counter()
        r = http.request(method, path, json=body)
        data = r.json()
        calls.append({"call": f"{method} {path.split('?')[0]}", "http_status": r.status_code,
                      "elapsed_s": round(time.perf_counter() - t0, 3),
                      "status": data.get("status") if isinstance(data, dict) else None})
        if r.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {json.dumps(data)[:500]}")
        return data

    s = call("POST", "/sessions", {"config": config, "label": case["id"],
                                   "model_modifications": case.get("model_modifications", []),
                                   "solution": {"routes": case["solution"]["routes"]}})
    sid = s["session_id"]
    v = call("POST", f"/sessions/{sid}/feedback", {"complaint": case["complaint"],
                                                   "solution_version": s["current_plan"]["version"]})
    fid, shown = v["feedback_id"], []
    while v["status"] not in TERMINAL:
        if v["status"] == "needs_clarification":
            v = call("POST", f"/feedback/{fid}/clarification",
                     {"answer": user.clarify(v["clarification"]["question"])})
        elif v["status"] == "awaiting_reply":
            verdict = user.verdict({"routes": v["plan"]["routes"]})
            shown.append({"iteration": v["iteration"], "version": v["plan"]["version"],
                          "routes": v["plan"]["routes"], "resolved": verdict["resolved"],
                          "feasible_on_real_data": verdict["feasible"]})
            if on_awaiting:
                on_awaiting(case, config, v)
            body = {"resolved": True} if verdict["resolved"] else {"resolved": False,
                                                                   "comment": user.feedback(verdict)}
            v = call("POST", f"/feedback/{fid}/reply", body)
        else:  # still queued or running after the service's wait limit
            time.sleep(poll_s)
            v = call("GET", f"/feedback/{fid}")
    return {"case_id": case["id"], "config": config, "session_id": sid, "feedback_id": fid, "status": v["status"],
            "iterations": v["iteration"], "clarified": v["clarification"] is not None,
            "clarification": v["clarification"], "shown_plans": shown, "final_plan": v["plan"],
            "usage": v["usage"], "error": v["error"], "calls": calls}


class Server:
    """serve.py as a child process; it inherits the environment (credentials included) and logs to a file."""

    def __init__(self, data, port, log_path):
        self.data, self.port, self.log_path = data, port, log_path
        self.proc = self.log = None
        self.url = f"http://127.0.0.1:{port}"

    def start(self, timeout=90):
        self.log = open(self.log_path, "a")
        self.log.write(f"--- start {datetime.datetime.now().astimezone().isoformat(timespec='seconds')}\n")
        self.log.flush()
        self.proc = subprocess.Popen([sys.executable, os.path.join(TASK4_ROOT, "serve.py"), "--data", self.data,
                                      "--port", str(self.port)], cwd=TASK4_ROOT, stdout=self.log,
                                     stderr=subprocess.STDOUT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(f"serve.py exited with {self.proc.returncode}; see {self.log_path}")
            try:
                h = httpx.get(self.url + "/health", timeout=2)
                if h.status_code == 200:
                    return h.json()
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        raise RuntimeError("serve.py did not become healthy in time")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(60)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        if self.log:
            self.log.write(f"--- stopped, exit code {self.proc.returncode if self.proc else None}\n")
            self.log.close()
            self.log = None


def count_llm_requests(store):
    path = os.path.join(store, "logs", "llm_requests.jsonl")
    if not os.path.exists(path):
        return 0
    with open(path) as f:
        return sum(1 for line in f if line.strip())


def require_freeze():
    from freeze_service import current, read_freeze
    frozen, now = read_freeze(), current()
    if frozen is None:
        sys.exit("refused: test cases need service_freeze.json (plan 5.3)")
    changed = sorted(k for k in set(frozen["hashes"]) | set(now["hashes"])
                     if frozen["hashes"].get(k) != now["hashes"].get(k))
    if changed or not now["task3_protocol_check"]["ok"]:
        sys.exit(f"refused: files changed since service_freeze.json: {changed or now['task3_protocol_check']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="dev", help="dev, test or a path")
    ap.add_argument("--configs", default="A0B0C1")
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=8004)
    ap.add_argument("--restart-at", default=None, help="CONFIG:N restarts the server while the N-th case of "
                                                       "CONFIG waits for its first reply")
    ap.add_argument("--max-requests", type=int, default=400)
    args = ap.parse_args()
    path = CASES.get(args.cases, args.cases)
    cases = load_cases(path)
    if any(c.get("split") == "test" for c in cases):
        require_freeze()
    configs = args.configs.split(",")
    base = t2.load_frozen_instance()
    out = os.path.abspath(args.out)
    store = os.path.join(out, "store")
    if os.path.exists(os.path.join(out, "e2e_results.json")):
        sys.exit(f"refused: {out} already has results")
    os.makedirs(out, exist_ok=True)
    restart_at = tuple(args.restart_at.split(":")) if args.restart_at else None
    server = Server(store, args.port, os.path.join(out, "server.log"))
    run = {"started_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "cases_file": os.path.relpath(path, os.path.dirname(os.path.dirname(TASK4_ROOT))),
           "cases_sha256": t2.sha256(path), "configs": configs, "restart_at": args.restart_at,
           "max_requests": args.max_requests, "results": [], "restart": None}
    run["health_at_start"] = server.start()
    restarted = {}

    def maybe_restart(case, config, view):
        if restart_at and (config, str(cases.index(case) + 1)) == restart_at and not restarted:
            server.stop()
            health = server.start()
            after = http.get(f"/feedback/{view['feedback_id']}").json()
            restarted.update({"case_id": case["id"], "config": config, "feedback_id": view["feedback_id"],
                              "status_before": view["status"], "status_after_restart": after["status"],
                              "plan_version_before": view["plan"]["version"],
                              "plan_version_after_restart": after["plan"]["version"],
                              "sessions_after_restart": health["sessions"],
                              "recovered_at_startup": health["recovered_at_startup"]})

    http = httpx.Client(base_url=server.url, timeout=900, limits=httpx.Limits(max_keepalive_connections=0))
    aborted = None
    try:
        for config in configs:
            for case in cases:
                res = drive(http, case, base, config, on_awaiting=maybe_restart)
                res["llm_requests_total_so_far"] = count_llm_requests(store)
                run["results"].append(res)
                with open(os.path.join(out, "client_log.jsonl"), "a") as f:
                    f.write(json.dumps(res, ensure_ascii=False) + "\n")
                print(config, case["id"], res["status"], "iterations", res["iterations"],
                      "clarified" if res["clarified"] else "", "requests", res["llm_requests_total_so_far"],
                      flush=True)
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
        run.update(restart=restarted or None, aborted=aborted, llm_requests=count_llm_requests(store),
                   finished_at=datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
        with open(os.path.join(out, "e2e_results.json"), "w") as f:
            json.dump(run, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
