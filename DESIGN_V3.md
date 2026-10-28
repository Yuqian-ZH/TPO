# Third experiment design (task2_v3 / task3_v3 / task4_v3)

> 2026-10-27. Motivation: after reviewing the v2 results, the user pointed out that the Task 3 ablation could not, by design, answer the question the task asks, and asked for an architecture designed properly against the task requirements, and then for the runs.
> This file was written before any LLM call. After the pilot, changes were allowed only under the rules written in advance in section 6; any change is recorded in section 9.


## 1. Task requirements and where the first two versions fell short

| Task requirement | What v1 and v2 did | Problem |
|---|---|---|
| Task 2: 10 test cases, each with a solution, a user-style complaint or question, and hand-labelled ground truth | All 10 cases start from the same optimal plan and were written so that each of the three components had cases to test | Did not consider that Task 3 runs its ablation on the same cases: 7 cases were solved at iteration 1 by every configuration |
| Task 3: the same 10 cases, compare mechanisms A, B and C; convergence = a feasible plan with no complaint within 3 iterations | The simulated user looked at a single checker; without C the feedback was the fixed template "Still not solved: <original complaint>" | (1) The thresholds of the vague complaints (vehicle 1 ≤ 92, load difference ≤ 5) appeared only in C's clarification answer, so configurations without C could never get them: C's advantage came from an information gap. (2) Every complaint could be expressed directly as one soft constraint, so attribution (A) and the counterfactual probe (B) had nothing to do. (3) 3 runs per configuration: the noise was as large as the effects |
| State which mechanism contributes most to reliable convergence | "Cannot tell", by the rule fixed in advance | Under that design this outcome was inevitable, not a finding |

## 2. Design principles

1. **Equal information.** Every requirement of the user is a "condition", stated in the complaint or in the "explanation". The explanation is the user's answer when asked "what do you mean?", and also what the user says on seeing a plan that does not solve the problem. Configurations with C get the explanation through clarification before iteration 1; configurations without C get the same words in the feedback after their first unsuccessful attempt. Every later feedback lists, condition by condition, the conditions still unmet and their current values (values the plan already shows). All configurations see exactly the same user utterances; they differ only in when they see them.
2. **"No complaint" means every condition the user has stated is met**, plus feasibility on the real data (data the user has corrected counts as real data). There is no longer a single checker, and there is no hidden threshold the user never stated.
3. **The cases give every mechanism a chance to matter**, and this is verified by exhaustive enumeration when the cases are built, not by an LLM:
   - **Control (2 cases):** one clearly stated requirement; the most direct formulation (a soft constraint at the user's limit) solves it.
   - **Ambiguous (3 cases):** the complaint does not say which quantity it means; a change based on the most likely misreading does not solve it. Tests C.
   - **Side condition (5 cases):** a clearly stated main requirement plus a second condition that dispatchers often state but the modelling language cannot express directly: "vehicle 1 has already left, its route cannot change", "both vehicles are half loaded, at most two customers may switch vehicles", "if that is impossible, settle for the next best, and the total distance must not exceed X", "a problem fixed earlier must not come back". Writing only the main requirement directly, **every optimal plan violates the second condition**; at most 4 modifications can satisfy both. Finding such modifications requires knowing how the plan will change and which groupings are feasible under capacity, which is exactly the information attribution (A) and the counterfactual probe (B) provide. Tests A and B.
4. **The mechanisms themselves do not change.** The implementations, prompts and seed derivation of A, B and C are task3_v1's (the components are task2_v2.1's). This version rebuilds the cases, the simulated user and the analysis plan; the loop changes in one place only, identically for all configurations (every iteration starts from the plan the user complained about, see section 9), and the Task 4 service changes accordingly.
5. **Separate development and test sets built by the same recipe.** The 10 development cases (P1 to P10) are used only for the pilot; the 10 test cases (U1 to U10) are not shown to the LLM before the freeze.
6. **Sample size:** 5 runs per configuration and case (the task requires at least 3): 8 configurations × 10 cases × 5 runs = 400 trials.

