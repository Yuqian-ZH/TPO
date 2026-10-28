"""Freeze protocol_v2.json before the task3_v2 formal run. run_experiment_v2.py refuses unless every hash still
matches. protocol.json (task3_v1) is kept as it is; the v1 sources are hashed again here because v2 runs them."""
import datetime
import json
import os
import sys

sys.dont_write_bytecode = True

from tpo import task2_bridge as t2  # noqa: E402
from tpo.loop import MAIN, Settings  # noqa: E402
from freeze_protocol import TASK2_DEPENDS, TASK3_SOURCES, hashes  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
TEST_CASES = os.path.join(t2.TASK2_ROOT, "cases", "test_cases.json")
TASK3_V2_SOURCES = ["tpo_v2/*.py", "run_experiment_v2.py", "freeze_protocol_v2.py"]
TASK2_V2_DEPENDS = TASK2_DEPENDS + ["v2/__init__.py", "v2/attribution.py", "v2/localization.py", "v2/prompts/*.txt",
                                    "v2/protocol_v2.json"]


def current():
    return {"task3_v1_sources": hashes(ROOT, TASK3_SOURCES), "task3_v2_sources": hashes(ROOT, TASK3_V2_SOURCES),
            "task2_files": hashes(t2.TASK2_ROOT, TASK2_V2_DEPENDS)}


def main():
    path = os.path.join(ROOT, "protocol_v2.json")
    if os.path.exists(path):
        sys.exit("protocol_v2.json already exists; it is frozen and must not be overwritten")
    v1 = json.load(open(os.path.join(ROOT, "protocol.json")))
    t2.load_frozen_instance()
    s = Settings()
    proto = {
        "protocol": "task3_v2",
        "frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "confirmed_by": "user, 2026-10-26: re-run Task 2 onwards after the audit",
        "supersedes": "nothing: task3_v1 (protocol.json, results/formal) is kept and reported beside v2",
        "change": "condition A uses Task 2's task2_v2 attribution (audit F1); localization uses task2_v2's rule, "
                  "applied to task3_v1's shared samples after checking it reaches the same decisions",
        "instance": v1["instance"], "test_cases": v1["test_cases"],
        "task2_protocol_v2_sha256": t2.sha256(os.path.join(t2.TASK2_ROOT, "v2", "protocol_v2.json")),
        "hashes": current(),
        "llm": {**v1["llm"], "seed": "unchanged from task3_v1 (tpo/llm.py derive_seed with 'task3_v1'): with A off "
                                     "the prompts are byte for byte task3_v1's"},
        "loop": {**v1["loop"], "max_iterations": s.max_iters},
        "configs": {g: v1["configs"][g] for g in MAIN}, "main_configs": list(MAIN), "runs": [1, 2, 3],
        "not_rerun": {"S1": "all 30 trials converged at iteration 1, where the v1 attribution was correct",
                      "S2": "same"},
        "metrics": v1["metrics"], "decision_rule": v1["decision_rule"],
    }
    with open(path, "w") as f:
        json.dump(proto, f, indent=2, ensure_ascii=False)
    print(f"frozen {path}: " + ", ".join(f"{len(v)} {k}" for k, v in proto["hashes"].items()))


if __name__ == "__main__":
    main()
