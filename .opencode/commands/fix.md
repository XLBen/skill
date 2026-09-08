---
description: Reproduce a defect, fix its root cause, and verify the behavior
agent: build
---

Load the `mvp-delivery` skill in Fix Mode for:

$ARGUMENTS

Resolve and reuse the matching active/blocked goal card; do not create a second
active fix goal. Ask if the target or completed Audited repair base is ambiguous.
Preserve completed packages; use a new affected-only FIX package for their repair.
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
state. Report the delivery location, verified setup/use steps and working directory,
prerequisites, a sample result, tested environment and remaining limitations;
if blocked, identify what is still unusable and the smallest required owner action.
