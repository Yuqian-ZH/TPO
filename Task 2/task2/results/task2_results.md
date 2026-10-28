# Task 2 results

Split `test`, run 2026-10-23T01:49:39+08:00 to 2026-10-23T02:03:03+08:00 on Apple M2 Pro (arm64), Python 3.12.8, Gurobi 13.0.3, LLM `qwen3.8-max` (alias; no fixed snapshot), power: Now drawing from 'AC Power', low-power mode 0. LLM parts: 3 independent runs (mean ± sample std); deterministic parts once; 20 timing repeats per query and method. Protocol `protocol.json` sha256 `dd0b13230f90eeb05d4079310f4ec6d439382c51730bead7df7cf483f5b13005`. Schema violations in component outputs: 0.

## 1. Decision attribution

- Inclusion rate (returned set contains every ground-truth element): 100.0% (10/10)
- Precision / recall, per-case mean: 1.000 / 1.000
- Pooled precision / recall: 1.000 / 1.000 (64 of 64 returned, 64 in ground truth)
- Constraint part (2 cases): pooled precision 1.000, recall 1.000
- Variable part (8 cases): pooled precision 1.000, recall 1.000
- LLM explanation passes the number/entity checks: 100.0% ± 0.0 (first attempt 100.0% ± 0.0; template fallbacks 0)

| Case | Decision | Conclusion (GT) | Returned set | Contains GT | P / R |
|---|---|---|---|---|---|
| T1 | ADJ(0,8) | objective_preferred (objective_preferred) | 12 edges | yes | 1.00 / 1.00 |
| T2 | SAME(1,2) | objective_preferred (objective_preferred) | 8 edges | yes | 1.00 / 1.00 |
| T3 | ADJ(3,6) | objective_preferred (objective_preferred) | e[0,3], e[0,5], e[3,6], e[5,6] | yes | 1.00 / 1.00 |
| T4 | SEP(1,3) | hard_constraint_forced (capacity_forced) | cap[1], cap[2] | yes | 1.00 / 1.00 |
| T5 | ADJ(4,7) | objective_preferred (objective_preferred) | e[0,2], e[0,7], e[2,4], e[4,7] | yes | 1.00 / 1.00 |
| T6 | ADJ(2,7) | objective_preferred (objective_preferred) | e[1,4], e[1,7], e[2,4], e[2,7] | yes | 1.00 / 1.00 |
| T7 | SEP(2,6) | objective_preferred (objective_preferred) | 10 edges | yes | 1.00 / 1.00 |
| T8 | SAME(2,7) | objective_preferred (objective_preferred) | 8 edges | yes | 1.00 / 1.00 |
| T9 | SEP(2,5) | hard_constraint_forced (capacity_forced) | cap[1], cap[2] | yes | 1.00 / 1.00 |
| T10 | ADJ(6,8) | objective_preferred (objective_preferred) | 10 edges | yes | 1.00 / 1.00 |

Example explanation (run 0, first case of each conclusion type):

> **T1, ADJ(0,8)** (llm): The current plan includes the direct leg e[0,8] between the depot and customer 8 with a distance of 44 km. This decision is not forced by any hard constraint, but it keeps the total route length at 351 km. If the decision were dropped, the plan would still be feasible but the total distance would increase by 20 km to 371 km. In that alternative, customers 4 and 8 would be served by the other vehicle, and the plan would replace legs such as e[0,2], e[0,5], e[0,8], e[1,4], e[4,7], and e[6,8] with different legs including e[0,4], e[0,6], e[0,7], e[1,8], e[2,8], and e[4,5]. Therefore, visiting customer 8 directly from the depot is preferred because it avoids these longer detours and keeps the overall plan shorter.

