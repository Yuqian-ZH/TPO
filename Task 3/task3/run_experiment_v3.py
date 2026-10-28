"""task3_v3 runs (DESIGN_V3.md): the 8 main configurations on Task 2's task2_v3 cases, with the v3 simulated user and
Task 2's task2_v2.1 components. Resumable, parallel over processes, as run_experiment.py.

    python run_experiment_v3.py --configs A0B0C0,A1B1C1 --runs 1,2 --out results/pilot_v3     # dev cases
    python freeze_protocol_v3.py
    python run_experiment_v3.py --cases test --configs main --runs 1,2,3,4,5 --out results/formal_v3

Test cases are refused unless protocol_v3.json is frozen and every hash in it still matches."""
import argparse
import concurrent.futures as cf
import os
import sys

sys.dont_write_bytecode = True

from tpo import task2_bridge as t2  # noqa: E402
from tpo.loop import CONFIGS, MAIN, Settings, needs_localization  # noqa: E402
from run_experiment import load_cases, loc_path, read_json, trial_path, write_json  # noqa: E402
from tpo_v3.loop import localize_with_clarification, run_trial  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
CASES = {s: os.path.join(t2.TASK2_ROOT, "v3", "cases", f"{s}_cases.json") for s in ("dev", "test")}
PROTOCOL_V3 = os.path.join(ROOT, "protocol_v3.json")


def require_protocol_v3(cases_path):
    if not os.path.exists(PROTOCOL_V3):
        sys.exit("refused: test cases need protocol_v3.json (python freeze_protocol_v3.py)")
    from freeze_protocol_v3 import current
    from v3.freeze import check as task2_v3_check      # Task 2's protocol: its own files still match
    task2_v3_check()
    frozen, now = read_json(PROTOCOL_V3), current()
    if frozen["test_cases"]["sha256"] != t2.sha256(cases_path):
        sys.exit("refused: test case file hash differs from protocol_v3.json")
    for group, files in frozen["hashes"].items():
        changed = sorted(f for f in set(files) | set(now[group]) if files.get(f) != now[group].get(f))
        if changed:
            sys.exit(f"refused: {group} changed since protocol_v3.json was frozen: {changed}")
    return frozen


def make_v3_worker(out_dir, base):
    from tpo.llm import real_client
    from tpo_v21.components import Task2ComponentsV21
    llm = real_client(os.path.join(out_dir, "logs", f"llm_{os.getpid()}.jsonl"))
    return Task2ComponentsV21(base, llm), llm


_W = {}


def _init(factory, out_dir, base, settings):
    sys.dont_write_bytecode = True
    _W["comps"], _W["llm"] = factory(out_dir, base)
    _W["base"], _W["settings"] = base, settings


def _loc_job(case, run, out_dir):
    write_json(loc_path(out_dir, case["id"], run), localize_with_clarification(case, _W["base"], _W["comps"], run))
    return ("loc", case["id"], run)


def _trial_job(case, config, run, out_dir):
    flags = CONFIGS[config]
    loc = read_json(loc_path(out_dir, case["id"], run)) if needs_localization(flags) else None
    rec = run_trial(case, _W["base"], flags, config, run, _W["comps"], _W["llm"], _W["settings"], loc)
    write_json(trial_path(out_dir, config, case["id"], run), rec)
    return ("trial", config, case["id"], run, rec["outcome"], rec.get("converged_at"))


def run_all(cases, base, configs, runs, out_dir, factory=make_v3_worker, settings=Settings(), workers=0, log=print):
    """As run_experiment.run_all, with the task3_v3 trial and shared localization."""
    loc_jobs = sorted({(c["id"], r) for c in cases for r in runs for g in configs if needs_localization(CONFIGS[g])
                       and not os.path.exists(loc_path(out_dir, c["id"], r))})
    trial_jobs = [(c, g, r) for g in configs for c in cases for r in runs
                  if not os.path.exists(trial_path(out_dir, g, c["id"], r))]
    by_id = {c["id"]: c for c in cases}
    log(f"{len(loc_jobs)} localizations and {len(trial_jobs)} trials to run")
    if workers == 0:
        _init(factory, out_dir, base, settings)
        for cid, r in loc_jobs:
            log(_loc_job(by_id[cid], r, out_dir))
        for c, g, r in trial_jobs:
            log(_trial_job(c, g, r, out_dir))
        return
    with cf.ProcessPoolExecutor(workers, initializer=_init, initargs=(factory, out_dir, base, settings)) as ex:
        for fut in cf.as_completed([ex.submit(_loc_job, by_id[cid], r, out_dir) for cid, r in loc_jobs]):
            log(fut.result())
        for fut in cf.as_completed([ex.submit(_trial_job, c, g, r, out_dir) for c, g, r in trial_jobs]):
            log(fut.result())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", choices=list(CASES), default="dev")
    ap.add_argument("--configs", default="main", help="'main' or a comma list")
    ap.add_argument("--runs", default="1,2,3,4,5")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    path = CASES[args.cases]
    cases = load_cases(path)
    if args.cases == "test":
        require_protocol_v3(path)
    configs = list(MAIN) if args.configs == "main" else args.configs.split(",")
    runs = [int(r) for r in args.runs.split(",")]
    base = t2.load_frozen_instance()
    run_all(cases, base, configs, runs, args.out, workers=args.workers, log=lambda m: print(m, flush=True))


if __name__ == "__main__":
    main()
