# Historical comparison

| Run | Stage | WR (%) | LC (%) |
|---|---|---|---|
| original | baseline | 9.1430 | 16.2906 |
| original | step0 | 11.2248 | 21.6696 |
| original | step1 | 10.0930 | 16.0231 |
| original | step2 | 8.2717 | 10.5139 |
| original | bon15 | 14.0158 | 24.5279 |
| rerun | baseline | 7.6425 | 13.4600 |
| rerun | step0 | 10.5835 | 19.6729 |
| rerun | step1 | 9.2503 | 15.2756 |
| rerun | step2 | 10.5565 | 14.9043 |
| rerun | bon15 | 12.6688 | 21.7793 |
| task1_frozen_v1 | baseline | 8.7683 | 18.7986 |
| task1_frozen_v1 | step0 | 12.6882 | 21.5070 |
| task1_frozen_v1 | step1 | 12.0856 | 16.8352 |
| task1_frozen_v1 | step2 | 14.1336 | 17.5680 |
| task1_frozen_v1 | bon15 | 13.9743 | 24.9654 |

Historical runs have unseeded critique/gradient calls. Differences include regeneration, revised seed/execution rules and fresh judging. These are not interchangeable seeds from one frozen protocol; no causal attribution or best-run selection.

Per-prompt paired WR differences and intervals for each new stage versus each history are saved in `historical_comparison.json`.
