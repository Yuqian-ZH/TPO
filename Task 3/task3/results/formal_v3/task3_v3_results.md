# Task 3 results, protocol task3_v3 (test cases)

Trials: 400 in `results/formal_v3`. Design: DESIGN_V3.md; analyses as pre-registered there.

## 1. Convergence within 3 iterations (primary)

| Config | Mean ± std over runs | Per run | At iteration 1 | Mean iterations | Excess km when converged | Requests / tokens per trial (localization incl.) |
|---|---|---|---|---|---|---|
| A0B0C0 | 96.0% ± 5.5 | 100% / 100% / 100% / 90% / 90% | 62.0% | 1.4583 | 5.02 | 1.52 / 2718 |
| A0B0C1 | 90.0% ± 14.1 | 100% / 100% / 80% / 100% / 70% | 82.0% | 1.1111 | 2.98 | 8.64 / 14042 |
| A0B1C0 | 98.0% ± 4.5 | 100% / 100% / 90% / 100% / 100% | 64.0% | 1.3673 | 3.53 | 5.56 / 10499 |
| A0B1C1 | 94.0% ± 5.5 | 90% / 90% / 100% / 100% / 90% | 80.0% | 1.1915 | 2.34 | 12.34 / 22058 |
| A1B0C0 | 86.0% ± 5.5 | 80% / 90% / 90% / 80% / 90% | 54.0% | 1.3953 | 3.56 | 1.62 / 12255 |
| A1B0C1 | 82.0% ± 8.4 | 70% / 90% / 90% / 80% / 80% | 68.0% | 1.2683 | 4.0 | 8.92 / 23336 |
| A1B1C0 | 90.0% ± 7.1 | 90% / 100% / 90% / 80% / 90% | 60.0% | 1.3556 | 2.91 | 6.08 / 47082 |
| A1B1C1 | 96.0% ± 5.5 | 90% / 100% / 100% / 100% / 90% | 86.0% | 1.1458 | 3.17 | 12.04 / 47736 |

## 2. Mechanism effects (case-clustered bootstrap, 95% CI)

| Effect | Within 3 iterations | At iteration 1 |
|---|---|---|
| main_A | -6.0 pp [-16.0, +0.0] | -5.0 pp [-18.0, +5.0] |
| main_B | +6.0 pp [+0.0, +13.0] | +6.0 pp [-1.0, +14.5] |
| main_C | -2.0 pp [-8.0, +4.0] | +19.0 pp [+0.0, +44.0] |
| interaction_AB | +6.0 pp [+0.0, +12.0] | +12.0 pp [+2.0, +23.0] |
| interaction_AC | +6.0 pp [+0.0, +12.0] | +2.0 pp [-12.0, +15.0] |
| interaction_BC | +6.0 pp [+0.0, +12.0] | +4.0 pp [-7.0, +16.0] |

**Pre-registered rule (primary):** At 10 cases and 5 runs per configuration, no mechanism can be singled out.  
**Same rule at iteration 1 (secondary):** At 10 cases and 5 runs per configuration, no mechanism can be singled out.

## 3. By stratum (pre-registered, descriptive)

| Stratum | A | B | C | A at t=1 | B at t=1 | C at t=1 |
|---|---|---|---|---|---|---|
| control | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] |
| ambiguity | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | -5.0 pp [-10.0, +0.0] | -1.7 pp [-10.0, +5.0] | +61.7 pp [+5.0, +100.0] |
| side | -12.0 pp [-32.0, +0.0] | +12.0 pp [+2.0, +22.0] | -4.0 pp [-16.0, +8.0] | -7.0 pp [-31.0, +13.0] | +13.0 pp [+2.0, +26.0] | +1.0 pp [-6.0, +7.0] |

| Stratum | A0B0C0 | A0B0C1 | A0B1C0 | A0B1C1 | A1B0C0 | A1B0C1 | A1B1C0 | A1B1C1 |
|---|---|---|---|---|---|---|---|---|
| control | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| ambiguity | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| side | 92% | 80% | 96% | 88% | 72% | 64% | 80% | 92% |

## 4. Per case (converged runs)

| Case | Stratum | A0B0C0 | A0B0C1 | A0B1C0 | A0B1C1 | A1B0C0 | A1B0C1 | A1B1C0 | A1B1C1 |
|---|---|---|---|---|---|---|---|---|---|
| U1 | control | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| U2 | control | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| U3 | ambiguity | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| U4 | ambiguity | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| U5 | ambiguity | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| U6 | side | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| U7 | side | 5 | 3 | 5 | 4 | 4 | 3 | 5 | 5 |
| U8 | side | 4 | 3 | 4 | 5 | 2 | 3 | 4 | 5 |
| U9 | side | 5 | 4 | 5 | 4 | 5 | 4 | 5 | 4 |
| U10 | side | 4 | 5 | 5 | 4 | 2 | 1 | 1 | 4 |

## 5. Paired comparisons (exact McNemar over (case, run) pairs)

| Slice | Comparison | Pairs | Only first | Only second | p |
|---|---|---|---|---|---|
| full_minus | A1B1C1 vs A0B1C1 | 50 | 2 | 1 | 1.0 |
| full_minus | A1B1C1 vs A1B0C1 | 50 | 7 | 0 | 0.0156 |
| full_minus | A1B1C1 vs A1B1C0 | 50 | 4 | 1 | 0.375 |
| bare_plus | A1B0C0 vs A0B0C0 | 50 | 2 | 7 | 0.1797 |
| bare_plus | A0B1C0 vs A0B0C0 | 50 | 2 | 1 | 1.0 |
| bare_plus | A0B0C1 vs A0B0C0 | 50 | 2 | 5 | 0.4531 |

Shared localizations: 50, asked 24; final high-confidence and correct 49, high but wrong 0, still low 1.
