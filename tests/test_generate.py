from pathlib import Path

from scheduler_kernel.io import load_problem
from scheduler_kernel.solver import solve
from scheduler_kernel.solver.validator import validate_schedule

FIXTURES = Path(__file__).parents[1] / "data" / "fixtures"


def test_generate_produces_independently_valid_schedule() -> None:
    problem = load_problem(FIXTURES / "small_school.json")
    result = solve(problem)
    assert result.status in {"optimal", "feasible"}
    assert result.state is not None
    assert len(result.state.placements) == len(problem.lessons)
    assert validate_schedule(problem, result.state) == ()

