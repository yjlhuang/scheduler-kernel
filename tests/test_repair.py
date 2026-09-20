from pathlib import Path

from scheduler_kernel.domain import SchoolProblem, Slot
from scheduler_kernel.io import load_problem
from scheduler_kernel.repair import repair_teacher_slot
from scheduler_kernel.solver import solve
from scheduler_kernel.solver.validator import validate_schedule

FIXTURES = Path(__file__).parents[1] / "data" / "fixtures"


def _avoid_decisions(problem: SchoolProblem, teacher_id: str, slot: Slot) -> tuple:
    return tuple(
        d
        for d in problem.decisions
        if d.kind == "teacher_avoid_slot" and d.entity_id == teacher_id and d.slot == slot
    )


def _avoid_decisions_for_day(problem: SchoolProblem, teacher_id: str, day: int) -> tuple:
    return tuple(
        d
        for d in problem.decisions
        if d.kind == "teacher_avoid_slot" and d.entity_id == teacher_id and d.slot.day == day
    )


def _free_slot_for_teacher(problem: SchoolProblem, state, teacher_id: str) -> Slot:
    """A slot where the teacher has no lesson (so no move is needed) and is not
    already declared unavailable — otherwise the regression would be vacuous."""
    lessons = {lesson.id: lesson for lesson in problem.lessons}
    occupied = {
        placement.slot
        for placement in state.placements
        if lessons[placement.lesson_id].teacher_id == teacher_id
    }
    blocked = occupied | set(problem.teachers_by_id[teacher_id].unavailable)
    return next(slot for slot in problem.slots if slot not in blocked)


def test_repair_changes_only_target_lesson_and_persists_accepted_decision() -> None:
    problem = load_problem(FIXTURES / "small_school.json")
    baseline = solve(problem).state
    assert baseline is not None
    target = baseline.placements[0]
    lesson = next(l for l in problem.lessons if l.id == target.lesson_id)

    repaired = repair_teacher_slot(problem, baseline, lesson.teacher_id, target.slot)

    assert repaired.state is not None
    assert repaired.outcome == "success"
    assert repaired.changed_lessons == (target.lesson_id,)
    assert repaired.preservation_ratio == 1 - (1 / len(problem.lessons))
    assert repaired.state.parent_version == baseline.version
    assert validate_schedule(repaired.authoritative_problem, repaired.state) == ()


def test_no_change_needed_still_persists_requested_decision() -> None:
    """A: 使用者已表達「T 不要 s」；目前剛好沒排到不代表 intent 可以丟掉。"""
    problem = load_problem(FIXTURES / "small_school.json")
    baseline = solve(problem).state
    assert baseline is not None
    teacher_id = problem.teachers[0].id
    free_slot = _free_slot_for_teacher(problem, baseline, teacher_id)

    repaired = repair_teacher_slot(problem, baseline, teacher_id, free_slot)

    assert repaired.outcome == "no_change_needed"
    assert repaired.state is baseline
    assert repaired.changed_lessons == ()
    assert len(_avoid_decisions(repaired.authoritative_problem, teacher_id, free_slot)) == 1


def test_persisted_decision_survives_a_fresh_generate() -> None:
    """B: 重新 Generate 不得把教師排回已被拒絕的時段。

    這是 forensic audit 實測到的 leak：對 T07 逐節請求避開整個星期四後，
    只有「當下剛好有課」的那一節被記錄，重新 Generate 就把 T07 排回星期四。
    多數請求會走 no_change_needed，正是被靜默丟棄的那條路徑。
    """
    problem = load_problem(FIXTURES / "small_school.json")
    baseline = solve(problem).state
    assert baseline is not None
    teacher_id = "T07"
    day = 3  # Thu

    current_problem, current_state = problem, baseline
    for period in range(1, problem.periods_per_day + 1):
        repaired = repair_teacher_slot(
            current_problem, current_state, teacher_id, Slot(day, period)
        )
        assert repaired.state is not None
        current_problem, current_state = repaired.authoritative_problem, repaired.state

    assert len(_avoid_decisions_for_day(current_problem, teacher_id, day)) == (
        problem.periods_per_day
    )

    regenerated = solve(current_problem)
    assert regenerated.state is not None
    lessons = {lesson.id: lesson for lesson in current_problem.lessons}
    leaked = [
        (placement.lesson_id, placement.slot.period)
        for placement in regenerated.state.placements
        if lessons[placement.lesson_id].teacher_id == teacher_id
        and placement.slot.day == day
    ]
    assert leaked == []


def test_repeated_identical_request_does_not_duplicate_decisions() -> None:
    """C: 同一個 teacher_avoid_slot 重複請求只留一筆。"""
    problem = load_problem(FIXTURES / "small_school.json")
    baseline = solve(problem).state
    assert baseline is not None
    teacher_id = problem.teachers[0].id
    free_slot = _free_slot_for_teacher(problem, baseline, teacher_id)

    first = repair_teacher_slot(problem, baseline, teacher_id, free_slot)
    second = repair_teacher_slot(
        first.authoritative_problem, first.state, teacher_id, free_slot
    )

    assert len(_avoid_decisions(second.authoritative_problem, teacher_id, free_slot)) == 1


def test_moving_path_still_records_exactly_one_decision() -> None:
    """D: 原本就需要搬動的路徑行為不變。"""
    problem = load_problem(FIXTURES / "small_school.json")
    baseline = solve(problem).state
    assert baseline is not None
    target = baseline.placements[0]
    lesson = next(l for l in problem.lessons if l.id == target.lesson_id)

    repaired = repair_teacher_slot(problem, baseline, lesson.teacher_id, target.slot)

    assert repaired.outcome == "success"
    assert repaired.state is not None
    assert target.lesson_id in repaired.changed_lessons
    assert len(_avoid_decisions(repaired.authoritative_problem, lesson.teacher_id, target.slot)) == 1
    assert validate_schedule(repaired.authoritative_problem, repaired.state) == ()
