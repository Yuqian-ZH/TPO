from pathlib import Path
import os
from frozen_common import ROOT as RUN
ROOT=Path(os.environ.get('TASK1_RUN_DIR',RUN))
PACKAGE_DIR=ROOT
REPO=RUN/'source/TPO'
def trace_path():
 paths=list((ROOT/'logs').glob('*.jsonl'))
 return max(paths,key=lambda p:p.stat().st_size)
