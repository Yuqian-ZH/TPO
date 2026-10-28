#!/usr/bin/env bash
set -euo pipefail
RUN_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
export CUDA_VISIBLE_DEVICES=${TASK1_RM_GPU:-3}
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export TASK1_RUN_DIR="$RUN_ROOT" TASK1_TPO_DIR="$RUN_ROOT/source/TPO"
cd "$RUN_ROOT"
"${TPO_PYTHON:-/dataMeR2/Yuqian/miniconda3/envs/tpo/bin/python}" -B "$RUN_ROOT/scripts/run_llama.py" "$@"
