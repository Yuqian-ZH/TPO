# Task 3 results, protocol task3_v3 (dev cases)

Trials: 40 in `results/pilot_v3b`. Design: DESIGN_V3.md; analyses as pre-registered there.

## 1. Convergence within 3 iterations (primary)

| Config | Mean ± std over runs | Per run | At iteration 1 | Mean iterations | Excess km when converged | Requests / tokens per trial (localization incl.) |
|---|---|---|---|---|---|---|
| A0B0C0 | 90.0% ± 0.0 | 90% / 90% | 65.0% | 1.3889 | 0.0 | 1.55 / 2809 |
| A1B1C1 | 95.0% ± 7.1 | 100% / 90% | 80.0% | 1.1579 | 0.0 | 5 / 30935 |

## 4. Per case (converged runs)

| Case | Stratum | A0B0C0 | A1B1C1 |
|---|---|---|---|
| P1 | control | 2 | 2 |
| P2 | control | 2 | 2 |
| P3 | ambiguity | 2 | 2 |
| P4 | ambiguity | 2 | 2 |
| P5 | ambiguity | 2 | 2 |
| P6 | side | 2 | 2 |
| P7 | side | 0 | 1 |
| P8 | side | 2 | 2 |
| P9 | side | 2 | 2 |
| P10 | side | 2 | 2 |

## 5. Paired comparisons (exact McNemar over (case, run) pairs)

| Slice | Comparison | Pairs | Only first | Only second | p |
|---|---|---|---|---|---|

Shared localizations: 20, asked 8; final high-confidence and correct 18, high but wrong 2, still low 0.