## 3. Cases

Code: `Task 2/task2/v3/cases.py` (specifications and exhaustive checks) and `v3/conditions.py` (conditions and user wording). The generated `v3/cases/cases.md` lists every number of every case. Each case asserts when it is built that:

- the plan complained about violates at least one condition;
- a plan meeting every condition exists, and its shortest distance is recorded (excluding "the two vehicles swap their whole routes": the commit solve always fixes one customer to its original vehicle and can never produce such a plan);
- the reference fix has at most 4 modifications, and every optimal plan obtained the way the commit solve obtains it (the same anchor, canonical direction on ties) meets every condition;
- the stratum property holds: control, the direct formulation solves the complaint on every optimal plan; ambiguous, the misreading leaves it unsolved on every optimal plan; side condition, the direct formulation violates the side condition on every optimal plan. Cases of the "settle for the next best" kind also assert that the first wish is indeed infeasible;
- Task 2's ground truth (localization target and modification type, attribution, counterfactual) is also computed by enumeration, as in v1.

| Test case | Stratum | Requirement |
|---|---|---|
| U1 | control | vehicle 2 ≤ 180 km |
| U2 | control | the road between 6 and 8 is closed |
| U3 | ambiguous | "vehicle 1 has too much work" → load ≤ 92 |
| U4 | ambiguous | "a number for customer 7 is wrong, it should be 18" → demand 18 |
| U5 | ambiguous | "the work is not split fairly" → load difference between the vehicles ≤ 5 |
| U6 | side condition | customer 6 reached within 70 km; vehicle 1 has left, its route cannot change |
| U7 | side condition | vehicle 1 load ≤ 94; at most two customers switch vehicles |
| U8 | side condition | the 4 south-western customers on one vehicle is impossible, so settle for: 4 and 5 on the same vehicle and total distance ≤ 370 |
| U9 | side condition | (the road 4 to 7 was closed earlier in the session) 5 and 7 on the same vehicle; at most two customers switch vehicles; 4 and 7 still not directly connected |
| U10 | side condition | (4 and 5 on the same vehicle was requested earlier in the session) the road between 2 and 7 is closed; vehicle 2 has left and cannot change; 4 and 5 still on the same vehicle |

The development cases P1 to P10 follow the same recipe: 2 control, 3 ambiguous, 5 side condition.

Two details found and handled during construction: (1) The commit solve fixes one customer to its original vehicle (the lowest-numbered customer not involved in any modification; customer 1 when the modifications involve every customer). In one early development case the only feasible swap had to move customer 1, which no modification could reach, so that case was replaced; the reference fixes of all cases were checked against this rule. (2) On direction ties the commit takes the canonical direction; the builder applies the same rule, otherwise whether a misreading solves the complaint would depend on the direction.

## 4. Simulated user (`Task 3/task3/tpo_v3/user_sim.py`)

- Verdict: feasible on the real data, and every condition met.
- Answer to a clarifying question: the explanation.
- Feedback on an unsuccessful plan: the first time, "That did not solve it. What I mean is: <explanation> In the new plan <each unmet condition with its current value>."; if the user has already explained (asked earlier under C), only the unmet conditions are listed.
- As with the v1 simulated user, it does not read the system's explanation text; it looks only at the plan.

## 5. Metrics and analyses fixed in advance

