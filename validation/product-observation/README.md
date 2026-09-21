# Product Observation Validation

> Two separate conclusions, never conflated:
>
> - `protocol-pass` — routing, packets, sidecar, engine gate and repair-loop
>   mechanics behave correctly (covered by `tests/test_product_observation.py`
>   and `tests/test_observer_packets.py`).
> - `detection-evaluated` — real observer runs actually find severe
>   non-crashing problems. Protocol tests can NEVER establish this.

## Status

- protocol-pass: verified by the repository test suite — S00–S21 mechanical
  regression: 1183 Python tests (`python -m unittest discover -s tests -p
  "test_*.py"`, skipped=3) + 23 Node plugin tests (`node --test
  "tests/js/**/*.test.mjs"`), and `python scripts/check.py --selftest` PASS.
- detection-evaluated: **PARTIAL** — CLI and one Web case were executed on
  2026-09-21 with a real model (`openai/gpt-5.6-luna`, nested `opencode run` +
  primary mirrors): the clean control passed the full
  discover/compare/review/gate loop with zero findings; 5 of 6 seeded CLI
  defects were detected and correctly blocked (silent save failure, archive
  entry missing, ignored theme with a README whitewash that did not downgrade
  the finding, non-persisted add, intermittent silent save kept as
  `intermittent`); one defect (silent mode B) was missed. One CLI case
  (archive entry) moved from missed-and-passed to detected-and-blocked after a
  calibration-driven prompt fix, and a seeded Web defect (silent Save on the
  Notes page) was detected and blocked through agent-browser. Audio/video,
  desktop and resume/lease cases are still NOT RUN. Full results, evidence
  paths, before/after and remaining prerequisites: `docs/po-repair/CALIBRATION.md`
  §8. Framework support (protocol tests, parser/planner unit tests) must never
  be reported as host-verified detection; unrun cases stay NOT RUN.

## Live Calibration Protocol

### Setup

- Pin `agent-browser` to the version recorded in
  `product-observer/UPSTREAM.md` and pass the backend probes in
  `product-observer/references/backend-routing.md` on the actual host.
- Prepare at least three small real applications with different interaction
  shapes (web app, CLI tool, one canvas/native or audio-dependent app).
- Use one or more executing models (e.g. the GLM/Luna/V41/Flash-class
  models intended for production) — record model identity per run; do not
  hardcode model names in any tooling.

### Seeded-defect matrix (observers never see the labels)

| Case | Seed |
|---|---|
| A | Clean build, no seeded defects (false-positive control) |
| B | Mode B of a two-mode product goes silent (audio removed) while the happy path still works |
| C | An old UI entry/control is disconnected (click does nothing, no error) |
| D | A whole entry point disappears from navigation |
| E | Cross-feature state inconsistency (setting saved in one surface ignored by another) |
| F | A reasonable, intended design change (must be classified intended-change, not a defect) |
| G | An intermittent failure (must be retained as `intermittent`, not discarded) |

Each seeded case gets: same candidate manifest shape, real launch entry,
discover then compare phases, reviewer adequacy pass, repair loop, and a
post-fix re-audit on the new candidate.

### Recorded metrics (per model, per case)

- critical/high defects found vs seeded (recall), with first-found times
- false positives on case A and misclassification on case F
- coverage: material surfaces actually visited vs claimed
- evidence quality: findings whose reproduction replays cleanly
- cost: wall-clock, actions, tokens

Results (sanitized: no credentials, no personal captures) are appended as
case files under `results/` with the run date, model identity, seeds used,
and raw metric tables.

## Non-Goals

- No claim that protocol tests prove detection ability.
- No claim that zero findings on a clean app proves the observer is good —
  only the seeded matrix and case F/G discipline can show that.
- No benchmark fabrication: unrun cases stay NOT RUN.
