# Experiment design v3.1 (task3_v31 / task4_v31)

> 2026-10-27. Motivation: the v3 results revealed a design shortcoming (`DESIGN_V3.md` section 10), and the user agreed to test it in a separate batch registered in advance. Re-reading the task text also showed that v3's B mixed two things; this batch tests that as well.
> This file was written before any LLM call. The v3 files and results are untouched, and v3.1 is reported side by side with v3. Cases, simulated user and the implementations of A, B and C are v3's.

## 1. Questions to answer

1. **Does A's negative effect in the side-condition stratum come only from "constraints already in force in the session are not shown"?** In v3, A in the side-condition stratum was −12 pp [−32, 0].
2. **Does B's effect come from "working out the consequences first" or from "generating more candidates"?** In v3, turning B on changed two things at once: 1 candidate became 3, and the selection could see the counterfactual probe's results. The task's condition B means the latter ("invoke the counterfactual component to evaluate candidate modifications before committing"). v1 had a blind-selection control (S1); v3 did not include it, so v3's "B contributes most" cannot tell which of the two did the work.
3. **(Secondary) Does C's advantage at iteration 1 in the ambiguous stratum** (v3: +61.7 pp) come from the structured localization itself, or from the one user answer the clarifying question obtains? (v1's S2.)

## 2. The only change to the loop: show the constraints already in force in the session

- **Current state.** The plans of U9 and U10 (P10 in the development set) were solved on a session model that already had a soft constraint: in U9 the road 4 to 7 was closed earlier, in U10 4 and 5 on the same vehicle was requested earlier. The solver always kept these constraints, but the prompt's "modifications currently in force" said none, and the system prompt even said "an empty list returns to the pure distance optimum". The LLM could only guess from the complaint text and often wrote the constraint again, using up one of the 4 modification slots. The most common failing proposal in v3 on U10 was `e[2,7], same[4,5], e[0,4], e[4,5]`: the repeated `same[4,5]` crowded out the fourth modification needed to fix vehicle 2's route.
- **Change.** A block listing the session constraints is added before "modifications currently in force". Its wording follows the "previously accepted modifications" section the Task 4 service already uses:

  ```
  ## Modifications set earlier in this session (kept in force)
  They were in the model before this complaint. They stay in force whatever you answer; do not repeat them. An empty answer returns the plan to the optimum of the model with them.
  - {"op": "add_soft_constraint", "target": "same[4,5]", ...}
  ```

- This is the same for all configurations; the implementations of A, B and C, the system prompts and the seed derivation rule do not change. For cases without session modifications (U1 to U8) the prompts are word for word v3's. A session modification may also be a data correction (development case P10: customer 4's demand changed to 20); it is listed too, and it already shows in the instance table.
- **Task 4 in step.** The service showed only modifications the user had accepted in the session, not the constraints the session was created with (`session_modifications`). `task4_v31` shows both, and tests prove the service matches the Task 3 v3.1 loop word for word (including development case P10, which has session constraints).

## 3. Configurations and sample

