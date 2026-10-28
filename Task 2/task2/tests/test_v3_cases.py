"""task2_v3 cases (DESIGN_V3.md section 3): the files are what the builder produces, and every design property holds."""
import json
import os

import pytest

from cvrp.data import load_instance
from v3 import cases as C
from v3.conditions import feedback, verdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = load_instance(os.path.join(ROOT, "instance", "cvrp_instance.json"))
FILES = {s: json.load(open(os.path.join(ROOT, "v3", "cases", f"{s}_cases.json")))["cases"] for s in ("test", "dev")}
SPECS = [("test", s) for s in C.TEST] + [("dev", s) for s in C.DEV]


@pytest.mark.parametrize("split,spec", SPECS, ids=[s["id"] for _, s in SPECS])
def test_file_matches_builder(split, spec):
    built = json.loads(json.dumps(C.build(spec, BASE, split)))
    assert built == next(c for c in FILES[split] if c["id"] == spec["id"])


def test_strata():
    for split in ("test", "dev"):
        strata = [c["stratum"] for c in FILES[split]]
        assert (strata.count("control"), strata.count("ambiguity"), strata.count("side")) == (2, 3, 5)
        assert all(c["clarity"] == ("ambiguous" if c["stratum"] == "ambiguity" else "clear") for c in FILES[split])
        assert all(c["gt"]["localization"]["confidence"] == ("low" if c["stratum"] == "ambiguity" else "high")
                   for c in FILES[split])


def test_feedback_words():
    c = next(x for x in FILES["test"] if x["id"] == "U7")
    v = verdict(c, c["solution"], BASE)
    assert not v["resolved"] and v["unmet"] == ["vehicle 1 carries 99 units, and it must carry at most 94"]
    first, later = feedback(c, v, False), feedback(c, v, True)
    assert first.startswith("That does not solve it. What I mean is: " + c["explanation"])
    assert later == "That does not solve it yet. In the new plan vehicle 1 carries 99 units, and it must carry at most 94."


def test_side_conditions_hold_at_the_start():
    """The second condition of a side case is met by the plan complained about; only the request is not."""
    for c in FILES["test"] + FILES["dev"]:
        if c["stratum"] == "side":
            v = verdict(c, c["solution"], BASE)
            failed = [r for r in v["conditions"] if not r["passed"]]
            assert len(failed) == 1 and failed[0] == {**c["conditions"][0], **failed[0]}, c["id"]


def test_ground_truth_covers_both_attribution_and_feasibility_outcomes():
    """As task2_v1's test set: some decisions forced by capacity (IIS path), some what-if queries infeasible."""
    att = [c["gt"]["attribution"]["conclusion"] for c in FILES["test"]]
    cf = [c["gt"]["counterfactual"]["feasible"] for c in FILES["test"]]
    assert att.count("capacity_forced") == 2 and cf.count(False) == 2
