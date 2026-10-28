# Task 3 results, protocol task3_v31 (dev cases)

Trials: 33 in `results/pilot_v31`. Design: DESIGN_V31.md (main and stratum analyses as DESIGN_V3.md section 5).

## 1. Convergence within 3 iterations (primary)

| Config | Mean ± std over runs | Per run | At iteration 1 | Mean iterations | Excess km when converged | Requests / tokens per trial (localization incl.) |
|---|---|---|---|---|---|---|
| A0B0C0 | 100.0% ± 0.0 | 100% | 66.7% | 1.3333 | 0.0 | 1.33 / 2300 |
| A0B0C1 | 100.0% ± 0.0 | 100% | 33.3% | 1.6667 | 0.0 | 8.33 / 13534 |
| A0B1C0 | 100.0% ± 0.0 | 100% | 33.3% | 1.6667 | 0.0 | 6.67 / 12770 |
| A0B1C1 | 100.0% ± 0.0 | 100% | 100.0% | 1 | 0.0 | 10.67 / 18048 |
| A1B0C0 | 100.0% ± 0.0 | 100% | 66.7% | 1.3333 | 0.0 | 1.33 / 8828 |
| A1B0C1 | 100.0% ± 0.0 | 100% | 100.0% | 1 | 0.0 | 7.67 / 17688 |
| A1B1C0 | 100.0% ± 0.0 | 100% | 66.7% | 1.3333 | 0.0 | 5.33 / 36064 |
| A1B1C1 | 100.0% ± 0.0 | 100% | 100.0% | 1 | 0.0 | 10.67 / 40504 |
| S1a | 100.0% ± 0.0 | 100% | 33.3% | 1.6667 | 0.0 | 6.67 / 11796 |
| S1b | 100.0% ± 0.0 | 100% | 100.0% | 1 | 0.0 | 10.67 / 39929 |
| S2a | 100.0% ± 0.0 | 100% | 100.0% | 1 | 0.0 | 7.67 / 11938 |

## 2. Mechanism effects (case-clustered bootstrap, 95% CI)

| Effect | Within 3 iterations | At iteration 1 |
|---|---|---|
| main_A | +0.0 pp [+0.0, +0.0] | +25.0 pp [+0.0, +50.0] |
| main_B | +0.0 pp [+0.0, +0.0] | +8.3 pp [+0.0, +25.0] |
| main_C | +0.0 pp [+0.0, +0.0] | +25.0 pp [-25.0, +100.0] |
| interaction_AB | +0.0 pp [+0.0, +0.0] | -16.7 pp [-50.0, +0.0] |
| interaction_AC | +0.0 pp [+0.0, +0.0] | +16.7 pp [-0.0, +50.0] |
| interaction_BC | +0.0 pp [+0.0, +0.0] | +50.0 pp [+0.0, +100.0] |

**Pre-registered rule (primary):** At 10 cases and 1 runs per configuration, no mechanism can be singled out.  
**Same rule at iteration 1 (secondary):** At 10 cases and 1 runs per configuration, no mechanism can be singled out.

## 3. By stratum (pre-registered, descriptive)

| Stratum | A | B | C | A at t=1 | B at t=1 | C at t=1 |
|---|---|---|---|---|---|---|
| ambiguity | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +100.0 pp [+100.0, +100.0] |
| side | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +0.0 pp [+0.0, +0.0] | +37.5 pp [+25.0, +50.0] | +12.5 pp [+0.0, +25.0] | -12.5 pp [-25.0, +0.0] |

| Stratum | A0B0C0 | A0B0C1 | A0B1C0 | A0B1C1 | A1B0C0 | A1B0C1 | A1B1C0 | A1B1C1 |
|---|---|---|---|---|---|---|---|---|
| ambiguity | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| side | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |

## 4. Per case (converged runs)

| Case | Stratum | A0B0C0 | A0B0C1 | A0B1C0 | A0B1C1 | A1B0C0 | A1B0C1 | A1B1C0 | A1B1C1 | S1a | S1b | S2a |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P3 | ambiguity | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| P6 | side | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| P10 | side | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

## 5. Paired comparisons (exact McNemar over (case, run) pairs)

| Slice | Comparison | Pairs | Only first | Only second | p |
|---|---|---|---|---|---|
| full_minus | A1B1C1 vs A0B1C1 | 3 | 0 | 0 | 1.0 |
| full_minus | A1B1C1 vs A1B0C1 | 3 | 0 | 0 | 1.0 |
| full_minus | A1B1C1 vs A1B1C0 | 3 | 0 | 0 | 1.0 |
| bare_plus | A1B0C0 vs A0B0C0 | 3 | 0 | 0 | 1.0 |
| bare_plus | A0B1C0 vs A0B0C0 | 3 | 0 | 0 | 1.0 |
| bare_plus | A0B0C1 vs A0B0C0 | 3 | 0 | 0 | 1.0 |

Shared localizations: 3, asked 1; final high-confidence and correct 3, high but wrong 0, still low 0.

