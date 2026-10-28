#!/usr/bin/env bash
# Judge all five stages with the fixed Qwen weighted judge in the aeval environment.
set -euo pipefail
TASK_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
cd "$TASK_DIR"
if [[ -n ${TASK1_JUDGE_ENV:-} ]]; then
  source "$TASK1_JUDGE_ENV"
elif [[ -z ${DASHSCOPE_API_KEY:-} && -f "$HOME/.dashscope_env" ]]; then
  source "$HOME/.dashscope_env"
fi
: "${DASHSCOPE_API_KEY:?Missing judge credential}"
: "${DASHSCOPE_BASE_URL:?Missing judge endpoint}"
export JUDGE_MODEL=${JUDGE_MODEL:-qwen3.8-max}
[[ "$JUDGE_MODEL" == qwen3.8-max ]] || { echo 'JUDGE_MODEL must be qwen3.8-max'; exit 1; }
RUN_DIR=${TASK1_RUN_DIR:-"$TASK_DIR"}
STAGES_DIR=${1:-"$RUN_DIR/stages"}
REF=${2:-"$RUN_DIR/data/reference100.json"}
python "$TASK_DIR/build_judge_config.py"
for s in baseline step0 step1 step2 bon15; do
  echo "Judging $s"
  python "$TASK_DIR/evaluate_stage.py" --stage "$s" \
    --stages-dir "$STAGES_DIR" --reference "$REF"
done
python "$TASK_DIR/summarize.py"
