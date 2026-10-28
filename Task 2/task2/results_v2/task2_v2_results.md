# Task 2 results, protocol task2_v2

Fixed attribution (audit F1), fair counterfactual timing (F4) and the localization rule that counts only what the user can answer (F5, Task 4's T7). task2_v1's results (`results/`) are unchanged and quoted beside v2.

## 1. Decision attribution

### 1.1 The 10 test cases (same ground truth as v1)

| | v1 | v2 |
|---|---|---|
| Returned set contains the ground truth | 10/10 | 10/10 |
| Pooled precision / recall | 1.000 / 1.000 | 1.000 / 1.000 |

LLM explanation passes the number and entity checks: v1 100.0% ± 0.0, v2 100.0% ± 0.0 (first attempt 100.0%; template fallbacks 0).

### 1.2 Where v1 was wrong: plans under soft constraints and weights

The 10 test cases are optimal plans of the unmodified model, where vehicle labels and driving direction do not change the objective; the 10/10 above says nothing about other plans. Here every ADJ, SAME and SEP decision is attributed on 24 plans that carry soft constraints, weights or corrected data: the 10 reference-fix plans and the 14 Task 3 loop states where condition A ran at iteration 2 or 3. Ground truth: brute force (no Gurobi), with labels free for v1 (what v1 solves) and under the anchor v2 chose for v2.

| | v1 | v2 |
|---|---|---|
| Decisions | 912 | 912 |
| Forced by capacity, conclusion correct | 27/27 | 27/27 |
| Objective of the alternative correct | 83.2% (736/885) | 100.0% (885/885) |
| Edge set correct | 885/885 | 885/885 |
| A cheaper plan exists without the decision | 96 (all called objective_preferred: 96) | 0 |

v1's wrong numbers by plan: {'reference_fix/T1': 22, 'reference_fix/T2': 32, 'reference_fix/T3': 10, 'reference_fix/T4': 23, 'task3_loop/A1B0C0/T2/r3/t3': 23, 'task3_loop/A1B1C0/T2/r2/t2': 2, 'task3_loop/A1B1C0/T2/r2/t3': 37}. Largest error: (46500.0, 'task3_loop/A1B1C0/T2/r2/t3', {'type': 'SEP', 'i': 6, 'j': 7}, 47418, 918.0).
v2's anchor claim (the current plan is optimal under the chosen anchor) checked by brute force: 912/912.

## 2. Counterfactual: escalation rule and timing with equal set-up

warm: the model of the state is built once, before the timed calls; cold: built inside every call. local_v1 is the frozen rule, local_v2 is Task 3's (the probe the TPO loop uses), full frees every customer and has no MIP start. task2_v1 timed local warm against full cold.

### 10 test-case queries

| Method / set-up | Feasibility | Objective within 1% | Change set | Levels | Median / mean / p95 ms |
|---|---|---|---|---|---|
| full/cold | 10/10 | 8/8 | 8/8 | - | 37.9 / 32.7 / 53.7 |
| full/warm | 10/10 | 8/8 | 8/8 | - | 35.6 / 31.0 / 52.3 |
| local_v1/cold | 10/10 | 7/8 | 6/8 | {'L0': 4, 'L2': 4} | 13.4 / 22.0 / 55.7 |
| local_v1/warm | 10/10 | 7/8 | 6/8 | {'L0': 4, 'L2': 4} | 12.8 / 21.6 / 63.8 |
| local_v2/cold | 10/10 | 8/8 | 7/8 | {'L1': 1, 'L2': 4, 'L0': 3} | 16.3 / 22.5 / 54.9 |
| local_v2/warm | 10/10 | 8/8 | 7/8 | {'L1': 1, 'L2': 4, 'L0': 3} | 14.9 / 22.1 / 63.5 |

### 120 supplementary queries (every MOVE and FIX_ARC on the reference optimum)

| Method / set-up | Feasibility | Objective within 1% | Change set | Levels | Median / mean / p95 ms |
|---|---|---|---|---|---|
| full/cold | 120/120 | 101/101 | 101/101 | - | 6.3 / 11.5 / 39.2 |
| full/warm | 120/120 | 101/101 | 101/101 | - | 4.9 / 10.2 / 38.0 |
| local_v1/cold | 120/120 | 87/101 | 83/101 | {'L1': 35, 'L2': 42, 'L0': 24} | 4.3 / 7.1 / 26.3 |
| local_v1/warm | 120/120 | 87/101 | 83/101 | {'L1': 35, 'L2': 42, 'L0': 24} | 2.8 / 5.7 / 23.4 |
| local_v2/cold | 120/120 | 87/101 | 83/101 | {'L1': 35, 'L2': 42, 'L0': 24} | 4.2 / 7.2 / 26.1 |
| local_v2/warm | 120/120 | 87/101 | 83/101 | {'L1': 35, 'L2': 42, 'L0': 24} | 2.8 / 5.7 / 23.4 |

## 3. Feedback localization

### 3.1 The v2 rule on v1's samples

Same 5 samples per complaint, only the rule changes: 60/60 decisions (10 cases x 3 runs x first pass and clarified pass) are the same as v1's; changed: none.

Task 4's T7 (`A1B1C1`, task4_v1 end-to-end run), the complaint the frozen rule stopped:

| Pass | v1 | Modification types in the samples | v2 | v2 critique |
|---|---|---|---|---|
| initial | low | {'set_objective_weight': 2, 'add_soft_constraint': 3} | high | {'target': 'balance', 'modification_type': 'add_soft_constraint', 'threshold': 50} |
| after_clarification | low | {'set_objective_weight': 2, 'add_soft_constraint': 3} | high | {'target': 'balance', 'modification_type': 'add_soft_constraint', 'threshold': 50} |

### 3.2 Fresh v2 run (3 runs, new samples)

| Metric | v1 | v2 |
|---|---|---|
| Accuracy, first pass | 90.0% ± 0.0 | 90.0% ± 0.0 |
| Accuracy, predicted high | 100.0% | 100.0% |
| Predicted high / low per run | [7, 7, 7] / [3, 3, 3] | [7, 7, 7] / [3, 3, 3] |
| Clarifying-question rate | 30.0% | 30.0% |
| Accuracy after the clarification answer | 100.0% | 100.0% |
| Modification type correct | 100.0% | 100.0% |
| Low-confidence results that carried a critique | 0 | 0 |

Questions asked in the v2 run:

- run 0 T2 (none): Do you mean vehicle 1's load (99 units), its route length (140 km), or its number of stops (4) is too high?
- run 0 T6 (none): Which value for customer 7 should be 18: its demand, x-coordinate, or y-coordinate?
- run 0 T8 (none): Do you want to balance the route distances (km driven) or the loads (units carried) between the two vehicles?
- run 1 T2 (none): Do you mean vehicle 1 is carrying too much load (99 units) or driving too many kilometers (140 km)?
- run 1 T6 (none): Which attribute of customer 7 should be corrected to 18: its demand, x-coordinate, y-coordinate, or direct distance from the depot?
- run 1 T8 (none): Do you mean the difference in route lengths (km driven) or the difference in loads (units carried) between the two vehicles?
- run 2 T2 (none): Do you mean vehicle 1 is carrying too much load (99 units) or driving too far (140 km)?
- run 2 T6 (none): Which attribute of customer 7 should be 18—its demand, or one of its coordinates?
- run 2 T8 (none): Do you mean the difference in route lengths (km driven) or the difference in loads (units carried) between the two vehicles?

