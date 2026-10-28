# Five-stage Qwen-judged results

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
