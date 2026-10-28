"""Task 2, protocol task2_v2.1: the defects an independent review found in task2_v2 after its runs, fixed.

v2/ stays as frozen in v2/protocol_v2.json (it produced the reported v2 results, and Task 3 / Task 4 hash it); this
package imports it and replaces only the functions that change. Nothing here calls the LLM: recheck.py re-computes
v2.1 on every state and sample set the v2 runs recorded and compares it with what v2 produced.

  attribution.py   the current plan is optimal under the anchor by the exact objective (v2: 0.1% tolerance);
                   a plan infeasible on the model's data is reported as such instead of attributed
  localization.py  only the limit that applies to the target and direction counts towards agreement; the
                   modification type is one the target admits"""
