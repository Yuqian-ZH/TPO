#!/usr/bin/env bash
set -euo pipefail
BASE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
RUN=${FROZEN_RUN_DIR:-"$BASE/$(cat "$BASE/LATEST.txt")"}
export FROZEN_RUN_DIR="$RUN" CUDA_VISIBLE_DEVICES=${FROZEN_RM_GPU:-3}
export HF_HUB_OFFLINE=${FROZEN_OFFLINE:-1} TRANSFORMERS_OFFLINE=${FROZEN_OFFLINE:-1}
export PYTHONDONTWRITEBYTECODE=1 LITELLM_LOCAL_MODEL_COST_MAP=True
cd "$RUN"
"${TPO_PYTHON:-/dataMeR2/Yuqian/miniconda3/envs/tpo/bin/python}" "$BASE/scripts/guard_data.py"
exec "${TPO_PYTHON:-/dataMeR2/Yuqian/miniconda3/envs/tpo/bin/python}" "$BASE/scripts/generate.py" "$@"