- **Primary metric** (as defined by the task): the share converged within 3 iterations. For each configuration, the mean ± standard deviation over the 5 runs.
- **Main analysis:** main effects of A, B and C and their two-way interactions over the 8 configurations, with 95% intervals from a bootstrap clustered by case (10,000 resamples). The decision rule is v1's: "X contributes most" only if the interval of the largest main effect lies entirely above 0 and the interval of its difference from the second largest also lies above 0.
- **Stratified analysis fixed in advance:** the three main effects reported within each stratum (descriptive, with bootstrap intervals). Expectation stated in advance: C's effect should appear mainly in the ambiguous stratum, A's and B's mainly in the side-condition stratum, and in the control stratum every configuration should be close to 100%.
- **Secondary metrics:** convergence at iteration 1; mean iterations when converged; extra distance of the converged plan over the shortest compliant plan; LLM requests and tokens per trial (including the shared localization); paired comparisons (McNemar) as in v1.
- The batches are not pooled: v3 uses different cases and a different simulated user from v1 and v2, so the numbers are listed side by side and never subtracted.

## 6. Pilot (development cases only)

- Step 1: `A0B0C0` and `A1B1C1`, 2 runs each, 40 trials. Purpose: catch process errors; see whether the difficulty falls in a range where configurations can differ.
- **Calibration rule fixed in advance:**
  - if the bare configuration `A0B0C0` converges within 3 iterations in ≥ 90% of side-condition trials, the recipe is too easy: add "a problem fixed earlier must not come back" to the side-condition cases and pilot once more;
  - if both configurations are at ≤ 10% in the side-condition stratum, the recipe is too hard: relax the side conditions one step (for example at most three customers switching vehicles instead of two) and pilot once more;
  - otherwise do not change the recipe. Calibrate at most once; freeze whatever the second result, and state it in the report.
- Calibration looks only at these two configurations on the development cases; it never looks at the test cases and never compares A, B and C.

## 7. Freeze and run order

1. Pilot, and decide on calibration by section 6.
2. Freeze `Task 2/task2/v3/protocol_v3.json` (case files, conditions, builder, evaluation code, v2.1 components) and `Task 3/task3/protocol_v3.json` (loop, simulated user, runner, statistics).
3. Task 2 evaluation on the test cases: attribution and counterfactuals (no LLM), explanation and localization (LLM, 3 runs each).
4. Task 3 formal run: 8 configurations × 10 cases × 5 runs.
5. Task 4 end to end: the v2.1 service on the test cases with two configurations (`A0B0C1`, `A1B1C1`) and the v3 simulated user's wording; freeze `service_freeze_v3.json` first.
6. Reporting: each task README, the project notes and the written report; old and new versions side by side, old results unchanged.

## 8. Known limitations (known at design time)

- The instance has only 8 customers and 2 vehicles, fixed by the task; each stratum has few cases (3 ambiguous, 5 side condition), so intervals within a stratum will be wide.
- We built the cases ourselves; the share of side-condition cases (5 of 10) determines how far the overall conclusion leans towards A and B, so the stratified results matter as much as the overall ones.
- The LLM is not reproducible even with fixed seeds (measured in task3_v2); 5 runs mitigate this but do not remove it.

## 9. Pilot record and calibration (filled in after the pilot)

**First pilot** (`Task 3/task3/results/pilot_v3`, development cases, `A0B0C0` and `A1B1C1` 2 runs each, 40 trials, no process errors):

| Stratum | A0B0C0 within 3 | A1B1C1 within 3 |
|---|---|---|
| control | 4/4 | 4/4 |
| ambiguous | 6/6 | 6/6 |
| side condition | 8/10 | 7/10 |

**A design flaw (not a difficulty problem).** The task3_v1 loop starts each iteration from the plan committed in the previous one. In the new cases, the conditions "at most two customers switch vehicles" and "vehicle 1's route cannot change" are stated relative to the original plan the user complained about; from iteration 2 on, the "current plan" in the prompt, the decision A attributes, the changes B's probe reports ("no customer switches vehicle") and the anchor of the commit all referred to the previous, rejected plan, while the user was saying "4 customers switched vehicles". On P7 the fully enabled configuration was misled by B's probe in all three iterations; on P9 the bare configuration also used the rejected plan as the baseline to "fix" customers at iteration 3.

