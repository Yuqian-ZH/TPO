# Task 3 decision log

Decisions outside the plan, or ones that needed the user's confirmation, in chronological order. The "Limitations" section of the README draws on this file.

## Stage 0 and 1 implementation choices (2026-10-23)

1. **Public fields:** Task 2's case fields were checked at G1. Prompts use only `id`, `solution`, `complaint` and `model_modifications`; `scenario`, `clarity`, `complaint_object`, `why_*`, `what_if*`, `checker`, `gt`, `reference_*`, `initial_check`, `solution_metrics` and `allowed_data_corrections` never enter a prompt. `clarification_answer` appears only as "the user's answer" in C's clarification flow and in supplementary arm S2. pytest checks this with sentinel strings.
2. **Canonical direction on direction ties** (added to section 3.3 of the plan). Rendering prompts in stage 1 showed that after committing a direction-independent modification such as `S[2] ≤ 3`, Gurobi reversed vehicle 2's whole route, so `A[3]` went from 60 to 151 and `A[8]` from 167 to 44. The verdicts of arrival and detour checkers would flip at random (for example development case D4's `arrival_max(8, 100)` would be "solved" for nothing). Now every route whose objective is unchanged by reversal is written with its first customer lower-numbered than its last; when the objective depends on direction (modifications of `A[i]` / `sum_arrival`), the solver's direction is kept.
3. **Candidates are validated against a per-operation allow list, not only `ids.target_exists`:** that function also returns true for `capacity` and `demand[i]`; `ids.OBJECTIVE_TERMS` includes `distance`, and setting a weight on it raises a KeyError in `model.py`. With n = 8, candidates first pass Task 2's `schemas/modification.schema.json` (which does not reject i = j targets such as `e[3,3]`) and then the semantic checks. The penalty cap of 1000 and weight cap of 100 are Task 3's own.
4. **Task 2 localization uses run labels `t3-{run}`:** Task 2's `localize` derives seeds from `(case_id, component, run, sample)`. Labels `t3-1` to `t3-3` keep them apart from Task 2's own evaluation runs, so Task 3's localizations are new samples. Task 3 reports their accuracy separately (against the cases' `gt.localization`, used only on the evaluation side).
5. **The critique text is regenerated every iteration:** Task 2 provides `localization.evidence()` and `critique_text()`, so, following section 3.7 of the plan, the evidence is recomputed from the current plan and the critique rewritten each iteration.
6. **The attribution block holds only compact fields:** the decision, the conclusion, the constraints and variables of `attribution_set`, the objective increase with the decision forbidden (split by term when additional terms exist), the edges unique to each side with their distances, and the customers that switch vehicles. LP duals and reduced costs, constraint slack and IIS details go only to the log (`raw`).
7. **Task 2's clarification argument is a `{"question", "answer"}` dict**; the adapter converts it.

## Smoke-test observations (no tuning from these; left to stage 2 on development cases)

- All 5 real requests `json_ok` and all candidates valid; the responding model is `qwen3.8-max` with no reasoning content; about 2.3k input tokens each.
- Both times the LLM set the weight of `balance` to 50. Item 1 of Task 2's DECISIONS already notes that above 1 this weight makes the solver deliberately lengthen the short route. On the toy instance the complaint was removed, but the total distance rose from 278 to 325. Stage 2 will check how often this happens on the development cases before deciding whether the system prompt needs a reminder (the same for all configurations).

## A Task 2 problem found at G2: the local counterfactual often stops at a wrong L0 on "modify the model" queries (2026-10-23 01:50, waiting for the user's decision)

**Symptom:** `counterfactual(method="local")` widens the neighbourhood only when infeasible. For `APPLY_MODIFICATIONS` queries, L0 frees only the customers on the routes of the modified quantity; a soft constraint never makes the model infeasible, so L0 returns as soon as it is feasible, however far from optimal.