## 6. Pre-registered v3.1 questions (DESIGN_V31.md section 4)

**Question 1 (A):** no harm from A detectable in the side stratum (interval includes 0).

A by side case (converged / trials over the 8 main configurations):

| Case | A0 | A1 |
|---|---|---|
| P6 | 4/4 | 4/4 |
| P10 | 4/4 | 4/4 |

Valid proposals that write a session modification again (cases with session modifications): P10 {'A0': '0/12 (0%)', 'A1': '0/8 (0%)'}

**Question 2 (where B's effect comes from):** cannot be separated (both intervals include 0).

### Probe vs blind

| Pairs | Scope | Within 3 iterations | At iteration 1 |
|---|---|---|---|
| pooled | all | 100% vs 100% (6 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 67% vs 67% (6 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| pooled | side | 100% vs 100% (4 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 75% vs 75% (4 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| pooled | ambiguity | 100% vs 100% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 50% vs 50% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| A0B1C0 vs S1a | all | 100% vs 100% (3 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 33% vs 33% (3 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| A0B1C0 vs S1a | side | 100% vs 100% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 50% vs 50% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| A0B1C0 vs S1a | ambiguity | 100% vs 100% (1 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 0% vs 0% (1 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| A1B1C1 vs S1b | all | 100% vs 100% (3 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 100% (3 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| A1B1C1 vs S1b | side | 100% vs 100% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 100% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| A1B1C1 vs S1b | ambiguity | 100% vs 100% (1 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 100% (1 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |

### Blind vs single candidate

| Pairs | Scope | Within 3 iterations | At iteration 1 |
|---|---|---|---|
| pooled | all | 100% vs 100% (6 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 67% vs 83% (6 pairs): -16.7 pp [-50.0, +0.0], 0 vs 1, p = 1.0 |
| pooled | side | 100% vs 100% (4 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 75% vs 100% (4 pairs): -25.0 pp [-50.0, +0.0], 0 vs 1, p = 1.0 |
| pooled | ambiguity | 100% vs 100% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 50% vs 50% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| S1a vs A0B0C0 | all | 100% vs 100% (3 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 33% vs 67% (3 pairs): -33.3 pp [-100.0, +0.0], 0 vs 1, p = 1.0 |
| S1a vs A0B0C0 | side | 100% vs 100% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 50% vs 100% (2 pairs): -50.0 pp [-100.0, +0.0], 0 vs 1, p = 1.0 |
| S1a vs A0B0C0 | ambiguity | 100% vs 100% (1 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 0% vs 0% (1 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| S1b vs A1B0C1 | all | 100% vs 100% (3 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 100% (3 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| S1b vs A1B0C1 | side | 100% vs 100% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 100% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| S1b vs A1B0C1 | ambiguity | 100% vs 100% (1 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 100% (1 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |

### Structured localization vs answer as text (question 3)

| Pairs | Scope | Within 3 iterations | At iteration 1 |
|---|---|---|---|
| pooled | all | 100% vs 100% (3 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 33% vs 100% (3 pairs): -66.7 pp [-100.0, +0.0], 0 vs 2, p = 0.5 |
| pooled | side | 100% vs 100% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 0% vs 100% (2 pairs): -100.0 pp [-100.0, -100.0], 0 vs 2, p = 0.5 |
| pooled | ambiguity | 100% vs 100% (1 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 100% (1 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| A0B0C1 vs S2a | all | 100% vs 100% (3 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 33% vs 100% (3 pairs): -66.7 pp [-100.0, +0.0], 0 vs 2, p = 0.5 |
| A0B0C1 vs S2a | side | 100% vs 100% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 0% vs 100% (2 pairs): -100.0 pp [-100.0, -100.0], 0 vs 2, p = 0.5 |
| A0B0C1 vs S2a | ambiguity | 100% vs 100% (1 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 100% (1 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |

### Answer before iteration 1 vs after the first failure (question 3)

| Pairs | Scope | Within 3 iterations | At iteration 1 |
|---|---|---|---|
| pooled | all | 100% vs 100% (3 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 67% (3 pairs): +33.3 pp [+0.0, +100.0], 1 vs 0, p = 1.0 |
| pooled | side | 100% vs 100% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 100% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| pooled | ambiguity | 100% vs 100% (1 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 0% (1 pairs): +100.0 pp [+100.0, +100.0], 1 vs 0, p = 1.0 |
| S2a vs A0B0C0 | all | 100% vs 100% (3 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 67% (3 pairs): +33.3 pp [+0.0, +100.0], 1 vs 0, p = 1.0 |
| S2a vs A0B0C0 | side | 100% vs 100% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 100% (2 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 |
| S2a vs A0B0C0 | ambiguity | 100% vs 100% (1 pairs): +0.0 pp [+0.0, +0.0], 0 vs 0, p = 1.0 | 100% vs 0% (1 pairs): +100.0 pp [+100.0, +100.0], 1 vs 0, p = 1.0 |
