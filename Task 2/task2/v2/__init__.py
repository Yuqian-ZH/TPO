"""Task 2, protocol task2_v2: fixed versions of two components, written after the 2026-10 audit.

The frozen task2_v1 files (cvrp/, components/, cases/, schemas/, protocol.json, results/) are not modified;
Tasks 3 and 4 hash them. Everything new lives in this package and writes to results_v2/ and logs/eval_v2/.

  attribution.py   F1: an anchor relative to the current plan, no relabelling, direction flipped only on ties,
                   and "a cheaper plan exists without the decision" reported as its own conclusion
  localization.py  F5 / T7: confidence counts only what the user can settle (target, direction, threshold,
                   corrected value); the clarifying question asks about the point the samples disagree on
  timing.py        F4: counterfactual latency with equal model set-up for both methods"""
