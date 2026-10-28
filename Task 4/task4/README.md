# Task 4: A Minimal Feedback Collection Pipeline

A small backend that runs the Task 3 TPO loop as a service: a user posts a complaint about a plan in natural language, the service stores it with the plan and the session, turns it into a critique, runs TPO refinement (the LLM edits the optimization model, Gurobi re-solves) and returns the refined plan; every loop iteration is logged. Same CVRP instance and model as Tasks 2 and 3 (`qwen3.8-max` through DashScope, `enable_thinking=false`; Gurobi 13.0.3), all on a laptop CPU. FastAPI with JSON files on disk; interactive API docs at `/docs`. Design decisions and deviations: [`DECISIONS.md`](DECISIONS.md).

> **After the 2026-10 audit** a second version, task4_v2, fixes one service rule (a data correction that leaves the optimal routes unchanged was never shown and was rolled back) and runs Task 2's fixed components. Sections 1 to 9 describe task4_v1 as frozen and run; its code, `service_freeze.json` and results are unchanged. Section 10 reports task4_v2; section 11 the review fixes of task4_v2.1, checked on the v2 runs' records without the LLM; section 12 task4_v3, the service with the re-designed experiment's loop, run on the new test cases.

## 1. Requirements and where they are met

| Required component | Implementation |
|---|---|
| Feedback ingestion endpoint: natural-language complaint stored with its solution and session ID | `POST /sessions/{sid}/feedback`; the record `sessions/<sid>/feedback/<fid>.json` holds the complaint, a snapshot of the plan it is about (version and routes) and the session ID |
| Complaint processor: stored feedback to TPO-compatible textual critique | [`processor.py`](feedback_service/processor.py): Task 2's feedback localization (5 samples, rule-based confidence); low confidence asks the user one clarifying question and never reaches TPO; high confidence yields the structured critique (target ID, aspect, direction, modification type, threshold, evidence) plus its text |
| Trigger: receiving feedback starts a TPO refinement run and returns the refined solution | [`worker.py`](feedback_service/worker.py): the request enqueues a job; one engine thread runs it; the response (by default) waits and carries the refined plan |
| Logging layer: input solution, complaint, critique, refined solution, feasibility per iteration | `sessions/<sid>/iterations.jsonl`, one line per iteration, also at `GET /sessions/{sid}/iterations` (section 5) |
| REST API with in-memory or file storage | FastAPI ([`app.py`](feedback_service/app.py)) over JSON files written atomically ([`store.py`](feedback_service/store.py)); the files are the source of truth and survive a restart |

## 2. Architecture

```
 client (user, or the simulated user in the end-to-end run)
      |  HTTP + JSON
      v
 FastAPI routes (app.py)          validate -> store -> enqueue -> wait -> view
      |                                   |
      v                                   v
 job queue + ONE engine thread     file store (store.py)
 (worker.py), in arrival order:      sessions/<sid>/session.json
   - initial solve of a session      sessions/<sid>/feedback/<fid>.json
   - localization / clarification    sessions/<sid>/iterations.jsonl   <- logging layer
     (processor.py)                  sessions/<sid>/events.jsonl       <- audit trail
   - TPO iterations (engine.py)      logs/llm_requests.jsonl            (credentials redacted)
       Task 3 Trial.step():
         critique -> LLM proposal(s) -> [counterfactual probe + selector] -> Gurobi commit
```

