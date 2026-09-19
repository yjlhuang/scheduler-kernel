from scheduler_kernel.state import DependencyGraph, DerivedArtifact, ScheduleState


def test_derived_artifact_becomes_stale_after_new_schedule_version() -> None:
    first = ScheduleState.create([])
    second = ScheduleState.create([], parent_version=first.version)
    graph = DependencyGraph()
    artifact = DerivedArtifact("teacher-view", "teacher_timetable", first.version)
    graph.register(artifact)
    assert graph.stale_for(first.version) == ()
    assert graph.stale_for(second.version) == (artifact,)

