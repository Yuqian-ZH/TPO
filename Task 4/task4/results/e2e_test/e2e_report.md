# End-to-end run

Cases: `Task 2/task2/cases/test_cases.json` (10), configurations A0B0C1, A1B1C1, one run each; 2026-10-23T13:08:36+08:00 to 2026-10-23T13:15:01+08:00. LLM requests in the service log: 181.

| Config | Resolved | At iteration 1 | Clarified | LLM requests | Tokens (prompt + completion) | POST /feedback median s | POST /reply median s | Task 3 same config (30 trials) |
|---|---|---|---|---|---|---|---|---|
| A0B0C1 | 10/10 | 10/10 | 3 | 75 | 111,502 + 6,777 | 11.86 | 0.01 | 30/30 converged, 30 at iteration 1 |
| A1B1C1 | 9/10 | 9/10 | 4 | 106 | 319,257 + 9,253 | 17.13 | 0.01 | 30/30 converged, 30 at iteration 1 |

| Config | Case | Status | Iterations | Clarified | Final distance | LLM requests | POST /feedback s | Triggers |
|---|---|---|---|---|---|---|---|---|
| A0B0C1 | T1 | resolved | 1 |  | 368 | 6 | 9.778 | feedback |
| A0B0C1 | T2 | resolved | 1 | yes | 390 | 11 | 10.926 | clarification |
| A0B0C1 | T3 | resolved | 1 |  | 368 | 6 | 13.056 | feedback |
| A0B0C1 | T4 | resolved | 1 |  | 363 | 6 | 13.071 | feedback |
| A0B0C1 | T5 | resolved | 1 |  | 368 | 6 | 11.336 | feedback |
| A0B0C1 | T6 | resolved | 1 | yes | 391 | 11 | 12.69 | clarification |
| A0B0C1 | T7 | resolved | 1 |  | 368 | 6 | 10.935 | feedback |
| A0B0C1 | T8 | resolved | 1 | yes | 369 | 11 | 12.377 | clarification |
| A0B0C1 | T9 | resolved | 1 |  | 368 | 6 | 10.738 | feedback |
| A0B0C1 | T10 | resolved | 1 |  | 368 | 6 | 12.463 | feedback |
| A1B1C1 | T1 | resolved | 1 |  | 368 | 9 | 18.198 | feedback |
| A1B1C1 | T2 | resolved | 1 | yes | 390 | 14 | 11.862 | clarification |
| A1B1C1 | T3 | resolved | 1 |  | 368 | 9 | 20.865 | feedback |
| A1B1C1 | T4 | resolved | 1 |  | 363 | 9 | 20.559 | feedback |
| A1B1C1 | T5 | resolved | 1 |  | 368 | 9 | 17.255 | feedback |
| A1B1C1 | T6 | resolved | 1 | yes | 391 | 14 | 13.855 | clarification |
| A1B1C1 | T7 | stopped_low_confidence | 0 | yes | None | 10 | 8.963 |  |
| A1B1C1 | T8 | resolved | 1 | yes | 369 | 14 | 11.059 | clarification |
| A1B1C1 | T9 | resolved | 1 |  | 368 | 9 | 17.009 | feedback |
| A1B1C1 | T10 | resolved | 1 |  | 368 | 9 | 19.144 | feedback |

Restart: the server process was stopped and started again while T5 (A0B0C1) waited for its first reply; after the restart the complaint was `awaiting_reply` with plan v1 (before: `awaiting_reply`, v1), 5 sessions were reloaded, and the reply was handled by the new process.

Final check after the run: {"sessions_listed": 20, "all_sessions_present": true, "none_open": true}.

## Example: an ambiguous complaint, end to end

Session `s_db5643a1`, feedback `f_829c0628`, config A0B0C1, case T2.

1. Session created with plan v0 `[[1, 4, 7, 2], [5, 3, 6, 8]]`.
1. Complaint received about plan v0: "Vehicle 1 is doing too much work."
1. Localization not confident (5 LLM requests); the service asks: "Do you mean vehicle 1's load (99 units), its route length (140 km), or its number of stops (4) is too high?"
1. User answers: "I mean the load: vehicle 1 leaves the depot with 99 units, which is practically full. It should carry at most 92 units."
1. Critique: target `W[1]` (load, decrease), add_soft_constraint, threshold 92, evidence {'W[1]': 99, 'W[2]': 90, 'capacity': 100}.
1. TPO iteration 1 (trigger: clarification): the LLM proposed `[{"op": "add_soft_constraint", "target": "W[1]", "sense": "<=", "rhs": 92, "penalty": 500}]`; Gurobi re-solved to plan v1 `[[1, 4, 6, 8], [2, 7, 5, 3]]`, total distance 390, feasible True. Proposer's rationale: "User wants vehicle 1 load at most 92. Adding soft constraint W[1] <= 92 with high penalty forces solver to redistribute demand, likely moving customer 1 (demand 52) to vehicle 2 and shifting a lighter customer to vehicle 1."
1. User reply: resolved=True
1. Final status: resolved.
