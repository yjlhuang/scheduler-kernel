from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
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
    assigned_class_id: str | None = None


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
    class_ids: tuple[str, ...]
    subject: str
    teacher_ids: tuple[str, ...]
    room_kind: str = "general"
    is_main_subject: bool = False

    @property
    def class_id(self) -> str:
        return self.class_ids[0]

    @property
    def teacher_id(self) -> str:
        return self.teacher_ids[0]


@dataclass(frozen=True)
class SchedulingDecision:
    kind: Literal["teacher_avoid_slot"]
    entity_id: str
    slot: Slot
    provenance: str
    status: Literal["accepted"] = "accepted"

    @classmethod
    def teacher_avoid_slot(
        cls, teacher_id: str, slot: Slot, provenance: str
    ) -> "SchedulingDecision":
        return cls("teacher_avoid_slot", teacher_id, slot, provenance)


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
    decisions: tuple[SchedulingDecision, ...] = ()

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

    @property
    def content_fingerprint(self) -> str:
        payload = {
            "days": self.days,
            "periods_per_day": self.periods_per_day,
            "classes": self.classes,
            "teachers": [
                {
                    "id": t.id,
                    "unavailable": sorted((s.day, s.period) for s in t.unavailable),
                    "preferences": [
                        {
                            "mode": p.mode,
                            "slots": sorted((s.day, s.period) for s in p.slots),
                            "weight": p.weight,
                            "note": p.note,
                        }
                        for p in t.preferences
                    ],
                }
                for t in self.teachers
            ],
            "rooms": [
                (r.id, r.kind, r.assigned_class_id) for r in self.rooms
            ],
            "lessons": [
                (
                    l.id,
                    l.class_ids,
                    l.subject,
                    l.teacher_ids,
                    l.room_kind,
                    l.is_main_subject,
                )
                for l in self.lessons
            ],
            "policy": {
                "max_same_subject_per_day": self.policy.max_same_subject_per_day,
                "spread_main_subjects_weight": self.policy.spread_main_subjects_weight,
            },
            "decisions": [
                (d.kind, d.entity_id, d.slot.day, d.slot.period, d.provenance, d.status)
                for d in self.decisions
            ],
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return sha256(encoded).hexdigest()

    def validate(self) -> None:
        teacher_ids = set(self.teachers_by_id)
        class_ids = set(self.classes)
        room_kinds = {room.kind for room in self.rooms}
        lesson_ids: set[str] = set()
        for lesson in self.lessons:
            if lesson.id in lesson_ids:
                raise ValueError(f"duplicate lesson id: {lesson.id}")
            lesson_ids.add(lesson.id)
            if len(lesson.teacher_ids) != 1:
                raise ValueError(
                    f"Phase 0.5 supports exactly one teacher per lesson: {lesson.id}"
                )
            if len(lesson.class_ids) != 1:
                raise ValueError(
                    f"Phase 0.5 supports exactly one class per lesson: {lesson.id}"
                )
            if lesson.teacher_id not in teacher_ids:
                raise ValueError(f"unknown teacher {lesson.teacher_id} in {lesson.id}")
            if lesson.class_id not in class_ids:
                raise ValueError(f"unknown class {lesson.class_id} in {lesson.id}")
            if lesson.room_kind not in room_kinds:
                raise ValueError(f"unknown room kind {lesson.room_kind} in {lesson.id}")
            if lesson.room_kind == "general" and not any(
                room.kind == "general" and room.assigned_class_id == lesson.class_id
                for room in self.rooms
            ):
                raise ValueError(f"no assigned general room for {lesson.class_id}")

        for decision in self.decisions:
            if decision.kind == "teacher_avoid_slot" and decision.entity_id not in teacher_ids:
                raise ValueError(f"unknown teacher in decision: {decision.entity_id}")
