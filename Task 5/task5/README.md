# Task 5: Production-Grade Self-Evolution

The technical plan is [`DESIGN.md`](DESIGN.md). It covers the four required points and grounds each design choice in what Tasks 1 to 4 measured:

| Required point | Section |
|---|---|
| Closing the loop: distilling converged TPO trajectories with SFT and DPO, data pipeline, training cadence | 2 |
| Feedback quality: filtering, weighting, validating; the Meta RLUF reward-hacking failure mode; how decision attribution and counterfactuals flag praise based on a misunderstanding and complaints against constraints the user imposed | 3 |
| Multi-tenant isolation with a shared base that improves from aggregated signals | 4 |
| A/B testing strategy, metrics, rollback triggers and mechanics | 5 |

Section 3.4 is backed by a small runnable feedback validator ([`validator/`](validator/)): Task 2's attribution (protocol task2_v2.1, IIS for forced decisions) and the counterfactual re-solve, applied to sessions from the Task 4 end-to-end run. Ten scenarios (seven checks, three controls) all get the expected verdict ([`results/validator_demo.md`](results/validator_demo.md)). It uses Gurobi only, no LLM, and demonstrates the mechanism rather than measuring detection rates.

**Changes after the 2026-10 audit.** (1) The validator crashed when dropping a user input left no feasible plan (F6); that case is now recorded as evidence ("no feasible plan without it"), and scenario V9 exercises it. (2) It uses Task 2's fixed attribution (F1); the verdicts and numbers of V1 to V8 are unchanged. (3) DESIGN.md said in one place that training labels need the full re-solve and in another that probe-labelled DPO pairs come "for free" (F8); probe pairs are now confirmed by a full re-solve before training. (4) The Task 1 row no longer mentions three runs, whose data is not in this repository (F7). (5) Section 0 now gives the scope of Task 2's 10/10 attribution result and the T7 fix.

```bash
cd "Task 5/task5"
export PYTHONDONTWRITEBYTECODE=1
python -m pytest -q          # 6 tests
python -m validator.demo     # results/validator_demo.{json,md}
python check_doc.py          # numbers traced to their sources, coverage, style: results/checks.json
```
