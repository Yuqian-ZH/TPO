"""Run the original Tulu policy and Llama RM; Qwen is used only for judging."""
import argparse
import concurrent.futures
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import random
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source/TPO'
sys.dont_write_bytecode = True
sys.path[:0] = [str(SOURCE / 'textgrad-main'), str(SOURCE)]


def save(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    destination = ROOT / 'smoke' if args.smoke else ROOT
    destination.mkdir(exist_ok=True)
    os.chdir(destination)
    lock = (destination / 'generation.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    from llama_engine import create_engine
    from reward_model import TPORewardModel
    from tpo_utils import run_test_time_training_tpo, run_test_time_training_bon
    import textgrad
    assert Path(textgrad.__file__).is_relative_to(SOURCE)
    engine = create_engine(destination)
    print('Loading unchanged sfairXC/FsfairX-LLaMA3-RM-v0.1', flush=True)
    rm = TPORewardModel('sfairXC/FsfairX-LLaMA3-RM-v0.1')
    queries = json.loads((ROOT / 'data/alpaca100.json').read_text())
    random.seed(7)
    random.shuffle(queries)
    if args.smoke:
        queries = queries[:1]
    status_path = destination / 'generation_status.json'
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    for phase, n in [('run100', 5), ('bon15', 15)]:
        if args.smoke and phase == 'bon15':
            continue
        engine.phase = phase
        folder = destination / phase
        folder.mkdir(exist_ok=True)
        path = folder / 'results.json'
        results = json.loads(path.read_text()) if path.exists() else []
        completed = {key.split('<SEP>', 2)[1] for row in results for key in row}
        remaining = [q for q in queries if q not in completed]
        status[phase] = dict(state='running', completed=len(completed), target=len(queries),
            started_at=datetime.now(ZoneInfo('America/Los_Angeles')).isoformat())
        save(status_path, status)
        started = time.monotonic()
        fn = run_test_time_training_tpo if phase == 'run100' else run_test_time_training_bon
        params = dict(n=n, temperature=0.7, top_p=0.95, seed=7, max_tokens=2048)
        errors = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(fn, q, engine, rm, gen_params=params, tpo_mode='tpo', max_iters=2): q for q in remaining}
            for future in concurrent.futures.as_completed(futures):
                q = futures[future]
                try:
                    result = future.result()
                    assert result and {k.split('<SEP>', 2)[1] for k in result} == {q}
                    results.append(result)
                    save(path, results)
                except Exception as exc:
                    errors.append(dict(instruction=q, error_type=type(exc).__name__, error=str(exc)[:200]))
                    save(folder / 'errors.json', errors)
                status[phase].update(completed=len(results), failed=len(errors), elapsed_seconds=time.monotonic() - started)
                save(status_path, status)
                print(f'{phase}: {len(results)}/{len(queries)} complete; {len(errors)} failed', flush=True)
        status[phase].update(state='complete' if len(results) == len(queries) else 'incomplete',
            elapsed_seconds=time.monotonic() - started,
            finished_at=datetime.now(ZoneInfo('America/Los_Angeles')).isoformat())
        save(status_path, status)
        if errors:
            raise RuntimeError(f'{phase}: {len(errors)} prompts failed; rerun to resume')


if __name__ == '__main__':
    main()
