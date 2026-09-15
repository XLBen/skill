# Workflow Refactor Report

Executed 2026-09-15 against commit 71d358a (clean baseline). This report states
what changed, the measured effect, the verification actually performed, and the
parts that remain unverified.

## Result

The suite now has a single machine-readable routing authority, one result
envelope, on-demand loading for the heavy Audited material, honest hash
semantics, and opt-in isolated concurrent writers. The controller entry cost
roughly halved; the strict reviewer seat cost fell less and is reported as a
miss against the original target.

## Per-package changes

### P0 baseline

- Commit 71d358a, clean worktree.
- `check.py --selftest` PASS; 175 unit tests OK.
- Workflow text baseline: 325,602 bytes (skills + agents + commands, md/json).

### P1 routing (one authority)

- `mvp-delivery/references/stage-routing.json` bumped to schema 2 with explicit
  `rigors`, per-stage `reviewer.condition`, `seat_selection`,
  `pua_conditions`, and per-PUA-entry `roles`.
- New `scripts/workflow_protocol.py` resolves stages, required skills, PUA
  narrowing, reviewer conditions, and the Audited implementation seat. Unknown
  rigor fails closed for guarded-or-audited cards.
- `runtime_trace.py` derives PUA requirements from the routing table instead of
  `PUA_REQUIRING_ROLES = {"reviewer"}`; it now also accepts a dispatch-declared
  `pua_stage_id` and requires a matching `pua_acceptance`. `check.py` passes the
  dispatch record's slice rigor and the goal's cumulative rigor separately.
- Contradictions fixed: cardless Normal tasks are allowed (with no `/resume`
  claim), controller execution is seat selection rather than a skipped
  dispatch, `i-have-adhd` no longer decides dispatches, the reviewer no longer
  self-adds a second PUA pass, construction returns next-slice risk to
  mvp-delivery, and the converge-audit / slice-acceptance card split is
  explicit (reviewer executes `review-verdict`; the controller executes
  `slice-acceptance`).

### P2 returns and recovery

- `subagent-templates.md` defines the `task-result/1` envelope: statuses
  `completed | needs_input | waiting_controller | blocked | failed`, plus
  changes/evidence/not_verified/issues/controller_actions/next_context and a
  role `payload`. Legacy `done/needs_context/blocked` is read as legacy.
- `CONTROLLER_ACTION` requests carry a stable `action_id`; the dispatch record
  gains `attempt` and `actions` state. The runtime gate fails completion on
  unresolved/`failed`/`unknown` actions and on `completed` actions without
  evidence.
- test-author bootstrap has an explicit `phase: bootstrap` return.

### P3 context compression

- Command wrappers: build 3883 → 500, fix 3590 → 682, resume 3852 → 591,
  plan 2645 → 520 bytes; they now delegate the mode contract to mvp-delivery.
- `mvp-delivery/SKILL.md`: 315 → 115 lines, 34,250 → 15,890 bytes. Details
  moved to `references/goal-definition.md`, `delivery-execution.md`,
  `delivery-finish.md`, `delivery-recovery.md`.
- PUA cards split into `pua/references/stage-checks/` (one card per load);
  `stage-checks.md` is now a 34-line index with the shared card rules.
- `construction/SKILL.md` 19,157 → 16,147 bytes; seat dispatch moved to
  `construction/references/seat-dispatch.md`.
- The research seat no longer loads the controller skill.

### P4 hashes and evidence

- v0.2 contracts no longer require an E-node `bundle_hash`; a present hash is
  still verified. Legacy contracts keep the old requirement.
- Workspace snapshots fail on unreadable files instead of recording an
  `unreadable` marker.
- New optional `goal.snapshot_include` re-includes normally excluded delivery
  inputs (validated as project-relative); inclusive bindings win over
  exclusions.
- `check.py check-current <card>` is a read-only freshness check for completed
  cards; `finish-goal` on a completed card still returns "historically
  complete", now with an explicit CLI message instead of a fresh-finish read,
  and it is documented next to `check-current`.
- Skill-tree freshness is a diagnostic: `--strict` no longer fails on it,
  `--strict-freshness` opts in. Installed engine/agent copies are checked
  against the manifest and always fail strict when changed.

### P5 isolated concurrency

- New `scripts/worktree_tasks.py`: admission, create detached worktree,
  collect (binary/rename/untracked-safe), scope check, patch preflight/apply,
  cleanup with `--integrated`/`--discard`, status.
- Orchestration protocol documents the admission conditions and the
  single-integrator rule; the worker agent accepts an assigned absolute
  worktree root. Audited steps keep their existing semantics.

### P6 install and docs

- Installer copies `workflow_protocol.py`, `worktree_tasks.py`, and
  `stage-routing.json` into the engine; the installed engine resolves its own
  routing copy.
- test-author edit globs extended to `**/__tests__/**`, `**/*.test.*`,
  `**/*.spec.*` while product paths stay denied.
- README updated for concurrency, the result envelope, `check-current`, and
  `--strict-freshness`.

## Measured effect

