# Task 3 results, protocol task3_v31 (test cases)

Trials: 550 in `results/formal_v31`. Design: DESIGN_V31.md (main and stratum analyses as DESIGN_V3.md section 5).

## 1. Convergence within 3 iterations (primary)

| Config | Mean ± std over runs | Per run | At iteration 1 | Mean iterations | Excess km when converged | Requests / tokens per trial (localization incl.) |
|---|---|---|---|---|---|---|
| A0B0C0 | 96.0% ± 5.5 | 90% / 100% / 100% / 100% / 90% | 60.0% | 1.5208 | 3.23 | 1.58 / 2907 |
| A0B0C1 | 82.0% ± 10.9 | 80% / 80% / 80% / 100% / 70% | 68.0% | 1.2439 | 2.68 | 9.18 / 15130 |
| A0B1C0 | 94.0% ± 5.5 | 100% / 90% / 90% / 90% / 100% | 64.0% | 1.3404 | 2.34 | 5.76 / 11150 |
| A0B1C1 | 86.0% ± 5.5 | 90% / 80% / 90% / 90% / 80% | 66.0% | 1.3023 | 3.05 | 13.22 / 24278 |
| A1B0C0 | 98.0% ± 4.5 | 100% / 100% / 100% / 90% / 100% | 60.0% | 1.4694 | 2.67 | 1.5 / 11134 |
| A1B0C1 | 82.0% ± 13.0 | 90% / 80% / 60% / 90% / 90% | 70.0% | 1.1707 | 3.2 | 9.12 / 22365 |
| A1B1C0 | 98.0% ± 4.5 | 90% / 100% / 100% / 100% / 100% | 58.0% | 1.4694 | 2.67 | 5.98 / 45637 |
| A1B1C1 | 90.0% ± 7.1 | 100% / 80% / 90% / 90% / 90% | 68.0% | 1.2889 | 2.91 | 12.92 / 51648 |
| S1a | 86.0% ± 5.5 | 90% / 80% / 80% / 90% / 90% | 54.0% | 1.3953 | 4.51 | 6.46 / 11794 |
| S1b | 80.0% ± 12.2 | 80% / 70% / 70% / 100% / 80% | 62.0% | 1.275 | 3.27 | 13.56 / 55809 |
| S2a | 88.0% ± 8.4 | 90% / 90% / 80% / 100% / 80% | 74.0% | 1.2273 | 4.41 | 9.24 / 14950 |

## 2. Mechanism effects (case-clustered bootstrap, 95% CI)

| Effect | Within 3 iterations | At iteration 1 |
|---|---|---|
| main_A | +2.5 pp [-0.5, +6.5] | -0.5 pp [-7.0, +6.5] |
| main_B | +2.5 pp [-3.0, +8.5] | -0.5 pp [-6.0, +5.0] |
| main_C | -11.5 pp [-25.5, +0.0] | +7.5 pp [-17.5, +37.0] |
| interaction_AB | +3.0 pp [-1.0, +8.0] | -3.0 pp [-17.0, +11.0] |
| interaction_AC | -1.0 pp [-12.0, +9.0] | +5.0 pp [-7.0, +18.0] |
| interaction_BC | +7.0 pp [-1.0, +17.0] | -3.0 pp [-10.0, +4.0] |

**Pre-registered rule (primary):** At 10 cases and 5 runs per configuration, no mechanism can be singled out.  
**Same rule at iteration 1 (secondary):** At 10 cases and 5 runs per configuration, no mechanism can be singled out.

## 3. By stratum (pre-registered, descriptive)

| Stratum | A | B | C | A at t=1 | B at t=1 | C at t=1 |
|---|---|---|---|---|---|---|
| control | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] |
| ambiguity | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | -6.7 pp [-20.0, +0.0] | +0.0 pp [+0.0, +0.0] | +60.0 pp [+0.0, +100.0] |
| side | +5.0 pp [-1.0, +11.0] | +5.0 pp [-6.0, +17.0] | -23.0 pp [-43.0, -3.0] | +3.0 pp [-8.0, +14.0] | -1.0 pp [-12.0, +10.0] | -21.0 pp [-35.0, -7.0] |

