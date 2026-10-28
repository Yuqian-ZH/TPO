# Frozen Task 1 experiment results

One formal TPO run and one Best-of-15 control; 100 identical AlpacaEval-2 prompts and references. No score-driven rerun.

## Primary stages

> The judge is Qwen (`qwen3.8-max`), not the official AlpacaEval GPT-4 Turbo judge. Absolute win rates are therefore not comparable to the AlpacaEval leaderboard or the TPO paper; they measure relative change across stages of this run only.

| Stage | WR (%) | LC (%) | WR SE (pp) | LC conditional SE (pp) | Selected RM | Avg chars | Judged |
|---|---|---|---|---|---|---|---|
| baseline | 8.7683 | 18.7986 | 2.6037 | 1.6854 | -4.1430 | 677.5000 | 100 |
| step1 | 12.0856 | 16.8352 | 3.1411 | 1.4109 | -1.3442 | 1343.1600 | 100 |
| step2 | 14.1336 | 17.5680 | 3.3539 | 1.3425 | -0.7062 | 1629.1600 | 100 |

WR point estimates are monotonic (8.7683 → 12.0856 → 14.1336%); LC is not (18.7986 → 16.8352 → 17.5680%). Both adjacent WR changes exceed one paired standard error, but the step1−baseline 95% interval includes zero. Step2−baseline is +5.3653 pp [0.7432, 10.6143]; step2−step1 is +2.0481 pp [0.0483, 4.6741]. These are paired percentile intervals conditional on this saved run and judge outputs, not repeat-run guarantees. Five comparisons were prespecified; intervals are per-comparison and not adjusted for multiple comparisons.

## Controls

| Stage | WR (%) | LC (%) | WR SE (pp) | LC conditional SE (pp) | Selected RM | Avg chars | Judged |
|---|---|---|---|---|---|---|---|
| step0 | 12.6882 | 21.5070 | 3.0979 | 1.6644 | -2.3954 | 1023.9000 | 100 |
| bon15 | 13.9743 | 24.9654 | 3.1260 | 1.7714 | -1.5872 | 1090.7400 | 100 |

Step2−step0 WR is +1.4455 pp [−1.3956, 4.8883]; step2−Best-of-15 is +0.1594 pp [−5.5083, 5.9471]. Both control intervals include zero. This run therefore does not demonstrate that textual-feedback optimization improves WR over compute-matched response sampling. Best-of-15 matches 15 requested answer candidates, excluding TPO critique/gradient compute. Selected RM increases by construction and is not independent quality evidence.

## Paired WR differences

| Comparison | Δ (pp) | Paired SE | Absolute Δ exceeds SE | 95% paired CI |
|---|---|---|---|---|
| step1 - baseline | 3.3172 | 2.2176 | True | [-0.7810, 7.8465] |
| step2 - step1 | 2.0481 | 1.1983 | True | [0.0483, 4.6741] |
| step2 - baseline | 5.3653 | 2.5353 | True | [0.7432, 10.6143] |
| step2 - step0 | 1.4455 | 1.6240 | False | [-1.3956, 4.8883] |
| step2 - bon15 | 0.1594 | 2.9184 | False | [-5.5083, 5.9471] |

10,000 paired prompt bootstrap resamples; seed 42. Exceeding one SE is not a 95% significance test. The same prompt indices are drawn jointly across stages. These differences compare soft scores against the same GPT-4 Turbo reference, not direct head-to-head stage judgments.

## LC differences (descriptive)

| Comparison | Δ (pp) | Paired SE | Absolute Δ exceeds SE | 95% paired CI |
|---|---|---|---|---|
| step1 - baseline | -1.9634 | 0.2756 | True | [-2.5315, -1.4398] |
| step2 - step1 | 0.7328 | 0.0758 | True | [0.5735, 0.8735] |
| step2 - baseline | -1.2306 | 0.3459 | True | [-1.9459, -0.5777] |
| step2 - step0 | -3.9391 | 0.3250 | True | [-4.6071, -3.3190] |
| step2 - bon15 | -7.3974 | 0.4415 | True | [-8.2815, -6.5442] |

LC uses GPT-4 calibration unvalidated for Qwen. Its SEs and intervals condition on already fitted GLMs and omit fitting uncertainty; do not use LC alone to claim a significant benefit.

## Robustness


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


The complete-case subset contains 46 prompts and remains selective; rising subset RM does not eliminate survivorship bias. Both candidate-weighted and equal-prompt RM means are reported below. Improved-prompt percentages count every positive soft-score change, including tiny differences.

## Process diagnostics


| Iteration | Stored unique | Prompts with candidates | Candidate weighted mean RM | Equal prompt mean RM |
|---|---|---|---|---|
| init | 495 | 100 | -4.2334 | -4.2193 |
| iter1 | 406 | 100 | -2.0048 | -2.2530 |
| iter2 | 407 | 100 | -1.5347 | -1.7832 |