> **T4, SEP(1,3)** (llm): The current plan serves customers 1 and 3 with different vehicles, and this decision is forced by the capacity limits of both vehicles. If the plan were required to serve them together on the same vehicle, no feasible plan would exist at all. This infeasibility is caused by the capacity constraints cap[1] and cap[2]. In the current plan, vehicle 1 carries a load of 99 against its capacity of 100, while vehicle 2 carries a load of 90 against its capacity of 100. Because neither vehicle has enough remaining capacity to absorb the other customer's demand, they must be split across the two vehicles.

## 2. Counterfactual explanation

### 2.1 The 10 test-case queries

10 queries. Local re-optimization vs full re-solve:

| Agreement | Rate |
|---|---|
| Feasibility | 100.0% (10/10) |
| Objective within 1% (both feasible) | 87.5% (7/8) |
| Change set (both feasible) | 75.0% (6/8) |

Each method against the exhaustive ground truth:

| Method | Feasibility | Objective within 1% | Change set |
|---|---|---|---|
| local | 100.0% (10/10) | 87.5% (7/8) | 75.0% (6/8) |
| full | 100.0% (10/10) | 100.0% (8/8) | 100.0% (8/8) |

Levels where the local method stopped: L0 4, L1 0, L2 4; infeasible after L2: 2 (infeasible reported before L2: 0).

Latency in ms over all repeats (median / mean / p95):

| Method | Including model setup | Solver only |
|---|---|---|
| local | 17.1 / 26.5 / 77.1 | 16.5 / 26.1 / 76.6 |
| full | 45.7 / 40.0 / 68.0 | 43.9 / 38.0 / 65.2 |

| Case | Query | Local (level) | Full | Feasible / objective / change set agree | Median ms local / full |
|---|---|---|---|---|---|
| T1 | APPLY(L[2] <= 180) | 661 (L0) | 368 | yes / no / no | 6.4 / 63.5 |
| T2 | MOVE(7→v2) | 369 (L2) | 369 | yes / yes / yes | 77.1 / 67.6 |
| T3 | FIX_ARC(v2: 0→6) | 369 (L0) | 368 | yes / yes / no | 4.9 / 38.0 |
| T4 | MOVE(3→v1) | infeasible | infeasible | yes / n/a / n/a | 1.1 / 1.8 |
| T5 | MOVE(4→v2) | 368 (L2) | 368 | yes / yes / yes | 39.9 / 40.2 |
| T6 | FORCE_SEP(2,7) | 391 (L2) | 391 | yes / yes / yes | 50.0 / 50.3 |
| T7 | APPLY(w[balance]=0.8) | 404.8 (L0) | 404.8 | yes / yes / yes | 54.5 / 59.0 |
| T8 | SWAP(1,8) | 389 (L2) | 389 | yes / yes / yes | 24.9 / 23.7 |
| T9 | FORCE_SAME(2,5) | infeasible | infeasible | yes / n/a / n/a | 1.1 / 2.2 |
| T10 | FIX_ARC(v2: 0→8) | 351 (L0) | 351 | yes / yes / yes | 4.6 / 48.8 |

### 2.2 Supplementary: every MOVE and FIX_ARC query on the reference optimum

120 queries. Local re-optimization vs full re-solve:

| Agreement | Rate |
|---|---|
| Feasibility | 100.0% (120/120) |
| Objective within 1% (both feasible) | 86.1% (87/101) |
| Change set (both feasible) | 82.2% (83/101) |

Each method against the exhaustive ground truth:

| Method | Feasibility | Objective within 1% | Change set |
|---|---|---|---|
| local | 100.0% (120/120) | 86.1% (87/101) | 82.2% (83/101) |
| full | 100.0% (120/120) | 100.0% (101/101) | 100.0% (101/101) |

Levels where the local method stopped: L0 24, L1 35, L2 42; infeasible after L2: 19 (infeasible reported before L2: 0).

Latency in ms over all repeats (median / mean / p95):

| Method | Including model setup | Solver only |
|---|---|---|
| local | 3.6 / 7.2 / 28.7 | 3.2 / 6.8 / 28.3 |
| full | 7.6 / 14.0 / 46.7 | 5.8 / 12.1 / 44.8 |

