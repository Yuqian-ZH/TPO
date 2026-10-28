# Task 2 results, protocol task2_v3

The 10 test cases of DESIGN_V3.md (2 control, 3 ambiguity, 5 side), task2_v2.1's components. Ground truth by brute force.

## 1. Decision attribution

- Returned set contains the ground truth: 10/10
- Pooled precision / recall: 1.000 / 1.000; macro 1.000 / 1.000

| Case | Decision | Conclusion | GT conclusion | Contains GT | P | R |
|---|---|---|---|---|---|---|
| U1 | SEP(1,3) | hard_constraint_forced | capacity_forced | True | 1.00 | 1.00 |
| U2 | ADJ(6,8) | objective_preferred | objective_preferred | True | 1.00 | 1.00 |
| U3 | SAME(1,2) | objective_preferred | objective_preferred | True | 1.00 | 1.00 |
| U4 | ADJ(2,7) | objective_preferred | objective_preferred | True | 1.00 | 1.00 |
| U5 | SAME(2,7) | objective_preferred | objective_preferred | True | 1.00 | 1.00 |
| U6 | ADJ(3,6) | objective_preferred | objective_preferred | True | 1.00 | 1.00 |
| U7 | SEP(2,5) | objective_preferred | objective_preferred | True | 1.00 | 1.00 |
| U8 | SEP(2,5) | objective_preferred | objective_preferred | True | 1.00 | 1.00 |
| U9 | SEP(1,3) | hard_constraint_forced | capacity_forced | True | 1.00 | 1.00 |
| U10 | ADJ(2,7) | objective_preferred | objective_preferred | True | 1.00 | 1.00 |

LLM explanation passes the number and entity checks: 100.0% ± 0.0 (first attempt 100.0%; template fallbacks 0).

## 2. Counterfactual

Per case: the what-if query, the reference fix and the direct (or misread) encoding as APPLY_MODIFICATIONS queries. Against brute force under the same anchor.

### what_if

| Method / set-up | Feasibility | Objective within 1% | Change set | Levels | Median / mean / p95 ms |
|---|---|---|---|---|---|
| full/cold | 10/10 | 8/8 | 8/8 | - | 25.3 / 26.7 / 54.5 |
| full/warm | 10/10 | 8/8 | 8/8 | - | 23.8 / 25.3 / 53.7 |
| local_v1/cold | 10/10 | 6/8 | 5/8 | {'L0': 4, 'L2': 3, 'L1': 1} | 5.4 / 14.8 / 55.2 |
| local_v1/warm | 10/10 | 6/8 | 5/8 | {'L0': 4, 'L2': 3, 'L1': 1} | 3.8 / 14.3 / 64.0 |
| local_v2/cold | 10/10 | 7/8 | 6/8 | {'L1': 2, 'L0': 3, 'L2': 3} | 5.4 / 15.2 / 54.8 |
| local_v2/warm | 10/10 | 7/8 | 6/8 | {'L1': 2, 'L0': 3, 'L2': 3} | 3.8 / 14.9 / 63.3 |

### reference_fix

| Method / set-up | Feasibility | Objective within 1% | Change set | Levels | Median / mean / p95 ms |
|---|---|---|---|---|---|
| full/cold | 10/10 | 10/10 | 10/10 | - | 42.4 / 38.4 / 57.9 |
| full/warm | 10/10 | 10/10 | 10/10 | - | 40.7 / 36.9 / 56.2 |
| local_v1/cold | 10/10 | 7/10 | 6/10 | {'L0': 9, 'L1': 1} | 10.8 / 15.1 / 42.9 |
| local_v1/warm | 10/10 | 7/10 | 6/10 | {'L0': 9, 'L1': 1} | 9.4 / 13.9 / 41.0 |
| local_v2/cold | 10/10 | 10/10 | 8/10 | {'L1': 3, 'L0': 6, 'L2': 1} | 21.2 / 22.7 / 44.5 |
| local_v2/warm | 10/10 | 10/10 | 8/10 | {'L1': 3, 'L0': 6, 'L2': 1} | 19.5 / 21.1 / 43.1 |

### direct_or_misreading

| Method / set-up | Feasibility | Objective within 1% | Change set | Levels | Median / mean / p95 ms |
|---|---|---|---|---|---|
| full/cold | 10/10 | 10/10 | 10/10 | - | 52.2 / 49.7 / 58.7 |
| full/warm | 10/10 | 10/10 | 10/10 | - | 51.2 / 46.9 / 57.0 |
| local_v1/cold | 10/10 | 7/10 | 5/10 | {'L0': 10} | 5.8 / 22.7 / 67.9 |
| local_v1/warm | 10/10 | 7/10 | 5/10 | {'L0': 10} | 4.5 / 21.1 / 65.7 |
| local_v2/cold | 10/10 | 8/10 | 6/10 | {'L1': 2, 'L0': 6, 'L2': 2} | 22.8 / 32.6 / 77.6 |
| local_v2/warm | 10/10 | 8/10 | 6/10 | {'L1': 2, 'L0': 6, 'L2': 2} | 21.6 / 31.2 / 77.1 |

### all

| Method / set-up | Feasibility | Objective within 1% | Change set | Levels | Median / mean / p95 ms |
|---|---|---|---|---|---|
| full/cold | 30/30 | 28/28 | 28/28 | - | 43.0 / 38.3 / 57.8 |
| full/warm | 30/30 | 28/28 | 28/28 | - | 41.8 / 36.4 / 56.0 |
| local_v1/cold | 30/30 | 20/28 | 16/28 | {'L0': 23, 'L2': 3, 'L1': 2} | 5.9 / 17.5 / 58.4 |
| local_v1/warm | 30/30 | 20/28 | 16/28 | {'L0': 23, 'L2': 3, 'L1': 2} | 4.7 / 16.5 / 64.0 |
| local_v2/cold | 30/30 | 25/28 | 20/28 | {'L1': 7, 'L0': 15, 'L2': 6} | 19.0 / 23.5 / 66.6 |
| local_v2/warm | 30/30 | 25/28 | 20/28 | {'L1': 7, 'L0': 15, 'L2': 6} | 15.2 / 22.4 / 65.5 |

## 3. Feedback localization

| Metric | Value |
|---|---|
| Accuracy, first pass | 90.0% ± 0.0 |
| Accuracy, predicted high | 100.0% ± 0.0 |
| Accuracy, predicted low (first pass, before the question) | 80.0% ± 0.0 |
| Predicted high / low per run | [5, 5, 5] / [5, 5, 5] |
| Clarifying-question rate | 50.0% ± 0.0 |
| Accuracy after the clarification answer | 100.0% ± 0.0 |
| Modification type correct | 100.0% ± 0.0 |
| Low-confidence results that carried a critique | 0 |

| Stratum | First pass correct | Correct when high | After clarification |
|---|---|---|---|
| control | 6/6 | 6/6 | 6/6 |
| ambiguity | 6/9 | - | 9/9 |
| side | 15/15 | 9/9 | 15/15 |
