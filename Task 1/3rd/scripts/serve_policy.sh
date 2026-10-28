#!/usr/bin/env bash
set -euo pipefail
BASE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
RUN=${FROZEN_RUN_DIR:-"$BASE/$(cat "$BASE/LATEST.txt")"}
POLICY_PYTHON=${TPO_PYTHON:-/dataMeR2/Yuqian/miniconda3/envs/tpo/bin/python}
GPU=${FROZEN_POLICY_GPU:-2}
PORT=${FROZEN_POLICY_PORT:-8002}
export CUDA_VISIBLE_DEVICES="$GPU" PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export XDG_CACHE_HOME="$RUN/cache" HF_HOME="$HOME/.cache/huggingface"
export VLLM_CONFIG_ROOT="$RUN/vllm_config" VLLM_CACHE_ROOT="$RUN/vllm_cache"
cd "$RUN"
exec "$POLICY_PYTHON" -m vllm.entrypoints.openai.api_server \
 --model allenai/Llama-3.1-Tulu-3-8B-SFT --revision f2a0b46b0cfda21003c6141b1ff837b7e165524d \
 --tokenizer-revision f2a0b46b0cfda21003c6141b1ff837b7e165524d \
 --dtype bfloat16 --api-key token-abc123 --port "$PORT" --host 127.0.0.1 \
 --max-model-len 16384 --seed 7 --gpu-memory-utilization 0.9 \
 --max-num-seqs 256 --max-num-batched-tokens 16384
