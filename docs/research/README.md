# Research corpus and evidence status

Phase 0 uses the seven cases as research inputs, not as a codebase to merge. Public repositories were inspected in isolated research copies; no source tree was imported into this project.

| Case | Evidence available in this run | Phase 0 use |
|---|---|---|
| 01 kent-css | public repository | human-in-the-loop baseline; constraint inputs and manual completion |
| 02 AI Etudes class-schedule | deployed page + prior supplied single-file analysis in referenced conversation | priority heuristic and repeated search comparison |
| 03 Course_Scheduling_System | public repository | CP-SAT, pre-flight, explain-by-relaxation, locked drafts |
| 04 substitution workflow | prior supplied spreadsheet/workflow discussion; no authoritative source imported into Phase 0 | boundary reminder only; out of scope |
| 05 timetable-demo | public repository | read-only timetable/query surface and local-first data handling |
| 06 class-swap-radar | public repository | candidate reasoning, explicit rejection reasons, reversible local swaps |
| 07 Tsai case | user-provided field account in referenced conversation | progressive constraint discovery and derived-output drift risk |

The Meta Review v0.2 concepts recoverable from the referenced conversation were: authoritative schedule state, Constraint Registry, Teacher Preference Profiles, dependency graph, and global-generate/local-repair separation. No standalone v0.2 attachment was available in the current workspace, so these notes do not claim to reproduce an unseen document verbatim.

## Primary sources

- <https://github.com/kentxchang-goedutw/kent-css>
- <https://aietudes.github.io/my-apps-hub/apps/class-schedule/index.html>
- <https://github.com/begin0808/Course_Scheduling_System>
- <https://github.com/alvicss/timetable-demo>
- <https://github.com/yjlhuang/class-swap-radar>
- <https://developers.google.com/optimization/scheduling>

Case 04 and Case 07 are explicitly marked as conversation-derived evidence because no stable public source was available in the current workspace.
