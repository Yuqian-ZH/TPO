# End-to-end run, task4_v3

Cases: Task 2 v3 test cases (10), configurations A0B0C1, A1B1C1, one run each; 2026-10-27T14:21:34+08:00 to 2026-10-27T14:34:20+08:00. LLM requests in the service log: 224.

| Config | Resolved | At iteration 1 | By stratum (control / ambiguity / side) | Clarified | LLM requests | Tokens | POST /feedback median s | Task 3 v3 same config (50 trials) |
|---|---|---|---|---|---|---|---|---|
| A0B0C1 | 10/10 | 8 | 2/2 / 3/3 / 5/5 | 6 | 93 | 142,208 + 9,970 | 16.77 | 45/50 converged, 41 at 1 |
| A1B1C1 | 9/10 | 8 | 2/2 / 3/3 / 4/5 | 5 | 131 | 526,027 + 14,985 | 20.4 | 48/50 converged, 43 at 1 |

| Config | Case | Stratum | Status | Iterations | Clarified | Plans shown | Excess km | Requests | Triggers |
|---|---|---|---|---|---|---|---|---|---|
| A0B0C1 | U1 | control | resolved | 1 |  | 1 | 0.0 | 6 | feedback |
| A0B0C1 | U2 | control | resolved | 1 |  | 1 | 0.0 | 6 | feedback |
| A0B0C1 | U3 | ambiguity | resolved | 1 | yes | 1 | 22.0 | 11 | clarification |
| A0B0C1 | U4 | ambiguity | resolved | 1 | yes | 1 | 0.0 | 11 | clarification |
| A0B0C1 | U5 | ambiguity | resolved | 1 | yes | 1 | 0.0 | 11 | clarification |
| A0B0C1 | U6 | side | resolved | 1 |  | 1 | 0.0 | 6 | feedback |
| A0B0C1 | U7 | side | resolved | 1 | yes | 1 | 0.0 | 11 | clarification |
| A0B0C1 | U8 | side | resolved | 2 | yes | 2 | 0.0 | 12 | clarification, reply |
| A0B0C1 | U9 | side | resolved | 3 | yes | 2 | 0.0 | 13 | clarification, reply, auto_continue |
| A0B0C1 | U10 | side | resolved | 1 |  | 1 | 0.0 | 6 | feedback |
| A1B1C1 | U1 | control | resolved | 1 |  | 1 | 0.0 | 9 | feedback |
| A1B1C1 | U2 | control | resolved | 1 |  | 1 | 0.0 | 9 | feedback |
| A1B1C1 | U3 | ambiguity | resolved | 1 | yes | 1 | 22.0 | 14 | clarification |
| A1B1C1 | U4 | ambiguity | resolved | 1 | yes | 1 | 0.0 | 14 | clarification |
| A1B1C1 | U5 | ambiguity | resolved | 1 | yes | 1 | 0.0 | 14 | clarification |
| A1B1C1 | U6 | side | resolved | 1 |  | 1 | 0.0 | 9 | feedback |
| A1B1C1 | U7 | side | resolved | 3 |  | 3 | 21.0 | 17 | feedback, reply, reply |
| A1B1C1 | U8 | side | resolved | 1 | yes | 1 | 0.0 | 14 | clarification |
| A1B1C1 | U9 | side | resolved | 1 | yes | 1 | 0.0 | 14 | clarification |
| A1B1C1 | U10 | side | not_converged | 3 |  | 2 | None | 17 | feedback, reply, reply |

Final check: {"sessions_listed": 20, "all_sessions_present": true, "none_open": true}. Iteration records complete: 20/20.
