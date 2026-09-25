# Upstream Provenance

## Source

| Field | Value |
|---|---|
| Repository | https://github.com/vercel-labs/agent-browser |
| Snapshot commit | `44583ac8385d814ab98cbf40feec97620376b50e` (main, 2026-09-18) |
| Skill path | `skill-data/dogfood/` |
| Files snapshotted | `upstream/dogfood.md`, `upstream/issue-taxonomy.md`, `upstream/dogfood-report-template.md` |
| License | Apache-2.0 (see `LICENSE`; canonical text at https://www.apache.org/licenses/LICENSE-2.0) |
| Copyright | Copyright (c) Vercel, Inc. and agent-browser contributors |
| Snapshotted | 2026-09-20 |

The three files above are pinned to a Git commit, not to a locally recorded
CLI binary: the CLI version used to serve this snapshot was **not recorded**.
Before claiming runtime command compatibility, probe the installed CLI version
and syntax. If upgrading the CLI or claiming parity with its bundled skill,
record the exact version, compare the versioned `agent-browser skills get dogfood`
output, and re-review the adaptations below. No parity is inferred from the
Git snapshot alone.

## Methodology adapted from the snapshot

- Exploration strategy: orient from top-level navigation, visit material
  surfaces, exercise interactive elements, edge cases and real journeys;
  inspect errors/console when the backend exposes them.
- Repro-first evidence discipline: match evidence weight to the issue and
  record findings incrementally. Interactive repro video is conditional on
  a working capture backend; screenshots plus trace are the local fallback.
- Severity ladder (critical / high / medium / low) and core taxonomy
  categories (visual, functional, UX, content, performance, console/errors,
  accessibility) are retained; local `continuity` adds cross-mode defects.
- "Never read the target app's source code" — the observer works from what
  the product presents, not from implementation files.

## Local adaptations (this repository)

These changes are ours; upstream does not provide them:

1. **Removed the "aim to find 5-10 issues, then wrap up" quota.** Wrap-up is
   governed by material-surface coverage and unresolved findings, not an
   issue count. Issue quotas incentivize fabricated findings or premature
   stops.
2. **Intermittent issues are retained.** Upstream discards issues that do
   not reproduce consistently on retry. We keep them with status
   `intermittent` and the observed evidence; a critical/high intermittent
   finding still blocks delivery until investigated.
3. **Report feeds a repair loop and a delivery gate.** Upstream ends at a
   report. Here the structured findings enter `/fix`, re-observation, and
   `check.py product-audit-gate` before `finish-goal`.
4. **Two phases instead of one pass.** `discover` runs blind to
   implementation context; `compare` then receives the original goal,
   historical product maps, and prior-version behavior evidence to hunt for
   disappeared capabilities. Upstream has no second phase.
5. **Exclusive UI lease.** During observation phases the observer holds the
   lease over the delivered artifact's UI session; other runners are paused
   per the controller's existing pause rules.
6. **Backend routing beyond the browser.** Web journeys use agent-browser;
   native/desktop/mobile/CLI/API surfaces route through the backends in
   `references/backend-routing.md`. Upstream is web-only.
7. **Write scope limited to the observation evidence directory.** The
   observer never modifies product files, tests, goal cards, or gates.

## Not claimed from upstream

The goal-card declaration (`product_observation`), candidate-version
binding, `product-observation/2` schema, packets, engine gate, and reviewer
adequacy duties are this repository's integration; they are not upstream
features.
