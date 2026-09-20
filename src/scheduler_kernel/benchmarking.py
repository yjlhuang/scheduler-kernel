from __future__ import annotations

from math import ceil

from .domain import Lesson, PolicyConfig, Room, SchoolProblem, Slot, TeacherProfile

SUBJECTS = ("Chinese", "English", "Math", "Science", "Social", "PE", "Arts")


def make_dense_problem(class_count: int) -> SchoolProblem:
    """Deterministic 35-slot school with a known feasible high-density pattern."""
    classes = tuple(f"C{i + 1:02d}" for i in range(class_count))
    teacher_count = ceil(class_count * 35 / 21)
    teacher_ids = tuple(f"T{i + 1:02d}" for i in range(teacher_count))
    rooms = [
        Room(f"{class_id}-HOME", "general", assigned_class_id=class_id)
        for class_id in classes
    ]
    rooms.extend(Room(f"LAB-{i + 1}", "lab") for i in range(ceil(class_count / 7)))

    lessons = []
    for class_index, class_id in enumerate(classes):
        for slot_index in range(35):
            subject_index = (slot_index + class_index) % len(SUBJECTS)
            subject = SUBJECTS[subject_index]
            lessons.append(
                Lesson(
                    id=f"{class_id}-{subject}-{slot_index // 7 + 1}",
                    class_ids=(class_id,),
                    subject=subject,
                    teacher_ids=(
                        teacher_ids[(slot_index * class_count + class_index) % teacher_count],
                    ),
                    room_kind="lab" if subject == "Science" else "general",
                    is_main_subject=subject in {"Chinese", "English", "Math"},
                )
            )
    occupied_by_teacher = {
        teacher_id: {
            Slot(slot_index // 7, slot_index % 7 + 1)
            for class_index in range(class_count)
            for slot_index in range(35)
            if teacher_ids[(slot_index * class_count + class_index) % teacher_count]
            == teacher_id
        }
        for teacher_id in teacher_ids
    }
    all_slots = tuple(Slot(index // 7, index % 7 + 1) for index in range(35))
    teachers = tuple(
        TeacherProfile(
            teacher_id,
            frozenset(
                tuple(
                    slot
                    for slot in all_slots
                    if slot not in occupied_by_teacher[teacher_id]
                )[:2]
            ),
        )
        for teacher_id in teacher_ids
    )
    problem = SchoolProblem(
        days=("Mon", "Tue", "Wed", "Thu", "Fri"),
        periods_per_day=7,
        classes=classes,
        teachers=teachers,
        rooms=tuple(rooms),
        lessons=tuple(lessons),
        policy=PolicyConfig(max_same_subject_per_day=1, spread_main_subjects_weight=3),
    )
    problem.validate()
    return problem
