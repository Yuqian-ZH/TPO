#!/usr/bin/env bash
set -euo pipefail
BASE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
RUN=${FROZEN_RUN_DIR:-"$BASE/$(cat "$BASE/LATEST.txt")"}
AEVAL=${AEVAL_PYTHON:-/dataMeR2/Yuqian/miniconda3/envs/aeval/bin/python}
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$BASE/scripts${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
source "${TASK1_JUDGE_ENV:-$HOME/.dashscope_env}"
export JUDGE_MODEL=qwen3.8-max FROZEN_RUN_DIR="$RUN"
if [[ ${1:-} == --preflight ]]; then
 export TASK1_RUN_DIR="$RUN/preflight" FROZEN_JUDGE_ROOT="$RUN/preflight" FROZEN_JUDGE_STAGE=preflight
 exec "$AEVAL" "$BASE/scripts/evaluate_stage.py" --stage step2 --preflight
fi
export TASK1_RUN_DIR="$RUN" FROZEN_JUDGE_ROOT="$RUN"
for STAGE in baseline step0 step1 step2 bon15; do
 export FROZEN_JUDGE_STAGE="$STAGE"
 "$AEVAL" "$BASE/scripts/evaluate_stage.py" --stage "$STAGE"
done
