"""Freeze protocol_v31.json before the task3_v31 test run (DESIGN_V31.md section 6). run_experiment_v31.py refuses
test cases unless every hash still matches and Task 2's v3/protocol_v3.json still matches its files.
protocol.json, protocol_v2.json and protocol_v3.json are kept as they are."""
import datetime
import json
import os
import sys
from dataclasses import asdict

sys.dont_write_bytecode = True

from tpo import task2_bridge as t2  # noqa: E402
from tpo.loop import Settings  # noqa: E402
from freeze_protocol import TASK2_DEPENDS, TASK3_SOURCES, hashes  # noqa: E402
from freeze_protocol_v3 import TASK3_ADAPTERS, TASK3_V3_SOURCES, TEST_CASES  # noqa: E402
from tpo_v31.loop import ALL, CONFIGS, RUNS, SUPPLEMENTARY  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
TASK3_V31_SOURCES = ["tpo_v31/*.py", "run_experiment_v31.py", "freeze_protocol_v31.py", "tests/test_v31.py"]


def current():
    return {"task3_v1_sources": hashes(ROOT, TASK3_SOURCES), "task3_adapters": hashes(ROOT, TASK3_ADAPTERS),
            "task3_v3_sources": hashes(ROOT, TASK3_V3_SOURCES + ["protocol_v3.json"]),
            "task3_v31_sources": hashes(ROOT, TASK3_V31_SOURCES),
            "task2_files": hashes(t2.TASK2_ROOT, TASK2_DEPENDS + ["v3/protocol_v3.json"])}


def main():
    path = os.path.join(ROOT, "protocol_v31.json")
    if os.path.exists(path):
        sys.exit("protocol_v31.json already exists; it is frozen and must not be overwritten")
    sys.path.append(t2.TASK2_ROOT)
    from v3.freeze import check as task2_v3_check
    task2_v3_check()
    v3 = json.load(open(os.path.join(ROOT, "protocol_v3.json")))
    t2.load_frozen_instance()
    cases = json.load(open(TEST_CASES))["cases"]
    s = Settings()
    proto = {
        "protocol": "task3_v31",
        "frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "confirmed_by": "user, 2026-10-27: run a separate pre-registered v3.1 batch that shows the session's "
                        "modifications in the prompt",
        "design": "DESIGN_V31.md at the project root (sections 1-7 written before any LLM call; pilot in section 8)",
        "supersedes": "nothing: task3_v3 (results/formal_v3) is kept and reported beside v3.1; not pooled",
        "test_cases": {"file": "Task 2/task2/v3/cases/test_cases.json", "sha256": t2.sha256(TEST_CASES),
                       "strata": {c["id"]: c["stratum"] for c in cases},
                       "with_session_modifications": [c["id"] for c in cases if c.get("model_modifications")]},
        "task2_protocol_v3_sha256": t2.sha256(os.path.join(t2.TASK2_ROOT, "v3", "protocol_v3.json")),
        "hashes": current(),
        "report_v31_sha256_at_freeze": t2.sha256(os.path.join(ROOT, "report_v31.py")),
        "change_to_the_loop": "tpo_v31.loop.TrialV31: a block listing the session's modifications before "
                              "'Modifications currently in force'; prompts of cases without them are task3_v3's",
        "components": v3["components"], "simulated_user": v3["simulated_user"], "llm": v3["llm"],
        "loop": {**v3["loop"], "max_iterations": s.max_iters},
        "configs": list(ALL),
        "supplementary": {g: asdict(CONFIGS[g]) for g in SUPPLEMENTARY},
        "runs": list(RUNS),
        "primary_metric": v3["primary_metric"],
        "decision_rule": v3["decision_rule"],
        "preregistered_questions": {
            "1_A": "A's main effect in the side stratum: upper CI bound < 0 -> still harmful, harm not only from the "
                   "hidden session modifications; CI includes 0 -> no harm detectable; lower bound > 0 -> helps. "
                   "Descriptive: A1 vs A0 per side case, session-modification repeats on U9/U10, beside v3",
            "2_B": "pooled pairs within 3 iterations, all cases: probe vs blind (A0B1C0-S1a, A1B1C1-S1b) lower CI > 0 "
                   "-> at least partly from seeing consequences; else blind vs single (S1a-A0B0C0, S1b-A1B0C1) "
                   "lower CI > 0 -> mainly more candidates; else not separable",
            "3_C": "A0B0C1 vs S2a and S2a vs A0B0C0, ambiguity stratum at iteration 1, descriptive",
        },
        "preregistered_secondary": v3["preregistered_secondary"],
        "expectation_stated_before_running": "A's harm on U10 disappears or shrinks; U8 (no session modification) "
                                             "is unaffected by the change",
    }
    with open(path, "w") as f:
        json.dump(proto, f, indent=2, ensure_ascii=False)
    print(f"frozen {path}: " + ", ".join(f"{len(v)} {k}" for k, v in proto["hashes"].items()))


if __name__ == "__main__":
    main()
