# Phase 0 architecture

## Goal and non-goals

Phase 0 proves a narrow kernel, not a product shell. The vertical slice is:

```text
Synthetic school JSON
        ↓
Domain model + Constraint Registry
        ↓
CP-SAT Generate ──→ authoritative ScheduleState(version)
        │                         │
        ├── infeasible ──→ Explain│
        │                         └──→ derived artifacts (version-pinned)
        └── accepted draft ──→ Repair (mostly locked) ──→ child version
```

Out of scope: production UI, accounts, notifications, reports, persistence, full substitute-teaching workflow, and school SIS integration.

## Domain boundaries

- `SchoolProblem` is immutable solver input: days, slots, classes, teachers, rooms, lessons, policy.
- `Lesson` is the Phase 0 scheduling unit. A later phase may generalize this to linked groups or blocks, but Phase 0 does not invent that abstraction before a fixture needs it.
- `TeacherProfile` separates availability from preferences. Preference state is explicit: `prefer`, `avoid`, `indifferent`, or `unknown`.
- `ConstraintRegistry` records semantics, category, implementation status, and whether humans may authorize relaxation.
- `ScheduleState` is authoritative. Views, exports, reports, and future spreadsheets are derived artifacts; each declares the source schedule version.
- A repair produces a new state whose `parent_version` points to the accepted baseline. It does not mutate the baseline in place.

## Generate

The solver uses Boolean decisions for `(lesson, slot, room)`. Physical collisions and completion are hard constraints. Teacher availability and the tacit same-subject-per-day rule are hard by default. Main-subject spreading and explicit teacher preferences contribute penalties.

Unknown and indifferent preferences deliberately contribute no penalty. Missing data is not silently treated as a dislike.

## Explain

Explanation has two layers:

1. cheap pre-flight checks provide human-readable necessary-condition evidence;
2. deletion-filter trials actually disable one authorized constraint family and solve again.

A suggested relaxation is labelled verified only when the relaxed model produces a schedule. Physical constraints are never trial-relaxed.

This is not a minimum unsatisfiable core and does not claim completeness. It is a small, testable decision-support mechanism.

## Repair

Phase 0 local repair targets one teacher/slot complaint. All non-target lessons are fixed to the accepted baseline; the target lesson is re-solved with the disliked slot forbidden. The resulting state records its parent version and reports changed lessons and preservation ratio.

This deliberately starts with the smallest useful repair neighborhood. If real cases require swaps or multi-lesson neighborhoods, those will be added from observed failures rather than pre-built speculatively.

## Dependency concept

`DependencyGraph` tracks version-pinned derived artifacts. Once a repair creates a new authoritative version, any artifact built from the old version is stale. Phase 0 only proves invalidation semantics; it does not generate reports or notifications.

