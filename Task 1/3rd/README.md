# Task 1 frozen experiment

Protocol: `task1_frozen_v1`. Historical `TPO/` and `TPO_Test/` are read-only inputs. Results, five stages, raw journals, paired robustness, diagnostics, historical comparisons and integrity evidence are contained in this directory.

Policy/critique/gradient: `allenai/Llama-3.1-Tulu-3-8B-SFT`; RM: `sfairXC/FsfairX-LLaMA3-RM-v0.1`; independent judge only: `qwen3.8-max`. Fixed 100 prompts, D=2/N=5, one formal TPO and one BoN15 control. Seeds, revisions, request settings, stop/retry rules and bootstrap comparisons are frozen in `protocol.json` and `freeze.json`.

Read `results_task1.md`, `robustness.md`, `diagnostics.md`, `HISTORICAL_COMPARISON.md`, and the full `run_report.md`. Machine-readable counterparts and `FINAL_AUDIT.json` support every table. WR is primary; LC is descriptive because GPT-4 calibration is unvalidated for Qwen. Do not infer independent quality gains from nondecreasing selected RM. Paper comparisons are background, not a directly comparable 8B AlpacaEval target.

The code is in `scripts/`; its SHA-256 hashes are frozen in `freeze.json`. On the GPU server this folder was `/home/yuqian/TPO_fixed`, and the commands ran from there:

```bash
# Analyze saved results only; no model/judge/network clients are imported.
PYTHONDONTWRITEBYTECODE=1 /dataMeR2/Yuqian/miniconda3/envs/aeval/bin/python scripts/analyze.py
# Verify weighted preference parsing/order on saved annotations only.
PYTHONDONTWRITEBYTECODE=1 /dataMeR2/Yuqian/miniconda3/envs/aeval/bin/python scripts/check_methodology.py
# Audit preservation, frozen hashes and credentials without showing secret values.
source ~/.dashscope_env
PYTHONDONTWRITEBYTECODE=1 /dataMeR2/Yuqian/miniconda3/envs/aeval/bin/python scripts/final_audit.py
```

Actual generation workflow, already executed once for this run:

```bash
# Check current GPU occupancy first. This run used GPUs 2 (policy) and 3 (RM).
bash scripts/serve_policy.sh
# Separate terminal: fixed first-three-prompt technical preflight.
bash scripts/run_generation.sh --preflight
python scripts/export_stages.py --preflight
# Preflight also requires replay verification and the Qwen parsing check.
bash scripts/evaluate.sh --preflight
python scripts/freeze.py
# After freeze only, one main TPO and BoN15 execution:
bash scripts/run_generation.sh
bash scripts/export_saved.sh
bash scripts/evaluate.sh
```

Use `FROZEN_RUN_DIR`, `TPO_PYTHON`, `AEVAL_PYTHON`, `FROZEN_POLICY_GPU`, `FROZEN_RM_GPU`, and `FROZEN_POLICY_PORT` to configure paths/deployment. Historical model snapshots were already cached and used offline. To prepare another machine, inspect `scripts/setup_env.sh --install` and `--prepare-models`; model repository access, conda and compatible NVIDIA drivers are prerequisites. Package inventories, constraints and locks are saved. A clean-machine installation has not been tested. Credentials load only from external mode-600 `~/.dashscope_env` (or `TASK1_JUDGE_ENV`) and are never copied here.

Generation keeps one persistent eight-worker pool. Each successful logical request is saved under `request_cache/`; RM scoring under `rm_cache/`; per-prompt completion under `checkpoints/`. Transport retries are limited to three attempts, waiting 2 and 8 seconds, with unchanged parameters. Replay verifies hashes and never resamples a completed request. Preflight and formal caches are separate. Evaluation uses a fresh full-request/configuration cache in `judge_cache/`, shared only within this run. Saved-only analysis cannot trigger API calls.

`DEVIATIONS.md` records seed control, retry/checkpoint wrappers, compatibility repairs, Qwen/LC limits and preflight path repair. `source_changes.patch` preserves historical compatibility changes; copied official algorithm/prompt/optimizer files are hash protected. No Git commit or push was performed.

Primary/auxiliary tables, paired intervals, exact token usage and interpretation: [EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md). [FINAL_AUDIT.json](FINAL_AUDIT.json) records preservation and credential checks.

The endpoint URL in `evaluation.log` and `preflight/judge.log` is replaced by `<DASHSCOPE_BASE_URL>`; the vLLM usage-statistics file (`vllm_config/`) and run-time pid and lock files are left out.

`LATEST.txt` contains `.` so that `scripts/` finds this folder as the run directory (on the server it named the run directory). Checked on a laptop CPU: `PYTHONDONTWRITEBYTECODE=1 python scripts/analyze.py`, run from this folder with numpy installed, prints `OFFLINE_ANALYSIS_PASS` and reproduces every JSON output byte for byte. `results_task1.md` and `run_report.md` come out with the same numbers but plainer formatting, because they were re-rendered afterwards by `publish_reports.py` (see `presentation_provenance.json`; that renderer stayed on the server).
