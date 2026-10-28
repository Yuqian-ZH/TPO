# Task 1 — completed GPU experiment and Qwen evaluation

TPO improves the stored RM scores but does **not** monotonically improve Qwen-judged WR or LC. Step2 has lower point estimates than Best-of-5 and Best-of-15. Paired 95% WR intervals for both control comparisons include zero, so this run does not establish an independent judge-measured gain.

## Experiment and completed checks

- Policy: `allenai/Llama-3.1-Tulu-3-8B-SFT` via vLLM on H100 GPU 2, port 8002. RM: `sfairXC/FsfairX-LLaMA3-RM-v0.1` on H100 GPU 3. Both generation runs completed; the confirmed user-owned policy server was stopped after Best-of-15. Phase 1 verified no `yuqian` processes remained on GPUs 2 and 3.
- Same 100-prompt AlpacaEval-2 slice and GPT-4 Turbo references for every stage. Slice seed 42; exact original indices in `data/slice_ids.json`. TPO D=2, N=5; sampling temperature 0.7, top_p 0.95, seed 7.
- Candidate response cap 2048; critique/gradient output cap 8192; vLLM context 16384; 8 worker threads; bfloat16. TPO runtime 347.9887 seconds; Best-of-15 runtime 96.5834 seconds.
- Best-of-15 acceptance: 100 nonempty matching outputs; mean selected RM -1.6083; 14 prompts have fewer than 15 stored answers due to duplicate merging. It matches the response-candidate budget, not full FLOPs, because TPO also generates critiques/gradients.
- Phase 2: HTTP 200; populated top logprobs; no reasoning content. Reasoning-token detail is absent (not an explicitly reported zero). Every judge request sends `enable_thinking=false` and is validated for reasoning content and any exposed reasoning-token count. The response model is the alias `qwen3.8-max`; no dated snapshot was exposed.
- Phase 3: five-example parsing smoke passed; baseline, step0, step1, step2, and bon15 each have 100 valid annotations and saved LC fits. Phase 4 uses only stored scores and annotations on CPU.
- TPO/optimizer source hashes match their pre-finish values. No TPO generation was rerun during Phases 2–6. Full configuration: `run_config.json`; deviations and limits: `DEVIATIONS.md`.

## Five-stage results

> The judge is Qwen (`qwen3.8-max`), not the official AlpacaEval GPT-4 Turbo judge. Absolute win rates are therefore not comparable to the AlpacaEval leaderboard or the TPO paper; they measure relative change across stages of this run only.

| Stage    |   LC (%) |   WR (%) |   WR SE (pp) |   LC SE (pp) |      RM |   Avg length (chars) |   Judged |   Judge requests |   Judge tokens |
|:---------|---------:|---------:|-------------:|-------------:|--------:|---------------------:|---------:|-----------------:|---------------:|
| baseline |  16.2906 |   9.1430 |       2.6056 |       1.2843 | -3.9737 |                  828 |      100 |               99 |         100698 |
| step0    |  21.6696 |  11.2248 |       2.8357 |       1.5495 | -2.3567 |                  927 |      100 |               70 |          72139 |
| step1    |  16.0231 |  10.0930 |       2.7527 |       1.4065 | -1.3607 |                 1240 |      100 |               73 |          77981 |
| step2    |  10.5139 |   8.2717 |       2.5987 |       0.9915 | -0.8038 |                 1511 |      100 |               56 |          64487 |
| bon15    |  24.5279 |  14.0158 |       3.3534 |       1.6750 | -1.6083 |                 1086 |      100 |              100 |         103316 |

Monotonic baseline → step1 → step2: WR **False**, LC **False**.

| Comparison | WR Δ (pp) | Paired SE | Δ exceeds SE | LC Δ (pp) | Paired SE | Δ exceeds SE |
|---|---:|---:|---|---:|---:|---|
| step1 - baseline | 0.9500 | 2.5621 | False | -0.2676 | 0.1269 | True |
| step2 - step1 | -1.8213 | 1.6433 | True | -5.5092 | 0.4209 | True |
| step2 - step0 | -2.9531 | 2.0581 | True | -11.1558 | 0.5829 | True |
| step2 - bon15 | -5.7442 | 3.0165 | True | -14.0141 | 0.7152 | True |

SEs of differences use paired per-instruction scores. LC SEs condition on the fitted GLM; they do not include refitting uncertainty. Exceeding one SE is not a 95% significance test.

Lengths are characters, as reported by AlpacaEval. Token totals count successful API requests; cached judgments are reused across stages. No price estimate is inferred for this endpoint.

Fresh full-run requests: 398; tokens: 418621. Smoke requests: 5; tokens: 4077. Full usage: results_task1.json.

Baseline is the first plain SFT sample. Step0 is Best-of-5. Step1 and step2 choose the best cached answer after each refinement. Selected RM scores are nondecreasing by construction and are not independent evidence of improved response quality. Both WR and LC monotonicity verdicts are **false**.

The observed WR sequence is non-monotonic. Paired bootstrap 95% intervals for baseline→step1 and step1→step2 include zero, so these data do not establish a population-level decline. LC values and their conditional SEs are descriptive: GLM-refitting uncertainty is omitted. See `METHODOLOGY_REVIEW.md` and `methodology_checks.json` for the additional comparisons.

