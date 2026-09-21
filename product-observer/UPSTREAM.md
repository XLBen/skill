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

The upstream skill is served versioned by the installed CLI via
`agent-browser skills get dogfood`. Because bundled skills track the
installed CLI version, **pin the CLI version when installing**
(`npm i -g agent-browser@<version>`) and record it here:

```text
agent-browser CLI version used for this snapshot: <pin at install time>
```

If the CLI is upgraded, re-snapshot the skill, update the commit above, and
re-review the adaptations below.

## What is reused verbatim

- The exploration strategy: orient from top-level navigation, visit each
  section, exercise interactive elements, edge cases, realistic end-to-end
  flows, periodic console checks.
- Repro-first evidence discipline: match evidence weight to the issue
  (video + step screenshots for interactive issues, one annotated screenshot
  for static issues), write findings incrementally, never delete evidence.
- The severity ladder (critical / high / medium / low) and the issue
  taxonomy categories (visual, functional, UX, content, performance,
  console/errors, accessibility).
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
