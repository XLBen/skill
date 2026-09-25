---
description: Reproduce a defect, fix its root cause, and verify the behavior
agent: build
---

Load the `mvp-delivery` skill in Fix Mode for:

$ARGUMENTS

When the reported defect comes from review findings, load
`receiving-code-review` before treating a suggestion as an implementation
requirement. Select `skill-creator` for a skill behavior/trigger defect,
`frontend-design` only for a requested visual redesign, and
`vercel-react-best-practices` only for an affected React/Next.js path.
The current owner of the repair loads the original applicable skill;
no skill permits edits outside the affected task or protected acceptance.

Load `i-have-adhd` for concise user-facing progress and final delivery. Follow
`systematic-debugging` (reproduce / isolate / hypothesize / verify) before
editing. When the root cause is unclear, dispatch a read-only research seat
first to reproduce and diagnose, then dispatch the fix as a bounded work
package per `mvp-delivery/references/subagent-orchestration.md`; Normal
repairs may stay in-session with the controller integrating and re-verifying.
Reuse the matching unfinished card and never create a second active fix goal;
a completed Audited package is repaired through a new FIX package, never
reopened.

For schema-3 goals reproduce through the affected engineering-plan journey
first, then repair inside a new `begin-cycle` for the affected step (its
downstream steps are invalidated automatically); `verify-cycle`, read the
receipts, `observe-cycle`, and re-run `cycle-gate` plus the final gates. A
regression test that only exercises a mock driver does not close a defect
observed at a real boundary.

Use next-step for the bounded task and its failure_routes. Fix implementation
errors locally; a contradicted interface/architecture assumption requires
observe-cycle replan and a revised planner artifact, not speculative expansion
by the implementation model. Component repairs need their own checks first,
then affected boundary/milestone and final validation.
