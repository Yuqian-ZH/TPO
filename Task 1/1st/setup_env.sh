#!/usr/bin/env bash
# Reproduce environments on Linux with conda, git, and a compatible NVIDIA driver.
# Run `bash setup_env.sh` to install; `bash setup_env.sh --serve-policy` to serve.
# GPU selection must be checked before starting a new experiment.
set -euo pipefail
TASK_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
TPO_DIR=${TASK1_TPO_DIR:-"$HOME/TPO"}
CONDA=${TASK1_CONDA_BIN:-conda}

if [[ ${1:-} == --serve-policy ]]; then
  export CUDA_VISIBLE_DEVICES=${TASK1_POLICY_GPU:-2}
  exec "$CONDA" run --no-capture-output -n tpo vllm serve \
    allenai/Llama-3.1-Tulu-3-8B-SFT --dtype bfloat16 \
    --api-key token-abc123 --port 8002 --max-model-len 16384
fi

if [[ ! -d "$TPO_DIR/.git" ]]; then
  git clone https://github.com/Simplified-Reasoning/TPO.git "$TPO_DIR"
  git -C "$TPO_DIR" checkout 395c3d763a4c3df0ae72a4352b0db16fe5ee18e9
fi
if ! "$CONDA" run -n tpo python -c 'import sys' >/dev/null 2>&1; then
  "$CONDA" create -n tpo python=3.10 -y
fi
# Install the genuine dependency before resolving outlines to avoid the empty 0.0.1 package.
"$CONDA" run --no-capture-output -n tpo python -m pip install --no-deps \
  'git+https://github.com/NICTA/pyairports.git@9699eae8c6b03c97239018dea92e01daa8594936'
"$CONDA" run --no-capture-output -n tpo python -m pip install \
  -c "$TASK_DIR/tpo_constraints.txt" -r "$TPO_DIR/requirements.txt"
# Environment packaging fix only; do not alter run.py, reward logic, or textgrad internals.
"$CONDA" run -n tpo python -c \
  'from pathlib import Path; import sys; p=Path(sys.argv[1]); s=p.read_text(); p.write_text(s.replace("long_description=readme,", "long_description=\"\","))' \
  "$TPO_DIR/textgrad-main/setup.py"
"$CONDA" run --no-capture-output -n tpo python -m pip install \
  -c "$TASK_DIR/tpo_constraints.txt" -e "$TPO_DIR/textgrad-main"

if ! "$CONDA" run -n aeval python -c 'import sys' >/dev/null 2>&1; then
  "$CONDA" create -n aeval python=3.10 -y
fi
"$CONDA" run --no-capture-output -n aeval python -m pip install \
  -r "$TASK_DIR/aeval_requirements.lock.txt" alpaca-eval tabulate
"$CONDA" run --no-capture-output -n aeval python "$TASK_DIR/build_judge_config.py"
bash -n "$TASK_DIR/run_alpaca_eval.sh"
printf '%s\n' \
  'Environments and the weighted Qwen config are ready.' \
  'Keep ~/.dashscope_env mode 600 with exported DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, JUDGE_MODEL=qwen3.8-max.' \
  'The key is read at runtime by judge_client.py and is never embedded in a config.' \
  'Policy: bash setup_env.sh --serve-policy (check GPU availability first).' \
  'RM/TPO: use run_task1.sh with the tpo environment and GPU 3 after the policy is ready.' \
  'Judge: conda run --no-capture-output -n aeval bash run_alpaca_eval.sh.'
