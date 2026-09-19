from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .domain import Slot
from .explain import explain_infeasibility
from .io import load_problem, state_to_dict
from .repair import repair_teacher_slot
from .solver import solve


def _print(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="scheduler-kernel")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("generate", "explain", "demo-repair"):
        child = sub.add_parser(name)
        child.add_argument("fixture")
    args = parser.parse_args()
    problem = load_problem(args.fixture)

    if args.command == "generate":
        result = solve(problem)
        _print(
            {
                "status": result.status,
                "objective": result.objective,
                "schedule": state_to_dict(result.state) if result.state else None,
            }
        )
    elif args.command == "explain":
        _print(asdict(explain_infeasibility(problem)))
    else:
        generated = solve(problem)
        if generated.state is None:
            _print({"status": generated.status, "error": "baseline generation failed"})
            return
        target = generated.state.placements[0]
        lesson = next(l for l in problem.lessons if l.id == target.lesson_id)
        repaired = repair_teacher_slot(problem, generated.state, lesson.teacher_id, target.slot)
        _print(
            {
                "status": repaired.status,
                "teacher": lesson.teacher_id,
                "avoided_slot": {"day": target.slot.day, "period": target.slot.period},
                "changed_lessons": repaired.changed_lessons,
                "locked_lessons": repaired.locked_lessons,
                "preservation_ratio": repaired.preservation_ratio,
                "schedule": state_to_dict(repaired.state) if repaired.state else None,
            }
        )


if __name__ == "__main__":
    main()

