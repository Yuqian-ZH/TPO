# Frozen Task 1 results

> The judge is Qwen (`qwen3.8-max`), not the official AlpacaEval GPT-4 Turbo judge. Absolute win rates are therefore not comparable to the AlpacaEval leaderboard or the TPO paper; they measure relative change across stages of this run only.

| Stage | WR (%) | LC (%) | WR SE (pp) | Selected RM | Avg chars | Judged |
|---|---|---|---|---|---|---|
| baseline | 8.7683 | 18.7986 | 2.6037 | -4.1430 | 677.5000 | 100 |
| step0 | 12.6882 | 21.5070 | 3.0979 | -2.3954 | 1023.9000 | 100 |
| step1 | 12.0856 | 16.8352 | 3.1411 | -1.3442 | 1343.1600 | 100 |
| step2 | 14.1336 | 17.5680 | 3.3539 | -0.7062 | 1629.1600 | 100 |
| bon15 | 13.9743 | 24.9654 | 3.1260 | -1.5872 | 1090.7400 | 100 |

Unrounded baseline → step1 → step2 monotonicity: WR **True**, LC **False**. RM selection alone cannot establish judge improvement.

Qwen-adapted AlpacaEval uses the historical weighted GPT-4-Turbo prompt and soft logprob parser; temperature 1, max_tokens 1, top_logprobs 5, thinking disabled, output-order seed 0. LC uses GPT-4 calibration unvalidated for Qwen and is descriptive. The judge alias does not expose a dated immutable backend snapshot.

| Comparison | WR Δ (pp) | Paired SE | Absolute Δ > SE | 95% paired CI |
|---|---|---|---|---|
| step1 - baseline | 3.3172 | 2.2176 | True | [-0.7810, 7.8465] |
| step2 - step1 | 2.0481 | 1.1983 | True | [0.0483, 4.6741] |
| step2 - baseline | 5.3653 | 2.5353 | True | [0.7432, 10.6143] |
| step2 - step0 | 1.4455 | 1.6240 | False | [-1.3956, 4.8883] |
| step2 - bon15 | 0.1594 | 2.9184 | False | [-5.5083, 5.9471] |

Intervals use 10,000 paired prompt resamples, seed 42, percentile limits. Exceeding one SE is not a 95% significance test. LC intervals in JSON condition on fitted GLMs and omit fitting uncertainty. No score-driven additional run was performed.
