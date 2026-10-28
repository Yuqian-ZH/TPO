"""Resolve checkout, run artifacts, and preserved traces without server paths."""
import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('TASK1_RUN_DIR', PACKAGE_DIR.parent)).expanduser().resolve()
REPO = Path(os.environ.get('TASK1_TPO_DIR', PACKAGE_DIR.parent)).expanduser().resolve()


def snapshot_dir():
    return PACKAGE_DIR / 'experiments' / (PACKAGE_DIR / 'experiments/LATEST.txt').read_text().strip()


def trace_path():
    explicit = os.environ.get('TASK1_TRACE_PATH')
    if explicit:
        return Path(explicit).expanduser().resolve()
    if ROOT == PACKAGE_DIR:
        return snapshot_dir() / 'TPO_logs/2026-10-19_19-50-42.jsonl'
    traces = [p for p in (ROOT / 'logs').glob('*.jsonl') if p.stat().st_size]
    if not traces:
        raise FileNotFoundError('No generation trace found. Set TASK1_TRACE_PATH explicitly.')
    return max(traces, key=lambda p: p.stat().st_size)
