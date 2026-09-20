from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace

from ..domain import SchoolProblem, SchedulingDecision, Slot
from ..solver import solve
from ..state import ScheduleState


@dataclass(frozen=True)
class QualityVector:
    change_cost: int
    teacher_preference_cost: int
    teacher_days: int
    teacher_gaps: int


def evaluate_quality(
    problem: SchoolProblem,
    state: ScheduleState,
    *,
    reference: ScheduleState | None = None,
) -> QualityVector:
    placements = state.by_lesson
    lessons = {lesson.id: lesson for lesson in problem.lessons}
    teacher_slots: dict[str, list[Slot]] = defaultdict(list)
    for lesson_id, placement in placements.items():
        teacher_slots[lessons[lesson_id].teacher_id].append(placement.slot)

    preference_cost = 0
    for teacher in problem.teachers:
        occupied = set(teacher_slots[teacher.id])
        for preference in teacher.preferences:
            if preference.mode == "avoid":
                preference_cost += preference.weight * len(occupied & set(preference.slots))
            elif preference.mode == "prefer" and occupied:
                preference_cost += preference.weight * len(set(preference.slots) - occupied)

    teacher_days = sum(len({slot.day for slot in slots}) for slots in teacher_slots.values())
    teacher_gaps = 0
    for slots in teacher_slots.values():
        by_day: dict[int, list[int]] = defaultdict(list)
        for slot in slots:
            by_day[slot.day].append(slot.period)
        for periods in by_day.values():
            teacher_gaps += max(periods) - min(periods) + 1 - len(set(periods))

    change_cost = 0
    if reference is not None:
        change_cost = sum(
            reference.by_lesson.get(lesson_id) != placement
            for lesson_id, placement in placements.items()
        )
    return QualityVector(change_cost, preference_cost, teacher_days, teacher_gaps)


@dataclass(frozen=True)
class RepairResult:
    outcome: str
    solver_status: str
    state: ScheduleState | None
    authoritative_problem: SchoolProblem
    changed_lessons: tuple[str, ...]
    locked_lessons: int
    total_lessons: int
    before_quality: QualityVector
    after_quality: QualityVector | None

    @property
    def status(self) -> str:
        return self.outcome

    @property
    def preservation_ratio(self) -> float | None:
        if self.state is None:
            return None
        if not self.total_lessons:
            return 1.0
        return 1 - (len(self.changed_lessons) / self.total_lessons)


def repair_teacher_slot(
    problem: SchoolProblem,
    baseline: ScheduleState,
    teacher_id: str,
    avoid_slot: Slot,
) -> RepairResult:
    before = evaluate_quality(problem, baseline, reference=baseline)
    lesson_ids = {lesson.id for lesson in problem.lessons if lesson.teacher_id == teacher_id}
    targets = {
        lesson_id
        for lesson_id, placement in baseline.by_lesson.items()
        if lesson_id in lesson_ids and placement.slot == avoid_slot
    }
    if not targets:
        return RepairResult(
            "no_change_needed",
            "not_run",
            baseline,
            problem,
            (),
            len(problem.lessons),
            len(problem.lessons),
            before,
            before,
        )

    decision = SchedulingDecision.teacher_avoid_slot(
        teacher_id, avoid_slot, "accepted repair request"
    )
    updated_problem = replace(problem, decisions=problem.decisions + (decision,))
    fixed = {
        lesson_id: placement
        for lesson_id, placement in baseline.by_lesson.items()
        if lesson_id not in targets
    }
    result = solve(updated_problem, fixed=fixed, baseline=baseline)
    if result.state is None:
        outcome = "unknown" if result.status == "unknown" else "infeasible"
        return RepairResult(
            outcome,
            result.status,
            None,
            updated_problem,
            (),
            len(fixed),
            len(problem.lessons),
            before,
            None,
        )
    changed = tuple(
        lesson_id
        for lesson_id, placement in result.state.by_lesson.items()
        if baseline.by_lesson[lesson_id] != placement
    )
    after = evaluate_quality(updated_problem, result.state, reference=baseline)
    return RepairResult(
        "success",
        result.status,
        result.state,
        updated_problem,
        changed,
        len(fixed),
        len(problem.lessons),
        before,
        after,
    )
