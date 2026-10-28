# Five-stage Qwen-judged results

> The judge is Qwen (`qwen3.8-max`), not the official AlpacaEval GPT-4 Turbo judge. Absolute win rates are therefore not comparable to the AlpacaEval leaderboard or the TPO paper; they measure relative change across stages of this run only.

| Stage    |   LC (%) |   WR (%) |   WR SE (pp) |   LC SE (pp) |      RM |   Avg length (chars) |   Judged |   Judge requests |   Judge tokens |
|:---------|---------:|---------:|-------------:|-------------:|--------:|---------------------:|---------:|-----------------:|---------------:|
| baseline |  13.4600 |   7.6425 |       2.4227 |       1.2373 | -3.9896 |                  782 |      100 |               99 |          99818 |
| step0    |  19.6729 |  10.5835 |       2.7445 |       1.6718 | -2.3364 |                  975 |      100 |               72 |          75830 |
| step1    |  15.2756 |   9.2503 |       2.6152 |       1.3771 | -1.3038 |                 1278 |      100 |               70 |          73566 |
| step2    |  14.9043 |  10.5565 |       2.8122 |       1.3212 | -0.7642 |                 1489 |      100 |               62 |          70842 |
| bon15    |  21.7793 |  12.6688 |       3.1246 |       1.5693 | -1.6378 |                 1076 |      100 |              100 |         103227 |

Monotonic baseline → step1 → step2: WR **True**, LC **False**.

| Comparison | WR Δ (pp) | Paired SE | Δ exceeds SE | LC Δ (pp) | Paired SE | Δ exceeds SE |
|---|---:|---:|---|---:|---:|---|
| step1 - baseline | 1.6078 | 1.8380 | False | 1.8157 | 0.1420 | True |
| step2 - step1 | 1.3063 | 1.1806 | True | -0.3714 | 0.0560 | True |
| step2 - step0 | -0.0269 | 1.7966 | False | -4.7687 | 0.3579 | True |
| step2 - bon15 | -2.1123 | 2.7385 | False | -6.8750 | 0.2793 | True |

SEs of differences use paired per-instruction scores. LC SEs condition on the fitted GLM; they do not include refitting uncertainty. Exceeding one SE is not a 95% significance test.

Lengths are characters, as reported by AlpacaEval. Token totals count successful API requests; cached judgments are reused across stages. No price estimate is inferred for this endpoint.

Fresh full-run requests: 403; tokens: 423283. Smoke requests: 0; tokens: 0. Full usage: results_task1.json.