- **Why a single engine thread.** Task 2's model code shares one Gurobi environment per process and Task 3's counterfactual probe keeps resident models; neither is thread-safe (Task 3 parallelized over processes for this reason). All solver and LLM work therefore runs on one thread; HTTP threads only validate, store, enqueue and wait. A test submits three sessions concurrently and checks that every component call ran on that thread. One uvicorn process only.
- **Why the LLM edits the model, not the routes.** As in Tasks 2 and 3: the LLM outputs soft constraints, objective weights or data corrections (at most 4, Task 3's whitelist and ranges), and Gurobi guarantees feasibility.
- **Configuration.** Each session picks one of Task 3's eight configurations (A attribution, B counterfactual probing, C localization). The default is `A0B0C1`: in Task 3 every configuration with C converged in the first iteration on all 30 trials, A and B added nothing measurable once C was on, and the TPO part of `A0B0C1` used about 1.8k tokens per trial against 25k for `A1B1C1` (localization not included). That was task3_v1. In the re-designed experiments C no longer helps within 3 iterations (task3_v3.1: `A0B0C1` 82% against 96% for `A0B0C0`, partly because C stops a trial whose complaint stays unclear after the question). The default stays `A0B0C1` because the task defines the localization's structured output as the critique the loop consumes and requires a low-confidence localization to ask the user first; with C off the service passes the raw complaint and never asks.

## 3. API

| Method and path | Body | Effect |
|---|---|---|
| `GET /health` | | status, model, default configuration, queue length, Task 3 hash check |
| `GET /instance` | | the public instance specification |
| `POST /sessions` | `config?`, `label?`, `model_modifications?`, `solution?`, `max_iterations?` (1 to 3) | new session; plan v0 is the optimal plan unless one is given (checked for feasibility) |
| `GET /sessions`, `GET /sessions/{sid}` | | sessions; one session with its current plan, plan versions, accepted modifications and complaints |
| `POST /sessions/{sid}/feedback` | `complaint`, `solution_version?` or `solution?` | **ingestion + trigger**: returns a clarifying question or the refined plan |
| `GET /feedback/{fid}` | | one complaint: status, critique, current plan, iterations, LLM usage |
| `POST /feedback/{fid}/clarification` | `answer` | re-localizes with the answer; refines if confident, stops otherwise |
| `POST /feedback/{fid}/reply` | `resolved`, `comment?`, `stop?` | accept the plan, or give feedback for the next iteration, or give up |
| `GET /sessions/{sid}/iterations`, `GET /sessions/{sid}/events` | | logging layer; audit trail |

Work-starting POSTs take `?wait=true` (default: 200 with the result, or 202 after 600 s) or `?wait=false` (202 at once; poll `GET /feedback/{fid}`). Request bodies reject unknown fields, so nothing beyond the documented fields can reach a session. Errors: 404 unknown ID; 409 a complaint about a plan that is no longer current, a second complaint while one is open, or a reply in the wrong state; 422 invalid input (empty complaint, a modification outside the whitelist, an infeasible initial plan).

## 4. Life of a complaint

```
received -> processing -> needs_clarification -(answer)-> processing -> awaiting_reply | stopped_low_confidence
                       -> awaiting_reply -(resolved)-> resolved
                                         -(not resolved, iterations left)-> processing -> awaiting_reply ...
                                         -(not resolved, 3 iterations used)-> not_converged
                                         -(stop)-> stopped_by_user
                       -> failed   (LLM unavailable, engine error, or process stopped mid-job)
```

Rules that make it safe to run with real users:

1. **Low confidence never reaches TPO.** The localizer's question goes back to the user; if the answer still leaves it unsure, the complaint stops and the user is asked to rephrase.
2. **Only accepted changes stay.** Until the user replies "resolved", the plan and the modifications are a proposal. Any other ending returns the session to the plan the complaint was about (everything stays in the logs). Accepted modifications stay in force for later complaints (and are shown to the LLM), with soft-constraint IDs rewritten so they cannot collide.
3. **The user is asked only about a plan they have not seen.** If an iteration produces no new plan (all candidates invalid, no feasible plan, or the same routes), the service runs the next iteration at once, feeding back the user's last statement about this plan.
4. **One question at a time per session.** A complaint must name the current plan version, and a session has at most one open complaint.
5. **An LLM outage is a failure, not an answer.** Task 2's client returns an empty result on a network error or HTTP 403 instead of raising; unchecked, localization would then look "not confident" and proposals "invalid". The service counts transport failures per job and marks the complaint `failed` (`llm_unavailable`) without keeping anything the job computed.

## 5. Logging layer and storage

Each line of `iterations.jsonl` (the five required fields in bold):

| Field | Content |
|---|---|
| `session_id`, `feedback_id`, `iteration`, `config`, `time`, `trigger` | trigger: feedback, clarification, reply or auto_continue |
| **`input_solution`** | version, routes and all indicators of the plan the iteration started from |
| **`complaint`** | the complaint, plus every reply the user gave so far |
| **`critique`** | the structured localization with evidence recomputed on the input plan (null when C is off), and the exact critique text in the prompt: complaint, clarification, localization, attribution and previous attempts |
| `candidates`, `selection`, `committed_modifications`, `status`, `rationale` | each candidate's modifications, validation errors and probe result; the selector's choice; what was committed; committed, rejected or no_plan |
| **`refined_solution`** | version, routes, indicators, and what changed (customers that switched vehicle, edges added and removed) |
| **`feasibility`** | the solver status, and an independent pure-Python check of the plan on the data in force and on the data the user has confirmed, with the data changes the plan depends on |
| `llm`, `wall_s`, `detail` | requests, tokens and LLM time of the iteration; wall time; Task 3's full step record including the prompt |

`events.jsonl` records every API action and state change (complaint received, question asked, answer, reply, revert, failure), so a session can be replayed from the two logs. JSON documents are written to a temporary file and renamed. At start-up the service reloads every session; a complaint whose job was queued or running when the process stopped is marked `failed` (`interrupted_by_restart`) and its session rolled back, while complaints waiting for a clarification or a reply simply continue.

## 6. Integration with Tasks 2 and 3

The service does not reimplement the loop. It imports Task 3's frozen `tpo` package (and through it Task 2's components) read-only, refuses to start if any of the 49 files hashed in Task 3's `protocol.json` has changed, and adapts the loop with three seams instead of edits ([`engine.py`](feedback_service/engine.py)): a user object whose verdict is always "pending" inside a step; the user's reply written into the trial history before the next step; and a subclass that shows accepted modifications to the LLM (without them the prompt is Task 3's byte for byte).

**Equivalence test.** For each of the 8 configurations and 6 scenarios (fixed at once; new plan then fixed; rejected proposal and unchanged plan then fixed; never fixed; clarified then fixed; still unclear after clarification), Task 3's simulated user drives the service over HTTP, and the result is compared with calling Task 3's `run_trial` directly on the same synthetic case, stub LLM script and components. Every iteration has the same status, full prompt text, candidates, selection, committed modifications and plan, and the outcome is the same (48 tests). The test also checks which branches each scenario took, and that no private case field reached the service.

## 7. End-to-end run

A real server process (`serve.py`), real HTTP, the real LLM and Gurobi, and Task 3's checker-based simulated user as the client. The client sends only what a user would: the plan, the complaint, the case's model modifications, the clarification answer when asked, and Task 3's fixed reply templates; checkers and thresholds stay on the client side. The 10 Task 2 test cases ran under the default configuration and under the full system, one session each, after the service code was frozen ([`service_freeze.json`](service_freeze.json)); while T5 waited for its reply, the server was stopped with SIGTERM and started again. Full report: [`results/e2e_test/e2e_report.md`](results/e2e_test/e2e_report.md).

| Config | Resolved | At iteration 1 | Asked to clarify | LLM requests | Tokens | `POST /feedback`, median (range) | Task 3, same config |
|---|---|---|---|---|---|---|---|
| `A0B0C1` (default) | 10/10 | 10/10 | 3 (T2, T6, T8) | 75 | 118k | 11.9 s (9.8 to 13.1) | 30/30 at iteration 1 |
| `A1B1C1` (full system) | 9/10 | 9/10 | 4 (T2, T6, T7, T8) | 106 | 329k | 17.1 s (9.0 to 20.9) | 30/30 at iteration 1 |

- 181 LLM requests, all answered; 0.45M tokens; 6 minutes 25 seconds. Almost all of the time is the LLM's (95 to 99% of the time spent inside HTTP calls); a Gurobi commit solve takes 58 to 70 ms (median), creating a session 72 ms (median), a reply 4 to 10 ms.
- **The restart**: T5's complaint was `awaiting_reply` with plan v1 before and after; the new process reloaded the 5 sessions created so far, recovered no interrupted job, and handled the reply. After the run all 20 sessions were listed and none had an open complaint.
- **The logging layer** holds 19 iteration records (one per TPO iteration), each with the five required fields; the independent feasibility check agrees with the solver on every one. In T5 and T6 the committed list corrects a demand as the user stated (customer 4 to 20, customer 7 to 18); those plans are also feasible on the data without the correction.
- **T7 under `A1B1C1` stopped at the confidence gate**, which is the behaviour the task asks for, but the cause deserves a note. The localization prompt is byte-for-byte the one Task 3 sent for T7 (only the seeds differ). All five samples named the same target (`balance`, limit 50 km) and none marked the complaint as ambiguous, but they split 3 to 2 between a soft constraint and an objective weight, and Task 2's frozen rule needs 4 of 5 to agree on target *and* modification type. The service asked Task 2's generic question (which vehicle, customer or aspect), the user answered about the target (which was never in doubt), and the second localization split 3 to 2 again. A user cannot settle a choice that is internal to the system, so the rule should only count disagreement the user can resolve (here the target), leaving the modification type to TPO or to the counterfactual probe. Not changed here: Task 2's localizer is frozen and the test run is one-shot. (Fixed after the audit in task2_v2; T7 resolves at iteration 1 under task4_v2, section 10.) Every other low-confidence localization, in Task 3 (9 of its 30 for these cases) and here (10 of the other 29, test and dev), was a complaint written to be ambiguous (T2, T6, T8; D1, D4).
- A development run before the freeze (5 dev cases, both configurations, one restart) resolved 10 of 10 in the first iteration with 95 requests ([`results/e2e_dev/`](results/e2e_dev/e2e_report.md)).
- Acceptance checks (frozen hashes, all cases final, storage fields, log fields, restart, no private case field reached the service, no credential, no bytecode written into Tasks 2 to 4, tests): all 10 pass ([`results/acceptance.json`](results/acceptance.json)).

One exchange from the run (T2, default configuration, IDs shortened):

```
POST /sessions {"label": "T2", "solution": {"routes": [[1,4,7,2],[5,3,6,8]]}, ...}        201, 0.07 s
POST /sessions/s_db56/feedback {"complaint": "Vehicle 1 is doing too much work.",
                                "solution_version": 0}                                    200, 10.9 s
  -> status needs_clarification, question: "Do you mean vehicle 1's load (99 units), its route
     length (140 km), or its number of stops (4) is too high?"
POST /feedback/f_829c/clarification {"answer": "I mean the load: ... It should carry at most 92 units."}
                                                                                         200, 10.8 s
  -> status awaiting_reply, iteration 1
     critique: target W[1] (load, decrease), add_soft_constraint, limit 92, evidence W[1] = 99
     committed: {"op": "add_soft_constraint", "target": "W[1]", "sense": "<=", "rhs": 92, "penalty": 500}
     plan v1: [[1,4,6,8],[2,7,5,3]], total distance 390 (was 351), load of vehicle 1: 91 (was 99)
POST /feedback/f_829c/reply {"resolved": true}                                            200, 0.006 s
  -> status resolved; plan v1 and its modification stay in force for later complaints
```

## 8. Limitations

1. One engine thread: complaints from different sessions queue behind each other (a complaint call took 9 to 37 s in these runs, almost all of it LLM time). Scaling out means several worker processes, each with its own Gurobi environment, with sessions assigned to workers; not needed here.
2. No authentication, tenants or rate limits; storage is local JSON files. Task 5 discusses the production version.
3. Requests block for up to 600 s by default (`wait=false` and polling avoid it).
4. A failed complaint is not retried by the service; the user submits it again.
5. The service cannot tell whether a plan is really acceptable; it relies on the user's reply. The end-to-end run uses Task 3's checker-based simulated user, which answers more consistently than people do.

## 9. Reproduce

```bash
cd "Task 4/task4"
export PYTHONDONTWRITEBYTECODE=1
python -m pytest -q                       # 73 tests, no network, stub LLM
source ~/.dashscope_env                   # DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL (never committed)
python serve.py --data store/ --port 8004 # then open http://127.0.0.1:8004/docs
python e2e_client.py --cases test --configs A0B0C1,A1B1C1 --restart-at A0B0C1:5 --out results/e2e_test
python report_e2e.py --out results/e2e_test
python acceptance.py
```

`e2e_client.py` starts its own server process; on test cases it refuses to run unless `service_freeze.json` matches the code. New dependencies: `fastapi`, `uvicorn`, `httpx` ([`env.json`](env.json)).

## 10. task4_v2 (after the 2026-10 audit)

New code in [`feedback_service_v2/`](feedback_service_v2/), [`serve_v2.py`](serve_v2.py), [`e2e_client_v2.py`](e2e_client_v2.py) and [`freeze_service_v2.py`](freeze_service_v2.py); `feedback_service/` is imported unchanged and subclassed. Tests: `tests/test_v2_service.py` (77 tests in total, all pass).

**The defect (audit F2).** task4_v1 decided from the routes alone whether an iteration had produced something to show the user. A correct data correction that leaves the optimal routes unchanged therefore never reached the user: the loop ran on, used up its three iterations, closed the complaint as `not_converged` and rolled the correction back.

**The fix.** An iteration has something to show when the routes changed *or the data in force changed*. Same routes on corrected data become a new plan version of kind `data_corrected`; the view carries the notice "Your data correction is applied. On the corrected data the current routes are still the best plan, so they stay as they are. Please confirm.", and accepting it keeps the correction in force. Same routes on the same data (a soft constraint or weight that moved nothing) still runs the next iteration at once, as in v1. The service also runs Task 2's task2_v2 components through Task 3's `tpo_v2` adapter (fixed attribution; localization rule that counts only what the user can answer), and refuses to start unless both Task 3 protocols match.

**Runs (2026-10-27, after freezing [`service_freeze_v2.json`](service_freeze_v2.json); 256 requests, all answered on the first attempt by `qwen3.8-max`).**

| Run | task4_v1 | task4_v2 |
|---|---|---|
| Test cases, `A0B0C1` | 10/10 resolved, all at iteration 1 | 10/10 resolved, all at iteration 1 (T2, T6, T8 asked first) |
| Test cases, `A1B1C1` | 9/10; T7 stopped at the confidence gate | **10/10**, all at iteration 1; T7 resolved without a question |
| Data corrections kept after acceptance (T5, T6) | yes | yes, in both configurations |
| Restart while T5 waited for its reply | state kept | state kept (plan v1 before and after, 5 sessions reloaded, nothing to recover) |
| Iteration records with the five required fields / solver and independent feasibility check agree | 19 / 19 | 20 / 20 |

The audit scenario ([`scenarios/audit_cases.json`](scenarios/audit_cases.json), written after the audit and reported separately from the test cases): customer 4's order grows from 12 to 13 units; vehicle 1 then carries exactly 100 of 100, so the optimal routes do not change. Both services, both configurations, Task 3's checker-based simulated user:

| Service, config | Outcome | Accepted modifications afterwards | Final plan |
|---|---|---|---|
| task4_v1, `A0B0C1` | `not_converged` after 3 iterations; the LLM committed `demand[4] = 13` every time, the routes never changed, so nothing was shown | none: the correction was rolled back | 351 km, on the old data |
| task4_v1, `A1B1C1` | "resolved" at iteration 2: told the first answer did not fix the complaint, the LLM added an unneeded `balance <= 20` constraint to produce different routes | `demand[4] = 13` **and** `balance <= 20` (stays in force for later complaints) | **398 km** |
| task4_v2, `A0B0C1` | resolved at iteration 1: `data_corrected` plan shown with the notice, user confirmed | `demand[4] = 13` | 351 km, on the corrected data |
| task4_v2, `A1B1C1` | resolved at iteration 1, same | `demand[4] = 13` | 351 km |

The second v1 row is the worse failure: the checker only asks whether the plan works with 13 units, so the simulated user accepted a plan 47 km longer than necessary together with a constraint nobody asked for.

**Latency of this run is not comparable with task4_v1's.** During the v2 test run a Time Machine backup and the editor's C++ indexer were running on the machine (15-minute load average about 18 on 12 cores). `POST /feedback` medians were 13.9 s (`A0B0C1`) and 35.1 s (`A1B1C1`); in the `A1B1C1` part even the commit solve took 0.42 s against 0.06 s earlier in the same run. The functional results above do not depend on timing. The cost of the v2 attribution itself, measured in-process on an idle machine: 0.077 s per attributed decision against 0.051 s for v1 (Task 3's batch medians: 0.085 vs 0.065 s); the test run was not repeated to get cleaner timings.

**Known issue found after the runs.** The v2 rule treats any change of the data in force as "something to show" and always attaches the "your data correction is applied" notice. Two cases are wrong: (a) the user rejects a `data_corrected` plan and the next proposal drops the correction (each list replaces the last), so the data reverts and the reverted plan is shown with a notice that claims the correction is in force; (b) the LLM changes data nobody asked for and the routes stay the same, so the invented change is presented as the user's correction and stops the search for a real fix. Neither happened in the reported runs: the only `data_corrected` iterations were the audit scenario's two, both with the requested correction, and no user rejected any plan. The fix is to compare the new (routes, data) state with every state the user has already seen in the complaint, and to list the concrete data changes in the notice instead of calling them the user's correction; it is fixed in task4_v2.1 (section 11), not in the frozen service.

```bash
python -m pytest -q
source ~/.dashscope_env
python e2e_client_v2.py --cases dev --configs A0B0C1 --out results/e2e_dev_v2
python freeze_service_v2.py
python e2e_client_v2.py --cases test --configs A0B0C1,A1B1C1 --restart-at A0B0C1:5 --out results/e2e_test_v2
python e2e_client_v2.py --cases scenarios/audit_cases.json --configs A0B0C1,A1B1C1 --out results/audit_v2
python e2e_client.py    --cases scenarios/audit_cases.json --configs A0B0C1,A1B1C1 --out results/audit_v1
python report_e2e.py --out results/e2e_test_v2
```

## 11. task4_v2.1: the review fixes, checked on the v2 records (no new run)

New code in [`feedback_service_v21/`](feedback_service_v21/) (subclasses `FeedbackServiceV2`), [`serve_v21.py`](serve_v21.py) (port 8006), [`freeze_service_v21.py`](freeze_service_v21.py) and [`recheck_v21.py`](recheck_v21.py). `feedback_service/`, `feedback_service_v2/` and both earlier freezes are unchanged.

**State-change rule.** An iteration has something to show when its (routes, data in force) is a state the user has not seen in this complaint: neither the plan complained about nor a plan shown since. The states seen are kept with the trial. A shown plan whose data differs from the plan the iteration started from lists the changed values in its notice ("The routes stay as they are, but the data the plan uses changed: customer 4's order size 12 -> 13. ... Please check that these values are correct before you confirm.") and in `source.data_changes`; it no longer says whose correction they are. A plan with new routes on changed data now gets such a notice too (v2 showed none). The components are Task 2's task2_v2.1, through Task 3's `tpo_v21`; the service refuses to start unless both Task 3 protocols and Task 2's `v21/protocol_v21.json` match.

Tests: [`tests/test_v21_service.py`](tests/test_v21_service.py), 9 (86 in Task 4, all pass), with v2's behaviour kept beside v2.1's as a regression record: after a rejected correction that the next proposal drops, v2 shows the plan complained about again with "your data correction is applied", v2.1 runs on and closes `not_converged`; a demand change the LLM made on a stops complaint is called the user's correction by v2 and listed for checking by v2.1.

**Re-check** ([`results/recheck_v21/recheck.md`](results/recheck_v21/recheck.md); frozen first in [`service_freeze_v21.json`](service_freeze_v21.json)). Each complaint of `e2e_dev_v2`, `e2e_test_v2` and `audit_v2` is replayed iteration by iteration with v2.1's rule, and the components are re-computed on the logged states and samples:

| Records | Checked | v2.1 differs from v2 |
|---|---:|---:|
| State-change decisions (27 iterations, 27 complaints) | 27 | 0 |
| Attribution items (`A1B1C1` test cases and audit scenario) | 175 | 0 |
| Localization sample sets | 35 | 0 |

So every outcome in section 10 is what v2.1 would have produced on the same LLM outputs. The only visible difference: 7 of the 27 plans shown would carry a data notice instead of 2. The two audit plans list "customer 4's order size 12 -> 13" instead of "your correction is applied"; five plans with new routes (T5 in both configurations, T6 in both, one dev case) list the demand the user's complaint asked for (customer 4: 12 -> 20, customer 7: 11 -> 18, customer 2: 24 -> 30), where v2 showed no notice. Every one of these data changes is the correction the complaint states, so the v2 runs contain no invented data change, and the simulated user, which does not read the notice, would have answered the same.

## 12. task4_v3: the service with task3_v3's loop, on the new test cases (2026-10-27)

Design: [`../../DESIGN_V3.md`](../../DESIGN_V3.md). New code: [`feedback_service_v3/`](feedback_service_v3/) (subclasses `FeedbackServiceV21`), [`serve_v3.py`](serve_v3.py) (port 8007), [`e2e_client_v3.py`](e2e_client_v3.py), [`freeze_service_v3.py`](freeze_service_v3.py), [`report_e2e_v3.py`](report_e2e_v3.py). Frozen in [`service_freeze_v3.json`](service_freeze_v3.json) before the run.

**What changed.** Task 3's v3 loop starts every iteration from the plan the user complained about (the user's conditions "vehicle 1 keeps its route", "at most two customers change trucks" refer to it); the service does the same: `EngineV3.trial()` restores only the history, and within one refinement the trial is reset before every further iteration. The plan shown and its modifications stay in the feedback record for the reply and for acceptance. The client is Task 3's v3 simulated user (the same words in every configuration). Components: task2_v2.1.

**Equivalence with Task 3** (`tests/test_v3_service.py`, 26 tests; 112 in Task 4 in total, all pass): driven over HTTP by the v3 user with a scripted LLM, the service reproduces `tpo_v3.loop.run_trial` in all 8 configurations on three development-case scenarios (side case fixed at iteration 2, ambiguous case clarified then fixed, side case never fixed): the same prompt, candidates, selection, committed modifications and plan in every iteration, and the same outcome. One difference remains and is pinned by a test: when an iteration returns a state the user has already seen, the service does not show it and runs on with the user's last words, while Task 3's simulated user comments on that plan. The two coincide whenever every iteration produces a new plan.

**Run** (Task 2's v3 test cases, `A0B0C1` and `A1B1C1`, one run each, 2026-10-27 14:21–14:34; 224 requests, all answered; [`results/e2e_test_v3/e2e_report.md`](results/e2e_test_v3/e2e_report.md)):

| Config | Resolved | At iteration 1 | Control / ambiguity / side | Clarified | Requests | Tokens | `POST /feedback` median | Task 3 v3, same config (50 trials) |
|---|---|---|---|---|---|---|---|---|
| A0B0C1 | 10/10 | 8 | 2/2 / 3/3 / 5/5 | 6 | 93 | 152k | 16.8 s | 45/50, 41 at iteration 1 |
| A1B1C1 | 9/10 | 8 | 2/2 / 3/3 / 4/5 | 5 | 131 | 541k | 20.4 s | 48/50, 43 at iteration 1 |

The one complaint not resolved is U10 with attribution on, the case where Task 3 found that A makes the LLM re-add the session's earlier constraint and run out of modifications. All 20 sessions present after the run, none left open; 20/20 iteration records have the five required fields. Two resolved plans (U3 in both configurations, U7 in `A1B1C1`) are 21–22 km longer than the shortest plan that meets every condition; the user's conditions did not limit distance there. Task 3's batch had finished before this run, but Task 2, 3 and 5's test suites ran for about two minutes during the `A1B1C1` part, so its latencies may be slightly inflated; the functional results do not depend on timing.

```bash
python -m pytest -q tests/test_v3_service.py
python freeze_service_v3.py                         # refuses if service_freeze_v3.json exists
source ~/.dashscope_env
python e2e_client_v3.py --configs A0B0C1,A1B1C1 --out results/e2e_test_v3
python report_e2e_v3.py --out results/e2e_test_v3
```

## 13. task4_v3.1: the session's own modifications are shown (2026-10-27)

Design: [`../../DESIGN_V31.md`](../../DESIGN_V31.md). New code: [`feedback_service_v31/`](feedback_service_v31/) (subclasses `FeedbackServiceV3`), [`serve_v31.py`](serve_v31.py) (port 8008), [`e2e_client_v31.py`](e2e_client_v31.py), [`freeze_service_v31.py`](freeze_service_v31.py), [`report_e2e_v31.py`](report_e2e_v31.py). Frozen in [`service_freeze_v31.json`](service_freeze_v31.json) after Task 3's `protocol_v31.json` and before the run.

**What changed.** The service already showed the modifications a user had accepted with earlier complaints, but not the ones a session was created with (`session_modifications`), although the solver's model contains them. `ServiceTrialV31` lists them first, in the block Task 3's v3.1 loop uses (the same function), then the accepted ones, then "Modifications currently in force". Sessions with neither get task4_v3's prompts byte for byte (tested).

**Equivalence with Task 3** (`tests/test_v31_service.py`, 36 tests; 148 in Task 4 in total, all pass): over HTTP, in all 8 configurations, the service reproduces `tpo_v31.loop.run_trial` on four development-case scenarios, two of them with session modifications (a data correction, P10; a soft constraint); a second complaint in the same session shows the session block before the accepted block.

**Run** (Task 2's v3 test cases, `A1B1C1`, one run, 2026-10-27 16:31–16:39; 118 requests, all answered; [`results/e2e_test_v31/e2e_report.md`](results/e2e_test_v31/e2e_report.md)): 8/10 resolved, 7 at iteration 1; control 2/2, ambiguity 3/3, side 3/5; 4 clarifications; 470k prompt + 13k completion tokens; `POST /feedback` median 24.9 s. Task 3 v3.1, same configuration: 45/50. Not resolved: U9, whose localization stayed unsure after the clarification, so the service did not pass it to TPO (Task 3 v3.1 stops there in 3 of 5 runs); U10 after 3 iterations (its prompts did list the session's `same[4,5]`). Task 3's v3 explanation of U10 (attribution makes the LLM re-add that constraint) did not hold up in Task 3 v3.1 (section 10 there). 10/10 sessions present and closed; 10/10 iteration records complete. Nothing else ran during this run. `serve_v31.py`'s start-up check covers the v1 to v2.1 protocols, as `serve_v3.py`'s did; the v3 and v3.1 files are checked by `e2e_client_v31.py` against `service_freeze_v31.json` before a run.

```bash
python -m pytest -q tests/test_v31_service.py
python freeze_service_v31.py                        # refuses if service_freeze_v31.json exists
source ~/.dashscope_env
python e2e_client_v31.py --configs A1B1C1 --out results/e2e_test_v31
python report_e2e_v31.py --out results/e2e_test_v31
```

