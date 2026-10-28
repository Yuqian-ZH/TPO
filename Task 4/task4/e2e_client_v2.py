"""End-to-end run of the task4_v2 service (serve_v2.py): the client of e2e_client.py (same drive() and simulated
user, same public fields only), plus one read-back per case: the session's modifications in force after the
complaint closed, so that an accepted data correction can be checked (audit F2).

    source ~/.dashscope_env
    PYTHONDONTWRITEBYTECODE=1 python e2e_client_v2.py --cases dev --configs A0B0C1 --out results/e2e_dev_v2
    PYTHONDONTWRITEBYTECODE=1 python e2e_client_v2.py --cases test --configs A0B0C1,A1B1C1 --restart-at A0B0C1:5 \\
        --out results/e2e_test_v2          # refused unless service_freeze_v2.json matches
    PYTHONDONTWRITEBYTECODE=1 python e2e_client_v2.py --cases scenarios/audit_cases.json --configs A0B0C1,A1B1C1 \\
        --out results/audit_v2
The audit scenario through the frozen v1 service, for comparison: e2e_client.py with the same --cases."""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

sys.dont_write_bytecode = True

import httpx  # noqa: E402

from e2e_client import CASES, Server, count_llm_requests, drive, load_cases  # noqa: E402
from feedback_service.bridge import TASK4_ROOT, t2  # noqa: E402

PORT = 8005


class ServerV2(Server):
    """Server running serve_v2.py instead of serve.py."""

    def start(self, timeout=90):
        self.log = open(self.log_path, "a")
        self.log.write(f"--- start {datetime.datetime.now().astimezone().isoformat(timespec='seconds')}\n")
        self.log.flush()
        self.proc = subprocess.Popen([sys.executable, os.path.join(TASK4_ROOT, "serve_v2.py"), "--data", self.data,
                                      "--port", str(self.port)], cwd=TASK4_ROOT, stdout=self.log,
                                     stderr=subprocess.STDOUT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(f"serve_v2.py exited with {self.proc.returncode}; see {self.log_path}")
            try:
                h = httpx.get(self.url + "/health", timeout=2)
                if h.status_code == 200:
                    return h.json()
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        raise RuntimeError("serve_v2.py did not become healthy in time")


def read_back(http, case, res):
    """Modifications in force after the complaint, and whether the case's allowed data corrections are among them."""
    s = http.get(f"/sessions/{res['session_id']}").json()
    accepted = [{k: v for k, v in m.items() if k != "id"} for m in s["accepted_modifications"]]
    wanted = case.get("allowed_data_corrections") or []
    return {"accepted_modifications": accepted, "current_plan": s["current_plan"]["routes"],
            "current_plan_source": s["current_plan"]["source"],
            "corrections_in_force": all(w in accepted for w in wanted) if wanted else None,
            "routes_changed": s["current_plan"]["routes"] != case["solution"]["routes"]}


def require_freeze_v2():
    from freeze_service_v2 import current, read_freeze
    frozen, now = read_freeze(), current()
    if frozen is None:
        sys.exit("refused: test cases need service_freeze_v2.json")
    changed = sorted(k for k in set(frozen["hashes"]) | set(now["hashes"])
                     if frozen["hashes"].get(k) != now["hashes"].get(k))
    if changed or not now["startup_checks"]["ok"]:
        sys.exit(f"refused: files changed since service_freeze_v2.json: {changed or now['startup_checks']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="dev", help="dev, test or a path")
    ap.add_argument("--configs", default="A0B0C1")
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--restart-at", default=None, help="CONFIG:N restarts the server while the N-th case of "
                                                       "CONFIG waits for its first reply")
    ap.add_argument("--max-requests", type=int, default=400)
    args = ap.parse_args()
    path = CASES.get(args.cases, args.cases)
    cases = load_cases(path)
    if any(c.get("split") == "test" for c in cases):
        require_freeze_v2()
    configs = args.configs.split(",")
    base = t2.load_frozen_instance()
    out = os.path.abspath(args.out)
    store = os.path.join(out, "store")
    if os.path.exists(os.path.join(out, "e2e_results.json")):
        sys.exit(f"refused: {out} already has results")
    os.makedirs(out, exist_ok=True)
    restart_at = tuple(args.restart_at.split(":")) if args.restart_at else None
    server = ServerV2(store, args.port, os.path.join(out, "server.log"))
    run = {"protocol": "task4_v2", "started_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
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
                res["after"] = read_back(http, case, res)
                res["llm_requests_total_so_far"] = count_llm_requests(store)
                run["results"].append(res)
                with open(os.path.join(out, "client_log.jsonl"), "a") as f:
                    f.write(json.dumps(res, ensure_ascii=False) + "\n")
                print(config, case["id"], res["status"], "iterations", res["iterations"],
                      "clarified" if res["clarified"] else "", "corrections in force",
                      res["after"]["corrections_in_force"], "requests", res["llm_requests_total_so_far"], flush=True)
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
