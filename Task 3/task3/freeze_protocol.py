"""Stage 3: freeze protocol.json (plan 6, stage 3 item 1). run_experiment.py refuses test cases unless every
hash recorded here still matches."""
import datetime
import glob
import json
import os
import sys

sys.dont_write_bytecode = True

from tpo import task2_bridge as t2  # noqa: E402
from tpo.loop import CONFIGS, MAIN, Settings  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
TEST_CASES = os.path.join(t2.TASK2_ROOT, "cases", "test_cases.json")
TASK3_SOURCES = ["tpo/*.py", "prompts/*.txt", "run_experiment.py", "stats.py", "recompute.py", "freeze_protocol.py"]
TASK2_DEPENDS = ["protocol.json", "FROZEN.json", "instance/cvrp_instance.json", "cases/test_cases.json",
                 "cases/checkers.py", "cvrp/*.py", "components/*.py", "components/prompts/*.txt", "schemas/*.json"]


def hashes(root, patterns):
    out = {}
    for pat in patterns:
        for path in sorted(glob.glob(os.path.join(root, pat))):
            out[os.path.relpath(path, root)] = t2.sha256(path)
    return out


def current():
    return {"task3_sources": hashes(ROOT, TASK3_SOURCES), "task2_files": hashes(t2.TASK2_ROOT, TASK2_DEPENDS)}


def main():
    with open(t2.FROZEN) as f:
        frozen = json.load(f)
    assert t2.sha256(TEST_CASES) == frozen["test_cases"]["sha256"], "test cases differ from Task 2's freeze"
    t2.load_frozen_instance()
    s = Settings()
    proto = {
        "protocol": "task3_v1",
        "frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "confirmed_by": "user at pause point 1 (2026-10-23, 'OK to run')",
        "instance": frozen["instance"],
        "test_cases": {"file": "Task 2/task2/cases/test_cases.json", "sha256": t2.sha256(TEST_CASES), "n_cases": 10},
        "task2_protocol_sha256": t2.sha256(os.path.join(t2.TASK2_ROOT, "protocol.json")),
        "hashes": current(),
        "llm": {"model": "qwen3.8-max", "enable_thinking": False,
                "propose": {"temperature": s.propose_temperature, "max_tokens": s.propose_max_tokens},
                "select": {"temperature": s.select_temperature, "max_tokens": s.select_max_tokens},
                "localization": "Task 2 frozen localize(): 5 samples, temperature 0.7, run label t3-{run}",
                "seed": "sha256('task3_v1|case|config|run|iteration|role|sample')[:4] & 0x7fffffff",
                "retry": "connection errors and rate limits only, 3 attempts in total, waits 2 s and 8 s"},
        "loop": {"max_iterations": s.max_iters, "candidates_with_B": s.n_candidates, "max_modifications": 4,
                 "penalty_range": "(0, 1000]", "weight_range": "[0, 100]",
                 "commit": "fresh Gurobi model, full solve, single anchor, tied directions canonical",
                 "probe": "tpo/counterfactual_v2.py (decision 4: escalate on infeasible, soft violation, unchanged, modify_data)",
                 "low_confidence": "one clarification; still low -> stop, counted as not converged"},
        "configs": {g: vars(f) for g, f in CONFIGS.items()}, "main_configs": list(MAIN),
        "runs": [1, 2, 3],
        "metrics": {"convergence": "resolved by Task 2 checkers.complaint_resolved within 3 iterations",
                    "per_config": "rate per run (10 cases); mean and sample std (ddof=1) over 3 runs; pooled Wilson 95%",
                    "effects": "main effects and difference-of-differences interactions over the 8 main configs; "
                               "case-clustered bootstrap, 10,000 resamples, seed 42",
                    "paired": "exact McNemar on (case, run) pairs for the plan's slices"},
        "decision_rule": "plan 5.4: top main effect, CI above 0, and top-minus-second CI above 0; at ceiling/floor "
                         "apply the same rule to first-iteration convergence and mean iterations as secondary",
    }
    path = os.path.join(ROOT, "protocol.json")
    if os.path.exists(path):
        sys.exit("protocol.json already exists; it is frozen and must not be overwritten")
    with open(path, "w") as f:
        json.dump(proto, f, indent=2, ensure_ascii=False)
    print(f"frozen {path}: {len(proto['hashes']['task3_sources'])} Task 3 files, "
          f"{len(proto['hashes']['task2_files'])} Task 2 files")


if __name__ == "__main__":
    main()
