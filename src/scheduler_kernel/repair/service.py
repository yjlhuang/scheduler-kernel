from __future__ import annotations

from dataclasses import dataclass

from ..domain import SchoolProblem, Slot
from ..solver import solve
from ..state import ScheduleState


@dataclass(frozen=True)
class RepairResult:
    status: str
    state: ScheduleState | None
    changed_lessons: tuple[str, ...]
    locked_lessons: int
    total_lessons: int

    @property
    def preservation_ratio(self) -> float:
        if not self.total_lessons:
            return 1.0
        return 1 - (len(self.changed_lessons) / self.total_lessons)


def repair_teacher_slot(
    problem: SchoolProblem,
    baseline: ScheduleState,
    teacher_id: str,
    avoid_slot: Slot,
) -> RepairResult:
    lesson_ids = {
        lesson.id for lesson in problem.lessons if lesson.teacher_id == teacher_id
    }
    targets = {
        lesson_id
        for lesson_id, placement in baseline.by_lesson.items()
        if lesson_id in lesson_ids and placement.slot == avoid_slot
    }
    if not targets:
        return RepairResult("no_change_needed", baseline, (), len(problem.lessons), len(problem.lessons))

    fixed = {
        lesson_id: placement
        for lesson_id, placement in baseline.by_lesson.items()
        if lesson_id not in targets
    }
    result = solve(
        problem,
        fixed=fixed,
        baseline=baseline,
        avoid={teacher_id: frozenset({avoid_slot})},
    )
    if result.state is None:
        return RepairResult(result.status, None, (), len(fixed), len(problem.lessons))
    changed = tuple(
        lesson_id
        for lesson_id, placement in result.state.by_lesson.items()
        if baseline.by_lesson[lesson_id] != placement
    )
    return RepairResult(result.status, result.state, changed, len(fixed), len(problem.lessons))

