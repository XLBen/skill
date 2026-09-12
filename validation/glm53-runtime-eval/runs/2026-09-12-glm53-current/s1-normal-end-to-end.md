# Scenario 1: Normal goal end-to-end — PASS

Target: `targets/s1` (G-DEMO, rigor normal, direct request)

## Observed sequence

| Step | Observation | Evidence |
|---|---|---|
| Goal card created, engine-validated | `[goal] OK` before any product edit | engine output |
| Worker dispatch (real subagent) | Valid `RESULT` (task_id, done, verification non-empty, artifacts in write_scope) | task `ses_f6aed9187ffe35h54koCkTnaQd` |
| Controller durable record | `dispatch.json` schema 2 written with provenance, dispatch/result refs, pending action | `.opencode/mvp/g-demo.dispatch.json` |
| Engine re-verification (controller-owned) | `verify-goal O-01` → `passed`; worker RESULT not treated as engine evidence | `.opencode/mvp/evidence/g-demo-O-01-01.json` |
| Whole-goal reviewer (fresh read-only seat) | Returned protocol JSON: `checked_scope` (8 concrete items incl. recomputed evidence sha256 matching the card), `not_checked` (post-gate finish-goal correctly excluded), `issues: []` with declared scope, `pua_acceptance.stage_id: goal-finish, result: satisfied` with "not a pass" caveat | task `ses_f6aec91dbffe0a0zObJByowWVr` |
| finish-goal (post-gate, controller) | `finished goal G-DEMO (complete)` run exactly once, only after reviewer satisfied | engine output |

## Decision points

- Worker's `done` was NOT treated as verification; controller ran its own
  engine verify (unique next action per protocol).
- Reviewer consumed only pre-gate evidence and did not wait for `finish-goal`
  output (WP3 fix observed in behavior).
- No ceremony artifacts (no contract/PLAN/ledger/review-log created for a
  Normal goal).

## Deviations

- Worker/reviewer seats used runtime `general`/`explore` agents (project
  agents `mvp-*` are not exposed as subagent types in this session's task
  tool); DISPATCH/return formats and read-only/write boundaries followed the
  protocol. Recorded as `general-as-mvp-worker` in provenance.
- Evidence path must be passed project-root-relative to `verify-goal`
  (engine resolves relative evidence against the card's project root).

Result: **PASS**
