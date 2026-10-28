#!/usr/bin/env bash
set -euo pipefail
RUN_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
export TASK1_RUN_DIR="$RUN_ROOT" PYTHONDONTWRITEBYTECODE=1
export PATH="${AEVAL_BIN:-/dataMeR2/Yuqian/miniconda3/envs/aeval/bin}:$PATH"
bash "$RUN_ROOT/scripts/run_alpaca_eval.sh"
python -B "$RUN_ROOT/scripts/robustness.py"
python -B "$RUN_ROOT/scripts/report_comparison.py"
python -B "$RUN_ROOT/scripts/audit_results.py"
