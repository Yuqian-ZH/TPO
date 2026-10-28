"""Plan section 10 acceptance checklist, run after the formal experiment. Writes results/formal/acceptance.json.
Reads the credential from the environment only to search for it; it is never printed or written."""
import glob
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True

import stats  # noqa: E402
from freeze_protocol import TEST_CASES, current  # noqa: E402
from recompute import load_trials, recompute  # noqa: E402
from run_experiment import load_cases, read_json, write_json  # noqa: E402
from tpo.loop import CONFIGS  # noqa: E402
from tpo.task2_bridge import TASK2_ROOT, load_frozen_instance, sha256  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "results", "formal")


def main():
    proto = read_json(os.path.join(ROOT, "protocol.json"))
    cases = load_cases(TEST_CASES)
    trials = load_trials(OUT)
    checks = {}
    now = current()
    checks["hashes_match_protocol"] = all(proto["hashes"][g] == now[g] for g in proto["hashes"])
    checks["test_cases_match_task2_freeze"] = (sha256(TEST_CASES) == proto["test_cases"]["sha256"] ==
                                               read_json(os.path.join(TASK2_ROOT, "FROZEN.json"))["test_cases"]["sha256"])
    keys = {(t["config"], t["case_id"], t["run"]) for t in trials}
    expected = {(g, c["id"], r) for g in CONFIGS for c in cases for r in (1, 2, 3)}
    checks["all_trials_present"] = keys == expected and len(trials) == len(expected)
    checks["mean_and_std_for_every_config"] = all(
        v["rate_mean_std_over_runs"]["std"] is not None for v in stats.summarize(trials, B=10)["configs"].values())
    leaked_low = [(t["config"], t["case_id"], t["run"]) for t in trials
                  if t["flags"]["C"] and t["localization"]["final"]["confidence"] != "high" and t["iterations"]]
    checks["no_low_confidence_reaches_tpo"] = not leaked_low
    by_id = {c["id"]: c for c in cases}
    leaks = []
    for t in trials:
        c = by_id[t["case_id"]]
        prompts = [it["proposal_prompt"] for it in t["iterations"]]
        # The bare checker name is not used as a marker: Task 2's localizer has the same vocabulary
        # ("detour_ratio" is one of its evidence keys, "same_vehicle" one of its aspects). Its full spec is.
        private = [json.dumps(c["checker"]), f'"name": "{c["checker"]["name"]}"', c["why_question"],
                   c["what_if_question"], c["scenario"]]
        asked = bool(t.get("localization") and t["localization"]["asked"])
        if not (asked and (t["flags"]["C"] or t["flags"]["clar_text"])):
            private.append(c["clarification_answer"])
        leaks += [(t["config"], t["case_id"], t["run"], s[:40]) for s in private if any(s in p for p in prompts)]
        ref = json.dumps(c["reference_modification"][0], separators=(", ", ": "))
        if t["iterations"] and ref in t["iterations"][0]["proposal_prompt"]:
            leaks.append((t["config"], t["case_id"], t["run"], "reference_modification"))
    checks["no_private_field_in_proposal_prompts"] = not leaks
    base = load_frozen_instance()
    a, b = recompute(OUT, cases, base), recompute(OUT, cases, base)
    saved = read_json(os.path.join(OUT, "task3_results.json"))["recompute"]
    checks["recompute_reproducible"] = (json.dumps(a, sort_keys=True, default=str) ==
                                        json.dumps(b, sort_keys=True, default=str) ==
                                        json.dumps(saved, sort_keys=True, default=str))
    key = os.environ.get("DASHSCOPE_API_KEY")
    hits = []
    if key:
        for path in glob.glob(os.path.join(os.path.dirname(ROOT), "**", "*"), recursive=True):
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    if key.encode() in f.read():
                        hits.append(os.path.relpath(path, ROOT))
    checks["no_credential_in_task3"] = bool(key) and not hits
    checks["no_bytecode_or_caches_in_task3"] = not [p for p in glob.glob(os.path.join(os.path.dirname(ROOT), "**"),
                                                                         recursive=True)
                                                    if os.path.basename(p) in ("__pycache__", ".pytest_cache")]
    py = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, capture_output=True, text=True,
                        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    checks["pytest"] = py.returncode == 0
    report = {"checks": checks, "all_passed": all(checks.values()), "pytest_tail": py.stdout.strip().splitlines()[-1:],
              "low_confidence_leaks": leaked_low, "prompt_leaks": leaks, "credential_hits": hits}
    write_json(os.path.join(OUT, "acceptance.json"), report)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
