from __future__ import annotations

import json
from pathlib import Path

from .domain import (
    Lesson,
    PolicyConfig,
    Room,
    SchoolProblem,
    SchedulingDecision,
    Slot,
    TeacherPreference,
    TeacherProfile,
)
from .state import Placement, ScheduleState


def _slot(value: list[int]) -> Slot:
    return Slot(day=int(value[0]), period=int(value[1]))


def load_problem(path: str | Path) -> SchoolProblem:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    teachers = tuple(
        TeacherProfile(
            id=t["id"],
            unavailable=frozenset(_slot(s) for s in t.get("unavailable", [])),
            preferences=tuple(
                TeacherPreference(
                    mode=p["mode"],
                    slots=frozenset(_slot(s) for s in p.get("slots", [])),
                    weight=int(p.get("weight", 1)),
                    note=p.get("note", ""),
                )
                for p in t.get("preferences", [])
            ),
        )
        for t in raw["teachers"]
    )
    problem = SchoolProblem(
        days=tuple(raw["days"]),
        periods_per_day=int(raw["periods_per_day"]),
        classes=tuple(raw["classes"]),
        teachers=teachers,
        rooms=tuple(Room(**room) for room in raw["rooms"]),
        lessons=tuple(
            Lesson(
                id=lesson["id"],
                class_ids=tuple(lesson.get("class_ids", (lesson.get("class_id"),))),
                subject=lesson["subject"],
                teacher_ids=tuple(lesson.get("teacher_ids", (lesson.get("teacher_id"),))),
                room_kind=lesson.get("room_kind", "general"),
                is_main_subject=bool(lesson.get("is_main_subject", False)),
            )
            for lesson in raw["lessons"]
        ),
        policy=PolicyConfig(**raw.get("policy", {})),
        decisions=tuple(
            SchedulingDecision(
                kind=d["kind"],
                entity_id=d["entity_id"],
                slot=_slot(d["slot"]),
                provenance=d["provenance"],
                status=d.get("status", "accepted"),
            )
            for d in raw.get("decisions", [])
        ),
    )
    problem.validate()
    return problem


def state_to_dict(state: ScheduleState) -> dict:
    return {
        "version": state.version,
        "parent_version": state.parent_version,
        "status": state.status,
        "created_at": state.created_at,
        "problem_fingerprint": state.problem_fingerprint,
        "placements": [
            {
                "lesson_id": p.lesson_id,
                "day": p.slot.day,
                "period": p.slot.period,
                "room_id": p.room_id,
            }
            for p in state.placements
        ],
    }


def state_from_dict(raw: dict) -> ScheduleState:
    return ScheduleState(
        version=raw["version"],
        parent_version=raw.get("parent_version"),
        status=raw.get("status", "draft"),
        created_at=raw.get("created_at", ""),
        problem_fingerprint=raw.get("problem_fingerprint", ""),
        placements=tuple(
            Placement(
                lesson_id=p["lesson_id"],
                slot=Slot(day=int(p["day"]), period=int(p["period"])),
                room_id=p["room_id"],
            )
            for p in raw["placements"]
        ),
    )
