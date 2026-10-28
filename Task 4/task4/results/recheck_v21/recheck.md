# task4_v2.1 re-check of the task4_v2 runs (no LLM)

Frozen: `service_freeze_v21.json` (2026-10-27T12:54:57+08:00).

| Records | Run | Checked | v2.1 differs from v2 |
|---|---|---:|---:|
| state_change | e2e_dev_v2 | 5 | 0 |
| state_change | e2e_test_v2 | 20 | 0 |
| state_change | audit_v2 | 2 | 0 |
| attribution | e2e_test_v2 | 166 | 0 |
| attribution | audit_v2 | 9 | 0 |
| localization | e2e_dev_v2 | 7 | 0 |
| localization | e2e_test_v2 | 26 | 0 |
| localization | audit_v2 | 2 | 0 |

Plans v2.1 would show: 27, of which with a data notice: 7.
- `f_d9591bb5/t1` (e2e_dev_v2): The data the plan uses also changed: customer 2's order size 24 -> 30. The plan is the best one on this data. Please check that these values are correct before you confirm.
- `f_564e6eaa/t1` (e2e_test_v2): The data the plan uses also changed: customer 4's order size 12 -> 20. The plan is the best one on this data. Please check that these values are correct before you confirm.
- `f_37dd18be/t1` (e2e_test_v2): The data the plan uses also changed: customer 4's order size 12 -> 20. The plan is the best one on this data. Please check that these values are correct before you confirm.
- `f_5ed92376/t1` (e2e_test_v2): The data the plan uses also changed: customer 7's order size 11 -> 18. The plan is the best one on this data. Please check that these values are correct before you confirm.
- `f_d2b18306/t1` (e2e_test_v2): The data the plan uses also changed: customer 7's order size 11 -> 18. The plan is the best one on this data. Please check that these values are correct before you confirm.
- `f_0a339891/t1` (audit_v2): The routes stay as they are, but the data the plan uses changed: customer 4's order size 12 -> 13. The plan is the best one on this data. Please check that these values are correct before you confirm.
- `f_e1c6edd5/t1` (audit_v2): The routes stay as they are, but the data the plan uses changed: customer 4's order size 12 -> 13. The plan is the best one on this data. Please check that these values are correct before you confirm.