| Stratum | A0B0C0 | A0B0C1 | A0B1C0 | A0B1C1 | A1B0C0 | A1B0C1 | A1B1C0 | A1B1C1 |
|---|---|---|---|---|---|---|---|---|
| control | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| ambiguity | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| side | 92% | 64% | 88% | 72% | 96% | 64% | 96% | 80% |

## 4. Per case (converged runs)

| Case | Stratum | A0B0C0 | A0B0C1 | A0B1C0 | A0B1C1 | A1B0C0 | A1B0C1 | A1B1C0 | A1B1C1 | S1a | S1b | S2a |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| U1 | control | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| U2 | control | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| U3 | ambiguity | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| U4 | ambiguity | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| U5 | ambiguity | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| U6 | side | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| U7 | side | 4 | 3 | 5 | 5 | 5 | 3 | 5 | 5 | 4 | 2 | 4 |
| U8 | side | 4 | 4 | 3 | 5 | 5 | 3 | 5 | 5 | 0 | 4 | 3 |
| U9 | side | 5 | 2 | 5 | 2 | 4 | 2 | 5 | 2 | 5 | 2 | 4 |
| U10 | side | 5 | 2 | 4 | 1 | 5 | 3 | 4 | 3 | 4 | 2 | 3 |

## 5. Paired comparisons (exact McNemar over (case, run) pairs)

| Slice | Comparison | Pairs | Only first | Only second | p |
|---|---|---|---|---|---|
| full_minus | A1B1C1 vs A0B1C1 | 50 | 2 | 0 | 0.5 |
| full_minus | A1B1C1 vs A1B0C1 | 50 | 6 | 2 | 0.2891 |
| full_minus | A1B1C1 vs A1B1C0 | 50 | 1 | 5 | 0.2188 |
| bare_plus | A1B0C0 vs A0B0C0 | 50 | 2 | 1 | 1.0 |
| bare_plus | A0B1C0 vs A0B0C0 | 50 | 2 | 3 | 1.0 |
| bare_plus | A0B0C1 vs A0B0C0 | 50 | 2 | 9 | 0.0654 |

Shared localizations: 50, asked 28; final high-confidence and correct 47, high but wrong 0, still low 3.

## 6. Pre-registered v3.1 questions (DESIGN_V31.md section 4)

**Question 1 (A):** no harm from A detectable in the side stratum (interval includes 0).

A by side case (converged / trials over the 8 main configurations):

| Case | A0 | A1 | v3 A0 | v3 A1 |
|---|---|---|---|---|
| U6 | 20/20 | 20/20 | 20/20 | 20/20 |
| U7 | 17/20 | 18/20 | 17/20 | 17/20 |
| U8 | 16/20 | 18/20 | 16/20 | 14/20 |
| U9 | 14/20 | 13/20 | 18/20 | 18/20 |
| U10 | 12/20 | 15/20 | 18/20 | 8/20 |

Valid proposals that write a session modification again (cases with session modifications): U9 {'A0': '43/43 (100%)', 'A1': '47/57 (82%)'}; U10 {'A0': '73/88 (83%)', 'A1': '29/77 (38%)'}
v3 for comparison: U9 {'A0': '50/54 (93%)', 'A1': '54/58 (93%)'}; U10 {'A0': '24/60 (40%)', 'A1': '82/103 (80%)'}

