"""Freeze v21/protocol_v21.json before the task2_v2.1 re-check. Refuses to overwrite.
    python -m v21.freeze"""
import datetime
import glob
import json
import os
import sys

from v2.evaluate import ROOT, frozen_files as v2_files, sha256

from .attribution import INFEASIBLE
from .localization import RULE

PROTOCOL = os.path.join(ROOT, "v21", "protocol_v21.json")


def frozen_files():
    """v2.1's own files, and everything task2_v2 froze (v2.1 imports it), with v2's protocol itself."""
    own = {os.path.relpath(p, ROOT) for pat in ("v21/*.py", "tests/test_v21.py")
           for p in glob.glob(os.path.join(ROOT, pat))}
    return sorted(own | set(v2_files()) | {"v2/protocol_v2.json"})


def check():
    if not os.path.exists(PROTOCOL):
        sys.exit("refused: run python -m v21.freeze first")
    proto = json.load(open(PROTOCOL))
    now = {f: sha256(os.path.join(ROOT, f)) for f in frozen_files()}
    changed = sorted(f for f in set(now) | set(proto["file_sha256"]) if now.get(f) != proto["file_sha256"].get(f))
    if changed:
        sys.exit(f"refused: files changed since protocol_v21.json was frozen: {changed}")
    return proto


def main():
    if os.path.exists(PROTOCOL):
        sys.exit(f"refused: {PROTOCOL} exists; the protocol is frozen once")
    proto = {
        "protocol": "task2_v2.1",
        "frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "supersedes": "nothing: task2_v2 (v2/, results_v2/) stays as frozen and produced the reported v2 results",
        "why": "independent review after the v2 runs (README 8.4): anchor accepted with a 0.1% tolerance; infeasible "
               "current plan attributed; modification type not checked against the target; limits that do not "
               "apply counted towards agreement",
        "file_sha256": {f: sha256(os.path.join(ROOT, f)) for f in frozen_files()},
        "attribution_rule": "v2's, with the anchor accepted only if the solver's plan under it costs at least the "
                            "current plan by the exact objective (tolerance 1e-6), and conclusion " + INFEASIBLE +
                            " for a plan over capacity on the data in force",
        "confidence_rule": RULE,
        "llm": "none: v2.1 is checked by re-computing it on the states and samples the v2 runs recorded",
    }
    with open(PROTOCOL, "w") as f:
        json.dump(proto, f, indent=2)
    print(f"frozen {PROTOCOL}: {len(proto['file_sha256'])} files")


if __name__ == "__main__":
    main()
