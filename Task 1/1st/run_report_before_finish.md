# Task 1 run report

Completed 100 AlpacaEval-2 prompts with D=2 and N=5 requested candidates per step.

Policy: `allenai/Llama-3.1-Tulu-3-8B-SFT` via vLLM on H100 GPU 2, port 8002. Reward model: `sfairXC/FsfairX-LLaMA3-RM-v0.1` on H100 GPU 3.

PyTorch 2.4.0+cu121; vLLM 0.6.3; bfloat16. Sampling temperature 0.7, top_p 0.95, seed 7. Slice seed 42; exact indices: `data/slice_ids.json`. Response cap 2048 tokens, critique/gradient cap 8192, server context 16384. Full configuration and data hashes: `run_config.json`.

## Results

| Stage | Mean selected RM score | AlpacaEval LC win rate | AlpacaEval win rate |
|---|---:|---|---|
| baseline | -3.9737 | Pending external judge | Pending external judge |
| step0 | -2.3567 | Pending external judge | Pending external judge |
| step1 | -1.3607 | Pending external judge | Pending external judge |
| step2 | -0.8038 | Pending external judge | Pending external judge |

Baseline is the first initial sample; step0 is Best-of-5; step1 and step2 select the best cached answer after each refinement. Selected reward scores are nondecreasing by construction and do not establish independent win-rate improvement.

Mean reward of all scored candidates, including less successful refinements:

| Iteration | Mean RM score | Scored candidates | Prompts with fewer than 5 stored candidates |
|---|---:|---:|---:|
| init | -4.3244 | 492 | 5 |
| iter1 | -2.1534 | 419 | 30 |
| iter2 | -1.6642 | 414 | 33 |

The official optimizer discards refinements missing its required response tags; identical responses within an iteration also share a cache key. Candidate counts therefore describe stored scored answers, not necessarily all requested generations.

## Independent evaluation

A dummy API key suffices for the local server. No external judge credential was available, and alpaca_eval was absent from the existing tpo environment. Independent win rates and their monotonicity remain unmeasured. With an AlpacaEval environment and valid judge credentials, run `bash run_alpaca_eval.sh stages data/reference100.json`, then `python summarize.py` from this directory. The reference contains the same 100 GPT-4 Turbo responses.

## Comparison with the paper

The [published ICML paper](https://proceedings.mlr.press/v267/li25ac.html) does not report an 8B-policy AlpacaEval win-rate table. Table 1 reports 70B-SFT LC 27.8% / WR 16.8%, rising to LC 33.0% / WR 40.5% with FsfairX and D2-N5. These are context, not directly comparable targets for this 8B, 100-prompt run. Section 7.4 and Figure 7 show declining reward for 8B-Instruct on HH-RLHF, attributed to instruction-following limitations. Improvement on this setup must therefore be measured rather than assumed.

## Environment repair

The existing vLLM process initially returned HTTP 500 because its lazy outlines import could not find pyairports. Replaced the installed nonfunctional 0.0.1 package with original NICTA/pyairports 2.1.1 at commit `9699eae8c6b03c97239018dea92e01daa8594936`. Actual text generation then succeeded. Existing repository modifications were preserved. The policy server was reused.
