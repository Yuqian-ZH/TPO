"""Run trials (plan 6). Resumable: a trial or shared localization whose file exists is not rerun.
Parallel over processes, never threads (Task 2's model.py shares one Gurobi env per process).

Test cases are refused unless protocol.json is frozen and records their hash (plan 0, rule 2)."""
import argparse
import concurrent.futures as cf
import json
import os
import sys

sys.dont_write_bytecode = True

from tpo import task2_bridge as t2  # noqa: E402
from tpo.loop import CONFIGS, MAIN, Settings, localize_with_clarification, needs_localization, run_trial  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
DEV_CASES = os.path.join(t2.TASK2_ROOT, "cases", "dev_cases.json")


def load_cases(path):
    with open(path) as f:
        d = json.load(f)
    return d["cases"] if isinstance(d, dict) else d


def trial_path(out, config, case_id, run):
    return os.path.join(out, "trials", config, f"{case_id}__r{run}.json")


def loc_path(out, case_id, run):
    return os.path.join(out, "localization", f"{case_id}__r{run}.json")


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def read_json(path):
    with open(path) as f:
        return json.load(f)


def require_protocol_for_test(cases_path, cases):
    if not any(c.get("split") == "test" for c in cases):
        return
    proto = os.path.join(ROOT, "protocol.json")
    if not os.path.exists(proto):
        sys.exit("refused: test cases need a frozen protocol.json (plan stage 3)")
    frozen = read_json(proto)
    if frozen["test_cases"]["sha256"] != t2.sha256(cases_path):
        sys.exit("refused: test case file hash differs from protocol.json")
    from freeze_protocol import current
    now = current()
    for group, files in frozen["hashes"].items():
        changed = sorted(f for f in set(files) | set(now[group]) if files.get(f) != now[group].get(f))
        if changed:
            sys.exit(f"refused: {group} changed since protocol.json was frozen: {changed}")


# ---------- workers ----------

_W = {}


def make_task2_worker(out_dir, base):
    from tpo.components import Task2Components
    from tpo.llm import real_client
    llm = real_client(os.path.join(out_dir, "logs", f"llm_{os.getpid()}.jsonl"))
    return Task2Components(base, llm), llm


def _init(factory, out_dir, base, settings):
    sys.dont_write_bytecode = True
    _W["comps"], _W["llm"] = factory(out_dir, base)
    _W["base"], _W["settings"] = base, settings


def _loc_job(case, run, out_dir):
    rec = localize_with_clarification(case, _W["base"], _W["comps"], run)
    write_json(loc_path(out_dir, case["id"], run), rec)
    return ("loc", case["id"], run)


def _trial_job(case, config, run, out_dir):
    flags = CONFIGS[config]
    loc = read_json(loc_path(out_dir, case["id"], run)) if needs_localization(flags) else None
    rec = run_trial(case, _W["base"], flags, config, run, _W["comps"], _W["llm"], _W["settings"], loc)
    write_json(trial_path(out_dir, config, case["id"], run), rec)
    return ("trial", config, case["id"], run, rec["outcome"])


def run_all(cases, base, configs, runs, out_dir, factory, settings=Settings(), workers=0, log=print):
    """factory(out_dir, base) -> (components, llm). workers=0 runs in this process (pytest)."""
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
    ap.add_argument("--cases", default=DEV_CASES)
    ap.add_argument("--configs", default="all", help="'main', 'all' or a comma list")
    ap.add_argument("--runs", default="1,2,3")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    cases = load_cases(args.cases)
    require_protocol_for_test(args.cases, cases)
    configs = list(MAIN) if args.configs == "main" else list(CONFIGS) if args.configs == "all" else \
        args.configs.split(",")
    runs = [int(r) for r in args.runs.split(",")]
    base = t2.load_frozen_instance()
    run_all(cases, base, configs, runs, args.out, make_task2_worker, workers=args.workers)


if __name__ == "__main__":
    main()
