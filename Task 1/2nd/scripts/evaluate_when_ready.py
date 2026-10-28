"""Evaluate TPO stages while the independent Best-of-15 control is generated."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ.update(TASK1_RUN_DIR=str(ROOT), PYTHONDONTWRITEBYTECODE='1')


def run(name, *args):
    print(f'Starting {name}', flush=True)
    subprocess.run([sys.executable, '-B', str(ROOT / 'scripts' / name), *args], check=True)


def wait_for(description, ready):
    print(f'Waiting for {description}', flush=True)
    while not ready():
        time.sleep(10)


def tpo_ready():
    path = ROOT / 'generation_status.json'
    return path.exists() and json.loads(path.read_text()).get('run100', {}).get('completed') == 100


wait_for('all 100 completed TPO trajectories', tpo_ready)
run('extract_stages.py', '--tpo_output', str(ROOT / 'run100/results.json'),
    '--meta', str(ROOT / 'data/alpaca100_meta.json'), '--out_dir', str(ROOT / 'stages'),
    '--generator', 'tulu3-8b-sft')
run('build_judge_config.py')
for stage in ['baseline', 'step0', 'step1', 'step2']:
    run('evaluate_stage.py', '--stage', stage)
wait_for('extracted Best-of-15 control', lambda: (ROOT / 'stages/bon15_rm_summary.json').exists())
run('evaluate_stage.py', '--stage', 'bon15')
run('summarize.py')
run('robustness.py')
run('report_comparison.py')
run('audit_results.py')
print('All five stages evaluated; results and comparison reports complete.', flush=True)
