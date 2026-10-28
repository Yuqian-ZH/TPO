# Experiment results: Tulu policy, FsfairX RM, Qwen judge

**Policy:** `allenai/Llama-3.1-Tulu-3-8B-SFT` for sampling, critique, textual gradient and refinement. **RM:** `sfairXC/FsfairX-LLaMA3-RM-v0.1`. **Qwen is the judge only:** `qwen3.8-max`, thinking disabled.

Fresh measurements on the same fixed 100 AlpacaEval-2 prompts and GPT-4 Turbo reference answers as the current experiment. D=2, N=5, candidate seed 7, temperature .7, top_p .95, response cap 2048. Critique/gradient: temperature .7, top_p .99, cap 8192, unset seed. vLLM context 16384; eight prompt workers; policy GPU 2 and RM GPU 3.

| Stage    |   LC (%) |   WR (%) |   WR SE (pp) |   LC SE (pp) |      RM |   Avg length (chars) |   Judged |   Judge requests |   Judge tokens |
|:---------|---------:|---------:|-------------:|-------------:|--------:|---------------------:|---------:|-----------------:|---------------:|
| baseline |  13.4600 |   7.6425 |       2.4227 |       1.2373 | -3.9896 |                  782 |      100 |               99 |          99818 |
| step0    |  19.6729 |  10.5835 |       2.7445 |       1.6718 | -2.3364 |                  975 |      100 |               72 |          75830 |
| step1    |  15.2756 |   9.2503 |       2.6152 |       1.3771 | -1.3038 |                 1278 |      100 |               70 |          73566 |
| step2    |  14.9043 |  10.5565 |       2.8122 |       1.3212 | -0.7642 |                 1489 |      100 |               62 |          70842 |
| bon15    |  21.7793 |  12.6688 |       3.1246 |       1.5693 | -1.6378 |                 1076 |      100 |              100 |         103227 |

Monotonic baseline → step1 → step2: WR **True**; LC **False**.

The baseline → step1 → step2 WR point estimates are monotonic in this rerun (7.64 → 9.25 → 10.56%), whereas the saved experiment was not monotonic. LC is not monotonic. Step2 minus baseline WR is +2.91 [-1.03, +7.19] pp, step2 minus Best-of-5 is -0.03 [-3.61, +3.52] pp, and step2 minus Best-of-15 is -2.11 [-7.67, +3.14] pp. All three intervals contain zero. The rerun therefore shows monotonic point estimates, but does not establish a reliable TPO benefit over the controls. The new final WR is +2.28 [-2.58, +7.12] pp above the saved final WR; that interval also contains zero.

Baseline is the first initial sample. Step0 is Best-of-5; step1/step2 select the best reward in the cumulative cache. Best-of-15 matches TPO’s answer-candidate count but excludes critique/gradient compute. Cumulative selection guarantees nondecreasing selected RM; independent win-rate improvement is an empirical question.

| New-run comparison | WR Δ pp [paired 95% CI] | LC Δ pp [descriptive CI] |
|---|---:|---:|
| step2 - baseline | +2.91 [-1.03, +7.19] | +1.44 [+1.28, +1.62] |
| step2 - step0 | -0.03 [-3.61, +3.52] | -4.77 [-5.50, -4.08] |
| step2 - step1 | +1.31 [-0.67, +3.90] | -0.37 [-0.49, -0.27] |
| step2 - bon15 | -2.11 [-7.67, +3.14] | -6.88 [-7.42, -6.33] |

All-candidate mean RM: {"initial": -4.264816750334139, "step1": -1.9762131157973057, "step2": -1.635222599424165}.
Unique cached candidates: {"initial": 491, "step1": 399, "step2": 406}; 500 requested per TPO round.
Raw candidate extraction diagnostics: {"initial": {"returned": 500}, "refinement": {"returned": 1000, "valid_tags": 999, "missing_tags": 1}, "bon15": {"returned": 1500}}.
Raw policy response finish reasons: {"stop": 3387, "length": 13}. Length indicates a raw response hit its cap.
Empty unique cached candidates: {"tpo": 1, "bon15": 1}; none of the 500 selected stage outputs is empty.
Local policy token usage: {"prompt_tokens": 688288, "completion_tokens": 692175, "total_tokens": 1380463}. These are local vLLM counts, not hosted Qwen generation usage.
Generation timing excluding model loading: TPO 300.6s; Best-of-15 72.7s.

Judge settings match the current experiment: weighted AlpacaEval prompt and soft logprob parser, temperature 1, max_tokens 1, top_logprobs 5, thinking disabled, answer-order seed 0. WR is mean weighted preference against the reference, not an integer win fraction. Uncertainty uses 10,000 paired prompt bootstrap resamples, seed 42. LC intervals condition on fitted GLMs and omit fit uncertainty; GPT-4-derived calibration is unvalidated for Qwen, so LC is descriptive.

The paper Table 1 uses a 70B SFT policy: FsfairX D2-N5 yields WR 16.8→40.5 and LC 27.8→33.0. There is no equivalent 8B AlpacaEval WR table; §7.4 discusses 8B-Instruct on HH-RLHF. Model size, subset and judge differ, so these are context, not comparable targets. [Published paper](https://proceedings.mlr.press/v267/li25ac.html).

Evidence: `run_config.json`, `results_task1.json`, `comparison.json`, `robustness.json`, `policy_requests.jsonl`, `stages/` and `eval_out/`. The discarded Qwen-policy run contributes no results.
