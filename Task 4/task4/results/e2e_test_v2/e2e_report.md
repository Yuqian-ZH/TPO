# End-to-end run

Cases: `Task 2/task2/cases/test_cases.json` (10), configurations A0B0C1, A1B1C1, one run each; 2026-10-27T10:52:44+08:00 to 2026-10-27T11:03:32+08:00. LLM requests in the service log: 180.

| Config | Resolved | At iteration 1 | Clarified | LLM requests | Tokens (prompt + completion) | POST /feedback median s | POST /reply median s | Task 3 same config (30 trials) |
|---|---|---|---|---|---|---|---|---|
| A0B0C1 | 10/10 | 10/10 | 3 | 75 | 111,451 + 6,665 | 13.9 | 0.01 | 30/30 converged, 30 at iteration 1 |
| A1B1C1 | 10/10 | 10/10 | 3 | 105 | 340,801 + 9,124 | 35.1 | 0.03 | 30/30 converged, 30 at iteration 1 |

| Config | Case | Status | Iterations | Clarified | Final distance | LLM requests | POST /feedback s | Triggers |
|---|---|---|---|---|---|---|---|---|
| A0B0C1 | T1 | resolved | 1 |  | 368 | 6 | 11.95 | feedback |
| A0B0C1 | T2 | resolved | 1 | yes | 390 | 11 | 15.538 | clarification |
| A0B0C1 | T3 | resolved | 1 |  | 368 | 6 | 13.484 | feedback |
| A0B0C1 | T4 | resolved | 1 |  | 363 | 6 | 14.927 | feedback |
| A0B0C1 | T5 | resolved | 1 |  | 368 | 6 | 11.902 | feedback |
| A0B0C1 | T6 | resolved | 1 | yes | 391 | 11 | 14.004 | clarification |
| A0B0C1 | T7 | resolved | 1 |  | 368 | 6 | 13.795 | feedback |
| A0B0C1 | T8 | resolved | 1 | yes | 369 | 11 | 14.488 | clarification |
| A0B0C1 | T9 | resolved | 1 |  | 368 | 6 | 11.471 | feedback |
| A0B0C1 | T10 | resolved | 1 |  | 368 | 6 | 14.221 | feedback |
| A1B1C1 | T1 | resolved | 1 |  | 368 | 9 | 29.245 | feedback |
| A1B1C1 | T2 | resolved | 1 | yes | 390 | 14 | 12.658 | clarification |
| A1B1C1 | T3 | resolved | 1 |  | 368 | 9 | 39.137 | feedback |
| A1B1C1 | T4 | resolved | 1 |  | 363 | 9 | 31.074 | feedback |
| A1B1C1 | T5 | resolved | 1 |  | 368 | 9 | 39.124 | feedback |
| A1B1C1 | T6 | resolved | 1 | yes | 391 | 14 | 13.605 | clarification |
| A1B1C1 | T7 | resolved | 1 |  | 368 | 9 | 48.402 | feedback |
| A1B1C1 | T8 | resolved | 1 | yes | 369 | 14 | 13.745 | clarification |
| A1B1C1 | T9 | resolved | 1 |  | 368 | 9 | 44.633 | feedback |
| A1B1C1 | T10 | resolved | 1 |  | 368 | 9 | 44.268 | feedback |

Restart: the server process was stopped and started again while T5 (A0B0C1) waited for its first reply; after the restart the complaint was `awaiting_reply` with plan v1 (before: `awaiting_reply`, v1), 5 sessions were reloaded, and the reply was handled by the new process.

Final check after the run: {"sessions_listed": 20, "all_sessions_present": true, "none_open": true}.

## Example: an ambiguous complaint, end to end

Session `s_ba09d294`, feedback `f_b2516d3d`, config A0B0C1, case T2.

1. Session created with plan v0 `[[1, 4, 7, 2], [5, 3, 6, 8]]`.
1. Complaint received about plan v0: "Vehicle 1 is doing too much work."
1. Localization not confident (5 LLM requests); the service asks: "Do you mean vehicle 1 is carrying too much load (99 units) or driving too many kilometers (140 km)?"
1. User answers: "I mean the load: vehicle 1 leaves the depot with 99 units, which is practically full. It should carry at most 92 units."
1. Critique: target `W[1]` (load, decrease), add_soft_constraint, threshold 92, evidence {'W[1]': 99, 'W[2]': 90, 'capacity': 100}.
1. TPO iteration 1 (trigger: clarification): the LLM proposed `[{"op": "add_soft_constraint", "target": "W[1]", "sense": "<=", "rhs": 92, "penalty": 500}]`; Gurobi re-solved to plan v1 `[[1, 4, 6, 8], [2, 7, 5, 3]]`, total distance 390, feasible True. Proposer's rationale: "User wants vehicle 1 load at most 92. Current load is 99, so adding a soft constraint with high penalty will force the solver to redistribute customers to meet this limit."
1. User reply: resolved=True
1. Final status: resolved.
