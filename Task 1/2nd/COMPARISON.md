# Comparison with the current experiment

**Both runs use the same roles: Tulu-3-8B-SFT policy, FsfairX-LLaMA3 reward model, Qwen judge.** This compares a fresh replication with the saved experiment; it is not a Qwen-policy versus Llama-policy comparison.

New WR baseline → step1 → step2: **7.64 → 9.25 → 10.56%**. Current: **9.14 → 10.09 → 8.27%**.

The baseline → step1 → step2 WR point estimates are monotonic in this rerun (7.64 → 9.25 → 10.56%), whereas the saved experiment was not monotonic. LC is not monotonic. Step2 minus baseline WR is +2.91 [-1.03, +7.19] pp, step2 minus Best-of-5 is -0.03 [-3.61, +3.52] pp, and step2 minus Best-of-15 is -2.11 [-7.67, +3.14] pp. All three intervals contain zero. The rerun therefore shows monotonic point estimates, but does not establish a reliable TPO benefit over the controls. The new final WR is +2.28 [-2.58, +7.12] pp above the saved final WR; that interval also contains zero.

| Stage    |   Current WR % |   New WR % | WR Δ pp [95% CI]     |   Current LC % |   New LC % |   Current RM |   New RM |   Identical outputs /100 |
|:---------|---------------:|-----------:|:---------------------|---------------:|-----------:|-------------:|---------:|-------------------------:|
| baseline |         9.1430 |     7.6425 | -1.50 [-4.11, +0.34] |        16.2906 |    13.4600 |      -3.9737 |  -3.9896 |                       64 |
| step0    |        11.2248 |    10.5835 | -0.64 [-4.02, +2.73] |        21.6696 |    19.6729 |      -2.3567 |  -2.3364 |                       42 |
| step1    |        10.0930 |     9.2503 | -0.84 [-4.89, +3.05] |        16.0231 |    15.2756 |      -1.3607 |  -1.3038 |                        6 |
| step2    |         8.2717 |    10.5565 | +2.28 [-2.58, +7.12] |        10.5139 |    14.9043 |      -0.8038 |  -0.7642 |                        3 |
| bon15    |        14.0158 |    12.6688 | -1.35 [-4.05, +0.58] |        24.5279 |    21.7793 |      -1.6083 |  -1.6378 |                       20 |

Every difference pairs the same instruction and reference. These are changes in reference-relative soft preference scores, not direct matches between the two runs. Intervals containing zero do not establish a difference.

| Improvement contrast | New change minus current change, WR pp [95% CI] |
|---|---:|
| step2 - baseline | +3.79 [-1.77, +9.35] |
| step2 - step0 | +2.93 [-2.14, +7.97] |
| step2 - step1 | +3.13 [-0.68, +7.16] |
| step2 - bon15 | +3.63 [-2.18, +9.56] |

Held fixed: policy and reward model identifiers and cached checkpoints, all TPO/TextGrad algorithm code and prompts, 100 exact questions and references, D/N, candidate seed, temperature/top_p, token limits, eight workers, vLLM context, stage definitions, judge prompt/parser/settings, and bootstrap method. The rerun uses a persistent eight-worker pool and per-prompt checkpoints; the historical launcher recreated its pool every 32 prompts. Fresh generation differs because critique/gradient requests are unseeded and server batching/scheduling can vary. The judge alias has no dated snapshot, and judging occurs at a later time. This single-seed rerun assesses observed repeatability, not a multi-seed estimate of the method’s general performance.

Both runs replace the official GPT-4 judge with Qwen; their absolute scores are not directly comparable to the paper or leaderboard. LC retains historical GPT-4 calibration and is descriptive. Reward increases alone do not establish improved answer quality.

`TPO/` preservation: **True**; 741 file contents match, with no additions/removals. See `tpo_preservation.json`. Current artifacts are copied in `llama_reference/`; stopped Qwen-policy artifacts are excluded.

See [experiment results](EXPERIMENT_RESULTS.md), [full paired statistics](comparison.json), [configuration](run_config.json), and [within-run robustness](robustness.md).