**Question 2 (where B's effect comes from):** cannot be separated (both intervals include 0).

### Probe vs blind

| Pairs | Scope | Within 3 iterations | At iteration 1 |
|---|---|---|---|
| pooled | all | 92% vs 83% (100 pairs): +9.0 pp [+0.0, +20.0], 11 vs 2, p = 0.0225 | 66% vs 58% (100 pairs): +8.0 pp [+2.0, +15.0], 14 vs 6, p = 0.1153 |
| pooled | side | 84% vs 66% (50 pairs): +18.0 pp [+2.0, +34.0], 11 vs 2, p = 0.0225 | 48% vs 32% (50 pairs): +16.0 pp [+6.0, +24.0], 13 vs 5, p = 0.0963 |
| pooled | ambiguity | 100% vs 100% (30 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 73% vs 73% (30 pairs): +0.0 pp [+0.0, +0.0], 1 vs 1, p = 1.0 |
| A0B1C0 vs S1a | all | 94% vs 86% (50 pairs): +8.0 pp [+0.0, +20.0], 5 vs 1, p = 0.2188 | 64% vs 54% (50 pairs): +10.0 pp [+0.0, +20.0], 8 vs 3, p = 0.2266 |
| A0B1C0 vs S1a | side | 88% vs 72% (25 pairs): +16.0 pp [+0.0, +40.0], 5 vs 1, p = 0.2188 | 60% vs 40% (25 pairs): +20.0 pp [+4.0, +36.0], 7 vs 2, p = 0.1797 |
| A0B1C0 vs S1a | ambiguity | 100% vs 100% (15 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 47% vs 47% (15 pairs): +0.0 pp [+0.0, +0.0], 1 vs 1, p = 1.0 |
| A1B1C1 vs S1b | all | 90% vs 80% (50 pairs): +10.0 pp [+0.0, +22.0], 6 vs 1, p = 0.125 | 68% vs 62% (50 pairs): +6.0 pp [+0.0, +12.0], 6 vs 3, p = 0.5078 |
| A1B1C1 vs S1b | side | 80% vs 60% (25 pairs): +20.0 pp [+4.0, +40.0], 6 vs 1, p = 0.125 | 36% vs 24% (25 pairs): +12.0 pp [+4.0, +20.0], 6 vs 3, p = 0.5078 |
| A1B1C1 vs S1b | ambiguity | 100% vs 100% (15 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 100% (15 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |

### Blind vs single candidate

| Pairs | Scope | Within 3 iterations | At iteration 1 |
|---|---|---|---|
| pooled | all | 83% vs 89% (100 pairs): -6.0 pp [-13.0, +0.0], 4 vs 10, p = 0.1796 | 58% vs 65% (100 pairs): -7.0 pp [-15.0, +0.0], 6 vs 13, p = 0.1671 |
| pooled | side | 66% vs 78% (50 pairs): -12.0 pp [-22.0, -2.0], 4 vs 10, p = 0.1796 | 32% vs 46% (50 pairs): -14.0 pp [-24.0, -2.0], 5 vs 12, p = 0.1435 |
| pooled | ambiguity | 100% vs 100% (30 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 73% vs 73% (30 pairs): +0.0 pp [+0.0, +0.0], 1 vs 1, p = 1.0 |
| S1a vs A0B0C0 | all | 86% vs 96% (50 pairs): -10.0 pp [-26.0, +0.0], 1 vs 6, p = 0.125 | 54% vs 60% (50 pairs): -6.0 pp [-12.0, +0.0], 4 vs 7, p = 0.5488 |
| S1a vs A0B0C0 | side | 72% vs 92% (25 pairs): -20.0 pp [-52.0, +0.0], 1 vs 6, p = 0.125 | 40% vs 52% (25 pairs): -12.0 pp [-20.0, -4.0], 3 vs 6, p = 0.5078 |
| S1a vs A0B0C0 | ambiguity | 100% vs 100% (15 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 47% vs 47% (15 pairs): +0.0 pp [+0.0, +0.0], 1 vs 1, p = 1.0 |
| S1b vs A1B0C1 | all | 80% vs 82% (50 pairs): -2.0 pp [-8.0, +4.0], 3 vs 4, p = 1.0 | 62% vs 70% (50 pairs): -8.0 pp [-20.0, +2.0], 2 vs 6, p = 0.2891 |
| S1b vs A1B0C1 | side | 60% vs 64% (25 pairs): -4.0 pp [-16.0, +8.0], 3 vs 4, p = 1.0 | 24% vs 40% (25 pairs): -16.0 pp [-36.0, +4.0], 2 vs 6, p = 0.2891 |
| S1b vs A1B0C1 | ambiguity | 100% vs 100% (15 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 100% (15 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |

### Structured localization vs answer as text (question 3)

| Pairs | Scope | Within 3 iterations | At iteration 1 |
|---|---|---|---|
| pooled | all | 82% vs 88% (50 pairs): -6.0 pp [-16.0, +2.0], 3 vs 6, p = 0.5078 | 68% vs 74% (50 pairs): -6.0 pp [-22.0, +8.0], 4 vs 7, p = 0.5488 |
| pooled | side | 64% vs 76% (25 pairs): -12.0 pp [-28.0, +8.0], 3 vs 6, p = 0.5078 | 36% vs 48% (25 pairs): -12.0 pp [-40.0, +16.0], 4 vs 7, p = 0.5488 |
| pooled | ambiguity | 100% vs 100% (15 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 100% (15 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| A0B0C1 vs S2a | all | 82% vs 88% (50 pairs): -6.0 pp [-16.0, +2.0], 3 vs 6, p = 0.5078 | 68% vs 74% (50 pairs): -6.0 pp [-22.0, +8.0], 4 vs 7, p = 0.5488 |
| A0B0C1 vs S2a | side | 64% vs 76% (25 pairs): -12.0 pp [-28.0, +8.0], 3 vs 6, p = 0.5078 | 36% vs 48% (25 pairs): -12.0 pp [-40.0, +16.0], 4 vs 7, p = 0.5488 |
| A0B0C1 vs S2a | ambiguity | 100% vs 100% (15 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 100% (15 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |

### Answer before iteration 1 vs after the first failure (question 3)

| Pairs | Scope | Within 3 iterations | At iteration 1 |
|---|---|---|---|
| pooled | all | 88% vs 96% (50 pairs): -8.0 pp [-18.0, +0.0], 2 vs 6, p = 0.2891 | 74% vs 60% (50 pairs): +14.0 pp [-8.0, +40.0], 12 vs 5, p = 0.1435 |
| pooled | side | 76% vs 92% (25 pairs): -16.0 pp [-28.0, -4.0], 2 vs 6, p = 0.2891 | 48% vs 52% (25 pairs): -4.0 pp [-20.0, +20.0], 4 vs 5, p = 1.0 |
| pooled | ambiguity | 100% vs 100% (15 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 47% (15 pairs): +53.3 pp [+0.0, +100.0], 8 vs 0, p = 0.0078 |
| S2a vs A0B0C0 | all | 88% vs 96% (50 pairs): -8.0 pp [-18.0, +0.0], 2 vs 6, p = 0.2891 | 74% vs 60% (50 pairs): +14.0 pp [-8.0, +40.0], 12 vs 5, p = 0.1435 |
| S2a vs A0B0C0 | side | 76% vs 92% (25 pairs): -16.0 pp [-28.0, -4.0], 2 vs 6, p = 0.2891 | 48% vs 52% (25 pairs): -4.0 pp [-20.0, +20.0], 4 vs 5, p = 1.0 |
| S2a vs A0B0C0 | ambiguity | 100% vs 100% (15 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 47% (15 pairs): +53.3 pp [+0.0, +100.0], 8 vs 0, p = 0.0078 |

## 7. Beside task3_v3 (not pooled, not tested)

| Config | U1-U8 v3 (runs 1-5) | U1-U8 v3.1 (runs 6-10) | U9-U10 v3 | U9-U10 v3.1 |
|---|---|---|---|---|
| A0B0C0 | 39/40 | 38/40 | 9/10 | 10/10 |
| A0B0C1 | 36/40 | 37/40 | 9/10 | 4/10 |
| A0B1C0 | 39/40 | 38/40 | 10/10 | 9/10 |
| A0B1C1 | 39/40 | 40/40 | 8/10 | 3/10 |
| A1B0C0 | 36/40 | 40/40 | 7/10 | 9/10 |
| A1B0C1 | 36/40 | 36/40 | 5/10 | 5/10 |
| A1B1C0 | 39/40 | 40/40 | 6/10 | 9/10 |
| A1B1C1 | 40/40 | 40/40 | 8/10 | 5/10 |
