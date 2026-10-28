# End-to-end run

Cases: `Task 2/task2/cases/dev_cases.json` (5), configurations A0B0C1, A1B1C1, one run each; 2026-10-23T13:03:09+08:00 to 2026-10-23T13:06:59+08:00. LLM requests in the service log: 95.

| Config | Resolved | At iteration 1 | Clarified | LLM requests | Tokens (prompt + completion) | POST /feedback median s | POST /reply median s | Task 3 same config (30 trials) |
|---|---|---|---|---|---|---|---|---|
| A0B0C1 | 5/5 | 5/5 | 2 | 40 | 59,138 + 3,834 | 12.37 | 0.01 | - |
| A1B1C1 | 5/5 | 5/5 | 2 | 55 | 181,217 + 5,039 | 18.34 | 0.01 | - |

| Config | Case | Status | Iterations | Clarified | Final distance | LLM requests | POST /feedback s | Triggers |
|---|---|---|---|---|---|---|---|---|
| A0B0C1 | D1 | resolved | 1 | yes | 397 | 11 | 12.37 | clarification |
| A0B0C1 | D2 | resolved | 1 |  | 371 | 6 | 11.81 | feedback |
| A0B0C1 | D3 | resolved | 1 |  | 397 | 6 | 10.97 | feedback |
| A0B0C1 | D4 | resolved | 1 | yes | 351 | 11 | 14.162 | clarification |
| A0B0C1 | D5 | resolved | 1 |  | 366 | 6 | 12.879 | feedback |
| A1B1C1 | D1 | resolved | 1 | yes | 397 | 14 | 14.201 | clarification |
| A1B1C1 | D2 | resolved | 1 |  | 371 | 9 | 37.031 | feedback |
| A1B1C1 | D3 | resolved | 1 |  | 397 | 9 | 18.336 | feedback |
| A1B1C1 | D4 | resolved | 1 | yes | 351 | 14 | 13.352 | clarification |
| A1B1C1 | D5 | resolved | 1 |  | 366 | 9 | 21.463 | feedback |

Restart: the server process was stopped and started again while D2 (A0B0C1) waited for its first reply; after the restart the complaint was `awaiting_reply` with plan v1 (before: `awaiting_reply`, v1), 2 sessions were reloaded, and the reply was handled by the new process.

Final check after the run: {"sessions_listed": 10, "all_sessions_present": true, "none_open": true}.

## Example: an ambiguous complaint, end to end

Session `s_daa771c7`, feedback `f_d3dd17a1`, config A0B0C1, case D1.

1. Session created with plan v0 `[[1, 4, 7, 2], [5, 3, 6, 8]]`.
1. Complaint received about plan v0: "The driver of vehicle 2 says today's plan is exhausting."
1. Localization not confident (5 LLM requests); the service asks: "Do you mean the total distance of vehicle 2's route is too long, or that it has too many stops?"
1. User answers: "It is the number of stops: the driver can make at most 3 deliveries today, but the plan has 4."
1. Critique: target `S[2]` (stops, decrease), add_soft_constraint, threshold 3, evidence {'S[1]': 4, 'S[2]': 4}.
1. TPO iteration 1 (trigger: clarification): the LLM proposed `[{"op": "add_soft_constraint", "target": "S[2]", "sense": "<=", "rhs": 3, "penalty": 500}]`; Gurobi re-solved to plan v1 `[[1, 5, 4, 7, 8], [2, 3, 6]]`, total distance 397, feasible True. Proposer's rationale: "Vehicle 2 driver can make at most 3 deliveries. Adding a soft constraint S[2] <= 3 with high penalty forces the solver to move one stop to vehicle 1, respecting the driver's limit."
1. User reply: resolved=True
1. Final status: resolved.