| Configuration | A | B | C | Purpose |
|---|---|---|---|---|
| 8 main configurations | 0/1 | 0/1 | 0/1 | as in v3; main and stratified analyses |
| `S1a` | 0 | blind | 0 | the 3 candidates and the selector of `A0B1C0`, but the probe is not called: the selector sees no forecasts and candidates are not filtered by the probe's feasibility |
| `S1b` | 1 | blind | 1 | the same, matching `A1B1C1` (identical to v1's S1) |
| `S2a` | 0 | 0 | 0 + answer | `A0B0C0`, but when the shared localization asked the user, the user's answer is appended to the complaint as text ("The user later added: …") and the simulated user counts as having explained; no structured localization block |

- 5 runs per configuration and case. **Run numbers are 6 to 10:** seeds are derived from (case, configuration, run number, iteration, role, sample), so new run numbers make the seed of every request differ from v3's runs 1 to 5; the shared localization is also redone (50 times).
- 11 × 10 × 5 = 550 trials in total. About 3,000 LLM requests, estimated from v3's usage.

## 4. Analyses fixed in advance

**Main and stratified analyses** exactly as in `DESIGN_V3.md` section 5 (8 main configurations; decision rule unchanged).

**Question 1 (A).**
- Report A's main effect in v3.1 (overall and per stratum, within 3 iterations and at iteration 1), side by side with v3.
- Reading fixed in advance: upper end of the 95% interval of A's main effect in the side-condition stratum < 0 → "A still hurts; the negative effect does not come only from the display problem"; interval includes 0 → "no harm detected"; lower end > 0 → "A helps".
- Expectation stated in advance: on U10, A's negative effect disappears or shrinks clearly; U8 has no session constraint and its prompts are not affected by this change, so if A still hurts on U8 there is another cause. Convergence counts of A1 against A0 per case (descriptive).
- Descriptive: the share of proposals on U9 and U10 that repeat a session constraint, split by A, side by side with v3.

**Question 2 (where B's effect comes from).** Pairs with the same case and run number:
- probe vs blind: `A0B1C0` vs `S1a`, `A1B1C1` vs `S1b`;
- blind vs single candidate: `S1a` vs `A0B0C0`, `S1b` vs `A1B0C1`.
- Each pair reported separately and pooled (100 pairs each): the difference in convergence with a 95% interval from a bootstrap clustered by case (10,000 resamples), and an exact McNemar test. Reported overall and in the side-condition stratum; within 3 iterations is primary, iteration 1 secondary.
- Reading fixed in advance (pooled, within 3 iterations): lower end of the "probe vs blind" interval > 0 → B's effect comes at least partly from seeing the consequences; "probe vs blind" includes 0 while the lower end of "blind vs single candidate" > 0 → B's effect comes mainly from generating more candidates; both include 0 → cannot tell.

**Question 3 (C, secondary).** `A0B0C1` vs `S2a` (structured localization vs only the user's answer) and `S2a` vs `A0B0C0` (answer given before iteration 1 vs after the first failure), paired; convergence at iteration 1 in the ambiguous stratum is primary; descriptive, with bootstrap intervals.

**Relation to v3.** The two batches are not pooled and not tested against each other by subtraction; they are only listed side by side. On U1 to U8 the prompts are v3's with different seeds, so the convergence of the 8 main configurations on U1 to U8 can be read as a replication of v3, described side by side.

## 5. Pilot (development cases only, process check only)

- No calibration and no comparison of configurations. All 11 configurations once each (run number 6) on P10 (has a session modification, a data correction; the development set has no case with a session soft constraint, so showing soft constraints is covered by unit tests), P3 (ambiguous, expected to be asked) and P6 (side condition): 33 trials.
- Checks: the session constraint block appears in P10's prompt and not in P3's or P6's; `S1a` and `S1b` have no forecasts in the selection prompt and no probe in the record; when `S2a` was asked, its prompt has the user's answer and no localization block, and the simulated user does not explain again.
- Pilot results are not used to adjust anything; if a process error is found, it is fixed and recorded in section 8 before the freeze.

## 6. Freeze and run order

1. Code and tests (stub LLM, no network).
2. Pilot on the development cases (section 5).
3. Freeze `Task 3/task3/protocol_v31.json` (v3's frozen files, new code, configurations, run numbers, analyses fixed in advance) and `Task 4/task4/service_freeze_v31.json`.
4. Task 3 formal run: 11 configurations × 10 test cases × runs 6 to 10.
5. Task 4 end to end: the v3.1 service runs `A1B1C1` once on the 10 test cases (comparable with v3's end-to-end run).
6. Reporting: `report_v31.py` (reads only the saved records), each task README, the project notes and the written report; v3 kept side by side.

## 7. Known limitations

- The supplementary configurations sit on one or two main configurations only, not a full factorial design; "probe vs blind" has only 50 pairs per pair of configurations and 25 in the side-condition stratum, so only large differences can be detected.
- Session constraints appear in only 2 test cases, so the direct evidence for question 1 comes mainly from U10; U8 shows whether A's negative effect has another source.
- Otherwise as in `DESIGN_V3.md` section 8: the cases are constructed, the strata have few cases, and the LLM is not reproducible even with fixed seeds.

## 8. Pilot record (filled in after the pilot)

`Task 3/task3/results/pilot_v31`: P10, P3 and P6 × 11 configurations × run 6, 33 trials and 3 shared localizations, no process errors, and all 33 converged within 3 iterations (development cases, not used for any adjustment). Checked item by item against section 5:

- the session modification block appears only in P10's prompt (listing `demand[4] = 20`), not in P3's or P6's;
- the candidates of `S1a` and `S1b` have no probe results and their selection prompts no forecasts; those of `A0B1C0` and `A1B1C1` have both;
- P3's shared localization asked the user: `S2a` on P3 has the user's answer in its prompt and no localization block, and the simulated user counts as having explained from the start; P6 and P10 were not asked, and there `S2a` is identical to the bare configuration;
- every candidate is valid JSON.

No process error was found; the code is unchanged and frozen as in section 6.

**API outage during the formal run (recorded after the run; the handling rule was fixed before looking at the supplementary configurations' results).** From 2026-10-27 16:13:37, DashScope returned 403 `AccessDenied.Unpurchased` for every `qwen3.8-max` request (an account permission or quota problem unrelated to the code; a minimal single request afterwards still got 403). The run proceeds configuration by configuration, and the 8 main configurations completed before that (400 trials) and the 50 shared localizations had no failed request. The affected trials were in the supplementary configurations, which ran last: 17 trials of `S1a`, 47 of `S1b` and 50 of `S2a` contain failed requests, and their "failures to converge" were caused by refused requests, not by model behaviour. Handling: every trial with at least one failed request is void regardless of its outcome (5 of them had converged before the failure and are void all the same), moved unchanged to `results/formal_v31/invalid_api_403/` (with `MOVED.json`); after access returned, these 114 trials were re-run with the same frozen code and the same seeds, and the re-run's request logs are saved separately. The supplementary configurations' results were not reported before the re-run.

**Re-run.** Access returned at 16:18 and the 114 trials were re-run (508 requests). Two requests again got the same 403 sporadically (`S1a` U7 run 6, `S1b` U2 run 8); by the same rule those trials were voided, moved to `invalid_api_403/second_pass/` and re-run. In the end none of the 550 trials contains a failed request. The batch made 3,204 requests in total: 2,522 returned normally (all from `qwen3.8-max`) and 682 were refused, all of them in voided trials. The re-run changed no code, and the frozen hashes were verified.

## 9. Results (filled in after the formal run)

Details in `Task 3/task3/results/formal_v31/task3_v31_results.md` and `Task 3/task3/README.md` section 10. 550 trials, 5 per configuration (runs 6 to 10).

**Main analysis (8 main configurations, rule fixed in advance):** A +2.5 pp [−0.5, +6.5], B +2.5 pp [−3.0, +8.5], C −11.5 pp [−25.5, 0.0]: "cannot tell"; also "cannot tell" at iteration 1.

**Strata:** in the control and ambiguous strata all 8 configurations reach 100% within 3 iterations (as in v3). Side-condition stratum: A +5 [−1, +11], B +5 [−6, +17], C −23 [−43, −3]. At iteration 1: ambiguous stratum C +60 [0, +100] (v3 +61.7), side-condition stratum C −21 [−35, −7].

**Question 1 (A):** by the reading fixed in advance, in the side-condition stratum "no harm from A detected" (v3: −12 [−32, 0]). But this did not come from showing the session modifications:
- after they were shown, the share of proposals repeating a session constraint did not drop: U10 62% (v3 65%), U9 90% (v3 93%).
- on U10, the side that repeats more switched from A on to A off (v3: A off 40%, A on 80%; v3.1: 83% and 38%), and the convergence counts switched with it (v3: 18/20 vs 8/20; v3.1: 12/20 vs 15/20).
- U8 has no session modification and its prompts are word for word v3's, only the seeds differ, and A's direction reversed there too (v3: 16 vs 14; v3.1: 16 vs 18).

Conclusion: v3's "A hurts" is more likely sampling variation than an effect of the hidden constraints; this change did not have the expected effect. A has no reliable effect in either batch.

**Question 2 (where B's effect comes from):** with the same 3 candidates, selecting with the probe's results converged more often than selecting blind: pooled +9.0 pp [0.0, +20.0], discordant pairs 11 to 2, McNemar p = 0.023; side-condition stratum +18 [+2, +34]. Selecting blind was worse than generating a single candidate: pooled −6 [−13, 0], side-condition stratum −12 [−22, −2]. The reading fixed in advance uses the lower end of the pooled interval over all cases, which is exactly 0 and does not satisfy "greater than 0", so **the verdict is "cannot tell"**. Descriptively the directions agree: if B has an effect, it comes from seeing the consequences, not from generating more candidates; generating more candidates without seeing the consequences is worse.

**Question 3 (where C's effect comes from):** at iteration 1 in the ambiguous stratum, `A0B0C1` and `S2a` (only the user's answer appended, no structured localization) are both at 100%, and `A0B0C0` at 47%. C resolves vague complaints one iteration earlier, and the effect comes entirely from asking first and getting the user's answer; the structure itself (target ID and modification type) adds nothing. C's loss in the side-condition stratum comes from its stopping rule: U9's localization was still uncertain after asking in 1 of 5 runs in v3 and in 3 of 5 this time, and the 4 configurations with C stopped in those runs. `S2a` has no such rule and reaches 88% within 3 iterations, against 82% for `A0B0C1`.

**Answer to the task's question, combining both batches:**
- On this instance, the bare loop already converges in 96% of trials within 3 iterations (the same in both batches), and the user explains after a failed plan anyway, so there is little room for any of the three mechanisms.
- The largest contribution to reliable convergence comes from B's counterfactual probe, with moderate evidence: B's main effect in the side-condition stratum is positive in both batches (+12 significant, +5 not), and with the same candidates, seeing the consequences beats selecting blind by +18 [+2, +34]. But the overall rule fixed in advance says "cannot tell" in both batches, and the reading fixed in advance for question 2 falls on the boundary.
- C's value lies in asking first (+60 at iteration 1 on vague complaints), not in the structure; the rule "stop if still unclear after asking" costs reliability.
- A has no reliable effect in either batch.
