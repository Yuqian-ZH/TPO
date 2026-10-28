"""Task 3, protocol task3_v2: the formal run repeated with Task 2's task2_v2 attribution in condition A.

Why: the 2026-10 audit (F1) found that Task 2's frozen attribution relabelled and re-oriented the alternative
plan, which changes its objective once a label- or direction-dependent soft constraint is in force. In
task3_v1 that happened in 2 of the 11 trials where A ran at iteration 2 or 3 (18 wrong numbers in the prompt),
and those 11 trials are the only ones where A could make a difference. task3_v1 therefore did not measure A.

What changes: only the attribution component (tpo_v2/components.py). The loop, prompts, seeds, probe, commit,
simulated user and statistics are the frozen task3_v1 files, imported unchanged; this package sits outside
tpo/ so task3_v1's protocol hashes, and Task 4's check of them, still hold."""
