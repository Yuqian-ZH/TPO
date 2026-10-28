# End-to-end run, task4_v31

Cases: Task 2 v3 test cases (10), configurations A1B1C1, one run each; 2026-10-27T16:31:47+08:00 to 2026-10-27T16:39:19+08:00. LLM requests in the service log: 118.

| Config | Resolved | At iteration 1 | By stratum (control / ambiguity / side) | Clarified | LLM requests | Tokens | POST /feedback median s | Task 3 v3.1 same config (50 trials) |
|---|---|---|---|---|---|---|---|---|
| A1B1C1 | 8/10 | 7 | 2/2 / 3/3 / 3/5 | 4 | 118 | 469,904 + 12,887 | 24.89 | 45/50 converged, 34 at 1 |

| Config | Case | Stratum | Status | Iterations | Clarified | Plans shown | Excess km | Requests | Triggers |
|---|---|---|---|---|---|---|---|---|---|
| A1B1C1 | U1 | control | resolved | 1 |  | 1 | 0.0 | 9 | feedback |
| A1B1C1 | U2 | control | resolved | 1 |  | 1 | 0.0 | 9 | feedback |
| A1B1C1 | U3 | ambiguity | resolved | 1 | yes | 1 | 22.0 | 14 | clarification |
| A1B1C1 | U4 | ambiguity | resolved | 1 | yes | 1 | 0.0 | 14 | clarification |
| A1B1C1 | U5 | ambiguity | resolved | 1 | yes | 1 | 0.0 | 14 | clarification |
| A1B1C1 | U6 | side | resolved | 2 |  | 2 | 0.0 | 13 | feedback, reply |
| A1B1C1 | U7 | side | resolved | 1 |  | 1 | 0.0 | 9 | feedback |
| A1B1C1 | U8 | side | resolved | 1 |  | 1 | 0.0 | 9 | feedback |
| A1B1C1 | U9 | side | stopped_low_confidence | 0 | yes | 0 | None | 10 |  |
| A1B1C1 | U10 | side | not_converged | 3 |  | 3 | None | 17 | feedback, reply, reply |

Final check: {"sessions_listed": 10, "all_sessions_present": true, "none_open": true}. Iteration records complete: 10/10.
