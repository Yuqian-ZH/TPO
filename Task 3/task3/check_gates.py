"""Read-only check of the three Task 2 gates (plan section 2). Prints JSON; never modifies Task 2."""
import json
import os
import re
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.abspath(__file__))
TASK2 = os.path.normpath(os.path.join(ROOT, "..", "..", "Task 2", "task2"))
COMPONENTS = ("attribution.py", "counterfactual.py", "localization.py")


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def task2_status():
    try:
        with open(os.path.join(TASK2, "PROGRESS.md")) as f:
            text = f.read()
    except OSError:
        return {}
    out = {}
    for key in ("status", "last_heartbeat", "next_step"):
        m = re.search(rf"^{key}:\s*(.+)$", text, re.M)
        out[key] = m.group(1).strip() if m else None
    return out


def gates():
    frozen = _read_json(os.path.join(TASK2, "FROZEN.json")) or {}
    comps = {c: os.path.exists(os.path.join(TASK2, "components", c)) for c in COMPONENTS}
    dev = os.path.exists(os.path.join(TASK2, "cases", "dev_cases.json"))
    protocol = os.path.exists(os.path.join(TASK2, "protocol.json"))
    results = os.path.exists(os.path.join(TASK2, "results", "task2_results.json"))
    g1 = bool(frozen.get("test_cases"))
    g2 = g1 and all(comps.values()) and dev
    g3 = g2 and protocol and results
    return {"task2": task2_status(),
            "G1_test_cases_frozen": g1,
            "G2_components_and_dev_cases": g2,
            "G3_protocol_frozen_and_evaluated": g3,
            "detail": {"components": comps, "dev_cases": dev, "protocol.json": protocol,
                       "task2_results.json": results}}


if __name__ == "__main__":
    print(json.dumps(gates(), indent=2, ensure_ascii=False))
