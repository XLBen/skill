# v0.1 Repair Plan

## Source And Boundary

- Source: `docs/brief.md`
- Brief revision: `7`
- Brief hash: `b278196021d23c21edbaa1b01a2765fc20c81ee8ef33be66ced8dd52c4b51e55`
- Scope: prompt-layer repair for the skill suite
- Engine boundary: do not modify `scripts/check.py`; do not add a Python or
  Node execution engine in v0.1
- Existing in-construction project 魔塔 remains on the legacy protocol

## Target Workflow

1. Rank risk by the cost of being wrong.
2. Run a bounded Phase 0 probe against the riskiest real boundary.
3. Draft only the thinnest end-to-end first slice after a passed probe or a
   justified `not-needed` decision.
4. Verify the slice with real data and owner acceptance.
5. Use SI (slice increment) for planned expansion after a passed slice.
6. Use CR (change/recovery) only for factual, interface, scope, or acceptance
   mismatch.

## v0.1 Rules

- Phase 0 declares request/call limits, cache, backoff, side effects, cleanup,
  and a stop condition. Its result is saved under
  `docs/evidence/phase-0-<id>.md`.
- The first-slice default budget is at most 3 active P, 3 active F, 3 active I,
  5 active V, 8 PLAN segments, and 180 non-blank contract lines. A wider budget
  requires an owner decision before drafting.
- Every acceptance scenario uses concrete Given/When/Then data and a meaningful
  content, invariant, schema, count, or user-visible assertion.
- Missing, empty, or zero-row output fails unless semantic zero is explicitly
  specified and asserted.
- `test-author` creates acceptance tests, runs and records the red result, and
  freezes test hashes before `step-executor` implements product code.
- The implementation write set excludes frozen test files. A suspected test or
  specification defect returns through CR.
- Failure signatures normalize V ID, command/scenario ID, failing assertion or
  exception type, and the first stable error summary. Timestamps, absolute
  paths, random IDs, and stack line numbers are removed.
- The third consecutive failure with the same signature stops ordinary retry.
  The third attempt counts; no fourth ordinary retry is allowed. Escalation must
  include three raw results, accumulated cost, projected cost, and two options.
- A passed slice may grow only through an SI with ADDED/MODIFIED/REMOVED deltas,
  affected IDs, budget, and scoped verification. Unaffected steps are not
  replayed.
- `docs/mvp-observation.md` is required for the next v0.1 real project and must
  record assertions, non-empty results, signatures, attempts, timing, author
  IDs, frozen hashes, budgets, real-data outcomes, and owner acceptance.
- Documentation-to-code ratio is a warning only; it does not block the engine.

## Phase 2 Trigger

The prompt-layer assumption BA-01 is supported only if the next real project
has a complete, traceable, owner-signed observation report with no observed
prompt failure. Any of these triggers phase-2 engine hardening: exit-code-only V,
empty output accepted, a fourth ordinary retry after the third same-signature
failure, shared test/implementation author identity, modified frozen tests, or
an over-budget first slice.

## Research Basis

- Spec Kit MVP/tasks flow: `https://github.com/github/spec-kit/blob/main/templates/tasks-template.md`
- OpenSpec delta/archive flow: `https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md`
- BMAD independent test role: `https://github.com/bmad-code-org/bmad-method-test-architecture-enterprise`
- Tenacity retry state and limits: `https://github.com/jd/tenacity`
- Resilience4j retry defaults: `https://github.com/resilience4j/resilience4j/blob/master/resilience4j-retry/src/main/java/io/github/resilience4j/retry/RetryConfig.java`