| Stage | Iteration | Requests | Returned | Parsed | Missing tags | Duplicate merges | Empty | Raw finish=length | Raw metadata flags |
|---|---|---|---|---|---|---|---|---|---|
| initial | -1 | 100 | 500 | 500 | 0 | 5 | 0 | 3 | 0 |
| critique | 0 | 100 | 100 | None | 0 | None | 0 | 0 | 100 |
| critique | 1 | 100 | 100 | None | 0 | None | 0 | 0 | 100 |
| gradient | 0 | 100 | 100 | None | 0 | None | 0 | 0 | 85 |
| gradient | 1 | 100 | 100 | None | 0 | None | 0 | 0 | 88 |
| refinement | 0 | 100 | 500 | 497 | 3 | 91 | 0 | 6 | 6 |
| refinement | 1 | 100 | 500 | 498 | 2 | 91 | 0 | 6 | 22 |
| bon15 | -1 | 100 | 1500 | 1500 | 0 | 39 | 0 | 11 | 0 |

| Stage | Selected with response provenance | Selected raw finish=length | Selected metadata flags |
|---|---|---|---|
| baseline | 100 | 0 | 0 |
| step0 | 100 | 1 | 0 |
| step1 | 100 | 1 | 2 |
| step2 | 100 | 1 | 3 |
| bon15 | 100 | 0 | 0 |

Raw finish_reason=length is a length cap flag and does not prove semantically incomplete text.

Metadata phrase counts are screening heuristics, not proven failures.

Candidate duplicate merging uses the official within-iteration cache key; identical text in different rounds remains separate.

Generation phase wall time excludes RM loading; policy request sums overlap across workers; RM sums include queue wait.


## Timing and usage

TPO wall time: 322.7723 s; Best-of-15: 78.2679 s; RM load: 4.5102 s. Independent judging: 419 fresh successful requests, 437,293 total tokens; 0 failed attempts. Preflight requests are separate. All 500 final annotations are saved; cache reuse and identical-reference auto-ties need no additional request.

Policy request elapsed-time sum: 2960.7125 s; RM call sum including queue: 82.7989 s; judge request sum: 794.9994 s; judge first-request-to-last-response span: 211.7842 s.

Generation phases include policy and RM interaction but exclude RM model load and prior policy-server startup. Policy/judge request sums overlap across workers. RM call sum includes queue waits; isolated GPU forward time cannot be recovered.

## Judge and protocol

Judge: `qwen3.8-max`, weighted_qwen3_8_max, exact weighted GPT-4-Turbo prompt and soft logprob parser; temperature 1, max_tokens 1, logprobs=true, top_logprobs=5, enable_thinking=false, output-order seed 0. All saved responses expose no reasoning content or positive reported reasoning-token count. Missing reasoning-token metadata is not an explicit reported zero. Returned model identifier remains the alias; an immutable dated backend snapshot is not exposed. Formal cache is independent of both historical runs and the technical preflight.

Policy/critique/gradient: pinned `allenai/Llama-3.1-Tulu-3-8B-SFT`; RM: pinned `sfairXC/FsfairX-LLaMA3-RM-v0.1`. Official algorithms, optimizer variable/context construction, prompts and cache/selection rules remain unchanged in the copied source. Candidate settings .7/.95/2048; critique/gradient .7/.99/8192; explicit SHA-256-derived seed for every policy request; D=2/N=5; persistent eight-worker pool; context 16384. Ties retain the first maximum in official cache insertion order.

See `protocol.json`, `freeze.json`, `run_config.json`, environment inventories, source/data hashes and raw request/response journals. `DEVIATIONS.md` records every compatibility/path/retry/seed change. Output publication stages the unchanged exporter to preserve the reference file’s exact bytes. Human-readable paired-table headers are rendered from saved numerical JSON; no metric changes.

## Historical comparison


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


## Paper comparison


The published ICML 2025 paper, Table 1, evaluates a 70B SFT policy with FsfairX reward model and D2-N5: WR 16.8 → 40.5%, LC 27.8 → 33.0%. These are background, not directly comparable targets for this 8B-policy, 100-prompt, Qwen-judged run. The table’s FsfairX 8B model is the reward model, not an 8B policy. There is no directly corresponding 8B-policy AlpacaEval WR table.

Section 7.4 and Figure 7 discuss an 8B-Instruct policy on HH-RLHF and instruction following; this is another dataset and a different policy. A nonmonotonic result here does not demonstrate that the paper or code is wrong, and a monotonic point estimate would not alone establish comprehensive reproduction. RM/judge divergence is not proof of reward hacking or a specific causal explanation.

Verified against the preserved published PDF/text (`tpo_icml2025.pdf`, Table 1 and §7.4). Publication: [Li et al., Test-Time Preference Optimization, ICML 2025](https://proceedings.mlr.press/v267/li25ac.html).


## Acceptance and limits

Five stages each have 100 unique, aligned, nonempty answers and finite saved preferences; selection provenance was checked against raw candidate caches and response journals. 800 formal policy requests are seeded, with no retries; 400 RM calls are saved. GPU 2/3 were released after verifying process ownership. No other users’ processes were touched.

Saved-only recomputation passed with network sockets disabled: all four numerical JSON files were byte-identical and generation/RM/judge journals were unchanged. Weighted judge parsing and seeded answer orientation were independently checked. Final preservation/credential evidence is in `FINAL_AUDIT.json`; an exhaustive new-file/hash list is in `../../DELIVERY_MANIFEST.json`.

No clean-machine installation test or bitwise reproducibility guarantee is claimed. Confidence intervals omit repeat-run/model/judge-backend variation. The Qwen judge and smaller policy prevent absolute comparison with the official leaderboard/paper. No extra seed experiment, Git commit or push was performed.