## Robustness

| Subset                          |   Prompts |    init |   iter1 |   iter2 |
|:--------------------------------|----------:|--------:|--------:|--------:|
| All prompts                     |       100 | -4.3244 | -2.1534 | -1.6642 |
| All 5 stored in every iteration |        51 | -4.5178 | -1.9307 | -1.4369 |

| Metric        | Comparison    |   Mean Δ |   Improved prompts (%) | 95% paired CI      |
|:--------------|:--------------|---------:|-----------------------:|:-------------------|
| RM            | step2 - step0 |   1.5529 |                89.0000 | [1.2954, 1.8204]   |
| RM            | step2 - bon15 |   0.8046 |                66.0000 | [0.4859, 1.1383]   |
| Judge WR (pp) | step2 - step0 |  -2.9531 |                55.0000 | [-7.1571, 1.0288]  |
| Judge WR (pp) | step2 - bon15 |  -5.7442 |                52.0000 | [-11.9185, 0.0072] |

Paired bootstrap: 10,000 resamples, fixed seed 42.

Paired differences in weighted preferences against the same GPT-4 reference. These are changes in reference-relative win scores, not direct step2-versus-control head-to-head win rates.

Step2 is byte-for-byte identical to step0 for **11/100** prompts.

| Iteration   |   Requested |   Stored |   Combined deficit | Missing tags     | Duplicate merges   |
|:------------|------------:|---------:|-------------------:|:-----------------|:-------------------|
| init        |         500 |      492 |                  8 | 0                | 8                  |
| iter1       |         500 |      419 |                 81 | Not identifiable | Not identifiable   |
| iter2       |         500 |      414 |                 86 | Not identifiable | Not identifiable   |

Initial samples bypass response-tag extraction, so the initial deficit is entirely duplicate merging. For refinements the only identifiable total is 500 minus stored unique answers. The official multi-sample optimizer discards malformed tags and then cache_scores merges identical answers, but neither the raw five outputs nor extraction counts are logged. The two components cannot be separated retrospectively; bounds and the exact combined deficit are reported instead.

Trace evidence: 200 optimizer update prompts were logged, but zero raw optimizer responses. No extra generations were run to fill in missing historical evidence.

The complete-case subset has rising mean rewards too, so the RM trend persists after restricting to prompts with five stored candidates in every round. This does not make the subset representative or turn RM improvement into judge improvement. Improved-prompt percentages count any positive soft-score change, including very small changes; they can differ from the sign of the mean effect.

## Reproducibility

`setup_env.sh` creates separate `tpo` and `aeval` environments, installs official requirements and the two required environment repairs, pins pyairports to its exact source commit, builds the environment-backed judge config, and provides the vLLM serve command. It was syntax checked; a clean-machine installation was not executed on this host. It does not rerun either completed experiment.

The delivery is now in `TPO/task1`. All scripts resolve the checkout and artifacts from their own location; `TASK1_TPO_DIR` and `TASK1_RUN_DIR` override those locations. The launcher writes new generations under `reruns/` by default, allows online weight downloads, and accepts configurable Python, GPU, host, and port settings. `report_local.py` writes `rm_report.md`; it cannot replace this final report. Robustness uses the preserved trace inside the experiment snapshot. The judge YAML uses relative paths, and evaluation uses the saved, hash-verified LC calibration. See `README.md` for the final workflow and `DELIVERY_STATUS.md` for packaging validation.

The exact weighted GPT-4-Turbo prompt bytes and soft logprob parser are retained with the judge model changed to Qwen. Judge temperature is the original **1**, with max_tokens=1; the distinct Phase 2 connection check used temperature=0/max_tokens=5. Identical pairs share the seeded annotation cache. The standard LC estimator receives original benchmark indices rather than slice row positions; its GPT-4-derived calibration is retained, so these LC values also inherit that calibration limitation.

Package locks, source patch, prompt hashes, LC calibration, usage, and an exhaustive file list are available through `FILES_FINISH.md`. Credentials remain in the external mode-600 environment file; no credential value is embedded in project files.

## Comparison with the paper

The [published ICML paper](https://proceedings.mlr.press/v267/li25ac.html) does not report an 8B-policy AlpacaEval win-rate table. Table 1 reports 70B-SFT LC 27.8% / WR 16.8%, rising to LC 33.0% / WR 40.5% with FsfairX and D2-N5. These are context, not directly comparable targets for this 8B, 100-prompt run. Section 7.4 and Figure 7 show declining reward for 8B-Instruct on HH-RLHF, attributed to instruction-following limitations. Improvement on this setup must therefore be measured rather than assumed.

The use of a different judge, a smaller policy, and a 100-prompt slice prevents direct comparison of this run’s absolute WR/LC with the published 70B numbers. The observed RM/judge divergence supports reporting the failure to demonstrate the requested monotonic improvement, rather than assuming it.

## Final validation

All five stages have 100 aligned, finite annotations. Robustness outputs use 10,000 paired bootstrap resamples with seed 42. Shell scripts pass syntax checks and new Python scripts compile. The secret-scan result is recorded in `secret_scan_result.json` after the final scan.