**Example** (development case D1's reference modification `S[2] ≤ 3`, penalty 60): vehicle 1 already carries 99/100, none of vehicle 2's customers can move over, and vehicle 1's customers cannot move under L0. The local method stops at L0 with the plan unchanged, only paying the penalty (objective 411); the full solve moves customer 2 to vehicle 2, reaching 397, and the complaint is removed.

**Scale** (`diagnostics/probe_vs_full.py` → `logs/probe_vs_full.json`; only the 5 reference modifications of the development cases and 200 random modifications on the reference optimum, no test case touched, solver calls only):

| Metric | Result |
|---|---|
| feasibility agrees | 205/205 |
| objective within 1% | 168/185 = 90.8% |
| change set agrees | 154/185 = 83.2% |
| local says "plan unchanged" while the full solve changes it | 15/185 = 8.1% |
| level stopped at | L0 181, L1 4, L2 0 |

**Impact:**
- With condition B on, the "forecast consequences" the selector sees are wrong for about one candidate in ten, and always in the same direction: a modification that really works is reported as "no effect". B's effect would be underestimated, possibly even negative.
- Task 2's own evaluation does not easily expose this: only 2 of its 10 test counterfactual queries are `APPLY_MODIFICATIONS`, and the 120 supplementary queries are all MOVE / FIX_ARC (hard constraints, which do escalate when infeasible).
- Task 2's `protocol.json` was frozen at 01:49 and its formal evaluation had started, so it could no longer be changed before the freeze.

**Options** (for the user to decide):

| Option | Cost | What the conclusion would mean |
|---|---|---|
| 1. Use Task 2's frozen local method as is, report how often the probe and the commit agree, and state it under limitations | none | whether "probing with Task 2's existing counterfactual component" helps |
| 2. Option 1 plus supplementary arm S3: like `A1B1C1` but probing with the full solve (exact consequences), 30 trials | about 120 to 360 more requests | separates "does the probing mechanism help" from "the local heuristic's error". **Recommended** |
| 3. Have Task 2 change its escalation rule (for example keep escalating modification queries while a soft constraint is still violated at the current level) and re-run Task 2's evaluation | Task 2 must be unfrozen and re-run | B uses a fixed component; Task 2's results must be updated as well |

The stage 2 pilot does not start before the user decides (B's pilot results depend on this decision).

**06:35 addendum: Task 2's formal evaluation independently confirmed the same problem** (`Task 2/task2/DECISIONS.md`, stage 4 item 6 and stages 5 and 6 items 2 and 3). On test case T1 (vehicle 2 ≤ 180 km) the local method stopped at L0, kept the original plan and paid the penalty, objective 661, while the full solve gives 368; the local method's objective agreement is 7/8 on the main queries and 87/101 on the supplementary ones. Under its freeze rule Task 2 did not change it, stated it in its README limitations, and recommended "if Task 3 or 4 uses the counterfactual component to evaluate candidate modifications, change this rule in a new protocol version" (also escalate when the penalty is positive or the gap to the lower bound is large). That gives one more option:

| Option | Cost | What the conclusion would mean |
|---|---|---|
| 4. Following Task 2's recommendation, put a new-protocol-version local method in Task 3 (only the escalation rule changes, everything else copied; Task 2's frozen files and results untouched) and let B use it; first verify its agreement with the full solve on development cases and random modifications, then bring in the LLM | code and tests, no extra requests | B tests "a working local probe"; still satisfies "do not re-solve from scratch every time" |

**Recommendation changed to option 4:** Task 2 has itself confirmed the problem and recommends this; B's conclusion in the main experiment would not rest on a known defect; and it avoids the 30 extra trials of option 2. The frozen version's deviation already has LLM-free diagnostic numbers (`logs/probe_vs_full.json`) that the report can show alongside. Still needs the user's confirmation.

**User decision (2026-10-23 09:05): option 4** (cited as "decision 4" in `protocol.json`). The new local method is in `tpo/counterfactual_v2.py`; Task 2's frozen files and results are untouched. Condition B's probe uses the new version; it is first cross-checked against the full solve without the LLM, then piloted on development cases.

### Option 4: implementation and cross-check (09:20)

- `tpo/counterfactual_v2.py` subclasses Task 2's `Engine` and copies the neighbourhoods, warm start, anchor and output fields; only the escalation condition of `solve_local` changes: infeasible; a soft constraint added by the query is still violated (`soft_violation`); the query changed the model but the plan did not change (`unchanged`); the query contains `modify_data` (changed data means a different problem, so go straight to L2).
- The fourth condition was added after the cross-check: with only the first three, the objective agreed 184/185, and the 4 that stopped at a worse plan were all demand changes (L1 stops at the first feasible new plan, at most 6.25% worse).
- Cross-check (`diagnostics/probe_vs_full.py`, the 5 reference modifications of the development cases plus 200 random modifications, no LLM, no test case):

| Metric | Task 2 frozen version | New version |
|---|---|---|
| feasibility agrees | 205/205 | 205/205 |
| objective within 1% | 168/185 = 90.8% | **185/185 = 100%** |
| change set agrees | 154/185 = 83.2% | 174/185 = 94.1% (all 11 disagreements are tied optima with the same objective) |
| says "unchanged" when it changed | 15 | 0 |
| level stopped at, L0 / L1 / L2 | 181 / 4 / 0 | 29 / 1 / 155 |
| latency median / p95 | 49 / 128 ms | 71 / 163 ms |

- The cost is stated in the README: on this capacity-tight instance most modification queries have to open up to L2, that is, a warm start on the resident model with every customer free. This is still the "warm start" approach the task allows, but the benefit of being "local" is mostly gone.
- `Task2Components(probe="task2_frozen")` is kept for diagnostics and tests; the formal experiment's B always uses the new version. 118 pytest tests pass.

## LLM API unavailable (2026-10-23 09:11, waiting for the user)

All 215 requests of the development pilot returned `403 AccessDenied.Unpurchased` ("Access to model denied. Please make sure you are eligible for using the model."), and a single minimal request sent afterwards to check also got 403. The last successful request in Task 2's logs was at 02:03, so the permission for `qwen3.8-max` lapsed between 02:03 and 09:10. Refused requests produce no output; this pilot is void, and none of its results entered any analysis.

Paused under item 4 of section 0 of the plan. The model is not changed: Tasks 2 to 4 must use the same model, and Task 2's frozen evaluation used `qwen3.8-max`.

## Stage 2: development pilot (2026-10-23 10:17 to 10:2x, `results/pilot_dev_v2/`, pause point 1 awaiting confirmation)

Access returned at 10:17 after the user topped up the account. 5 development cases × 10 configurations × 1 run = 50 trials plus 5 shared localizations. Reports: `results/pilot_dev_v2/pilot_report.json`, `pilot_report.txt`.

**Convergence matrix** (tN = converged at iteration N, x = not converged in 3 iterations):

| Case | A0B0C0 | A0B0C1 | A0B1C0 | A0B1C1 | A1B0C0 | A1B0C1 | A1B1C0 | A1B1C1 | S1 | S2 |
|---|---|---|---|---|---|---|---|---|---|---|
| D1 (vague: vehicle 2's driver says it is exhausting; actually the number of stops) | t2 | t1 | x | t1 | x | t1 | x | t1 | t1 | t1 |
| D2 to D5 | all t1 | | | | | | | | | |

- 47/50 converged, 46 of them at iteration 1. The only case that separates configurations is the vague complaint D1: without clarification the LLM first guesses distance, then load, and never thinks of the number of stops (A1B0C0's three iterations: makespan weight 50, `L[2] ≤ 150`, `W[2] ≤ 85`); with C on, or S2 with the clarification, it is solved at iteration 1.
- Localization: 5/5 targets right; both vague cases are first judged low confidence, ask for clarification, then become high confidence.
- Probe (new version) against commit: feasibility, objective and change set all agree.
- 1 invalid candidate (`op` was a space); no illegal data modification; converged plans are on average 5 to 6 km shorter than Task 2's reference modification plans.
- Leak scan: 91 real prompts. The only hit was D3's `demand[2]=30` in a selector prompt, which is a candidate the LLM proposed itself (the complaint says "we now order 30 units"); it is in no proposal prompt, so a false positive.

**Ceiling problem:** on development cases almost every clear complaint is solved at iteration 1. The test cases are designed like the development cases (6 to 7 clear, 3 to 4 vague), so the formal experiment is expected to hit the ceiling on clear complaints, and configurations will differ mainly on vague complaints (C's clarification). Under section 5.4 of the plan, a ceiling is reported as it is, and the same decision rule is applied to iteration-1 convergence, mean iterations and cost; **the prompts are not weakened and the model is not changed to manufacture differences**.

**Prompts unchanged:** a `balance` weight above 1 appeared 3 times (10, 50, 5) and caused no failure; the converged plans were even shorter than the reference plans. The concern from the smoke test finds no support on the development cases, so the system prompt stays as it is. The other parameters (N = 3, temperatures 0.7 / 0, at most 4 modifications, entity extraction rules) are not changed either.

**Measured cost and budget for the formal experiment:**

| | Development pilot, measured | Formal experiment, estimated (300 trials + 30 shared localizations) |
|---|---|---|
| requests | 194 | about 1,200; at worst about 3,000 (every trial running all 3 iterations) |
| tokens | 801k (784k input, 17k output) | about 4.8M; at worst about 12 to 13M |
| mean tokens per trial | without A or B: about 1.8k; with A or B: 7 to 10k; with both: 26 to 35k | |
| wall clock | 50 trials in about 2 minutes (4 processes) | about 15 to 40 minutes |

The worst case assumes every trial runs all 3 iterations; the development cases averaged only 1.14 iterations.

## Stage 3: freeze and formal experiment (2026-10-23)

- 11:50: after the user replied "OK to run" at pause point 1, `protocol.json` was frozen for the first time. At start-up the protocol check raised an ImportError: `task2_bridge` put Task 2's root at the front of `sys.path`, and Task 2's root also has `freeze_protocol.py` and `recompute.py`, so the check imported Task 2's modules of the same names. The formal experiment exited at the check, **sent no request and produced no trial result**.
- Fix: Task 2's root is now appended to the end of `sys.path`, so Task 3's modules of the same name take precedence; a new regression test `tests/test_imports.py` (120 pytest tests pass). `task2_bridge.py` is on the freeze list, so the old protocol was kept, renamed to `protocol_superseded_2026-10-23T1150.json`, and the protocol frozen again. No test case had any result yet, so this does not break "no code changes after seeing results once frozen".
- After the re-freeze the protocol check passed with the Task 2 folder unchanged; the formal experiment started: `results/formal/`, 10 configurations × 3 runs × 10 test cases.

## Stages 3 and 4: formal results and report (run 2026-10-23 11:51 to 12:02)

- 300 trials, 1,105 requests, all successful at the first attempt; 4.49M input + 0.09M output tokens; about 11 minutes of wall clock. All 10 acceptance items pass (`results/formal/acceptance.json`).
- **The ceiling, as expected:** 298/300 converged, 278 at iteration 1. By the rule written in advance, both the primary metric and the secondary one (iteration-1 convergence) "cannot tell which mechanism matters most" (every confidence interval touches 0).
- Descriptive conclusions (README section 4, marked as not a rule-based verdict): only C changed the speed of convergence (100% at iteration 1 against 80 to 83%), all of it from the two vague complaints T2 and T8; S2 is also 100% at iteration 1, so the gain comes from the clarification content that C's confidence gate triggers, not from the structured target ID / modification type; A has no measurable effect and about 4 times the prompt size; B helps only with C off (both failures were in configurations without B), at about 4 times the requests; S1 equals A1B1C1.
- The acceptance script's leak criterion was changed once: it first used checker function names as markers, which flagged T3's `detour_ratio` and T9's `same_vehicle` in configurations with C on; on inspection these were name collisions (Task 2's localization evidence has a field `detour_ratio`, and the "aspect" enum contains `same_vehicle`), and no threshold appeared in any prompt. The criterion now looks for the checker's full specification JSON and `"name": ...`, and adds "the iteration-1 prompt does not contain the reference modification".
- The new probe in the formal experiment: 164 committed candidates, objective within 1% 164/164, exactly equal 124; for the other 40 the forecast plan is 1 km longer than the committed one (L0/L1 stop once the soft constraint is met), so the change sets differ. Stated in README limitation 1.
- Every number in the README was recomputed from the raw trials: the first draft had 3 errors (296 converged and 268 at iteration 1; "the two failures never touched load" was wrong, they tried `load_balance` but never limited `W[1]` directly; T6 was missing), all corrected.

## The post-audit batch task3_v2 (2026-10-27)

1. **Why re-run:** audit item F1 holds (reproduced). v1's condition A wrote 18 wrong numbers into prompts in 2 trials, and A can only matter at iterations 2 and 3, which only 11 trials reached, including these 2 (`A1B0C0`/T2 run 3 is one of the two failures of the whole experiment). So v1 cannot support "A does not help", only "A was not tested correctly this time". F3 also holds: v1's cost counted only TPO requests and not the shared localization (195 requests, 301,495 tokens), so "C is also the cheapest" does not hold; corrected at the top of the README.
2. **Only the attribution changes:** `tpo_v2/components.py` subclasses v1's adapter and only swaps the attribution for Task 2's task2_v2 (also passing the objective change and edge differences for the `cheaper_without` conclusion). Loop, prompts, seeds, probe, commit, simulated user and statistics are all the frozen v1 code. The new code is outside `tpo/`, so v1's `protocol.json` and Task 4's check of it still pass (tested).
3. **All 8 main configurations re-run (240 trials)**, not only the 4 with A on: otherwise variation between the two batches would mix into A's effect. S1 and S2 are not re-run: all 60 of their trials converged at iteration 1, where the attribution was already correct.
4. **Seeds unchanged:** `tpo/llm.py`'s `task3_v1` derivation. Configurations without A have prompts identical to v1's, and configurations with A differ only in the attribution content, so only one thing changes between the batches.
5. **The 30 shared localizations of v1 are reused**, after checking each: recomputed with task2_v2's localization rule on the same samples, confidence, target, modification type, threshold and clarifying question must all equal v1's, or the run refuses. 30/30 equal (`run_experiment_v2.py` records each check). Their cost is still counted from the requests in v1's logs.
6. `protocol_v2.json` frozen: 18 v1 source files, 4 v2 source files and 36 Task 2 files (including the v2 components and Task 2's `v2/protocol_v2.json`). Frozen only after a dry run (fake LLM, 2 cases × 3 configurations) passed.
7. **Results (2026-10-27 10:39 to 10:47, all 687 requests successful at the first attempt, every response from `qwen3.8-max`):** 235 of 240 trials converged, 218 at iteration 1. All 510 attributions that entered iteration 2 and 3 prompts agree with enumeration (v1: 18 wrong in 11 trials). A's main effect −0.8 pp [−2.5, 0] within 3 iterations and −3.3 pp [−8.3, 0] at iteration 1; `A1B0C0` failed 3 times and `A0B0C0` 0 times (McNemar p = 0.25). By the rule fixed in advance it still cannot tell which mechanism matters most. All 5 failures were in configurations without C and all on T2/T8: the LLM kept adjusting the weights of distance difference, longest route and load difference; only once did it limit vehicle 1's load directly, with a cap of 95 (the plan stopped at 94), and never at the user's 92. Conclusion: with attribution fixed it was tested, and it still does not help.
8. **Fixed seeds do not reproduce:** the iteration-1 prompts of the 120 trials without A are identical to v1's, yet only 1 LLM output is the same; `A0B0C0` went from 1 failure to 0 and `A0B1C0` from 0 to 2 with nothing changed. This shows why item 3 (run all 8 configurations and compare only within a batch) was necessary; the README states that the batches cannot be pooled or subtracted.
9. One number check: the README draft said "`A1B1C0` has a data modification the user never mentioned that was not committed"; against the raw record this is wrong: it was committed at T6 iteration 1 (18 read as customer 7's y coordinate), the plan was infeasible under the real demand, and after the user's feedback iteration 2 changed the demand instead; corrected.
10. Post-run review: the enumeration check in `report_v2.py` used only the iterations' modifications and missed the case's own data modification (T9's demand 54); T9 never reached iteration 2, so nothing was affected. Fixed; the re-run report is word for word the same.
11. **task3_v2.1 (2026-10-27, check only, no re-run):** Task 2's v2.1 fixed the 4 problems found in review. Task 3 adds `tpo_v21/` (the `tpo_v2` adapter with the v2.1 components) and `recheck_v21.py`: it first checks Task 2's `v21/protocol_v21.json`, then recomputes, without the LLM, every state and every sample set recorded in formal_v2. All 2,502 attributions (compared both in prompt form and as full records) and 39 localization sample sets equal those used in the v2 run, so the conclusion of item 7 stands. No separate Task 3 protocol was frozen, since there was no new run; the hashes of `tpo_v21/` and `recheck_v21.py` are recorded in Task 4's `service_freeze_v21.json` and in the recomputation's meta. The first check produced 22 differing term names, caused by the trial records storing modifications without their soft-constraint numbers and the recomputation not restoring them; see item 6 of the same day in Task 2's DECISIONS.

## task3_v3: the redesigned experiment (2026-10-27)

12. **Motivation:** after reviewing the v2 results, the user pointed out that the Task 3 design could not answer the task's question and asked for "a properly designed architecture against the task requirements, and then the runs". The design is `DESIGN_V3.md` at the project root, written before any LLM call: new cases (2 control, 3 ambiguous, 5 side condition, each with properties asserted by enumeration at build time), a simulated user with equal information, 5 runs per configuration, and a stratified analysis and pilot calibration rule fixed in advance.
13. **The pilot revealed a design flaw, which was fixed:** the loop started each iteration from the previous, rejected plan, while the new cases' conditions ("at most two customers switch vehicles", "vehicle 1's route cannot change") are stated relative to the original plan, so B's probe reported "no customer switches vehicle", contradicting the user. Now every iteration starts from the plan complained about (`TrialV3` in `tpo_v3/loop.py`), the same for all configurations. After the fix the pilot was repeated; the bare configuration reached 80% in the side-condition stratum, so by the rule fixed in advance the difficulty was not calibrated.
14. **After the freeze the test set turned out to have no capacity-forced attribution and no infeasible counterfactual;** before any LLM call, 4 question fields were changed and Task 2's protocol was frozen again (details in Task 2's DECISIONS and `DESIGN_V3.md` section 9). Task 3's protocol was frozen only after that.
15. **Results:** 400 trials and 1,726 requests completed. The overall rule fixed in advance still cannot tell (the lower end of B's interval is 0); stratified: B +12 pp [+2, +22] in the side-condition stratum, C +61.7 pp for solving at iteration 1 in the ambiguous stratum, A −12 pp [−32, 0] in the side-condition stratum. Both reasons for A's harm were checked in the raw records: in U10 the attribution shows a soft constraint already in the session, and with A 84% of proposals write it again (50% without A), using one of the 4 modification slots; in U8 the configurations with A kept trying the impossible four customers on one vehicle.
16. **Two design shortcomings found in the results, not changed after the fact:** soft constraints already in force in the session do not appear in the prompt, and this interacts with the limit of 4 modifications. Testing whether A's negative effect comes only from this needs a separate v3.1 batch registered in advance.
17. The statistics module's verdict text hard-coded "3 runs"; the report script replaces it with the actual number of runs (the rule is unchanged).

## task3_v3.1: the v3 design repeated, with three controls (2026-10-27)

18. **Motivation:** the user agreed to a separate batch registered in advance to test whether A's negative effect came from "session constraints not shown". Re-reading the task text also showed that v3's B changed two things at once (1 candidate became 3, plus the probe), while the task's condition B means "evaluate with the counterfactual component before committing", and v3 had dropped the blind-selection control v1 had. The design `DESIGN_V31.md` was written before any LLM call.
19. **Changes:** the prompt lists the modifications already in the session before "modifications currently in force" (`tpo_v31/loop.py`), the same for all configurations, and the prompts of U1 to U8 are word for word v3's (tested); new arms `S1a` (A0B1C0 selecting blind), `S1b` (A1B1C1 selecting blind) and `S2a` (A0B0C0 plus the user's answer as text); run numbers 6 to 10, so every seed differs from v3's. The Task 4 service shows session modifications accordingly.
20. **Pilot** (development cases P10, P3, P6, 11 configurations once each) checked the process only; everything passed and no code changed.
21. **API outage:** as the formal run reached the last supplementary configurations, DashScope returned 403 `AccessDenied.Unpurchased` for every request from 16:13 (an account problem). The 8 main configurations and the shared localization had finished with no failed request. Rule: every trial with at least one refused request is void whatever its outcome, moved unchanged to `results/formal_v31/invalid_api_403/`, and re-run with the same seeds once access returns. The first re-run had 2 more sporadic 403s, handled the same way. 116 trials were voided in all, and none of the final 550 trials contains a refused request.
22. **Results:** the overall rule still cannot tell. Question 1: A's negative effect did not replicate, but not thanks to showing the session modifications: the share of proposals repeating a session constraint did not drop, it only moved from the A-on side to the A-off side; on U8, whose prompts are word for word v3's, A's direction reversed too. v3's "A hurts" is judged to be sampling variation. Question 2: with the same 3 candidates, selecting with the probe's results beats selecting blind (pooled +9 pp [0, +20], side-condition stratum +18 [+2, +34]), and selecting blind is worse than a single candidate; the reading fixed in advance needs the pooled lower end above 0, and it is exactly 0, so the verdict is "cannot tell", reported as it is. Question 3: the advantage on vague complaints at iteration 1 comes entirely from asking first; the structured localization adds nothing; C's loss in the side-condition stratum comes from "stop if still unclear after asking" (U9, 3 of 5 runs).
