from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..constraints.registry import ConstraintRegistry, default_registry
from ..domain import SchoolProblem
from ..solver import solve


@dataclass(frozen=True)
class Conflict:
    code: str
    message: str
    evidence: dict[str, int | str]


@dataclass(frozen=True)
class VerifiedRelaxation:
    code: str
    message: str
    resulting_status: str


@dataclass(frozen=True)
class Explanation:
    status: str
    conflicts: tuple[Conflict, ...]
    verified_relaxations: tuple[VerifiedRelaxation, ...]
    diagnostic_complete: bool
    limitations: tuple[str, ...]


def _preflight(problem: SchoolProblem) -> tuple[Conflict, ...]:
    conflicts: list[Conflict] = []
    all_slots = set(problem.slots)
    for teacher in problem.teachers:
        assigned = sum(1 for lesson in problem.lessons if lesson.teacher_id == teacher.id)
        available = len(all_slots - set(teacher.unavailable))
        if assigned > available:
            conflicts.append(
                Conflict(
                    "teacher_capacity",
                    f"教師 {teacher.id} 有 {assigned} 堂課，但只剩 {available} 個可用時段。",
                    {"teacher": teacher.id, "assigned": assigned, "available": available},
                )
            )

    for class_id in problem.classes:
        assigned = sum(1 for lesson in problem.lessons if lesson.class_id == class_id)
        if assigned > len(problem.slots):
            conflicts.append(
                Conflict(
                    "class_capacity",
                    f"班級 {class_id} 有 {assigned} 堂課，超過 {len(problem.slots)} 個時段。",
                    {"class": class_id, "assigned": assigned, "available": len(problem.slots)},
                )
            )

    rooms_by_kind: dict[str, list[str]] = {}
    for room in problem.rooms:
        if room.kind != "general":
            rooms_by_kind.setdefault(room.kind, []).append(room.id)
    demand_by_kind = Counter(
        lesson.room_kind for lesson in problem.lessons if lesson.room_kind != "general"
    )
    for kind, demand in demand_by_kind.items():
        room_ids = sorted(rooms_by_kind.get(kind, []))
        capacity = len(room_ids) * len(problem.slots)
        if demand > capacity:
            conflicts.append(
                Conflict(
                    "room_kind_capacity",
                    f"專科教室類型 {kind} 需要 {demand} 堂，但 {', '.join(room_ids) or '無'} 只能提供 {capacity} 格。",
                    {
                        "room_kind": kind,
                        "rooms": ",".join(room_ids),
                        "demand": demand,
                        "capacity": capacity,
                    },
                )
            )

    subject_counts = Counter(
        (lesson.class_id, lesson.subject) for lesson in problem.lessons
    )
    subject_capacity = len(problem.days) * problem.policy.max_same_subject_per_day
    for (class_id, subject), demand in subject_counts.items():
        if demand > subject_capacity:
            conflicts.append(
                Conflict(
                    "daily_subject_capacity",
                    f"班級 {class_id} 的 {subject} 需要 {demand} 堂，但每日上限合計只能容納 {subject_capacity} 堂。",
                    {
                        "class": class_id,
                        "subject": subject,
                        "demand": demand,
                        "capacity": subject_capacity,
                    },
                )
            )
    return tuple(conflicts)


def explain_infeasibility(
    problem: SchoolProblem,
    registry: ConstraintRegistry | None = None,
    *,
    time_limit_seconds: float = 10.0,
) -> Explanation:
    registry = registry or default_registry()
    baseline = solve(problem, time_limit_seconds=time_limit_seconds)
    if baseline.state is not None:
        return Explanation("feasible", (), (), True, ())
    if baseline.status == "unknown":
        return Explanation(
            "unknown",
            (),
            (),
            False,
            ("求解在時限內未完成；這不代表無解，也不執行 relaxation 因果宣稱。",),
        )

    verified: list[VerifiedRelaxation] = []
    for code in registry.feasibility_relaxable_codes():
        trial = solve(
            problem,
            disabled_constraints={code},
            time_limit_seconds=time_limit_seconds,
        )
        if trial.state is not None:
            definition = registry.get(code)
            verified.append(
                VerifiedRelaxation(
                    code,
                    f"實際關閉「{definition.name}」後可排出課表；是否放寬仍需人工授權。",
                    trial.status,
                )
            )
    return Explanation(
        baseline.status,
        _preflight(problem),
        tuple(verified),
        False,
        (
            "目前只做必要條件檢查與一次關閉一個 constraint family 的試驗；多因衝突可能未被列出，結果不是完整診斷或 MUS。",
        ),
    )
