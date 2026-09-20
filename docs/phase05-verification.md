# Phase 0.5 verification record

Date: 2026-09-20

## Red first

The Phase 0 checkpoint (`a1b7010`, with the review-only follow-up `094feec`) passed its original four tests. Phase 0.5 regression tests were then added before implementation. The first targeted run failed during collection:

```text
pytest tests/test_phase05_regressions.py -q
ImportError: cannot import name 'generate_payload' from 'scheduler_kernel.cli'
1 error during collection
```

That red result is expected: the tests referred to the new independent CLI validation boundary and the rest of the Phase 0.5 contract before those mechanisms existed. Subsequent targeted runs also exposed the dense fixture teacher-load distribution and stale-fingerprint validation until the implementation and tests used the updated authoritative problem.

The regression set covers:

- plural identity with the Phase 0.5 single-entity assertion;
- fixed homeroom eligibility and linear variable count;
- `UNKNOWN` without infeasibility or relaxation claims;
- named specialist-room capacity preflight;
- exclusion of soft objectives from feasibility relaxations;
- CLI rejection of independently invalid materialized schedules;
- explicit repair success/no-change/infeasible/unknown semantics and quality vectors;
- problem fingerprint staleness and accepted-decision writeback;
- realistic-density fixture feasibility and 6/12/24 scaling.

## Green

Final command and result:

```text
python -m pytest -q
................ [100%]
17 passed
```

An actual near-zero-budget dense solve returned:

```text
solve.status=unknown
explanation.status=unknown
conflicts=0
verified_relaxations=0
diagnostic_complete=false
```

This is intentionally different from an `infeasible` result: it makes no causal claim.

## Six-class realistic-density fixture

`data/fixtures/dense_school_6.json` is deterministic and has:

| Measure | Value |
|---|---:|
| classes | 6 |
| slots per class | 35 |
| lessons per class | 35 |
| total lessons | 210 |
| class occupancy | 100% |
| teachers | 10 |
| lessons per teacher | 21 |
| explicit unavailable slots per teacher | 2 |
| assigned general homerooms | 6 |
| shared specialist labs | 1 |
| lab lessons | 30 |

The fixture solves and passes independent `validate_schedule()`. If it later becomes infeasible and the explanation cannot name blocked lessons, the test message records the tripwire to prioritize partial scheduling.

## Scaling evidence

Measured locally on 2026-09-20; the machine-dependent timings are evidence, not fixed test thresholds. `UNKNOWN` and timeout are never converted to `INFEASIBLE`.

| Classes | Lessons | Variables | Model build | Solver | Status |
|---:|---:|---:|---:|---:|---|
| 6 | 210 | 7,350 | 0.101 s | 0.698 s | optimal |
| 12 | 420 | 16,800 | 0.281 s | 7.809 s | optimal |
| 24 | 840 | 42,000 | 0.910 s | 15.764 s | optimal |

Raw output is stored in `docs/phase05-scaling-results.json`. The regression asserts linear eligible-variable growth, while the benchmark records model-build and solver time separately.

## Explain and repair semantics

Specialist-room insufficiency reports `room_kind_capacity` with the room kind, concrete room IDs, demand, and capacity. The response also says that one-code-at-a-time trials are not exhaustive and can miss multi-factor causes.

Repair output distinguishes:

- `success`: state, persisted accepted decision, changed lessons, preservation ratio, before/after quality;
- `no_change_needed`: unchanged state and equal before/after quality;
- `infeasible`: no state, no preservation ratio, no after vector;
- `unknown`: no state, no preservation ratio, no after vector, and no infeasibility claim.

The quality vector names `change_cost`, `teacher_preference_cost`, `teacher_days`, and `teacher_gaps`. It is deliberately reported component-by-component rather than collapsed into the old `1 - 1/N` figure.

## Schema boundary

`teacher_ids` and `class_ids` avoid permanently singular identity and can later carry 2-teacher co-teaching or 2-class combined teaching. Phase 0.5 still validates exactly one of each because the solver has not implemented multi-entity occupancy.

One class split into two simultaneous groups with two teachers and two rooms is explicitly not solved by plural keys. It requires future group-aware H1_CLASS occupancy. No speculative `CourseOffering / SchedulingUnit / LessonRequirement` ontology was introduced.
