# Phase 0 architecture

## Goal and non-goals

Phase 0 proved only that three execution paths run end to end; it did not establish realistic-density capability. Phase 0.5 adds the first density, scalability, explanation-correctness, repair-quality, and state-boundary evidence. The vertical slice is:

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
- `Lesson` carries plural `teacher_ids` and `class_ids` so identity is not permanently encoded as singular. Phase 0.5 deliberately validates `len == 1`: this leaves room for 2-teacher co-teaching and 2-class combined teaching without pretending the solver implements them yet.
- Split-group teaching (one class split into two simultaneous groups using two teachers and two rooms) is not solved by plural keys. It requires future group-aware class occupancy in H1_CLASS. Phase 0.5 does not invent `CourseOffering / SchedulingUnit / LessonRequirement` before real curriculum-hour data exists.
- General lessons are bound to the class's assigned homeroom. Specialist rooms remain a scarce shared pool by `room_kind`.
- `TeacherProfile` separates availability from preferences. Preference state is explicit: `prefer`, `avoid`, `indifferent`, or `unknown`.
- `ConstraintRegistry` records semantics, category, implementation status, and whether humans may authorize relaxation.
- `ScheduleState` carries the `SchoolProblem` content fingerprint. A state loaded against changed teachers, lessons, policy, rooms, or accepted decisions is detectably stale.
- A repair produces a new state whose `parent_version` points to the accepted baseline. It does not mutate the baseline in place.

## Generate

The solver creates Boolean decisions only for eligible `(lesson, slot, room)` combinations and maintains indexed buckets rather than repeatedly scanning the whole variable map. Physical collisions and completion are hard constraints. Teacher availability and the tacit same-subject-per-day rule are hard by default. Main-subject spreading and explicit teacher preferences contribute penalties.

Unknown and indifferent preferences deliberately contribute no penalty. Missing data is not silently treated as a dislike.

## Explain

Explanation has two layers:

1. cheap pre-flight checks provide human-readable necessary-condition evidence;
2. deletion-filter trials actually disable one authorized feasibility constraint family and solve again with a budget at least equal to the baseline.

A suggested relaxation is labelled verified only when the relaxed model produces a schedule. Physical constraints are never trial-relaxed.

`UNKNOWN` is never presented as `INFEASIBLE`: it means the time limit did not prove either result and produces no relaxation claim. Preflight covers named teacher, class, specialist-room-kind, and daily-subject capacity. This is not a minimum unsatisfiable core and does not claim completeness; trying one code at a time can miss multi-factor causes, and the payload says so.

## Repair

Phase 0.5 local repair targets one teacher/slot complaint. All non-target lessons are fixed to the accepted baseline; the accepted request is written into the authoritative problem's decision layer before solving. The resulting state records its parent version and the updated problem fingerprint.

Repair has four explicit outcomes: `success`, `no_change_needed`, `infeasible`, and `unknown`. Failed repair has no preservation ratio. Success and no-change return named before/after quality vectors with change cost, teacher preference cost, teacher days, and teacher gaps; preservation remains a descriptive changed-set ratio, not quality evidence.

This deliberately starts with the smallest useful repair neighborhood. If real cases require swaps or multi-lesson neighborhoods, those will be added from observed failures rather than pre-built speculatively.

## Dependency concept

`DependencyGraph` tracks version-pinned derived artifacts. Once a repair creates a new authoritative version, any artifact built from the old version is stale. Phase 0 only proves invalidation semantics; it does not generate reports or notifications.

## Partial-scheduling tripwire

Partial scheduling remains deferred. If the realistic-density fixture becomes infeasible and the current explanation cannot identify the blocked lessons, that is the explicit condition to move partial placement ahead of further constraint work. Until implemented, no document may claim that H4_COMPLETE exposes unresolved lessons.
