"""Task 4, protocol task4_v2: the feedback service after the 2026-10 audit.

F2: v1 decided from the routes alone whether an iteration produced something to show. A correct data correction
that leaves the routes optimal (customer 4 orders 13 instead of 12) therefore never reached the user; the loop
used up its iterations, closed the complaint as not_converged and rolled the correction back.
Components: Task 3's tpo_v2 adapter, i.e. Task 2's task2_v2 attribution (F1) and localization (F5, the T7 stop).

feedback_service/ (task4_v1) is imported unchanged and stays frozen in service_freeze.json; this package only
subclasses it."""
