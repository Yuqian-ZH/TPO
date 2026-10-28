"""Task 4, protocol task4_v31: the feedback service with task3_v31's prompt (DESIGN_V31.md at the project root).

One change against task4_v3: the modifications a session was created with are listed in the prompt, before the ones
accepted with earlier complaints, in the block Task 3's tpo_v31.loop.TrialV31 shows. task4_v3 listed only the
accepted ones, so a session's own constraints were in the solver's model but not in the prompt.
feedback_service/ to feedback_service_v3/ are imported unchanged."""
