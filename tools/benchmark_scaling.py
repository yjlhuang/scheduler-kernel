from __future__ import annotations

import json
from pathlib import Path

from scheduler_kernel.benchmarking import make_dense_problem
from scheduler_kernel.solver import solve


def main() -> None:
    rows = []
    for class_count in (6, 12, 24):
        problem = make_dense_problem(class_count)
        result = solve(problem, time_limit_seconds=30)
        rows.append(
            {
                "classes": class_count,
                "lessons": len(problem.lessons),
                "variables": result.variable_count,
                "model_build_seconds": round(result.model_build_seconds, 6),
                "solver_seconds": round(result.solver_seconds, 6),
                "status": result.status,
            }
        )
    output = Path("docs/phase05-scaling-results.json")
    output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
