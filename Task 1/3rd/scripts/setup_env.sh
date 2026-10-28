#!/usr/bin/env bash
# Preparation only; this script never generates new experimental answers.
set -euo pipefail
BASE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
RUN=${FROZEN_RUN_DIR:-"$BASE/$(cat "$BASE/LATEST.txt")"}
CONDA=${CONDA_EXE:-conda}
TPO_ENV=${FROZEN_TPO_ENV:-tpo_frozen_reproduce}
AEVAL_ENV=${FROZEN_AEVAL_ENV:-aeval_frozen_reproduce}
case ${1:---help} in
 --install)
 "$CONDA" create -n "$TPO_ENV" python=3.10 -y
 "$CONDA" run -n "$TPO_ENV" pip install -r "$RUN/source/TPO/requirements.txt" -c "$RUN/tpo_constraints.txt"
 # The copied setup.py already contains the documented undefined-readme repair.
 "$CONDA" run -n "$TPO_ENV" pip install -e "$RUN/source/TPO/textgrad-main"
 "$CONDA" run -n "$TPO_ENV" pip install --force-reinstall 'git+https://github.com/NICTA/pyairports.git@9699eae8c6b03c97239018dea92e01daa8594936'
 "$CONDA" create -n "$AEVAL_ENV" python=3.10 -y
 "$CONDA" run -n "$AEVAL_ENV" pip install -r "$RUN/aeval_requirements.lock.txt"
 ;;
 --prepare-models)
 "$CONDA" run -n "$TPO_ENV" python -c 'from huggingface_hub import snapshot_download; snapshot_download("allenai/Llama-3.1-Tulu-3-8B-SFT",revision="f2a0b46b0cfda21003c6141b1ff837b7e165524d"); snapshot_download("sfairXC/FsfairX-LLaMA3-RM-v0.1",revision="94fad49f1b3227aa8b566f415a335adb68ec544c")'
 ;;
 *)
 printf '%s\n' 'Usage: setup_env.sh --install | --prepare-models' 'Requires conda, git, NVIDIA drivers, model access and adequate disk/GPU resources.' 'Authenticate with Hugging Face separately if needed. Judge credentials remain in external mode-600 ~/.dashscope_env.' 'Set TPO_PYTHON and AEVAL_PYTHON to the new environment interpreters for launch scripts.' 'Clean-machine installation has not been tested.'
 ;;
esac