| Metric | Baseline | Now | Delta |
|---|---:|---:|---:|
| Normal controller entry (wrapper + mvp-delivery + i-have-adhd) | 45,092 B | 23,424 B | **-48%** |
| Reviewer heavy seat (agent + reviewer + protocol + pua + one card) | 45,497 B | 34,114 B | **-25%** |
| Largest command wrapper (`build.md`) | 3,883 B | 500 B | -87% |
| `mvp-delivery/SKILL.md` | 34,250 B | 15,890 B | -54% |
| PUA stage checks per load | 14,372 B | ~0.6–1.0 KB | **-93%+** |
| Repo workflow text total | 325,602 B | 337,925 B | +3.8% |

The total grew because the removed controller text now lives in on-demand
references and ten card files; per-invocation reading is the metric that
improved. The reviewer target of -40% was **not met**: the reviewer skill,
reviewer protocol, and PUA principles were left intact rather than cut, and the
card split only covers part of that chain. Splitting `reviewer-protocol.md`
into core + per-mode files is the remaining lever if that target matters.

## Verification performed

| Check | Result |
|---|---|
| `python scripts/check.py --selftest` | PASS |
| `python -B -m unittest discover -s tests -p "test_*.py"` | 233 tests, OK (baseline 175; 12 review follow-up tests included) |
| New real-git worktree tests | 10 tests OK (isolation, binary, rename, scope, conflicts, cleanup) |
| Install smoke into a temp target | install OK; installed `check.py --selftest` PASS |
| `check_runtime.py doctor <smoke> --strict` | exit 0; `INSTALL_STATIC/FRESHNESS/INTEGRITY` all ok |
| CLI worktree end-to-end (2 tasks → collect → scope → apply → cleanup) | both patches integrated, worktrees removed |
| `check-current` after finish / after product change | exit 0 / non-zero with "workspace changed after verification" |
| `runtime_trace.py export .` smoke | trace written (108 sessions, 46 skill loads, 97 tasks) |
| `runtime_trace.py validate` on a real target dispatch | **not run** (needs a target project with a dispatch record and matching native sessions) |
| Hosted Normal / Guarded / Audited subagent scenarios | **not run** (this interface cannot host real OpenCode subagent sessions; static tests are not a substitute) |
| GUI (`computer-use`) | **not run** (no desktop MCP backend configured) |

## Compatibility

- Existing goal cards, dispatch records, contracts, PLANs and evidence files
  remain readable; new requirements apply to new work. A v1 dispatch record is
  upgraded only with verifiable fields.
- Legacy `RESULT`/`done/needs_context/blocked` returns are accepted as legacy;
  new dispatches require the envelope.
- E-node `bundle_hash` remains required for legacy contracts; dropping it only
  applies to new v0.2 contracts.
- `stage-routing.json` schema 1 is replaced by schema 2; nothing consumes the
  old shape (tests updated).

## Independent review follow-up

An independent read-only reviewer seat inspected the refactor and returned 12
issues (2 hard, 10 soft). All material findings were fixed:

| Issue | Finding | Fix |
|---|---|---|
| 01 (hard) | Normal brief/plan/finish review was mandatory in routing but risk-triggered in the docs | Normal is risk-triggered (`optional_rigors`) for brief-final, goal-validation and goal-finish; tests updated |
| 02 | Normal review-verdict card vs no-PUA rule | PUA index clarifies Guarded passes `pua_stage_id`, Normal does not |
| 03 | README "all tasks use a card" vs cardless Normal | README qualified to tracked tasks |
| 04 (hard) | Cross-boundary rename passed the scope check | both rename sides must match the scope; new regression test |
| 05 | Worktree root binding only in the agent file | `work_root` added to the DISPATCH template and task-worker inputs/procedure |
| 06 | Two skills still said `needs_context`; no envelope validation | instructions fixed; reviewer envelope status is now validated by the runtime gate |
| 07 | `runtime_trace.py validate` rejected a conforming Normal reviewer | CLI derives the slice rigor from the dispatch record; test added |
| 08 | Unrecognized rigor strings failed open in the resolver | unknown rigor now fails closed for PUA narrowing; test added |
| 09 | Stage inventory vs routing mismatches | `goal-verification` stage added; `required_skills_for_stage`/`pua_stage_card` respect stage rigors; `pua_stage_card` is role-aware |
| 10 | `bundle_hash` docs stale, no engine coverage | contract schema/evidence protocol qualified; three engine tests added |
| 11 | Broad `snapshot_include` globs could wedge on workflow state | include matching never re-includes `.opencode/mvp/**`; broad-glob test added |
| 12 | Completed-card `finish-goal` no-op not signposted | explicit CLI message plus README/goal-definition note |

Reviewer limitations (not defects): it could not run tests or diff against the
baseline under its read-only constraint, so assertion-relaxation was checked
statically only; hosted subagent scenarios and the native runtime-gate path
remain unexecuted as listed below.

## Known limitations

- Reviewer seat compression missed its -40% target (see above).
- `snapshot_include` is glob-based and engine-side; the controller must know
  which excluded directories actually ship with the product.
- Worktrees are detached; the tooling does not commit, branch or merge on the
  user's behalf, by design.
- The hosted end-to-end scenarios and the native runtime-gate path remain to be
  exercised on a real target before claiming the full gate works end to end.
- After installing or editing skills, OpenCode must be restarted for changes to
  take effect.
