#!/usr/bin/env bash
# Uses the existing policy server on GPU 2; runs the reward model on GPU 3.
set -euo pipefail
TASK_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
TPO_DIR="$TASK_DIR/../TPO"
PYTHON=/dataMeR2/Yuqian/miniconda3/envs/tpo/bin/python
export CUDA_VISIBLE_DEVICES=3
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1
export OPENAI_API_KEY=${OPENAI_API_KEY:-dummy}
exec 9>"$TASK_DIR/run_task1.lock"
flock -n 9 || { echo 'Task 1 is already running.'; exit 1; }
echo $$ > "$TASK_DIR/run_task1.pid"
trap 'code=$?; echo "$code" > "$TASK_DIR/run_task1.exitcode"' EXIT
cd "$TPO_DIR"
"$PYTHON" run.py \
  --data_path "$TASK_DIR/data/alpaca100.json" --output_path "$TASK_DIR/run100" \
  --ip 127.0.0.1 --port 8002 \
  --server_model allenai/Llama-3.1-Tulu-3-8B-SFT \
  --reward_model sfairXC/FsfairX-LLaMA3-RM-v0.1 \
  --tpo_mode tpo --sample_size 5 --max_iterations 2 \
  --max_tokens_response 2048 --max_tokens_all 8192 --seed 7 --num_threads 8
"$PYTHON" "$TASK_DIR/extract_stages.py" \
  --tpo_output "$TASK_DIR/run100/alpaca100.json_model_Llama-3.1-Tulu-3-8B-SFT_mode_tpo_rm_FsfairX-LLaMA3-RM-v0.1_max_iters2_sample_size5_seed7.json" \
  --meta "$TASK_DIR/data/alpaca100_meta.json" --out_dir "$TASK_DIR/stages"
"$PYTHON" "$TASK_DIR/report_local.py"
