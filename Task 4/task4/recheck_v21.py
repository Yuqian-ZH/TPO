"""task4_v2.1 re-check, no LLM: the v2.1 service rule and components re-computed on the records of the task4_v2 runs
(results/e2e_dev_v2, e2e_test_v2, audit_v2), and compared with what the v2 service did there.

    python recheck_v21.py          # writes results/recheck_v21/recheck.json and recheck.md once

State change: each complaint's iterations are replayed in order with v2.1's state_change() (the states the user has
seen, starting with the plan complained about) and compared with the v2 decision in the log; the notice v2.1 would
have shown is recorded. Until the first difference the replay is exact, because the next iteration's input depends
only on that decision. Attribution: every item of every iteration with A on, with the soft-constraint ids the loop
assigned at commit restored (the logs keep the modifications without them). Localization: every sample set.
Refuses unless service_freeze_v21.json matches."""
import datetime
import glob
import json
import os
import sys

sys.dont_write_bytecode = True

from feedback_service.bridge import TASK4_ROOT, t2  # noqa: E402
from feedback_service.engine import thread_mods  # noqa: E402
from freeze_service_v21 import current, read_freeze  # noqa: E402
from tpo.proposal import assign_ids  # noqa: E402

RUNS = ("e2e_dev_v2", "e2e_test_v2", "audit_v2")
OUT = os.path.join(TASK4_ROOT, "results", "recheck_v21")


class _Data:
    """engine.data() without the rest of the engine."""

    def __init__(self, base):
        self.base = base

    def data(self, mods):
        return t2.apply_data_mods(self.base, list(mods))


class _Trial:
    def __init__(self, mods):
        self.mods = mods

    def model_mods(self):
        return self.mods


def complaints(run):
    """(feedback record, its iteration log lines in order) for every complaint of a run."""
    for sdir in sorted(glob.glob(os.path.join(TASK4_ROOT, "results", run, "store", "sessions", "*"))):
        with open(os.path.join(sdir, "iterations.jsonl")) as f:
            logs = [json.loads(line) for line in f if line.strip()]
        for p in sorted(glob.glob(os.path.join(sdir, "feedback", "*.json"))):
            with open(p) as f:
                fb = json.load(f)
            yield fb, sorted((x for x in logs if x["feedback_id"] == fb["feedback_id"]), key=lambda x: x["iteration"])


def state_rows(run, eng):
    from feedback_service_v21.service import data_changes, data_key, notice, seen_state, state_change
    rows = []
    for fb, logs in complaints(run):
        thread = thread_mods(fb)
        seen = [seen_state(fb["solution"]["routes"], eng.data(thread))]
        prev_after = None
        for log in logs:
            d = log["detail"]
            if prev_after is not None:
                assert d["mods_before"] == prev_after, (fb["feedback_id"], log["iteration"])
            after_mods = d["committed_mods"] if d["status"] == "committed" else d["mods_before"]
            prev_after = after_mods
            change, after = state_change(eng, fb, d, _Trial(thread + after_mods), seen)
            changes = []
            if change:
                seen = seen + [after]
                changes = data_changes(data_key(eng.data(thread + d["mods_before"])), after["data"])
            v2_change = log["refined_solution"]["state_change"]
            rows.append({"source": run, "id": f"{fb['feedback_id']}/t{log['iteration']}",
                         "diffs": ["state_change"] if change != v2_change else [],
                         "v2": v2_change, "v21": change, "data_changes": changes,
                         "notice": notice(change, changes) if changes else None})
            if change != v2_change:
                break      # the logged run continues differently from here on
    return rows


