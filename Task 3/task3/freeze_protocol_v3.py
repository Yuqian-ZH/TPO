"""Freeze protocol_v3.json before the task3_v3 test run (DESIGN_V3.md section 7). run_experiment_v3.py refuses test
cases unless every hash still matches and Task 2's v3/protocol_v3.json still matches its files.
protocol.json (task3_v1) and protocol_v2.json (task3_v2) are kept as they are."""
import datetime
import json
import os
import sys

sys.dont_write_bytecode = True

from tpo import task2_bridge as t2  # noqa: E402
from tpo.loop import MAIN, Settings  # noqa: E402
from freeze_protocol import TASK2_DEPENDS, TASK3_SOURCES, hashes  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
TEST_CASES = os.path.join(t2.TASK2_ROOT, "v3", "cases", "test_cases.json")
TASK3_ADAPTERS = ["tpo_v2/*.py", "tpo_v21/*.py"]
TASK3_V3_SOURCES = ["tpo_v3/*.py", "run_experiment_v3.py", "freeze_protocol_v3.py", "tests/test_v3.py"]
RUNS = [1, 2, 3, 4, 5]


def current():
    return {"task3_v1_sources": hashes(ROOT, TASK3_SOURCES), "task3_adapters": hashes(ROOT, TASK3_ADAPTERS),
            "task3_v3_sources": hashes(ROOT, TASK3_V3_SOURCES),
            "task2_files": hashes(t2.TASK2_ROOT, TASK2_DEPENDS + ["v3/protocol_v3.json"])}


def main():
    path = os.path.join(ROOT, "protocol_v3.json")
    if os.path.exists(path):
        sys.exit("protocol_v3.json already exists; it is frozen and must not be overwritten")
    sys.path.append(t2.TASK2_ROOT)
    from v3.freeze import check as task2_v3_check
    task2_v3_check()
    v1 = json.load(open(os.path.join(ROOT, "protocol.json")))
    t2.load_frozen_instance()
    cases = json.load(open(TEST_CASES))["cases"]
    s = Settings()
    proto = {
        "protocol": "task3_v3",
        "frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "confirmed_by": "user, 2026-10-27: design the experiment properly according to the task, then run it",
        "design": "DESIGN_V3.md at the project root (sections 2-7 written before any LLM call; pilot in section 9)",
        "supersedes": "nothing: task3_v1 (results/formal) and task3_v2 (results/formal_v2) are kept and reported "
                      "beside v3; different cases and simulated user, so the batches are not pooled or differenced",
        "test_cases": {"file": "Task 2/task2/v3/cases/test_cases.json", "sha256": t2.sha256(TEST_CASES),
                       "strata": {c["id"]: c["stratum"] for c in cases}},
        "task2_protocol_v3_sha256": t2.sha256(os.path.join(t2.TASK2_ROOT, "v3", "protocol_v3.json")),
        "hashes": current(),
        "components": "tpo_v21.Task2ComponentsV21 (Task 2's task2_v2.1 attribution and localization; probe v2)",
        "simulated_user": "tpo_v3.user_sim.SimulatedUserV3 (Task 2 v3 conditions; same words in every configuration)",
        "llm": v1["llm"], "loop": {**v1["loop"], "max_iterations": s.max_iters},
        "configs": list(MAIN), "runs": RUNS,
        "primary_metric": "converged within 3 iterations (feasible on the real data and every stated condition met); "
                          "mean and std over the 5 runs per configuration",
        "decision_rule": v1["decision_rule"],
        "preregistered_secondary": ["main effects within each stratum (control, ambiguity, side), descriptive with "
                                    "case-clustered bootstrap intervals", "convergence at iteration 1",
                                    "mean iterations when converged", "excess distance over the shortest plan "
                                    "meeting every condition", "LLM requests and tokens per trial incl. the shared "
                                    "localization", "paired McNemar slices as task3_v1"],
        "expectation_stated_before_running": "C mainly in the ambiguity stratum, A and B mainly in the side stratum, "
                                             "every configuration near 100% on the control stratum",
    }
    with open(path, "w") as f:
        json.dump(proto, f, indent=2, ensure_ascii=False)
    print(f"frozen {path}: " + ", ".join(f"{len(v)} {k}" for k, v in proto["hashes"].items()))


if __name__ == "__main__":
    main()
