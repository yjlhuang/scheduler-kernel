from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PreferenceMode = Literal["prefer", "avoid", "indifferent", "unknown"]


@dataclass(frozen=True, order=True)
class Slot:
    day: int
    period: int

    @property
    def key(self) -> str:
        return f"d{self.day}p{self.period}"


@dataclass(frozen=True)
class Room:
    id: str
    kind: str = "general"


@dataclass(frozen=True)
class TeacherPreference:
    mode: PreferenceMode
    slots: frozenset[Slot] = frozenset()
    weight: int = 1
    note: str = ""


@dataclass(frozen=True)
class TeacherProfile:
    id: str
    unavailable: frozenset[Slot] = frozenset()
    preferences: tuple[TeacherPreference, ...] = ()


@dataclass(frozen=True)
class Lesson:
    id: str
    class_id: str
    subject: str
    teacher_id: str
    room_kind: str = "general"
    is_main_subject: bool = False


@dataclass(frozen=True)
class PolicyConfig:
    max_same_subject_per_day: int = 1
    spread_main_subjects_weight: int = 3


@dataclass(frozen=True)
class SchoolProblem:
    days: tuple[str, ...]
    periods_per_day: int
    classes: tuple[str, ...]
    teachers: tuple[TeacherProfile, ...]
    rooms: tuple[Room, ...]
    lessons: tuple[Lesson, ...]
    policy: PolicyConfig = field(default_factory=PolicyConfig)

    @property
    def slots(self) -> tuple[Slot, ...]:
        return tuple(
            Slot(day, period)
            for day in range(len(self.days))
            for period in range(1, self.periods_per_day + 1)
        )

    @property
    def teachers_by_id(self) -> dict[str, TeacherProfile]:
        return {teacher.id: teacher for teacher in self.teachers}

    def validate(self) -> None:
        teacher_ids = set(self.teachers_by_id)
        class_ids = set(self.classes)
        room_kinds = {room.kind for room in self.rooms}
        lesson_ids: set[str] = set()
        for lesson in self.lessons:
            if lesson.id in lesson_ids:
                raise ValueError(f"duplicate lesson id: {lesson.id}")
            lesson_ids.add(lesson.id)
            if lesson.teacher_id not in teacher_ids:
                raise ValueError(f"unknown teacher {lesson.teacher_id} in {lesson.id}")
            if lesson.class_id not in class_ids:
                raise ValueError(f"unknown class {lesson.class_id} in {lesson.id}")
            if lesson.room_kind not in room_kinds:
                raise ValueError(f"unknown room kind {lesson.room_kind} in {lesson.id}")

