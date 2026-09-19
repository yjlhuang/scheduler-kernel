from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ortools.sat.python import cp_model

from ..domain import SchoolProblem, Slot
from ..state import Placement, ScheduleState


@dataclass(frozen=True)
class SolveResult:
    status: str
    state: ScheduleState | None
    objective: float | None


def solve(
    problem: SchoolProblem,
    *,
    disabled_constraints: Iterable[str] = (),
    fixed: dict[str, Placement] | None = None,
    baseline: ScheduleState | None = None,
    avoid: dict[str, frozenset[Slot]] | None = None,
    change_weight: int = 100,
    time_limit_seconds: float = 10.0,
) -> SolveResult:
    problem.validate()
    disabled = frozenset(disabled_constraints)
    fixed = fixed or {}
    avoid = avoid or {}
    model = cp_model.CpModel()
    slots = problem.slots
    rooms_for_kind = {
        kind: tuple(room for room in problem.rooms if room.kind == kind)
        for kind in {room.kind for room in problem.rooms}
    }

    x: dict[tuple[str, Slot, str], cp_model.IntVar] = {}
    for lesson in problem.lessons:
        for slot in slots:
            for room in rooms_for_kind[lesson.room_kind]:
                x[(lesson.id, slot, room.id)] = model.new_bool_var(
                    f"x_{lesson.id}_{slot.key}_{room.id}"
                )

    by_lesson: dict[str, list[cp_model.IntVar]] = {lesson.id: [] for lesson in problem.lessons}
    for (lesson_id, _slot_value, _room_id), variable in x.items():
        by_lesson[lesson_id].append(variable)
    for variables in by_lesson.values():
        model.add_exactly_one(variables)

    lessons = {lesson.id: lesson for lesson in problem.lessons}
    for slot in slots:
        for class_id in problem.classes:
            model.add_at_most_one(
                variable
                for (lesson_id, candidate, _room_id), variable in x.items()
                if candidate == slot and lessons[lesson_id].class_id == class_id
            )
        for teacher in problem.teachers:
            model.add_at_most_one(
                variable
                for (lesson_id, candidate, _room_id), variable in x.items()
                if candidate == slot and lessons[lesson_id].teacher_id == teacher.id
            )
        for room in problem.rooms:
            model.add_at_most_one(
                variable
                for (_lesson_id, candidate, room_id), variable in x.items()
                if candidate == slot and room_id == room.id
            )

    if "H5_AVAIL" not in disabled:
        for teacher in problem.teachers:
            for slot in teacher.unavailable:
                for (lesson_id, candidate, _room_id), variable in x.items():
                    if candidate == slot and lessons[lesson_id].teacher_id == teacher.id:
                        model.add(variable == 0)

    if "H6_DAILY_SUBJECT" not in disabled:
        for class_id in problem.classes:
            subjects = {l.subject for l in problem.lessons if l.class_id == class_id}
            for subject in subjects:
                for day in range(len(problem.days)):
                    model.add(
                        sum(
                            variable
                            for (lesson_id, slot, _room_id), variable in x.items()
                            if slot.day == day
                            and lessons[lesson_id].class_id == class_id
                            and lessons[lesson_id].subject == subject
                        )
                        <= problem.policy.max_same_subject_per_day
                    )

    for lesson_id, placement in fixed.items():
        model.add(x[(lesson_id, placement.slot, placement.room_id)] == 1)

    for teacher_id, blocked_slots in avoid.items():
        for slot in blocked_slots:
            for (lesson_id, candidate, _room_id), variable in x.items():
                if candidate == slot and lessons[lesson_id].teacher_id == teacher_id:
                    model.add(variable == 0)

    penalties: list[cp_model.LinearExpr] = []
    if "S1_TEACHER_SLOT" not in disabled:
        for teacher in problem.teachers:
            for preference in teacher.preferences:
                if preference.mode not in {"avoid", "prefer"}:
                    continue
                for slot in preference.slots:
                    occupied = sum(
                        variable
                        for (lesson_id, candidate, _room_id), variable in x.items()
                        if candidate == slot and lessons[lesson_id].teacher_id == teacher.id
                    )
                    if preference.mode == "avoid":
                        penalties.append(preference.weight * occupied)
                    else:
                        penalties.append(preference.weight * (1 - occupied))

    if "P1_MAIN_SPREAD" not in disabled:
        for class_id in problem.classes:
            for day in range(len(problem.days)):
                main_count = sum(
                    variable
                    for (lesson_id, slot, _room_id), variable in x.items()
                    if slot.day == day
                    and lessons[lesson_id].class_id == class_id
                    and lessons[lesson_id].is_main_subject
                )
                overflow = model.new_int_var(0, len(problem.lessons), f"main_over_{class_id}_{day}")
                model.add(overflow >= main_count - 1)
                penalties.append(problem.policy.spread_main_subjects_weight * overflow)

    if baseline is not None:
        for lesson_id, placement in baseline.by_lesson.items():
            if lesson_id not in fixed:
                penalties.append(change_weight * (1 - x[(lesson_id, placement.slot, placement.room_id)]))

    if penalties:
        model.minimize(sum(penalties))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 7
    status_code = solver.solve(model)
    status = {
        cp_model.OPTIMAL: "optimal",
        cp_model.FEASIBLE: "feasible",
        cp_model.INFEASIBLE: "infeasible",
        cp_model.MODEL_INVALID: "invalid",
        cp_model.UNKNOWN: "unknown",
    }[status_code]
    if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolveResult(status=status, state=None, objective=None)

    placements: list[Placement] = []
    for key, variable in x.items():
        if solver.value(variable):
            lesson_id, slot, room_id = key
            placements.append(Placement(lesson_id=lesson_id, slot=slot, room_id=room_id))
    return SolveResult(
        status=status,
        state=ScheduleState.create(
            placements,
            parent_version=baseline.version if baseline else None,
        ),
        objective=solver.objective_value,
    )

