# Task 1: TPO on AlpacaEval 2

Policy `allenai/Llama-3.1-Tulu-3-8B-SFT` served by vLLM (H100), reward model `sfairXC/FsfairX-LLaMA3-RM-v0.1`, D = 2, N = 5, the same 100 AlpacaEval 2 prompts (seed 42) with GPT-4 Turbo references in every run. The judge is `qwen3.8-max` with AlpacaEval's weighted prompt and log-probability parser (temperature 1, one output token, thinking off), so absolute win rates are not comparable with the paper or the leaderboard. Five stages are judged: baseline, step 0 (best of 5), step 1, step 2 and Best-of-15.

The experiment was run three times. The runs differ in execution rules as well as random draws, so they are reported side by side and not averaged.

| Folder | Run | Notes | Win rate, baseline / step 1 / step 2 / Best-of-15 |
|---|---|---|---|
| [`3rd/`](3rd/README.md) | frozen protocol `task1_frozen_v1` (main result) | every policy request seeded; protocol, analysis and comparisons frozen before the run; one formal run after a 3-prompt preflight | 8.77 / 12.09 / 14.13 / 13.97% |
| [`2nd/`](2nd/README.md) | rerun | same settings as run 1 with a persistent worker pool; critique and rewrite requests unseeded | 7.64 / 9.25 / 10.56 / 12.67% |
| [`1st/`](1st/README.md) | original run | repository launcher as provided; critique and rewrite requests unseeded | 9.14 / 10.09 / 8.27 / 14.02% |

Main files in each run folder: `results_task1.md` (five-stage table and paired comparisons), `robustness.md`, `stages/` (the judged answers), `eval_out/` (judge annotations and leaderboards), `run_config.json`. Run 3 also has `EXPERIMENT_RESULTS.md`, `protocol.json`, `freeze.json`, the request journals and the caches; run 2 has `COMPARISON.md` against run 1. Each folder's README describes how that run was executed on the GPU server.

Code: run 1's scripts are in `1st/`, run 2's in `2nd/scripts/` and run 3's in `3rd/scripts/` (hashes frozen in `3rd/freeze.json`). All runs use the official TPO repository at commit `395c3d7`; run 3 keeps its copy in `3rd/source/TPO`, with the local compatibility changes in `3rd/source_changes.patch`. `3rd/scripts/analyze.py` recomputes run 3's results from the saved files on a CPU, without model or judge calls.

Summary across the runs, with the full discussion in the final report (section 2): the reward rises at every step in every run; step 1 is below step 0 in every run; step 2 never beats Best-of-15 reliably; the length-controlled win rate is never monotonic; the win rate is monotonic in runs 2 and 3 but not in run 1.
