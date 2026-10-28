"""task3_v2 formal run (audit F1): the 8 main configurations x 3 runs x 10 test cases, with Task 2's v2
attribution in condition A; everything else is task3_v1's frozen code (run_experiment.run_all, tpo/).

All 8 configurations are re-run, not only the four with A, so that the A effect is measured within one batch
instead of against the earlier one. S1 and S2 are not re-run: every one of their 60 trials converged at iteration
1, where the attribution was already correct.

The shared localizations of task3_v1 are re-used (the localization prompt and samples do not depend on A), but
only after checking, sample by sample, that Task 2's v2 confidence rule reaches the same confidence, target,
modification type, limit and clarifying question on them; otherwise the run stops.

    python freeze_protocol_v2.py
    python run_experiment_v2.py --out results/formal_v2 --workers 4"""
import argparse
import json
import os
import sys

sys.dont_write_bytecode = True

from tpo import task2_bridge as t2  # noqa: E402
from tpo.loop import MAIN  # noqa: E402
from run_experiment import load_cases, loc_path, read_json, run_all, write_json  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
TEST_CASES = os.path.join(t2.TASK2_ROOT, "cases", "test_cases.json")
V1_OUT = os.path.join(ROOT, "results", "formal")
PROTOCOL_V2 = os.path.join(ROOT, "protocol_v2.json")


def make_v2_worker(out_dir, base):
    from tpo.llm import real_client
    from tpo_v2.components import Task2ComponentsV2
    llm = real_client(os.path.join(out_dir, "logs", f"llm_{os.getpid()}.jsonl"))
    return Task2ComponentsV2(base, llm), llm


def require_protocol_v2():
    if not os.path.exists(PROTOCOL_V2):
        sys.exit("refused: run freeze_protocol_v2.py first")
    from freeze_protocol_v2 import current
    frozen, now = read_json(PROTOCOL_V2), current()
    if frozen["test_cases"]["sha256"] != t2.sha256(TEST_CASES):
        sys.exit("refused: test case file hash differs from protocol_v2.json")
    for group, files in frozen["hashes"].items():
        changed = sorted(f for f in set(files) | set(now[group]) if files.get(f) != now[group].get(f))
        if changed:
            sys.exit(f"refused: {group} changed since protocol_v2.json was frozen: {changed}")
    return frozen


def _same(old, new):
    """Same decision on the same samples: confidence, then the question or the critique fields TPO sees."""
    if old["confidence"] != new["confidence"]:
        return False
    if old["confidence"] == "low":
        return old["clarifying_question"] == new["clarifying_question"]
    keys = ("target", "aspect", "direction", "modification_type", "threshold", "corrected_value")
    return all(old["critique"].get(k) == new["critique"].get(k) for k in keys)


def reuse_localizations(cases, runs, out_dir):
    from components.state import make_state
    from v2.localization import decide
    checked = []
    for c in cases:
        for r in runs:
            dst = loc_path(out_dir, c["id"], r)
            if os.path.exists(dst):
                continue
            rec = read_json(loc_path(V1_OUT, c["id"], r))
            st = make_state(c["solution"], c.get("model_modifications", []))
            check = {}
            for phase, clar in (("initial", None), ("after_clarification",
                                                    {"question": rec["question"], "answer": rec["answer"]})):
                old = rec[phase]
                if old is None:
                    continue
                new = decide(old["raw"]["diagnostics"]["samples"], st, c["complaint"], clar)
                check[phase] = _same(old["raw"], new)
            if not all(check.values()):
                sys.exit(f"refused: the v2 localization rule changes {c['id']} run {r}: {check}")
            write_json(dst, {**rec, "reused_from": os.path.relpath(loc_path(V1_OUT, c["id"], r), ROOT),
                             "v2_rule_check": check})
            checked.append((c["id"], r))
    return checked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "formal_v2"))
    ap.add_argument("--runs", default="1,2,3")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    proto = require_protocol_v2()
    cases = load_cases(TEST_CASES)
    runs = [int(r) for r in args.runs.split(",")]
    base = t2.load_frozen_instance()
    reused = reuse_localizations(cases, runs, args.out)
    print(f"re-used {len(reused)} task3_v1 localizations (v2 rule: same decision and question on every one)")
    write_json(os.path.join(args.out, "batch.json"), {"protocol": proto["protocol"], "frozen_at": proto["frozen_at"],
                                                      "configs": list(MAIN), "runs": runs,
                                                      "localizations_reused": len(reused)})
    run_all(cases, base, list(MAIN), runs, args.out, make_v2_worker, workers=args.workers)


if __name__ == "__main__":
    main()
