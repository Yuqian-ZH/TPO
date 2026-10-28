#!/usr/bin/env bash
# Judge all five stages with the fixed Qwen weighted judge in the aeval environment.
set -euo pipefail
TASK_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$TASK_DIR"
source "$HOME/.dashscope_env"
: "${DASHSCOPE_API_KEY:?Missing judge credential}"
: "${DASHSCOPE_BASE_URL:?Missing judge endpoint}"
[[ "$JUDGE_MODEL" == qwen3.8-max ]] || { echo 'JUDGE_MODEL must be qwen3.8-max'; exit 1; }
STAGES_DIR=${1:-stages}
REF=${2:-data/reference100.json}
for s in baseline step0 step1 step2 bon15; do
  echo "Judging $s"
  python "$TASK_DIR/evaluate_stage.py" --stage "$s" \
    --stages-dir "$STAGES_DIR" --reference "$REF"
done
python "$TASK_DIR/summarize.py"
