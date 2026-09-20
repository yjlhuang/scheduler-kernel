from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from .domain import SchoolProblem, Slot


@dataclass(frozen=True)
class Placement:
    lesson_id: str
    slot: Slot
    room_id: str


@dataclass(frozen=True)
class ScheduleState:
    """Versioned schedule tied to the authoritative problem by content hash."""

    version: str
    placements: tuple[Placement, ...]
    problem_fingerprint: str
    parent_version: str | None = None
    status: str = "draft"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @classmethod
    def create(
        cls,
        placements: list[Placement],
        *,
        parent_version: str | None = None,
        status: str = "draft",
        problem_fingerprint: str = "",
    ) -> "ScheduleState":
        return cls(
            version=str(uuid4()),
            placements=tuple(sorted(placements, key=lambda p: p.lesson_id)),
            problem_fingerprint=problem_fingerprint,
            parent_version=parent_version,
            status=status,
        )

    @property
    def by_lesson(self) -> dict[str, Placement]:
        return {placement.lesson_id: placement for placement in self.placements}

    def is_stale_for(self, problem: SchoolProblem) -> bool:
        return self.problem_fingerprint != problem.content_fingerprint


@dataclass(frozen=True)
class DerivedArtifact:
    id: str
    kind: str
    source_schedule_version: str


class DependencyGraph:
    """Tracks which exports/views are stale after the authoritative state changes."""

    def __init__(self) -> None:
        self._artifacts: dict[str, DerivedArtifact] = {}

    def register(self, artifact: DerivedArtifact) -> None:
        self._artifacts[artifact.id] = artifact

    def stale_for(self, schedule_version: str) -> tuple[DerivedArtifact, ...]:
        return tuple(
            artifact
            for artifact in self._artifacts.values()
            if artifact.source_schedule_version != schedule_version
        )
