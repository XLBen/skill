---
description: Reproduce a defect, fix its root cause, and verify the behavior
agent: build
---

Load the `mvp-delivery` skill in Fix Mode for:

$ARGUMENTS

Load `i-have-adhd` for concise user-facing progress and final delivery. When
the root cause is unclear, first dispatch a read-only research seat to
reproduce and diagnose, then dispatch the fix as a bounded work package per
`mvp-delivery/references/subagent-orchestration.md`. Before a material
acceptance handoff, send its preview first, then dispatch a fresh reviewer
with the full `ACCEPTANCE_HANDOFF` and `pua_stage_id`, and consume its
structured result; do not hide unresolved gaps in the final summary.

Resolve and reuse the matching active/blocked goal card; do not create a second
active fix goal. Ask if the target or completed Audited repair base is ambiguous.
Preserve completed packages; use a new affected-only FIX package for their repair.
If no matching unfinished card exists, create a repair card before product edits.
Pass `goal` and any final source `brief` validation on that current unfinished
card; reading/validating the old complete card does not satisfy this gate. Before
product changes reset affected outcomes to pending and clear runtime evidence
references/blockers while keeping evidence files; reconcile card status and
revalidate under `mvp-delivery`. Definition changes require full
invalidation under `mvp-delivery`; never reopen a complete card.
Inspect the repository and reproduce the defect before editing when feasible.
Determine expected behavior from the request, existing tests, and public
interfaces; ask only when those sources leave a material product ambiguity.
Make the smallest root-cause fix, add or update a regression test when useful,
then run narrow verification and the relevant broader suite. If an active
Audited contract conflicts with reality, route the correction through its CR
mechanism internally instead of asking the user to invoke another command.
Use `goal`, `verify-goal`, and `finish-goal`, plus `verify-step` for automated
Audited V. Never manually mark verified/complete or bypass required approvals.

Reproduce and verify through the affected public user path, not just an internal
helper. Apply `mvp-delivery`'s Finish With Evidence gate to the final integrated
state against the original request/all brief BS, whole goal and deferred work;
slice clean is not whole-goal acceptance. Keep required real-boundary outcomes
pending/blocked for missing implementation or verification, recording these gaps
separately rather than deferring or substituting mock/sample scope. Create missing
README/quickstart or update it and replay declared setup/dependencies in isolation;
existing global dependencies do not prove a clean install.
Report the delivery location, verified setup/use steps and working directory,
prerequisites, a sample result, tested environment and remaining limitations;
before declaring completion load the `pua` skill and execute the affected
`goal-verification` and `goal-finish` cards. If blocked, identify what is still
unusable and the smallest required owner action.
