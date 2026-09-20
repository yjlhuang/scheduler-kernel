from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from scheduler_kernel.benchmarking import make_dense_problem
from scheduler_kernel.io import load_problem
from scheduler_kernel.solver import solve
from scheduler_kernel.solver.validator import validate_schedule

FIXTURES = Path(__file__).parents[1] / "data" / "fixtures"


def test_dense_six_class_fixture_is_realistically_loaded_and_feasible() -> None:
    problem = load_problem(FIXTURES / "dense_school_6.json")
    class_loads = Counter(lesson.class_id for lesson in problem.lessons)
    teacher_loads = Counter(lesson.teacher_id for lesson in problem.lessons)
    room_kind_loads = Counter(lesson.room_kind for lesson in problem.lessons)
    assert set(class_loads.values()) == {35}
    assert min(teacher_loads.values()) >= 18
    assert max(teacher_loads.values()) <= 22
    assert room_kind_loads["lab"] == 30
    assert all(teacher.unavailable for teacher in problem.teachers)

    result = solve(problem, time_limit_seconds=15)
    assert result.status in {"optimal", "feasible"}, (
        "Dense fixture became infeasible/unknown. If the explanation cannot name blocked lessons, "
        "this is the tripwire to prioritize partial scheduling."
    )
    assert result.state is not None
    assert validate_schedule(problem, result.state) == ()


@pytest.mark.parametrize("class_count", (6, 12, 24))
def test_scaling_generator_keeps_variable_growth_linear(class_count: int) -> None:
    problem = make_dense_problem(class_count)
    result = solve(problem, time_limit_seconds=30)
    assert result.status in {"optimal", "feasible"}
    assert result.variable_count <= len(problem.lessons) * len(problem.slots) * 2
