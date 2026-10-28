#!/usr/bin/env bash
# Call the frozen exporter in a staging directory so reference bytes stay frozen.
set -euo pipefail
BASE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export PYTHONPATH="$BASE/scripts${PYTHONPATH:+:$PYTHONPATH}" PYTHONDONTWRITEBYTECODE=1
"${ANALYSIS_PYTHON:-python}" - <<'PY'
from pathlib import Path
import hashlib,shutil
from frozen_common import ROOT,read,save
from export_stages import export
staging=ROOT/'export_staging'
for mode in ['run100','bon15']:
 (staging/mode).mkdir(parents=True,exist_ok=True)
 target=staging/mode/'results.json'
 if not target.exists():target.symlink_to(ROOT/mode/'results.json')
export(staging,100)
for path in (staging/'stages').glob('*.json'):shutil.copy2(path,ROOT/'stages'/path.name)
for name,h in read(ROOT/'data_hashes.json').items():assert hashlib.sha256((ROOT/'data'/name).read_bytes()).hexdigest()==h
save(ROOT/'export_execution.json',{'implementation':'unchanged frozen export_stages.export','destination':'export_staging','published':'stages','frozen_reference_bytes_preserved':True,'reason':'The exporter serializes a working reference copy with a terminal newline. Staging prevents changing the frozen original reference bytes; questions, answers, order and scoring are identical.'})
print('FROZEN_DATA_PRESERVED')
PY
