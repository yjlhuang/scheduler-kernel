# Constraint Registry

The registry avoids collapsing physical facts, institutional rules, tacit knowledge, policy choices, and personal preferences into one undifferentiated list.

| Code | Category | Rule | Default | Human-relaxable | Phase 0 |
|---|---|---|---|---|---|
| H1_CLASS | physical hard | A class cannot attend two lessons at once | hard | no | implemented |
| H2_TEACHER | physical hard | A teacher cannot teach in two places at once | hard | no | implemented |
| H3_ROOM | physical hard | A room cannot host two lessons at once | hard | no | implemented |
| H4_COMPLETE | explicit institutional hard | Every lesson must be placed exactly once | hard | no | implemented |
| H5_AVAIL | explicit institutional hard | A teacher cannot be placed in an explicitly unavailable slot | hard | yes, with authority | implemented + explain trial |
| H6_DAILY_SUBJECT | tacit domain hard | A class/subject may not exceed the configured daily limit | hard | yes | implemented + explain trial |
| P1_MAIN_SPREAD | negotiable policy | Main subjects should be spread across days | weighted penalty | policy-adjustable, not a feasibility relaxation | implemented |
| S1_TEACHER_SLOT | soft preference | Honour explicit prefer/avoid slots | weighted penalty | preference-adjustable, not a feasibility relaxation | implemented |

## Registry rules

- Physical hard constraints are never disabled by Explain or Repair.
- Explain feasibility trials may use only constraints marked `affects_feasibility`; disabling a soft objective can change search speed, never mathematical feasibility, so it cannot support a “relaxed and schedulable” claim.
- “Relaxable” means the engine may test the consequence; it does not grant itself permission to change school policy.
- Tacit rules must carry a source and confidence before production use. The synthetic fixture is only a modeling demonstration.
- `unknown` and `indifferent` are different: unknown means not elicited; indifferent means explicitly flexible. Neither receives a hidden default penalty in Phase 0.
- Each future constraint needs at least one positive test, one violating fixture or unit test, and a plain-language explanation.
- H1_CLASS remains one-class-one-cell in Phase 0.5. Plural identity prepares co-teaching and combined classes, but simultaneous split-group teaching remains explicitly deferred until occupancy becomes group-aware.