def attribution_rows(run, comps):
    from v21.recheck import compare_attribution
    rows = []
    for fb, logs in complaints(run):
        tag = None                              # iteration that committed the modifications in force
        for log in logs:
            d = log["detail"]
            mods = thread_mods(fb) + assign_ids(d["mods_before"], tag)
            if d["status"] == "committed":
                tag = log["iteration"]
            if not d.get("attribution"):
                continue
            for item in d["attribution"]["items"]:
                new = comps.attribute(mods, d["input_solution"], item["raw"]["decision"])
                shown = sorted(k for k in item if k != "raw" and item[k] != new.get(k))
                rows.append({"source": run, "id": f"{fb['feedback_id']}/t{log['iteration']}/{item['decision']}",
                             "diffs": compare_attribution(item["raw"], new["raw"]) + [f"prompt:{k}" for k in shown]})
    return rows


def localization_rows(run):
    from components.state import make_state
    from v2.localization import decide as decide_v2
    from v21.localization import decide as decide_v21
    from v21.recheck import compare_localization
    rows = []
    for fb, _ in complaints(run):
        loc = fb.get("localization")
        if not loc:
            continue
        st = make_state({"routes": fb["solution"]["routes"]}, thread_mods(fb))
        for phase in ("initial", "after_clarification"):
            if not loc.get(phase):
                continue
            raw = loc[phase]["raw"]
            args = (raw["diagnostics"]["samples"], st, raw["complaint"], raw["clarification"])
            rows.append({"source": run, "id": f"{fb['feedback_id']}/{phase}",
                         "diffs": compare_localization(decide_v2(*args), decide_v21(*args))})
    return rows


def main():
    path = os.path.join(OUT, "recheck.json")
    if os.path.exists(path):
        sys.exit(f"refused: {path} exists; the re-check runs once")
    frozen = read_freeze()
    if frozen is None:
        sys.exit("refused: run freeze_service_v21.py first")
    now = current()
    changed = sorted(p for p in set(frozen["hashes"]) | set(now["hashes"])
                     if frozen["hashes"].get(p) != now["hashes"].get(p))
    if changed or not now["startup_checks"]["ok"]:
        sys.exit(f"refused: changed since service_freeze_v21.json: {changed} {now['startup_checks']}")
    from tpo_v21.components import Task2ComponentsV21
    from v21.recheck import summary
    base = t2.load_frozen_instance()
    comps, eng = Task2ComponentsV21(base, llm=None, run_label="t4"), _Data(base)
    started = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    res = {"state_change": [], "attribution": [], "localization": []}
    for run in RUNS:
        res["state_change"] += state_rows(run, eng)
        res["attribution"] += attribution_rows(run, comps)
        res["localization"] += localization_rows(run)
    res = {"meta": {"protocol": "task4_v2.1 re-check", "frozen_at": frozen["frozen_at"],
                    "freeze_sha256": t2.sha256(os.path.join(TASK4_ROOT, "service_freeze_v21.json")),
                    "started": started,
                    "finished": datetime.datetime.now().astimezone().isoformat(timespec="seconds")},
           "summary": {k: summary(v) for k, v in res.items()}, **res}
    shown = [r for r in res["state_change"] if r["v21"]]
    res["summary"]["plans_shown"] = {"v21": len(shown), "with_data_notice": sum(bool(r["notice"]) for r in shown)}
    os.makedirs(OUT, exist_ok=True)
    with open(path, "w") as f:
        json.dump(res, f, indent=1)
    lines = ["# task4_v2.1 re-check of the task4_v2 runs (no LLM)", "",
             f"Frozen: `service_freeze_v21.json` ({frozen['frozen_at']}).", "",
             "| Records | Run | Checked | v2.1 differs from v2 |", "|---|---|---:|---:|"]
    for part in ("state_change", "attribution", "localization"):
        for run, s in res["summary"][part].items():
            lines.append(f"| {part} | {run} | {s['checked']} | {s['changed']} |")
    lines += ["", f"Plans v2.1 would show: {len(shown)}, of which with a data notice: "
                  f"{res['summary']['plans_shown']['with_data_notice']}."]
    lines += [f"- `{r['id']}` ({r['source']}): {r['notice']}" for r in shown if r["notice"]]
    with open(os.path.join(OUT, "recheck.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print(json.dumps(res["summary"], indent=1))


if __name__ == "__main__":
    main()
