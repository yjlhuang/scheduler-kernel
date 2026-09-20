from __future__ import annotations

import json
from pathlib import Path

from scheduler_kernel.benchmarking import make_dense_problem


def main() -> None:
    problem = make_dense_problem(6)
    payload = {
        "days": problem.days,
        "periods_per_day": problem.periods_per_day,
        "classes": problem.classes,
        "rooms": [
            {
                "id": room.id,
                "kind": room.kind,
                **(
                    {"assigned_class_id": room.assigned_class_id}
                    if room.assigned_class_id
                    else {}
                ),
            }
            for room in problem.rooms
        ],
        "teachers": [
            {
                "id": teacher.id,
                "unavailable": [[slot.day, slot.period] for slot in sorted(teacher.unavailable)],
                "preferences": [],
            }
            for teacher in problem.teachers
        ],
        "policy": {
            "max_same_subject_per_day": problem.policy.max_same_subject_per_day,
            "spread_main_subjects_weight": problem.policy.spread_main_subjects_weight,
        },
        "lessons": [
            {
                "id": lesson.id,
                "class_ids": lesson.class_ids,
                "subject": lesson.subject,
                "teacher_ids": lesson.teacher_ids,
                "room_kind": lesson.room_kind,
                "is_main_subject": lesson.is_main_subject,
            }
            for lesson in problem.lessons
        ],
    }
    Path("data/fixtures/dense_school_6.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
