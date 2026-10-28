# Task 1: TPO on 100 AlpacaEval-2 prompts

The generation, independent evaluation, robustness analysis, and output diagnostics are complete. **Monotonic independent win-rate improvement was not reproduced.** Selected FsfairX reward increases by construction; Qwen WR/LC do not. This is an adapted replication using Qwen instead of the official GPT-4 judge.

| Stage | WR (%) | WR SE (pp) | LC (%) | Selected RM |
|---|---:|---:|---:|---:|
| baseline | 9.14 | 2.61 | 16.29 | -3.9737 |
| step0 / Best-of-5 | 11.22 | 2.84 | 21.67 | -2.3567 |
| step1 | 10.09 | 2.75 | 16.02 | -1.3607 |
| step2 | 8.27 | 2.60 | 10.51 | -0.8038 |
| Best-of-15 | 14.02 | 3.35 | 24.53 | -1.6083 |

Every stage has 100 aligned judgments against the same GPT-4 Turbo reference outputs. Baseline is the first initial sample; step0 is the best initial sample; step1/step2 select the highest cached RM score after each refinement. WR is a logprob-weighted soft preference average, not an integer win count. Step2 minus step0 WR is -2.95 pp (paired bootstrap 95% CI [-7.16, 1.03]); step2 minus Best-of-15 is -5.74 pp [-11.92, 0.007]. These intervals include zero. LC is secondary/descriptive: its GPT-4-derived calibration is unvalidated for Qwen and its SE omits GLM-refitting uncertainty.

## Configuration and interpretation

- Source: official TPO commit `395c3d763a4c3df0ae72a4352b0db16fe5ee18e9`, with the preserved local patch in [tpo_existing_changes.patch](tpo_existing_changes.patch).
- Policy: `allenai/Llama-3.1-Tulu-3-8B-SFT`, vLLM 0.6.3, bfloat16, H100 80 GB; RM: `sfairXC/FsfairX-LLaMA3-RM-v0.1`, on a separate H100.
- D=2, N=5; candidate temperature 0.7, top_p 0.95, seed 7; 8 threads; 2048 output tokens. Critique/gradient calls use temperature 0.7, top_p 0.99, unset seed, and an 8192-token cap. Server context: 16384.
- Fixed 100/805 sample, seed 42; exact IDs/data/references are in [data/](data/). Best-of-15 uses 15 initial candidates and the same response sampling/RM. Its candidate budget matches TPO's 5+5+5, but excludes TPO's additional critique/gradient compute.
- Judge: `qwen3.8-max`, evaluated 2026-10-20; weighted AlpacaEval prompt/parser, temperature 1, max_tokens 1, top_logprobs 5, thinking disabled, output-order seed 0. The alias has no exposed dated snapshot.

Candidate mean rewards also rise (-4.3244 → -2.1534 → -1.6642), including when prompts receive equal weight. The RM/Qwen divergence is consistent with proxy mismatch or ineffective rewriting; it does not prove reward hacking. Stored unique counts are 492/419/414 out of 500 requested per round. Missing-tag discards and duplicates cannot be separated retrospectively. Complete-case analysis does not eliminate all survivorship bias.

The paper has no directly comparable 8B-policy AlpacaEval WR table. Table 1's 70B-SFT/FsfairX D2-N5 results are LC 27.8→33.0 and WR 16.8→40.5; these are context, not comparable targets. Its §7.4/Figure 7 describes an 8B-Instruct failure on HH-RLHF. Our judge, model size, and subset differ. See the [published paper](https://proceedings.mlr.press/v267/li25ac.html), [full report](run_report.md), [methodology review](METHODOLOGY_REVIEW.md), and [deviations](DEVIATIONS.md).

## Inspect and verify the saved experiment (CPU only)

Commands below run from the repository root. Reuse the existing environments, or install them as described below. These commands make no model or judge requests:

```bash
unset TASK1_RUN_DIR
conda run --no-capture-output -n aeval python task1/summarize.py
conda run --no-capture-output -n aeval python task1/robustness.py
conda run --no-capture-output -n aeval python task1/check_methodology.py
conda run --no-capture-output -n aeval python task1/finalize_report.py
conda run --no-capture-output -n tpo python task1/audit_task1.py
```

