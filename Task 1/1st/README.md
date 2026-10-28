# Task 1, run 1: the original run

The first full TPO run on the 100-prompt AlpacaEval 2 slice, launched with the official repository's `run.py`. Critique and rewrite requests were unseeded. Runs 2 and 3 are in [`../2nd`](../2nd/README.md) and [`../3rd`](../3rd/README.md).

## Configuration

- Source: official TPO commit `395c3d763a4c3df0ae72a4352b0db16fe5ee18e9` with the local patch [`tpo_existing_changes.patch`](tpo_existing_changes.patch). The patch changes only the output-token limits (and the keyword that passes them to vLLM) and fixes TextGrad's `setup.py`, which does not install as published; the algorithm, prompts and reward code are unchanged. [`DEVIATIONS.md`](DEVIATIONS.md) lists every deviation from the repository and the paper.
- Policy `allenai/Llama-3.1-Tulu-3-8B-SFT` on vLLM 0.6.3 (bfloat16, one H100, context 16384); reward model `sfairXC/FsfairX-LLaMA3-RM-v0.1` on a second H100.
- D = 2, N = 5; candidate temperature 0.7, top_p 0.95, seed 7; 2048 response tokens; critique and gradient calls capped at 8192 tokens.
- Data: 100 of the 805 AlpacaEval 2 prompts, sampled with seed 42, with their GPT-4 Turbo reference outputs ([`data/`](data/), indices in `data/slice_ids.json`).
- Judge: `qwen3.8-max` with AlpacaEval's weighted prompt and log-probability parser (temperature 1, one output token, top 5 log-probabilities, thinking off). Absolute win rates are not comparable with the paper or the leaderboard.

## Results

| Stage | WR (%) | WR SE (pp) | LC (%) | Selected RM |
|---|---:|---:|---:|---:|
| baseline | 9.14 | 2.61 | 16.29 | −3.97 |
| step 0 (Best-of-5) | 11.22 | 2.84 | 21.67 | −2.36 |
| step 1 | 10.09 | 2.75 | 16.02 | −1.36 |
| step 2 | 8.27 | 2.60 | 10.51 | −0.80 |
| Best-of-15 | 14.02 | 3.35 | 24.53 | −1.61 |

Neither the win rate nor the length-controlled win rate is monotonic from baseline to step 2. The reward model prefers step 2 over Best-of-15 (+0.80 [+0.49, +1.14]), while the judge's win rate is −5.74 pp [−11.92, +0.01] (paired bootstrap, 10,000 resamples). The mean reward of all candidates rises by iteration (−4.32, −2.15, −1.66).

Full tables: [`results_task1.md`](results_task1.md), [`robustness.md`](robustness.md), and [`run_report.md`](run_report.md), which includes the comparison with the paper.

## Files

| Path | Content |
|---|---|
| `run100/`, `bon15/` | raw TPO and Best-of-15 outputs from `run.py` |
| `stages/` | the five judged answer sets: baseline, step0, step1, step2, bon15 |
| `eval_out/`, `judge_config/` | judge annotations, leaderboards, usage and the judge configuration |
| `TPO_logs/2026-10-19_19-50-42.jsonl` | the TPO trace of the 100-prompt run (critiques and textual gradients) |
| `smoke/`, `smoke_stages/`, `eval_smoke/` | the 5-prompt smoke test |
| `*.log`, `gpu_*.csv`, `judge_endpoint_check.json` | run logs and environment checks |
| `run_report_before_finish.md`, `finish_status.md`, `FILES_FINISH.md` | the report before judging, and the record of the finishing phases |

## How it was run

These scripts ran on the GPU server, with `~/TPO` holding the official repository next to this folder. Some paths in them are that server's paths.

```bash
bash setup_env.sh                      # conda environments 'tpo' and 'aeval', TPO checkout at the pinned commit
bash setup_env.sh --serve-policy       # vLLM policy server on GPU 2, port 8002 (separate terminal)
python prepare_data.py --n 100 --seed 42 --out_dir data
bash run_task1.sh                      # TPO on the 100 prompts (reward model on GPU 3), then extract_stages.py
#   Best-of-15: the same run.py with --tpo_mode bon --sample_size 15 (output in bon15/, log in bon15.log)
python extract_bon15.py                # extract and validate the Best-of-15 stage
bash run_alpaca_eval.sh                # judge the five stages (needs DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, JUDGE_MODEL=qwen3.8-max)
python robustness.py                   # paired bootstrap on stored scores, no new requests
python diagnose_outputs.py             # format residue, truncation, per-prompt wins
```

`robustness.py` reads the TPO trace from the server's `~/TPO/logs/`; the same file is saved here in `TPO_logs/`.

The endpoint URL in `judge_full.log` and `judge_smoke.log` is replaced by `<DASHSCOPE_BASE_URL>`, so these two files no longer match the hashes recorded for them in `../2nd/tpo_before.sha256.json` and `../3rd/protected_before.json`.
