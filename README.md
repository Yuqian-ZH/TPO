# TPO in an enterprise optimization feedback loop

Yuqian Zhang, 28 October 2026

Test-Time Preference Optimization (TPO, arXiv 2501.12895) turns a reward into a textual critique and refines the output with it, without training. Task 1 reproduces it on AlpacaEval 2. Tasks 2 to 4 move it to a capacitated vehicle routing problem: a user complains about a plan, the system explains and localizes the complaint, an LLM proposes changes to the optimization model (never to the routes), and Gurobi re-solves. Task 5 is the plan for turning such corrections into model updates in production.

**Final report:** [`Report/TPO_Final_Report_EN.pdf`](Report/TPO_Final_Report_EN.pdf) (LaTeX source in [`Report/`](Report/)). Each task folder has its own README with details and commands.

## Where to look

| Task | Code and README | Final results |
|---|---|---|
| 1. TPO on AlpacaEval 2 | [`Task 1/`](Task%201/README.md): three runs, `3rd` is the frozen-protocol run | [`Task 1/3rd/EXPERIMENT_RESULTS.md`](Task%201/3rd/EXPERIMENT_RESULTS.md) |
| 2. Explanation, counterfactuals, localization | [`Task 2/task2/README.md`](Task%202/task2/README.md); instance spec in [`instance/instance.md`](Task%202/task2/instance/instance.md) | [`results_v3/task2_v3_results.md`](Task%202/task2/results_v3/task2_v3_results.md) |
| 3. Ablation of A, B, C | [`Task 3/task3/README.md`](Task%203/task3/README.md), section 10 | [`results/formal_v31/task3_v31_results.md`](Task%203/task3/results/formal_v31/task3_v31_results.md) |
| 4. Feedback service | [`Task 4/task4/README.md`](Task%204/task4/README.md) | [`results/e2e_test_v31/e2e_report.md`](Task%204/task4/results/e2e_test_v31/e2e_report.md) |
| 5. Production self-evolution | [`Task 5/task5/DESIGN.md`](Task%205/task5/DESIGN.md) | [`results/validator_demo.md`](Task%205/task5/results/validator_demo.md) |

## Results at a glance

**Task 1.** `Llama-3.1-Tulu-3-8B-SFT` on vLLM, reward model `FsfairX-LLaMA3-RM-v0.1`, D = 2, N = 5, 100 AlpacaEval 2 prompts, judge `qwen3.8-max` (so absolute numbers are not comparable with the paper). In the frozen run the win rate rose from 8.77% to 12.09% and 14.13%; step 2 over the baseline is +5.37 points [+0.74, +10.61]. The length-controlled win rate did not rise, and TPO did not beat Best-of-15 with the same number of candidates (+0.16 points [−5.51, +5.95]). The two earlier runs agree on the controls; the win rate rose monotonically in run 2 but not in run 1.

**Task 2.** One depot, 8 customers, 2 vehicles of capacity 100, minimum total distance (optimum 351, checked against all 282,240 solutions). On the 10 test cases: attribution 10/10 with precision and recall 1; counterfactual local method against a full re-solve agrees on feasibility 30/30, objective within 1% 25/28 and change set 20/28, with mean latency 22 ms against 36 ms; localization is correct in 90% of first passes (100% when high confidence, 80% when low), every low-confidence case asks the user first, and all are correct after the answer.

**Task 3.** 2³ configurations and three control arms, 10 cases, 5 runs (550 trials). The bare loop already converges in 96% of trials. The counterfactual probe (B) contributes most to reliable convergence, with moderate evidence: with the same three candidates, choosing after seeing the forecasts converged 18 points more often than choosing blind on cases whose plain fix has side effects. Asking first (C) resolves vague complaints one iteration earlier, and the gain comes from the question rather than the structured fields. Attribution (A) has no reliable effect.

**Task 4.** FastAPI service with JSON file storage, covering ingestion, complaint processing, triggering and per-iteration logging. It runs Task 3's frozen loop, and tests show byte-identical prompts, candidates and plans. The final end-to-end run with all mechanisms on resolved 8 of 10 complaints.

**Task 5.** Distillation by SFT and DPO with a data pipeline and cadence, feedback filtering with the Meta RLUF failure mode, tenant isolation with a shared base model, and A/B testing with rollback triggers. A small solver-only validator shows how attribution and counterfactuals flag praise based on a misunderstanding and complaints against constraints the user imposed.

## Running it

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # Tasks 2 to 5; Task 1 runs on a GPU server, see Task 1/
export PYTHONDONTWRITEBYTECODE=1
(cd "Task 2/task2" && python -m pytest -q)   # 186 tests; Task 3: 278, Task 4: 148, Task 5: 6
```

The tests and the report scripts that recompute metrics from the saved raw results need no network. New LLM runs need `DASHSCOPE_API_KEY` and `DASHSCOPE_BASE_URL` (DashScope's OpenAI-compatible endpoint; model `qwen3.8-max` with thinking off). Each task README lists its commands in order.

## Versions

Every experiment froze its protocol (SHA-256 of code and cases) before the first LLM call, and the runners refuse to start if a frozen file has changed. Fixes became new versions beside the old ones; old results were never edited.

| Version | What it is |
|---|---|
| v1 | The original runs. |
| v2, v2.1 | Fixes after an external audit and a later code review. |
| v3 | Test cases and simulated user re-designed so that each mechanism can matter ([`DESIGN_V3.md`](DESIGN_V3.md)). |
| v3.1 | Pre-registered replication of v3 with new seeds and three control arms ([`DESIGN_V31.md`](DESIGN_V31.md)). |

The results to quote are Task 2 v3, Task 3 v3.1 and Task 4 v3.1.
