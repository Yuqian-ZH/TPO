# Task 2 results

Split `dev`, run 2026-10-23T01:46:29+08:00 to 2026-10-23T01:48:39+08:00 on Apple M2 Pro (arm64), Python 3.12.8, Gurobi 13.0.3, LLM `qwen3.8-max` (alias; no fixed snapshot), power: Now drawing from 'AC Power', low-power mode 0. LLM parts: 1 independent runs (mean ± sample std); deterministic parts once; 3 timing repeats per query and method. Protocol `protocol.json` sha256 `None`. Schema violations in component outputs: 0.

## 1. Decision attribution

- Inclusion rate (returned set contains every ground-truth element): 100.0% (5/5)
- Precision / recall, per-case mean: 1.000 / 1.000
- Pooled precision / recall: 1.000 / 1.000 (34 of 34 returned, 34 in ground truth)
- Constraint part (1 cases): pooled precision 1.000, recall 1.000
- Variable part (4 cases): pooled precision 1.000, recall 1.000
- LLM explanation passes the number/entity checks: 100.0% ± 0.0 (first attempt 100.0% ± 0.0; template fallbacks 0)

| Case | Decision | Conclusion (GT) | Returned set | Contains GT | P / R |
|---|---|---|---|---|---|
| D1 | ADJ(1,4) | objective_preferred (objective_preferred) | e[0,2], e[0,4], e[1,2], e[1,4] | yes | 1.00 / 1.00 |
| D2 | SEP(2,4) | hard_constraint_forced (capacity_forced) | cap[1], cap[2] | yes | 1.00 / 1.00 |
| D3 | ADJ(0,1) | objective_preferred (objective_preferred) | 10 edges | yes | 1.00 / 1.00 |
| D4 | SAME(5,8) | objective_preferred (objective_preferred) | 10 edges | yes | 1.00 / 1.00 |
| D5 | SAME(3,5) | objective_preferred (objective_preferred) | 8 edges | yes | 1.00 / 1.00 |

Example explanation (run 0, first case of each conclusion type):

> **D1, ADJ(1,4)** (llm): The current plan visits customer 1 and customer 4 one right after the other, using the direct leg e[1,4] with a distance of 41 km. This decision is not forced by any constraint, but it keeps the total route length at 351 km. If the decision were dropped, the plan would still be feasible but the total distance would increase by 5 km to 356 km. In that alternative, the plan would no longer drive legs e[0,2] with a distance of 43 km and e[1,4] with a distance of 41 km, and would instead drive legs e[0,4] with a distance of 42 km and e[1,2] with a distance of 47 km. No customers would be moved to the other vehicle in this alternative.

> **D2, SEP(2,4)** (llm): The current plan assigns customers 2 and 4 to different vehicles, and this decision is forced by the capacity constraints of both vehicles. If the plan were required to serve them with the same vehicle, no feasible routing plan would exist at all. Vehicle 1 currently carries a load of 98 against its capacity limit of 100, leaving very little room for additional demand. Vehicle 2 carries a load of 96 against its own capacity limit of 100. Because both cap[1] and cap[2] are nearly full, combining customers 2 and 4 on a single vehicle would exceed the allowed capacity, making it impossible to visit all eight customers.

## 2. Counterfactual explanation

### 2.1 The 10 test-case queries

5 queries. Local re-optimization vs full re-solve:

| Agreement | Rate |
|---|---|
| Feasibility | 100.0% (5/5) |
| Objective within 1% (both feasible) | 100.0% (4/4) |
| Change set (both feasible) | 100.0% (4/4) |

Each method against the exhaustive ground truth:

| Method | Feasibility | Objective within 1% | Change set |
|---|---|---|---|
| local | 100.0% (5/5) | 100.0% (4/4) | 100.0% (4/4) |
| full | 100.0% (5/5) | 100.0% (4/4) | 100.0% (4/4) |

Levels where the local method stopped: L0 1, L1 1, L2 2; infeasible after L2: 1 (infeasible reported before L2: 0).

Latency in ms over all repeats (median / mean / p95):

| Method | Including model setup | Solver only |
|---|---|---|
| local | 4.5 / 20.8 / 81.2 | 4.0 / 20.3 / 80.7 |
| full | 30.3 / 31.6 / 82.5 | 28.4 / 29.3 / 80.3 |

| Case | Query | Local (level) | Full | Feasible / objective / change set agree | Median ms local / full |
|---|---|---|---|---|---|
| D1 | FIX_ARC(v1: 4→1) | 351 (L0) | 351 | yes / yes / yes | 3.9 / 8.3 |
| D2 | FORCE_SAME(2,4) | infeasible | infeasible | yes / n/a / n/a | 1.5 / 2.8 |
| D3 | MOVE(2→v2) | 369 (L2) | 369 | yes / yes / yes | 62.1 / 78.7 |
| D4 | FORCE_ADJ(7,8) | 371 (L1) | 371 | yes / yes / yes | 4.3 / 36.3 |
| D5 | FORCE_SEP(3,5) | 369 (L2) | 369 | yes / yes / yes | 24.9 / 30.3 |

## 3. Feedback localization

| Metric | First pass | After the clarification answer |
|---|---|---|
| Accuracy (majority target in GT list) | 80.0% ± 0.0 | 100.0% ± 0.0 |
| Accuracy, predicted high | 100.0% ± 0.0 | 100.0% ± 0.0 |
| Accuracy, predicted low | 50.0% ± 0.0 | n/a |
| Predicted high / low per run | [3] / [2] | [5] high |
| Clarifying-question rate | 40.0% ± 0.0 | 0.0% ± 0.0 |
| Invalid samples | 0.0% ± 0.0 | 0.0% ± 0.0 |
| Modification type correct | 100.0% ± 0.0 | |

Low-confidence results that carried a critique: 0 (must be 0).

Expected vs predicted confidence (first pass, per run):

- run 0: expected high → high 3, low 0; expected low → high 0, low 2

| Case | Clarity | GT targets | Run 0 / 1 / 2: confidence, majority target | After clarification |
|---|---|---|---|---|
| D1 | ambiguous | S[2] | low, L[2] ✗ | high, S[2] |
| D2 | clear | e[2,8] | high, e[2,8] | high, e[2,8] |
| D3 | clear | demand[2] | high, demand[2] | high, demand[2] |
| D4 | ambiguous | A[8] | low, A[8] | high, A[8] |
| D5 | clear | sum_arrival | high, sum_arrival | high, sum_arrival |

