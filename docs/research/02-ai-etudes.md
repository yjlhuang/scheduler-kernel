# 02 — AI Etudes class-schedule

Evidence: deployed page and prior conversation analysis of a user-supplied single-file implementation; the source file itself was not imported into this workspace.

Observed shape: repeated randomized scheduling, difficulty-aware priority, conflict-history feedback, shared resource awareness, and locking of accepted classes. The best solution was primarily measured by filled count, so equally complete schedules were not strongly distinguished by quality.

Useful concept: difficult units should be surfaced and accepted regions should survive another run.

Not adopted: repeated heuristic search as the authoritative solver. CP-SAT expresses feasibility and weighted preferences more directly for this Phase 0 experiment.

