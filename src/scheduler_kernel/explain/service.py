from __future__ import annotations

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


def _preflight(problem: SchoolProblem) -> tuple[Conflict, ...]:
    conflicts: list[Conflict] = []
    all_slots = set(problem.slots)
    for teacher in problem.teachers:
        assigned = sum(1 for lesson in problem.lessons if lesson.teacher_id == teacher.id)
        available = len(all_slots - set(teacher.unavailable))
        if assigned > available:
            conflicts.append(
                Conflict(
                    code="teacher_capacity",
                    message=(
                        f"教師 {teacher.id} 有 {assigned} 堂課，但扣除不可排時段後只剩 "
                        f"{available} 個可用時段。"
                    ),
                    evidence={"teacher": teacher.id, "assigned": assigned, "available": available},
                )
            )
    return tuple(conflicts)


def explain_infeasibility(
    problem: SchoolProblem,
    registry: ConstraintRegistry | None = None,
) -> Explanation:
    registry = registry or default_registry()
    baseline = solve(problem)
    if baseline.state is not None:
        return Explanation(status="feasible", conflicts=(), verified_relaxations=())

    verified: list[VerifiedRelaxation] = []
    for code in registry.relaxable_codes():
        trial = solve(problem, disabled_constraints={code}, time_limit_seconds=3.0)
        if trial.state is not None:
            definition = registry.get(code)
            verified.append(
                VerifiedRelaxation(
                    code=code,
                    message=f"實際關閉「{definition.name}」後可排出課表；是否放寬仍需人工授權。",
                    resulting_status=trial.status,
                )
            )
    return Explanation(
        status=baseline.status,
        conflicts=_preflight(problem),
        verified_relaxations=tuple(verified),
    )

