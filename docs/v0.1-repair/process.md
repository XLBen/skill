# v0.1 Repair Process

## 1. Diagnosis

The existing chain was inspected as `grill -> contract-review -> construction`,
including `reviewer`, `step-executor`, `scripts/check.py`, command wrappers,
fixtures, and the four project artifacts named in the brief. The main loss
points were real-world verification gaps, self-authored tests, late risk
discovery, unbounded retry, ceremony growth, and delivery drift.

The engine inspection confirmed that `scripts/check.py` performs deterministic
document, hash, ledger, coverage, and state checks. It does not execute V
commands or product code. That made a prompt-layer MVP the smallest compatible
v0.1 change.

## 2. Decisions

- `BD-03`: replace the default waterfall-like flow with Phase 0, a thin first
  slice, and SI expansion; keep CR for abnormal recovery.
- `BD-04`: document-to-code ratio is an owner-visible warning, not a hard gate.
- `BD-05`: implement the v0.1 change set in skills, references, command
  templates, an independent test author, and an observation template.
- `BD-06`: SI is the normal planned delta; CR is not reused for ordinary
  thickening.
- `BD-07`: test and implementation authors must use different subagent/session
  IDs at minimum.
- `BC-01..BC-10`: preserve the engine boundary, add measurable budgets,
  normalized failure signatures, exact circuit-breaker semantics, traceable
  observation, and project-level protocol migration.

## 3. Implementation

- `contract-review/SKILL.md` now describes Phase 0, first-slice budgets, SI/CR
  routing, independent test authorship, and the updated release gate.
- `contract-review/references/` now contains Phase 0, SI, ADR, GWT/empty-result,
  evidence, requirement, plan, reviewer, and verdict guidance.
- `construction/SKILL.md` and `construction/references/step-protocol.md` now
  carry the test-author handoff, protected test write set, normalized failure
  signature, third-failure circuit breaker, CR recovery, and MVP observation
  requirements.
- Added `construction/references/mvp-observation-template.md`.
- Added the independent `test-author/SKILL.md` and `test-author/README.md`.
- Updated `reviewer`, `step-executor`, their READMEs, and the root README so the
  new authorship, hash, budget, SI, and observation gates are visible at each
  handoff.
- Updated `.opencode/commands/build.md`, `change.md`, `finish.md`, `plan.md`,
  `resume.md`, `retro.md`, and `review.md`; added `test-author.md`.
- Updated contract and plan fixtures to match the new acceptance metadata and
  hashes.

## 4. Installer Check

`scripts/install.py` discovers command wrappers with
`source.glob("*.md")` and registers the repository root as the skills path.
Therefore the new `test-author` command and skill are included without an
installer code change.

## 5. Deliberate Non-Changes

- `scripts/check.py` was not modified.
- No new Python or Node execution engine was added.
- `grill` behavior was not redesigned; only downstream integration remains
  allowed by `BN-01`.
- No real project was migrated in this repair pass; the next new project must
  declare `workflow_protocol: v0.1`, while existing work remains `legacy`.
