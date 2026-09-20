# 01 — kent-css

Evidence: public repository, especially `ai.html`.

Observed shape: a small-school, browser-based scheduling tool with structured teacher/class constraints, randomized greedy placement, unplaced-lesson exposure, manual placement, and locking of human edits.

Useful concept for a later phase: automatic generation should expose unresolved work. Phase 0.5 still enforces H4_COMPLETE, so it returns a whole-problem failure rather than partial placements; a dense-fixture failure that cannot name blocked lessons is the tripwire for prioritizing partial scheduling. Accepted repair decisions are now preserved in the authoritative problem layer.

Not adopted: the single-file UI architecture and greedy first-fit algorithm. Phase 0 needs a solver-backed feasibility claim and independent validation.
