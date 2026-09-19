from __future__ import annotations

from collections import Counter

from ..domain import SchoolProblem
from ..state import ScheduleState


def validate_schedule(problem: SchoolProblem, state: ScheduleState) -> tuple[str, ...]:
    """Validate the materialized schedule without trusting the CP-SAT model."""
    violations: list[str] = []
    lessons = {lesson.id: lesson for lesson in problem.lessons}
    rooms = {room.id: room for room in problem.rooms}
    counts = Counter(p.lesson_id for p in state.placements)
    for lesson_id in lessons:
        if counts[lesson_id] != 1:
            violations.append(f"lesson {lesson_id} appears {counts[lesson_id]} times")

    class_cells: set[tuple[str, int, int]] = set()
    teacher_cells: set[tuple[str, int, int]] = set()
    room_cells: set[tuple[str, int, int]] = set()
    subject_days: Counter[tuple[str, str, int]] = Counter()
    teachers = problem.teachers_by_id
    for placement in state.placements:
        lesson = lessons.get(placement.lesson_id)
        room = rooms.get(placement.room_id)
        if lesson is None or room is None:
            violations.append(f"unknown materialized reference in {placement.lesson_id}")
            continue
        if room.kind != lesson.room_kind:
            violations.append(f"room kind mismatch for {lesson.id}")
        class_key = (lesson.class_id, placement.slot.day, placement.slot.period)
        teacher_key = (lesson.teacher_id, placement.slot.day, placement.slot.period)
        room_key = (placement.room_id, placement.slot.day, placement.slot.period)
        if class_key in class_cells:
            violations.append(f"class collision at {class_key}")
        if teacher_key in teacher_cells:
            violations.append(f"teacher collision at {teacher_key}")
        if room_key in room_cells:
            violations.append(f"room collision at {room_key}")
        class_cells.add(class_key)
        teacher_cells.add(teacher_key)
        room_cells.add(room_key)
        if placement.slot in teachers[lesson.teacher_id].unavailable:
            violations.append(f"teacher unavailable for {lesson.id}")
        subject_days[(lesson.class_id, lesson.subject, placement.slot.day)] += 1

    for key, count in subject_days.items():
        if count > problem.policy.max_same_subject_per_day:
            violations.append(f"daily subject limit exceeded at {key}")
    return tuple(violations)

