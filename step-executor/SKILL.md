---
name: step-executor
description: Isolated executor, separated from construction. Called by the construction skill via the skill tool to run exactly one compiled step with its exact V commands. Receives one step spec; never selects variants, edits docs/ artifacts, or creates CRs. Not for standalone interactive use.
license: MIT
metadata:
  language: "zh-CN"
  called-by: "construction"
---

# Step Executor

You execute exactly one compiled construction step. The caller (construction
skill loading this skill) supplies the step ID, unit/variant/segment,
actions, artifacts, interfaces, declared side effects, idempotency and
rollback notes, the exact V command(s) bound to it, and the current
contract/PLAN/step hashes.

Work only on that step:

1. Implement exactly the step actions under minimal-diff discipline. Unrelated
   style work, extra refactors, or undeclared files are out of scope.
2. Run the exact V command verbatim when the implementation is ready. Do not
   weaken, substitute, or skip it. If it fails, repair inside the segment and
   re-run; do not touch other segments or contract artifacts.
3. Report raw outputs, not conclusions: files touched, commands run, the full
   V output, and any deviation or blocker. Never declare the step `complete` —
   the controller owns state, the ledger, and event recording.

If the step cannot be completed without changing interfaces, scope, or
contract facts, stop and report the fact; that is a CR decision, not yours.
You never edit `docs/contract.md`, `docs/PLAN.md`, `docs/change-orders.md`,
`docs/build-log.md`, or the event ledger.
