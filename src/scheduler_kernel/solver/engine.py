from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from time import perf_counter
from typing import Iterable

from ortools.sat.python import cp_model

from ..domain import SchoolProblem, Slot
from ..state import Placement, ScheduleState


@dataclass(frozen=True)
class SolveResult:
    status: str
    state: ScheduleState | None
    objective: float | None
    model_build_seconds: float
    solver_seconds: float
    variable_count: int


def _eligible_room_ids(problem: SchoolProblem, lesson_id: str) -> tuple[str, ...]:
    lesson = next(lesson for lesson in problem.lessons if lesson.id == lesson_id)
    if lesson.room_kind == "general":
        return tuple(
            room.id
            for room in problem.rooms
            if room.kind == "general" and room.assigned_class_id == lesson.class_id
        )
    return tuple(room.id for room in problem.rooms if room.kind == lesson.room_kind)


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
    build_started = perf_counter()
    problem.validate()
    disabled = frozenset(disabled_constraints)
    fixed = fixed or {}
    avoid_slots = {teacher_id: set(slots) for teacher_id, slots in (avoid or {}).items()}
    for decision in problem.decisions:
        if decision.kind == "teacher_avoid_slot" and decision.status == "accepted":
            avoid_slots.setdefault(decision.entity_id, set()).add(decision.slot)

    model = cp_model.CpModel()
    slots = problem.slots
    lessons = {lesson.id: lesson for lesson in problem.lessons}
    x: dict[tuple[str, Slot, str], cp_model.IntVar] = {}
    by_lesson: dict[str, list[cp_model.IntVar]] = defaultdict(list)
    by_class_slot: dict[tuple[str, Slot], list[cp_model.IntVar]] = defaultdict(list)
    by_teacher_slot: dict[tuple[str, Slot], list[cp_model.IntVar]] = defaultdict(list)
    by_room_slot: dict[tuple[str, Slot], list[cp_model.IntVar]] = defaultdict(list)
    by_class_subject_day: dict[tuple[str, str, int], list[cp_model.IntVar]] = defaultdict(list)

    for lesson in problem.lessons:
        for slot in slots:
            for room_id in _eligible_room_ids(problem, lesson.id):
                variable = model.new_bool_var(f"x_{lesson.id}_{slot.key}_{room_id}")
                x[(lesson.id, slot, room_id)] = variable
                by_lesson[lesson.id].append(variable)
                by_class_slot[(lesson.class_id, slot)].append(variable)
                by_teacher_slot[(lesson.teacher_id, slot)].append(variable)
                by_room_slot[(room_id, slot)].append(variable)
                by_class_subject_day[(lesson.class_id, lesson.subject, slot.day)].append(variable)

    for variables in by_lesson.values():
        model.add_exactly_one(variables)
    for variables in by_class_slot.values():
        model.add_at_most_one(variables)
    for variables in by_teacher_slot.values():
        model.add_at_most_one(variables)
    for variables in by_room_slot.values():
        model.add_at_most_one(variables)

    if "H5_AVAIL" not in disabled:
        for teacher in problem.teachers:
            for slot in teacher.unavailable:
                for variable in by_teacher_slot[(teacher.id, slot)]:
                    model.add(variable == 0)

    if "H6_DAILY_SUBJECT" not in disabled:
        for variables in by_class_subject_day.values():
            model.add(sum(variables) <= problem.policy.max_same_subject_per_day)

    for lesson_id, placement in fixed.items():
        variable = x.get((lesson_id, placement.slot, placement.room_id))
        if variable is None:
            raise ValueError(f"fixed placement is not valid for current problem: {lesson_id}")
        model.add(variable == 1)

    for teacher_id, blocked_slots in avoid_slots.items():
        for slot in blocked_slots:
            for variable in by_teacher_slot[(teacher_id, slot)]:
                model.add(variable == 0)

    penalties: list[cp_model.LinearExpr] = []
    if "S1_TEACHER_SLOT" not in disabled:
        for teacher in problem.teachers:
            for preference in teacher.preferences:
                if preference.mode not in {"avoid", "prefer"}:
                    continue
                for slot in preference.slots:
                    occupied = sum(by_teacher_slot[(teacher.id, slot)])
                    penalties.append(
                        preference.weight * occupied
                        if preference.mode == "avoid"
                        else preference.weight * (1 - occupied)
                    )

    if "P1_MAIN_SPREAD" not in disabled:
        for class_id in problem.classes:
            for day in range(len(problem.days)):
                variables = [
                    variable
                    for (lesson_id, slot, _room_id), variable in x.items()
                    if slot.day == day
                    and lessons[lesson_id].class_id == class_id
                    and lessons[lesson_id].is_main_subject
                ]
                overflow = model.new_int_var(0, len(problem.lessons), f"main_over_{class_id}_{day}")
                model.add(overflow >= sum(variables) - 1)
                penalties.append(problem.policy.spread_main_subjects_weight * overflow)

    if baseline is not None:
        for lesson_id, placement in baseline.by_lesson.items():
            if lesson_id not in fixed:
                variable = x.get((lesson_id, placement.slot, placement.room_id))
                if variable is not None:
                    penalties.append(change_weight * (1 - variable))

    if penalties:
        model.minimize(sum(penalties))

    model_build_seconds = perf_counter() - build_started
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 7
    solve_started = perf_counter()
    status_code = solver.solve(model)
    solver_seconds = perf_counter() - solve_started
    status = {
        cp_model.OPTIMAL: "optimal",
        cp_model.FEASIBLE: "feasible",
        cp_model.INFEASIBLE: "infeasible",
        cp_model.MODEL_INVALID: "invalid",
        cp_model.UNKNOWN: "unknown",
    }[status_code]
    if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolveResult(status, None, None, model_build_seconds, solver_seconds, len(x))

    placements = [
        Placement(lesson_id, slot, room_id)
        for (lesson_id, slot, room_id), variable in x.items()
        if solver.value(variable)
    ]
    return SolveResult(
        status,
        ScheduleState.create(
            placements,
            parent_version=baseline.version if baseline else None,
            problem_fingerprint=problem.content_fingerprint,
        ),
        solver.objective_value,
        model_build_seconds,
        solver_seconds,
        len(x),
    )
