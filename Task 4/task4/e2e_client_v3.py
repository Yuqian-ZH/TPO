"""End-to-end run of the task4_v3 service (serve_v3.py) on Task 2's task2_v3 test cases (DESIGN_V3.md section 7):
the client of e2e_client.py with Task 3's v3 simulated user (the same words in every configuration).

    source ~/.dashscope_env
    PYTHONDONTWRITEBYTECODE=1 python freeze_service_v3.py
    PYTHONDONTWRITEBYTECODE=1 python e2e_client_v3.py --configs A0B0C1,A1B1C1 --out results/e2e_test_v3"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

sys.dont_write_bytecode = True

import httpx  # noqa: E402

from e2e_client import TERMINAL, Server, count_llm_requests, load_cases  # noqa: E402
from feedback_service.bridge import TASK4_ROOT, t2  # noqa: E402
from tpo_v3.user_sim import SimulatedUserV3  # noqa: E402
from v3.conditions import real_data  # noqa: E402

PORT = 8007
CASES = {s: os.path.join(t2.TASK2_ROOT, "v3", "cases", f"{s}_cases.json") for s in ("dev", "test")}


class ServerV3(Server):
    """Server running serve_v3.py instead of serve.py."""

    def start(self, timeout=90):
        self.log = open(self.log_path, "a")
        self.log.write(f"--- start {datetime.datetime.now().astimezone().isoformat(timespec='seconds')}\n")
        self.log.flush()
        self.proc = subprocess.Popen([sys.executable, os.path.join(TASK4_ROOT, "serve_v3.py"), "--data", self.data,
                                      "--port", str(self.port)], cwd=TASK4_ROOT, stdout=self.log,
                                     stderr=subprocess.STDOUT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(f"serve_v3.py exited with {self.proc.returncode}; see {self.log_path}")
            try:
                h = httpx.get(self.url + "/health", timeout=2)
                if h.status_code == 200:
                    return h.json()
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        raise RuntimeError("serve_v3.py did not become healthy in time")


def drive(http, case, base, config, poll_s=1.0):
    """e2e_client.drive with the v3 simulated user, who explains once and lists the unmet conditions."""
    user = SimulatedUserV3(case, base)
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
                          "routes": v["plan"]["routes"], "resolved": verdict["resolved"], "unmet": verdict["unmet"],
                          "notice": v.get("notice")})
            body = {"resolved": True} if verdict["resolved"] else {"resolved": False,
                                                                   "comment": user.feedback(verdict)}
            v = call("POST", f"/feedback/{fid}/reply", body)
        else:
            time.sleep(poll_s)
            v = call("GET", f"/feedback/{fid}")
    final = v["plan"]
    excess = None
    if v["status"] == "resolved":
        from tpo.task2_bridge import canon
        excess = canon.metrics({"routes": final["routes"]}, real_data(case, base))["total_distance"] - \
            case["min_compliant_distance"]
    return {"case_id": case["id"], "stratum": case["stratum"], "config": config, "session_id": sid,
            "feedback_id": fid, "status": v["status"], "iterations": v["iteration"],
            "clarified": v["clarification"] is not None, "clarification": v["clarification"], "shown_plans": shown,
            "final_plan": final, "excess_distance": excess, "usage": v["usage"], "error": v["error"], "calls": calls}


def require_freeze_v3():
    from freeze_service_v3 import current, read_freeze
    frozen, now = read_freeze(), current()
    if frozen is None:
        sys.exit("refused: test cases need service_freeze_v3.json")
    changed = sorted(k for k in set(frozen["hashes"]) | set(now["hashes"])
                     if frozen["hashes"].get(k) != now["hashes"].get(k))
    if changed or not now["startup_checks"]["ok"]:
        sys.exit(f"refused: files changed since service_freeze_v3.json: {changed or now['startup_checks']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="test", choices=list(CASES))
    ap.add_argument("--configs", default="A0B0C1,A1B1C1")
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--max-requests", type=int, default=600)
    args = ap.parse_args()
    path = CASES[args.cases]
    cases = load_cases(path)
    if args.cases == "test":
        require_freeze_v3()
    configs = args.configs.split(",")
    base = t2.load_frozen_instance()
    out = os.path.abspath(args.out)
    store = os.path.join(out, "store")
    if os.path.exists(os.path.join(out, "e2e_results.json")):
        sys.exit(f"refused: {out} already has results")
    os.makedirs(out, exist_ok=True)
    server = ServerV3(store, args.port, os.path.join(out, "server.log"))
    run = {"protocol": "task4_v3", "started_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
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