The audit verifies stage/data alignment, selection rules, scores, paired intervals, source/data/archive hashes, file presence, syntax, and credential patterns, including decompressed archive members. Token diagnostics use only an already cached tokenizer and are skipped if unavailable. For an exact-current-key scan, export `DASHSCOPE_API_KEY` from your external credential manager before running `python task1/secret_scan.py`; without it, the regex scan still runs. Git object history is not scanned.

[robustness.md](robustness.md), [methodology_checks.json](methodology_checks.json), and [audit_checks.json](audit_checks.json) contain the evidence. [DELIVERY_STATUS.md](DELIVERY_STATUS.md) records relocation and preservation checks. `conda run -n aeval python task1/verify_delivery.py` repeats the relocation, cached-evaluation, and launcher fixture checks in a temporary checkout without GPU or API calls.

## Install on another Linux GPU machine

Prerequisites: conda, git, a compatible NVIDIA driver, space for both 8B models, access to their Hugging Face repositories, and two suitable GPUs. Authenticate with Hugging Face first if either model requires it. GPU numbers below are configurable; check availability before serving.

```bash
bash task1/setup_env.sh
```

This installs separate `tpo` (Python 3.10, official requirements plus constraints) and `aeval` environments. It includes the TextGrad `setup.py` repair and pyairports source pin. The script uses this checkout by default; `TASK1_TPO_DIR` selects another checkout. It does not overwrite existing inference logic or apply the historical patch automatically. A full fresh-machine installation/GPU regeneration has not been performed during packaging; the historical locked environments and original outputs are the reproducibility record.

## Generate a new run

In one terminal, serve the policy (default policy GPU 2, port 8002):

```bash
TASK1_POLICY_GPU=2 bash task1/setup_env.sh --serve-policy
```

In another terminal, set a new output directory and run TPO plus Best-of-15 (default RM GPU 3):

```bash
export TASK1_RUN_DIR="$PWD/task1/reruns/reproduction-1"
TASK1_RM_GPU=3 conda run --no-capture-output -n tpo bash task1/run_task1.sh
```

The launcher copies the frozen data, writes new traces/results under this directory, extracts all five stage files, and writes the provisional `rm_report.md`. It refuses to use the saved artifact directory as its output. `--output-dir DIR` overrides the run directory, `--mode tpo|bon|all` selects the generation, and `--dry-run` prints commands without generating or changing artifacts. Reusing a separate run directory resumes its outputs.

`TASK1_PYTHON` selects the interpreter; otherwise the activated environment's `python` is used. `TASK1_POLICY_HOST`, `TASK1_POLICY_PORT`, `TASK1_RM_GPU`, and `TASK1_TPO_DIR` configure deployment. Downloads are enabled by default; use `TASK1_OFFLINE=1` only after both models are cached. The policy and client must use the same port. Stop your own policy process when finished; the scripts do not terminate other processes.

## Evaluate new outputs with Qwen (external API requests)

Keep the same exported `TASK1_RUN_DIR`. Export `DASHSCOPE_API_KEY`, `DASHSCOPE_BASE_URL`, and `JUDGE_MODEL=qwen3.8-max` in the shell, or set `TASK1_JUDGE_ENV` to a private mode-600 environment file outside the repository. The optional fallback is `~/.dashscope_env`. Credentials are read at runtime and must not be committed.

```bash
conda run --no-capture-output -n aeval bash task1/run_alpaca_eval.sh
conda run --no-capture-output -n aeval python task1/robustness.py
conda run --no-capture-output -n aeval python task1/check_methodology.py
```

The wrapper builds portable judge configuration for the selected run before evaluation; the saved calibration is hash checked and loaded locally. `TASK1_RUN_DIR` also selects the artifacts for analysis/report scripts. For new traces, robustness picks the largest nonempty run trace; set `TASK1_TRACE_PATH` if you need to select one explicitly. The finalizer is for the historical completed experiment (it retains that experiment's paper section); use the generated `results_task1.md` and `robustness.md` as the report for a new run.

## Artifact layout

`data/`, `run100/`, `bon15/`, `stages/`, `eval_out/`, and `judge_config/` preserve the completed experiment. `run_config.json`, package constraints/locks, source patch/hashes, and original reports record provenance. `experiments/` contains the immutable early snapshot and verified tarball; it predates final judging and is not the complete final delivery by itself. `run_report_before_finish.md`, `run_report_pre_delivery.md`, and the review documents retain earlier stages of the work. Ignore local `.tools`, bytecode, active PID/lock files, and `reruns/` when submitting. Historical PID files inside the snapshot are retained because they are part of its checksum manifest.
