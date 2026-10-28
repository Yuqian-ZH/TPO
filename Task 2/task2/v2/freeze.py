"""Freeze v2/protocol_v2.json before the LLM parts of the task2_v2 evaluation. Refuses to overwrite.
    python -m v2.freeze"""
import datetime
import json
import os
import sys

from components.localization import N_SAMPLES, TEMPERATURE
from components.llm_client import MODEL

from .evaluate import PROTOCOL, ROOT, RUNS, frozen_files, sha256
from .localization import RULE


def main():
    if os.path.exists(PROTOCOL):
        sys.exit(f"refused: {PROTOCOL} exists; the protocol is frozen once")
    proto = {
        "protocol": "task2_v2",
        "frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "supersedes": "nothing: task2_v1 (protocol.json, results/) stays as frozen; v2 results are reported beside it",
        "why": "audit findings F1 (attribution relabelling and missing anchor), F4 (unequal timing set-up), "
               "F5 / Task 4 T7 (confidence rule counted the modification type, ignored direction and limit)",
        "file_sha256": {f: sha256(os.path.join(ROOT, f)) for f in frozen_files()},
        "llm": {"model": MODEL, "enable_thinking": False, "runs": RUNS,
                "explanation": {"temperature": 0.2, "max_attempts": 2, "component": "explain_v2",
                                "fallback": "template, counted as failure"},
                "localization": {"temperature": TEMPERATURE, "samples": N_SAMPLES,
                                 "components": ["localize_v2", "localize_v2_clarified"]},
                "seed_rule": "Task 2's derive_seed (payload 'task2_v1|case|component|run|sample'); the component "
                             "names are new, so every sample is new"},
        "confidence_rule": {**RULE, "definition": "high iff >= min_agree valid samples share the same (target, "
                                                  "direction, threshold, corrected value), >= min_non_ambiguous valid "
                                                  "samples are not ambiguous and invalid samples <= max_invalid; the "
                                                  "modification type is the majority among the agreeing samples"},
        "attribution_rule": "forbid the decision, single anchor relative to the current plan (smallest customer not "
                            "involved in the decision or the modifications), no relabelling, direction reversed only "
                            "on objective ties; conclusion cheaper_without when forbidding lowers the objective",
    }
    with open(PROTOCOL, "w") as f:
        json.dump(proto, f, indent=2)
    print(f"frozen {PROTOCOL}: {len(proto['file_sha256'])} files")


if __name__ == "__main__":
    main()
