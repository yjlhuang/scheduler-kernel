from pathlib import Path

from scheduler_kernel.explain import explain_infeasibility
from scheduler_kernel.io import load_problem

FIXTURES = Path(__file__).parents[1] / "data" / "fixtures"


def test_explain_reports_capacity_and_verified_relaxation() -> None:
    problem = load_problem(FIXTURES / "unsat_teacher_capacity.json")
    explanation = explain_infeasibility(problem)
    assert explanation.status == "infeasible"
    assert any(c.code == "teacher_capacity" for c in explanation.conflicts)
    assert any(r.code == "H5_AVAIL" for r in explanation.verified_relaxations)

