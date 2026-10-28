"""task3_v2.1 re-check, no LLM: Task 2's v2.1 attribution and localization re-computed on every state and sample set
the task3_v2 formal run recorded, and compared with what that run used.

    python recheck_v21.py          # writes results/recheck_v21/recheck.json and recheck.md once

Attribution: every item of every iteration with A on (the prompt shows the item without "raw"; both are compared).
The trial records keep the modifications without their ids; the loop named each soft constraint tpo_<t>_<s> when it
committed it at iteration t (tpo/proposal.py assign_ids), and the attribution names objective terms by these ids, so
they are restored before re-computing.
Localization: the 30 shared localizations (task3_v1's samples, re-scored by v2 before the run), first pass and, where
asked, after the clarification. Refuses unless Task 2's protocol_v21.json matches."""
import datetime
import glob
import json
import os
import sys

sys.dont_write_bytecode = True

from tpo import task2_bridge as t2  # noqa: E402
from run_experiment import load_cases, write_json  # noqa: E402
from tpo.proposal import assign_ids  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
FORMAL_V2 = os.path.join(ROOT, "results", "formal_v2")
OUT = os.path.join(ROOT, "results", "recheck_v21")
TEST_CASES = os.path.join(t2.TASK2_ROOT, "cases", "test_cases.json")


def attribution_rows(comps, cases):
    from v21.recheck import compare_attribution
    rows = []
    for p in sorted(glob.glob(os.path.join(FORMAL_V2, "trials", "*", "*.json"))):
        with open(p) as f:
            r = json.load(f)
        case_mods = list(cases[r["case_id"]].get("model_modifications", []))
        tag = None                              # iteration that committed the modifications in force
        for it in r["iterations"]:
            mods = case_mods + assign_ids(it["mods_before"], tag)
            if it["status"] == "committed":
                tag = it["t"]
            if not it.get("attribution"):
                continue
            for item in it["attribution"]["items"]:
                new = comps.attribute(mods, it["input_solution"], item["raw"]["decision"])
                shown = sorted(k for k in item if k != "raw" and item[k] != new.get(k))
                rows.append({"source": r["config"], "id": f"{r['case_id']}/r{r['run']}/t{it['t']}/{item['decision']}",
                             "diffs": compare_attribution(item["raw"], new["raw"]) + [f"prompt:{k}" for k in shown]})
    return rows


def localization_rows(cases):
    from components.state import make_state
    from v2.localization import decide as decide_v2
    from v21.localization import decide as decide_v21
    from v21.recheck import compare_localization
    rows = []
    for p in sorted(glob.glob(os.path.join(FORMAL_V2, "localization", "*.json"))):
        with open(p) as f:
            r = json.load(f)
        c = cases[r["case_id"]]
        st = make_state(c["solution"], c.get("model_modifications", []))
        for phase, clar in (("initial", None), ("after_clarification", {"question": r["question"],
                                                                         "answer": r["answer"]})):
            if r[phase] is None:
                continue
            args = (r[phase]["raw"]["diagnostics"]["samples"], st, c["complaint"], clar)
            rows.append({"source": "shared localizations", "id": f"{r['case_id']}/r{r['run']}/{phase}",
                         "diffs": compare_localization(decide_v2(*args), decide_v21(*args))})
    return rows


def main():
    path = os.path.join(OUT, "recheck.json")
    if os.path.exists(path):
        sys.exit(f"refused: {path} exists; the re-check runs once")
    from v21.freeze import PROTOCOL, check
    from v21.recheck import markdown, summary
    from tpo_v21.components import Task2ComponentsV21
    proto = check()
    base = t2.load_frozen_instance()
    cases = {c["id"]: c for c in load_cases(TEST_CASES)}
    started = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    att, loc = attribution_rows(Task2ComponentsV21(base, llm=None), cases), localization_rows(cases)
    res = {"meta": {"protocol": "task3_v2.1 re-check of results/formal_v2", "task2_protocol": proto["protocol"],
                    "frozen_at": proto["frozen_at"], "task2_protocol_sha256": t2.sha256(PROTOCOL),
                    "source_sha256": {f: t2.sha256(os.path.join(ROOT, f))
                                      for f in ("recheck_v21.py", "tpo_v21/__init__.py", "tpo_v21/components.py")},
                    "started": started,
                    "finished": datetime.datetime.now().astimezone().isoformat(timespec="seconds")},
           "summary": {"attribution": summary(att), "localization": summary(loc)},
           "attribution": att, "localization": loc}
    os.makedirs(OUT, exist_ok=True)
    write_json(path, res)
    with open(os.path.join(OUT, "recheck.md"), "w") as f:
        f.write(markdown(res).replace("# task2_v2.1 re-check", "# task3_v2.1 re-check of results/formal_v2"))
    print(json.dumps(res["summary"], indent=1))


if __name__ == "__main__":
    main()
