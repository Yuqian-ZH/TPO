# TPO replication: Tulu policy, FsfairX reward model, Qwen judge

Completed: 100 prompts, all five stages judged, audit passed, original `TPO/` unchanged (741 file contents verified).

[Experiment results](EXPERIMENT_RESULTS.md) · [Comparison with the current experiment](COMPARISON.md)

New WR baseline → step1 → step2: **7.64 → 9.25 → 10.56%**. Current: **9.14 → 10.09 → 8.27%**. New WR point estimates are monotonic; paired intervals do not establish a reliable improvement over baseline or controls.

The model roles are unchanged from the current experiment:

| Role | Model |
|---|---|
| Policy, critique, textual gradient, refinement | `allenai/Llama-3.1-Tulu-3-8B-SFT` |
| Reward model | `sfairXC/FsfairX-LLaMA3-RM-v0.1` |
| Judge only | `qwen3.8-max`, thinking disabled |

This is a fresh run on the same 100 AlpacaEval-2 prompts and references, with D=2, N=5, candidate temperature .7, top_p .95, seed 7, 2048 response tokens, and 8192 critique/gradient tokens. Policy runs on GPU 2; reward model on GPU 3. The copied original TPO algorithms, reward code, prompts and inference engine remain unchanged. A transport wrapper records raw responses and finish reasons without changing request arguments. The historical experiment is frozen in `llama_reference/`. `TPO/` is content-hash protected.

Use the existing server environments from `/home/yuqian`:

```bash
# Serve the policy in a separate terminal (check GPU 2 is free first).
CUDA_VISIBLE_DEVICES=2 /dataMeR2/Yuqian/miniconda3/envs/tpo/bin/python -m vllm.entrypoints.openai.api_server \
  --model allenai/Llama-3.1-Tulu-3-8B-SFT --dtype bfloat16 \
  --api-key token-abc123 --port 8002 --max-model-len 16384
bash TPO_Test/run_experiment.sh > TPO_Test/generation.log 2>&1
bash TPO_Test/scripts/finish_generation.sh
bash TPO_Test/evaluate.sh > TPO_Test/evaluation.log 2>&1
```

Generation checkpoints each completed prompt and resumes missing prompts. Set `TASK1_RM_GPU`, `TASK1_POLICY_PORT`, `TPO_PYTHON`, or `AEVAL_BIN` if needed. Judge credentials are read from the external `~/.dashscope_env` or `TASK1_JUDGE_ENV`. They are not copied here.

Requested outputs: `EXPERIMENT_RESULTS.md` and `COMPARISON.md`, supported by `comparison.json`, `results_task1.json`, `run_config.json`, `robustness.json`, `audit_results.json`, five stage files and annotations, full candidate caches, and `policy_requests.jsonl`. Reports are generated after measurement.

Comparison limits: a fresh run with the same seed can differ because critique/gradient calls are unseeded and inference batching can vary. Both runs use a Qwen judge in place of official GPT-4; absolute scores are not directly comparable to the paper. The Qwen alias has no exposed dated snapshot. LC uses GPT-4-derived calibration and is descriptive. Paired deltas compare scores against the same references; they are not direct matches between runs.

A stopped run based on an incorrect interpretation of Qwen's role (`discarded_qwen_policy/` on the server) is excluded from all results and comparisons and is not included here.

Not included because they were truncated when copied from the server: `policy_requests.jsonl`, `policy_server.log`, `run100/results.json`, `bon15/results.json`, the TPO logs in `logs/` and `judge_config/annotations_seed0_configs.json`. The judge annotations in `eval_out/*/annotations.json` are intact copies (byte-identical to `../3rd/history/rerun/eval_out/`) and reproduce the leaderboards. `source/TPO/PROJECT_INFO.md`, a private planning note, is left out. The endpoint URL in `evaluation.log` is replaced by `<DASHSCOPE_BASE_URL>`.

Paper: [Test-Time Preference Optimization (ICML 2025)](https://proceedings.mlr.press/v267/li25ac.html).
