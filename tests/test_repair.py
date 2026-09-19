from pathlib import Path

from scheduler_kernel.io import load_problem
from scheduler_kernel.repair import repair_teacher_slot
from scheduler_kernel.solver import solve
from scheduler_kernel.solver.validator import validate_schedule

FIXTURES = Path(__file__).parents[1] / "data" / "fixtures"


def test_repair_changes_only_target_lesson_and_preserves_at_least_95_percent() -> None:
    problem = load_problem(FIXTURES / "small_school.json")
    baseline = solve(problem).state
    assert baseline is not None
    target = baseline.placements[0]
    lesson = next(l for l in problem.lessons if l.id == target.lesson_id)

    repaired = repair_teacher_slot(problem, baseline, lesson.teacher_id, target.slot)

    assert repaired.state is not None
    assert repaired.changed_lessons == (target.lesson_id,)
    assert repaired.preservation_ratio >= 0.95
    assert repaired.state.parent_version == baseline.version
    assert validate_schedule(problem, repaired.state) == ()

