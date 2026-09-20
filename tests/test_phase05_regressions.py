from __future__ import annotations

from dataclasses import replace

import pytest

from scheduler_kernel.cli import generate_payload
from scheduler_kernel.domain import (
    Lesson,
    Room,
    SchoolProblem,
    SchedulingDecision,
    Slot,
    TeacherProfile,
)
from scheduler_kernel.explain import explain_infeasibility
from scheduler_kernel.repair import repair_teacher_slot
from scheduler_kernel.solver import SolveResult, solve
from scheduler_kernel.state import Placement, ScheduleState


def tiny_problem(*, lessons: tuple[Lesson, ...] | None = None) -> SchoolProblem:
    return SchoolProblem(
        days=("Mon",),
        periods_per_day=2,
        classes=("C1",),
        teachers=(TeacherProfile("T1"),),
        rooms=(Room("C1-HOME", "general", assigned_class_id="C1"),),
        lessons=lessons
        or (
            Lesson("L1", ("C1",), "Math", ("T1",)),
        ),
    )


def test_schema_uses_plural_identity_but_phase05_rejects_multi_entity_solver() -> None:
    lesson = Lesson("L1", ("C1",), "Math", ("T1",))
    assert lesson.class_ids == ("C1",)
    assert lesson.teacher_ids == ("T1",)

    co_taught = replace(lesson, teacher_ids=("T1", "T2"))
    problem = replace(
        tiny_problem(lessons=(co_taught,)),
        teachers=(TeacherProfile("T1"), TeacherProfile("T2")),
    )
    with pytest.raises(ValueError, match="Phase 0.5 supports exactly one teacher"):
        problem.validate()


def test_general_lesson_is_pinned_to_its_classroom() -> None:
    problem = replace(
        tiny_problem(),
        rooms=(
            Room("C1-HOME", "general", assigned_class_id="C1"),
            Room("OTHER-HOME", "general", assigned_class_id="OTHER"),
        ),
    )
    result = solve(problem)
    assert result.state is not None
    assert {p.room_id for p in result.state.placements} == {"C1-HOME"}
    assert result.variable_count == len(problem.lessons) * len(problem.slots)


def test_unknown_is_not_explained_as_infeasible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scheduler_kernel.explain.service.solve",
        lambda *args, **kwargs: SolveResult("unknown", None, None, 0.0, 0.01, 0),
    )
    explanation = explain_infeasibility(tiny_problem(), time_limit_seconds=0.01)
    assert explanation.status == "unknown"
    assert explanation.conflicts == ()
    assert explanation.verified_relaxations == ()
    assert explanation.diagnostic_complete is False
    assert explanation.limitations


def test_room_kind_capacity_preflight_names_the_resource() -> None:
    lessons = tuple(
        Lesson(f"L{i}", ("C1",), f"S{i}", ("T1",), room_kind="lab")
        for i in range(3)
    )
    problem = SchoolProblem(
        days=("Mon",),
        periods_per_day=2,
        classes=("C1",),
        teachers=(TeacherProfile("T1"),),
        rooms=(Room("LAB-1", "lab"),),
        lessons=lessons,
    )
    explanation = explain_infeasibility(problem, time_limit_seconds=1)
    conflict = next(c for c in explanation.conflicts if c.code == "room_kind_capacity")
    assert conflict.evidence["room_kind"] == "lab"
    assert conflict.evidence["rooms"] == "LAB-1"
    assert explanation.diagnostic_complete is False


def test_soft_objectives_are_not_feasibility_relaxations() -> None:
    from scheduler_kernel.constraints.registry import default_registry

    assert default_registry().feasibility_relaxable_codes() == (
        "H5_AVAIL",
        "H6_DAILY_SUBJECT",
    )


def test_relaxation_trials_receive_the_baseline_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[float] = []

    def fake_solve(*args, **kwargs):
        calls.append(kwargs["time_limit_seconds"])
        return SolveResult("infeasible", None, None, 0.0, 0.0, 0)

    monkeypatch.setattr("scheduler_kernel.explain.service.solve", fake_solve)
    explanation = explain_infeasibility(tiny_problem(), time_limit_seconds=4.5)
    assert explanation.status == "infeasible"
    assert calls == [4.5, 4.5, 4.5]


def test_cli_validator_failure_is_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = tiny_problem()
    state = ScheduleState.create(
        [Placement("L1", Slot(0, 1), "C1-HOME")],
        problem_fingerprint=problem.content_fingerprint,
    )
    monkeypatch.setattr(
        "scheduler_kernel.cli.solve",
        lambda _problem: SolveResult("optimal", state, 0.0, 0.0, 0.0, 1),
    )
    monkeypatch.setattr(
        "scheduler_kernel.cli.validate_schedule",
        lambda _problem, _state: ("synthetic validator failure",),
    )
    payload = generate_payload(problem)
    assert payload["status"] == "invalid"
    assert payload["schedule"] is None
    assert payload["validation_errors"] == ("synthetic validator failure",)


def test_repair_result_distinguishes_failure_and_reports_quality_vectors() -> None:
    problem = tiny_problem()
    baseline = solve(problem).state
    assert baseline is not None
    target = baseline.placements[0]

    unused_slot = Slot(0, 2 if target.slot.period == 1 else 1)
    no_change = repair_teacher_slot(problem, baseline, "T1", unused_slot)
    assert no_change.outcome == "no_change_needed"
    assert no_change.before_quality == no_change.after_quality
    assert no_change.preservation_ratio == 1.0

    impossible_problem = replace(
        problem,
        decisions=(SchedulingDecision.teacher_avoid_slot("T1", unused_slot, "accepted-test"),),
    )
    failed = repair_teacher_slot(impossible_problem, baseline, "T1", target.slot)
    assert failed.outcome == "infeasible"
    assert failed.state is None
    assert failed.preservation_ratio is None
    assert failed.after_quality is None
    assert failed.before_quality.teacher_days >= 1


def test_problem_fingerprint_detects_stale_schedule_and_repair_persists_decision() -> None:
    problem = tiny_problem()
    baseline = solve(problem).state
    assert baseline is not None
    assert baseline.is_stale_for(problem) is False

    changed_problem = replace(problem, periods_per_day=3)
    assert baseline.is_stale_for(changed_problem) is True

    target = baseline.placements[0]
    repaired = repair_teacher_slot(problem, baseline, "T1", target.slot)
    assert repaired.state is not None
    assert repaired.authoritative_problem.decisions[-1].slot == target.slot
    assert repaired.state.problem_fingerprint == repaired.authoritative_problem.content_fingerprint
