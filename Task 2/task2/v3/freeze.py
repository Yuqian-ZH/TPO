"""Freeze v3/protocol_v3.json before any task2_v3 evaluation and before Task 3's v3 test run. Refuses to overwrite.
    python -m v3.freeze"""
import datetime
import glob
import json
import os
import sys

from v2.evaluate import ROOT, sha256
from v21.freeze import frozen_files as v21_files

PROTOCOL = os.path.join(ROOT, "v3", "protocol_v3.json")


def frozen_files():
    """task2_v3's files (cases, conditions, builder, evaluation, tests; not report.py) and everything task2_v2.1
    froze."""
    own = {os.path.relpath(p, ROOT) for pat in ("v3/*.py", "v3/cases/*.json", "tests/test_v3_*.py")
           for p in glob.glob(os.path.join(ROOT, pat))} - {"v3/report.py"}   # the report is a pure function of raw
    return sorted(own | set(v21_files()) | {"v21/protocol_v21.json"})


def check():
    if not os.path.exists(PROTOCOL):
        sys.exit("refused: run python -m v3.freeze first")
    proto = json.load(open(PROTOCOL))
    now = {f: sha256(os.path.join(ROOT, f)) for f in frozen_files()}
    changed = sorted(f for f in set(now) | set(proto["file_sha256"]) if now.get(f) != proto["file_sha256"].get(f))
    if changed:
        sys.exit(f"refused: files changed since protocol_v3.json was frozen: {changed}")
    return proto


def main():
    if os.path.exists(PROTOCOL):
        sys.exit(f"refused: {PROTOCOL} exists; the protocol is frozen once")
    cases = json.load(open(os.path.join(ROOT, "v3", "cases", "test_cases.json")))["cases"]
    proto = {
        "protocol": "task2_v3",
        "frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "design": "DESIGN_V3.md at the project root",
        "supersedes": "nothing: task2_v1, v2 and v2.1 keep their cases and results; v3 is reported beside them",
        "test_cases": {"file": "v3/cases/test_cases.json", "sha256": sha256(os.path.join(ROOT, "v3", "cases",
                                                                                       "test_cases.json")),
                       "strata": {c["id"]: c["stratum"] for c in cases}},
        "components": "task2_v2.1 (v21/attribution.py, v21/localization.py)",
        "file_sha256": {f: sha256(os.path.join(ROOT, f)) for f in frozen_files()},
        "llm": {"runs": 3, "explanation": "v21.explain, component explain_v3",
                "localization": "v21.localize, run labels v3-<run>, then with the case's explanation as the answer"},
    }
    with open(PROTOCOL, "w") as f:
        json.dump(proto, f, indent=2)
    print(f"frozen {PROTOCOL}: {len(proto['file_sha256'])} files")


if __name__ == "__main__":
    main()
