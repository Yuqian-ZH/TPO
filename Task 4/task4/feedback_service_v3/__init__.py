"""Task 4, protocol task4_v3: the feedback service with task3_v3's loop (DESIGN_V3.md at the project root).

One change against task4_v2.1: every iteration starts from the plan the user complained about and the session's
model, with the earlier attempts in the history block, as Task 3's tpo_v3.loop.TrialV3. The user's conditions
("vehicle 1 keeps its route", "at most two customers change trucks") refer to that plan, and so do the prompt, the
attribution, the probe and the commit's anchor. feedback_service/, feedback_service_v2/ and feedback_service_v21/
are imported unchanged."""
