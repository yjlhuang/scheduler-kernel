# 03 — Course_Scheduling_System

Evidence: public repository, including `backend/app/solver/`.

Observed shape: OR-Tools CP-SAT, explicit hard/soft constraint families, pre-flight checks, independent schedule validation/reporting, fixed/locked entries, solver hints, partial scheduling, and conflict explanation by disabling candidate constraints and re-solving. The repository explicitly documents why its production approach avoided relying on an assumption/unsat-core path.

Useful concepts adopted in reduced form: CP-SAT, cheap pre-flight, verified relaxation trials, immutable locked regions, and validation from the materialized schedule.

Not adopted: its database, API, UI, authentication, worker queue, notification, substitute workflow, or complete H1–H10/S1–S8 model. Reusing the whole product would violate the clean-kernel boundary.

