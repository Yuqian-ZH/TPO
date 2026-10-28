#!/usr/bin/env bash
set -euo pipefail
RUN_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
export TASK1_RUN_DIR="$RUN_ROOT" PYTHONDONTWRITEBYTECODE=1
PYTHON=${TPO_PYTHON:-/dataMeR2/Yuqian/miniconda3/envs/tpo/bin/python}
"$PYTHON" -B "$RUN_ROOT/scripts/extract_stages.py" \
  --tpo_output "$RUN_ROOT/run100/results.json" \
  --meta "$RUN_ROOT/data/alpaca100_meta.json" --out_dir "$RUN_ROOT/stages"
"$PYTHON" -B "$RUN_ROOT/scripts/extract_bon15.py"
