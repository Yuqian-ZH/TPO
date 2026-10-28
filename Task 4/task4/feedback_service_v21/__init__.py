"""Task 4, protocol task4_v2.1: the feedback service after the review of task4_v2 (README section 10, known issue).

The state-change rule compares an iteration's (routes, data in force) with every state the user has seen in the
complaint, and a plan whose data changed lists the changed values instead of calling them the user's correction.
Components: Task 3's tpo_v21 adapter, i.e. Task 2's task2_v2.1 attribution and localization.

feedback_service/ (task4_v1) and feedback_service_v2/ (task4_v2) are imported unchanged and stay frozen in
service_freeze.json and service_freeze_v2.json; this package only subclasses them."""
