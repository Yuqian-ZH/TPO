# Pause point 2 review: the 10 test cases finalized

- Date: 2026-10-23
- Reviewer: Claude (authorized by the user: "You decide; analyse carefully and settle the result")
- Conclusion: **all 10 test cases adopted unchanged**, `cases/test_cases.json` frozen (SHA-256 `43b31ce63a556e1cc309daef31a4812238499ec2479112a0fd6b52860214ecea`, recorded in `FROZEN.json`)
- One development case (D1) was adjusted at the same time; development cases may keep changing under the plan and are not frozen

## 1. What was reviewed

| Check | Method | Result |
|---|---|---|
| Numbers in the complaints match the solution | compared one by one with `solution_metrics` (211, 99, 95, 60, 167, 107, 106, ...) | all match |
| The initial solution fails the checker | `verify_cases.py` | 10/10 |
| The reference modification removes the complaint | enumeration: after the modification **every** optimal plan passes the checker; Gurobi: its optimal plan passes and its objective equals the enumerated one | 10/10 |
| A complaint cannot be removed for free by reversing a whole route | the checker run on the 3 reversal combinations of the two routes | 10/10 cannot |
| Attribution ground truth is unique | the optimum with the decision forbidden has a single edge-difference set | 10/10 unique |
| Counterfactual ground truth is unique | after the anchored solve there is a single acceptable change set (excluding the 2 infeasible ones) | 8/8 unique |
| Attribution ground truth agrees with Gurobi | objective preference: Δ and edge difference agree; capacity forced: the concrete business constraints in the IIS are `{cap[1], cap[2]}` | 10/10 |
| Counterfactual ground truth agrees with Gurobi | feasibility, objective, change set | 10/10 |
| IDs and JSON Schema | `ids.py`, `schemas/{decision,query,modification}` | all exist, all pass |
| The validators are not vacuous | 7 kinds of tampering in pytest (threshold, penalty, Δ, change, target ID, confidence, decision type) are all caught | 7/7 |
| §5.3 coverage requirements | see section 3 | all met |

## 2. Case by case

| Case | Content | Review notes | Verdict |
|---|---|---|---|
| T1 | vehicle 2's route is 211 km, required ≤ 180 | Clear; the object is a vehicle. The localization ground truth accepts only `L[2]`: `makespan` has the same value now but means "the longest route", not vehicle 2 as named by the complaint. After the fix vehicle 1 becomes 207 km, which does not violate the complaint (it is only about vehicle 2) | adopted |
| T2 | "Vehicle 1 is doing too much work." | The task's own example. Vehicle 1 drives less and has the same number of stops; only its load (99) is high, clarified as load ≤ 92. The answer to the counterfactual "move 7 to vehicle 2" has 6 customers switching vehicles, a consequence of the anchor convention (vehicle 1 = the route containing customer 1), which tests whether the local and the full solve agree on vehicle numbering | adopted |
| T3 | customer 6 is detoured (straight line 47, actual 95) | detour ratio 2.02 forwards and 2.47 in reverse; reversal does not remove it | adopted |
| T4 | customer 3 should be reached within the first 30 km (now 60) | the attribution `SEP(1,3)` is the only capacity-forced decision on the base data; the counterfactual "move 3 to vehicle 1" is infeasible by capacity | adopted |
| T5 | customer 4's demand should be 20 | the data correction is stated in the complaint; after it vehicle 1's load is 107 > 100 | adopted |
| T6 | "One of the numbers you have for customer 7 is wrong. It should be 18." | the value is given but not the field (demand 11, coordinates (6, 8)); clarified as the demand; a genuine ambiguity | adopted |
| T7 | the two drivers' distances differ by 71, at most 50 allowed | threshold 50 rather than 30: by changing weights alone `balance` can at best go down to 46; to get below 30 the weight must be exactly 1, which gives 56 tied optima and no unique ground truth | adopted |
| T8 | "The drivers are unhappy with how the work is split…" | could mean distance or load; clarified as load difference ≤ 5. On this instance the distance gap is the more visible one, and the real meaning is the less visible one, so that clarification shows its value (Task 3 condition C) | adopted |
| T9 | customers 4 and 5 are 14 km apart yet on different vehicles (variant: customer 3's demand 54) | the only case using a "modified model" (at most 2 allowed); the optimal routes do not change under the variant; `SEP(2,5)` is forced by capacity in the variant and only an objective preference on the base data (Δ = 39) | adopted |
| T10 | avoid the direct 6→8 link (72 km) | the counterfactual "vehicle 2 drives in reverse" leaves the objective unchanged and only records the reversal flag; it also shows that reversal does not remove this complaint | adopted |

## 3. Coverage (§5.3)

| Dimension | Requirement | Actual |
|---|---|---|
| Attribution conclusion | capacity forced ≥ 2; objective preference ≥ 6 | 2 (T4, T9); 8, with 8 distinct edge-difference sets |
| Counterfactual outcome | feasible and worse ≥ 4; feasible and unchanged ≥ 1; infeasible by capacity ≥ 2 | 7; 1 (T10); 2 (T4, T9) |
| Complaint clarity | clear 6 to 7; vague 3 to 4 | 7; 3 (T2, T6, T8) |
| Modification type | soft constraint, weight and data each ≥ 2 | 6, 2 (T7, T8), 2 (T5, T6) |
| Complaint object | vehicle, customer and data all present | vehicle 2, customer 4, data 2, global 2 |
| Cases with a modified model | ≤ 2 | 1 (T9) |

Counterfactual outcomes are classified by the change in **total distance**; `APPLY_MODIFICATIONS` queries also report the change of the objective including penalties (T1's objective falls by 293 because the current solution pays a penalty in the modified model).

## 4. Known limitations (stated in the README)

1. The counterfactual answers of T1, T3, T5 and T7 are the same alternative plan (368: `[1,7,2,8] / [4,5,3,6]`), the second best of the 14 groupings that satisfy capacity. The instance is small, and this repetition cannot be avoided.
2. The ground truth of "objective preference" attributions is "the edge difference between the current plan and the optimum with the decision forbidden", and the component computes the same definition, so its accuracy is close to true by construction; the discriminating parts are the IIS half and the validation of the LLM explanation.
3. With only 10 cases, every proportion is very uncertain.
4. Only `balance` (weight < 1) and `load_balance` are usable for weight complaints; `makespan` and `sum_arrival` leave almost no room for improvement on this instance.

## 5. Change to the development cases

Of the original 5 development cases only 1 was an ambiguous complaint (D4), and the confidence rule may only be tuned on development cases, so that was too few. D1 changed from "vehicle 1 may only make 3 stops" (clear) to "The driver of vehicle 2 says today's plan is exhausting." (ambiguous, clarified as vehicle 2 stops ≤ 3, `S[2]`, penalty 60). This target overlaps with no test case. The development cases now have 2 ambiguous and 3 clear complaints and all three modification types.

D4 ("Customer 8 is not happy", clarified as arrival distance ≤ 100) can be removed by reversing a whole route. Development cases are used only to tune localization and do not enter Task 3's convergence rate, so it was kept.