**Fix** (`TrialV3` in `tpo_v3/loop.py`): every iteration starts from the plan complained about and the session model; earlier attempts appear only in the "history" (modifications, resulting plan, user feedback). This is the same for every configuration and does not change A, B or C themselves; a proposal replaces all modifications anyway, and the solve depends on the starting point only through the anchor. A rejected plan never took effect, so this is also closer to practice. The Task 4 service changed accordingly (`feedback_service_v3/`).

**Second pilot** (`results/pilot_v3b`, same settings, shared localization reused from the first pilot):

| Stratum | A0B0C0 within 3 (at iteration 1) | A1B1C1 within 3 (at iteration 1) |
|---|---|---|
| control | 4/4 (4) | 4/4 (4) |
| ambiguous | 6/6 (4) | 6/6 (6) |
| side condition | 8/10 (5) | 9/10 (6) |

**By the rule of section 6:** the bare configuration converges in 80% of side-condition trials within 3 iterations, below 90%, and the two configurations are not both ≤ 10%, so **the recipe is not calibrated** and is frozen as it is. Note: this LLM solves more than half of the side-condition trials at iteration 1, so the primary metric may still be close to the ceiling; as planned in advance, convergence at iteration 1 is a secondary metric and is reported in the stratified analysis as well.

**A coverage gap found after the freeze; re-frozen before any LLM call.** After the first freeze of `Task 2/task2/v3/protocol_v3.json` and the LLM-free attribution and counterfactual runs, it turned out that all 10 attribution questions of the test set were of the "objective preference" kind and all 10 counterfactual queries were feasible: the "hard constraints that force the decision" (IIS) and the infeasible case of the "feasibility status" that the task asks for were not tested (the v1 test set had 2 of each). In these starting plans only "customers 1 and 3 on different vehicles" is forced by capacity (52 + 49 > 100). Change: the attribution questions of U1 and U9 were replaced by this decision, and the counterfactual questions of U7 and U9 by "vehicle 1 also serves customer 3" and "1 and 3 must be on the same vehicle" (both infeasible by capacity). Only these four question fields changed; complaints, conditions and strata did not. Attribution and counterfactual results are deterministic, so the change did not depend on any result. The first freeze file and its results were moved to a scratch directory for the record and never entered the repository; the cases were rebuilt and tested (with one new coverage check) and frozen again.


## 10. Summary of results (filled in after the formal run)

Details in `Task 2/task2/README.md` section 9, `Task 3/task3/README.md` section 9 and `Task 4/task4/README.md` section 12.

- **Task 2** (330 requests): attribution 10/10 (including 2 forced by capacity), explanation 30/30, full re-solve agrees with enumeration everywhere; the local probe B uses agrees on the objective 25/28 and on the change set 20/28; localization 90% right at the first pass, every high-confidence case right, 100% after clarification.
- **Task 3** (400 trials, 1,726 requests): the overall rule fixed in advance still cannot single out a mechanism (the lower end of B's interval is 0), because every configuration converges in 100% of control and ambiguous trials within 3 iterations. The stratified analysis registered in advance:
  - side-condition stratum: B +12 pp [+2, +22]; A −12 pp [−32, 0]; C −4 pp [−16, +8].
  - ambiguous stratum: no difference within 3 iterations; solved at iteration 1, C +61.7 pp [+5, +100].
  - Against the expectations stated in advance: C and B as expected; A not (expected to help, actually hurt). The raw records show why: in U10 attribution shows a soft constraint already in the session model, and with A 84% of proposals write it again (50% without A), using up one of the 4 modification slots; in U8 the configurations with A kept trying the impossible four customers on one vehicle.
- **A design shortcoming found in the results and not changed after the fact:** soft constraints already in force in the session are not shown in the prompt (v1's cases only had data corrections and were not affected), and this interacts with the limit of 4 modifications. Testing whether A's negative effect comes only from this needs a separate batch registered in advance.
