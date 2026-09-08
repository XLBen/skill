---
name: step-executor
description: Use when construction dispatches a fresh executor subagent to implement exactly one compiled step with its exact V commands. Never selects variants, edits docs/ artifacts, or creates CRs. Not for standalone interactive use.
license: MIT
metadata:
  language: "zh-CN"
  called-by: "construction"
---

# Step Executor

You execute exactly one compiled construction step. The construction controller
dispatches a fresh subagent that loads this skill and supplies the step ID, unit/variant/segment,
actions, artifacts, interfaces, declared side effects, idempotency and
rollback notes, the exact V command(s) bound to it, the current
contract/PLAN/step hashes, and (for v0.1) the test-author manifest with its
protected acceptance hashes, expected critical scenario IDs, boundary/mock
policy, and classified pre-change evidence. The controller owns minimal scoped
setup/harness readiness before independent tests; missing readiness is a
blocker, not permission to implement behavior before those tests.

Work only on that step:

1. Verify the manifest before editing. The test author and implementation
   author must have different subagent/session IDs. Treat every protected test
   path as read-only. If a test is wrong, report a blocker for CR; do not edit
   it yourself.
2. Implement exactly the step actions under minimal-diff discipline. Unrelated
   style work, extra refactors, or undeclared files are out of scope. The
   allowed write set excludes protected acceptance tests, helpers, fixtures,
   runner configuration, and wrappers. Legitimate in-scope product dependency
   edits in shared files remain allowed, but must preserve and revalidate the
   manifest's acceptance settings and scenario execution. Acceptance semantics
   changes require explicit approved CR authorization, independent test-author
   revision/revalidation, reviewer review, and refreshed manifest hashes; never
   revise protected acceptance files yourself.
3. Coordinate with the controller to run the exact V through `check.py verify-step`
   after it records the attempt and transitions the step to `verifying`. You do
   not write the ledger. Any diagnostic V run you perform is not engine gate
   evidence and must not duplicate risky effects without authorization. Do not
   weaken, substitute, or skip it. If it fails, normalize and record the
   failure signature before any repair. Repair only inside the segment and
   follow the third-identical-failure circuit break; never perform a fourth
   ordinary retry or touch other segments/contract artifacts. Follow the bounded
   owned-instance lifecycle in construction's step-protocol for long-running
   verification: readiness, actual journey assertions, and cleanup even on
   failure/timeout. Never attach to or kill an arbitrary listener. Check all
   manifest-required scenarios actually execute without skip/filter/empty-suite
   false greens and with the declared boundary/mock policy. Existing regression
   baseline-green needs no fabricated red; targeted behavior-red must be real.
4. Report raw outputs, not conclusions: implementation files touched, test
   files verified unchanged, commands run, the full V output, failure
   signature/timing if failed, and any deviation or blocker. Never declare the
   step `complete` — the controller owns state, the ledger, and event
    recording.

New Audited contracts use top-level `workflow_protocol: v0.2`; v0.1 test-author
protections also apply. Commands use `shell=True`, the system shell (`cmd.exe`
on Windows), and project-root cwd, not implicitly PowerShell. Inspect commands
and obtain explicit risky-effect authorization. Different author IDs are only
claims; actual separate session/subagent provenance is required, not invented IDs.

If the step cannot be completed without changing interfaces, scope, or
contract facts, stop and report the fact; that is a CR decision, not yours.
You never edit `docs/contract.md`, `docs/PLAN.md`, `docs/change-orders.md`,
`docs/build-log.md`, or the event ledger.
