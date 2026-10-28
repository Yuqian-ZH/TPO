# Robustness

| Subset | Prompts | init | iter1 | iter2 |
|---|---|---|---|---|
| All prompts | 100 | -4.2334 | -2.0048 | -1.5347 |
| 5 unique candidates in every round | 46 | -3.7240 | -1.4893 | -0.7812 |

| Metric | Comparison | Mean Δ | Improved prompts (%) | 95% paired CI |
|---|---|---|---|---|
| RM | step2 - step0 | 1.6892 | 92.0000 | [1.4161, 1.9697] |
| WR_pp | step2 - step0 | 1.4455 | 61.0000 | [-1.3956, 4.8883] |
| RM | step2 - bon15 | 0.8809 | 68.0000 | [0.4848, 1.2772] |
| WR_pp | step2 - bon15 | 0.1594 | 58.0000 | [-5.5083, 5.9471] |

Step2 answer identical to step0: 8/100.

Differences between saved soft preferences against the same reference; not direct head-to-head stage match win rates.

Missing-tag drops are counted directly from raw optimizer responses using the official tag split rule. Duplicate merges equal valid parsed candidates minus new within-iteration unique cache entries; empty parsed text is reported separately and is not resampled.

| Stage | Iteration | Requested choices | Returned | Parsed | Missing tags | Duplicate merges | Empty |
|---|---|---|---|---|---|---|---|
| initial | -1 | 500 | 500 | 500 | 0 | 5 | 0 |
| refinement | 0 | 500 | 500 | 497 | 3 | 91 | 0 |
| refinement | 1 | 500 | 500 | 498 | 2 | 91 | 0 |