Queries where local and full disagree on feasibility or objective: 14.

| Query | Local (level) | Full |
|---|---|---|
| FIX_ARC(v1: 4→6) | 412 (L1) | 390 |
| FIX_ARC(v1: 4→8) | 416 (L1) | 390 |
| FIX_ARC(v1: 6→4) | 412 (L1) | 390 |
| FIX_ARC(v1: 6→7) | 421 (L1) | 415 |
| FIX_ARC(v1: 7→6) | 421 (L1) | 415 |
| FIX_ARC(v1: 8→4) | 416 (L1) | 390 |
| FIX_ARC(v2: 1→7) | 413 (L1) | 396 |
| FIX_ARC(v2: 2→3) | 391 (L1) | 384 |
| FIX_ARC(v2: 3→2) | 391 (L1) | 384 |
| FIX_ARC(v2: 3→7) | 407 (L1) | 389 |
| FIX_ARC(v2: 4→7) | 398 (L1) | 369 |
| FIX_ARC(v2: 7→1) | 413 (L1) | 396 |
| FIX_ARC(v2: 7→3) | 407 (L1) | 389 |
| FIX_ARC(v2: 7→4) | 398 (L1) | 369 |

## 3. Feedback localization

| Metric | First pass | After the clarification answer |
|---|---|---|
| Accuracy (majority target in GT list) | 90.0% ± 0.0 | 100.0% ± 0.0 |
| Accuracy, predicted high | 100.0% ± 0.0 | 100.0% ± 0.0 |
| Accuracy, predicted low | 66.7% ± 0.0 | n/a |
| Predicted high / low per run | [7, 7, 7] / [3, 3, 3] | [10, 10, 10] high |
| Clarifying-question rate | 30.0% ± 0.0 | 0.0% ± 0.0 |
| Invalid samples | 0.0% ± 0.0 | 0.0% ± 0.0 |
| Modification type correct | 100.0% ± 0.0 | |

Low-confidence results that carried a critique: 0 (must be 0).

Expected vs predicted confidence (first pass, per run):

- run 0: expected high → high 7, low 0; expected low → high 0, low 3
- run 1: expected high → high 7, low 0; expected low → high 0, low 3
- run 2: expected high → high 7, low 0; expected low → high 0, low 3

| Case | Clarity | GT targets | Run 0 / 1 / 2: confidence, majority target | After clarification |
|---|---|---|---|---|
| T1 | clear | L[2] | high, L[2] / high, L[2] / high, L[2] | high, L[2] / high, L[2] / high, L[2] |
| T2 | ambiguous | W[1] | low, W[1] / low, W[1] / low, W[1] | high, W[1] / high, W[1] / high, W[1] |
| T3 | clear | A[6] | high, A[6] / high, A[6] / high, A[6] | high, A[6] / high, A[6] / high, A[6] |
| T4 | clear | A[3] | high, A[3] / high, A[3] / high, A[3] | high, A[3] / high, A[3] / high, A[3] |
| T5 | clear | demand[4] | high, demand[4] / high, demand[4] / high, demand[4] | high, demand[4] / high, demand[4] / high, demand[4] |
| T6 | ambiguous | demand[7] | low, demand[7] / low, demand[7] / low, demand[7] | high, demand[7] / high, demand[7] / high, demand[7] |
| T7 | clear | balance | high, balance / high, balance / high, balance | high, balance / high, balance / high, balance |
| T8 | ambiguous | load_balance | low, balance ✗ / low, balance ✗ / low, balance ✗ | high, load_balance / high, load_balance / high, load_balance |
| T9 | clear | same[4,5], sep[4,5] | high, same[4,5] / high, same[4,5] / high, same[4,5] | high, same[4,5] / high, same[4,5] / high, same[4,5] |
| T10 | clear | e[6,8] | high, e[6,8] / high, e[6,8] / high, e[6,8] | high, e[6,8] / high, e[6,8] / high, e[6,8] |

