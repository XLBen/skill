# Workflow Repair vNext — Status And Handoff

Status: WP0–WP4 and the mechanical WP7 fixes are implemented and verified in this
working tree. WP5 (concurrency), the Godot/Blender domain work (WP6) and the
broader WP8 cleanup are scoped but **not implemented**. This file records what
was done, the evidence, and how to continue.

## Baseline (WP0)

Confirmed by reproduction before the repair (`wp0_repro.py` / `wp0_repro2.py`,
run on 2026-09-15; working tree over `a18429f`, Python 3.10.7, OpenCode 1.18.25):

| Defect | Before | After |
|---|---|---|
| `ui-gate --bind` re-labelled old passed scenarios onto changed files | pass | fail (`artifact_identity mismatch`) |
| Missing / nonexistent UI result refs | pass | fail (refs must exist and be non-empty) |
| A `bash`/unrelated call as UI native evidence | pass | fail (policy `ui_tools` or `runner_refs` required) |
| Product changed after `verify-goal` | `finish-goal` complete | blocked (`workspace binding failed`) |
| Empty runtime-policy `requirements` removed reviewer/independence floors | gate pass with zero tasks | gate fail (defaults are a floor) |
| Unrelated child session claimed as dispatch provenance | pass | fail (no matching task event) |
| Reviewer `repair` overridden by controller-written `satisfied` | pass | fail (result_ref parsed; issues/pua checked) |
| Hand-written trace accepted as native evidence | pass | fail (native provenance required) |
| Interrupted verification reservation permanently wedged | unrecoverable | recoverable (`--recover-interrupted`, or valid temp payload auto-published) |
| Doctor `--lookback-days` discarded every normal session | 0 found | 1 found (operator precedence fixed) |
| Doctor did not find the Windows session store | missing | `%LOCALAPPDATA%\opencode\opencode.db` |

Review corrections applied: a shell-driven browser runner is valid UI evidence
(it is now representable via `runner_refs`/`ui_tools` instead of being treated as
an MCP failure); SHA-256 remains useful for staleness detection and was kept —
only its claimed guarantees were reduced; `bash: allow` is documented as an agent
boundary, not a sandbox.

## Machine-enforced changes

### WP2 — Artifact/evidence binding (`scripts/check.py`)

- `workspace_snapshot(root, extra_excludes)` computes a conservative content
  snapshot; excludes VCS metadata, `.opencode/**`, workflow artifacts
  (`docs/audit-slices`, `docs/evidence`, `docs/test-manifests`,
  `docs/slice-increments`, `docs/PLAN.md`, `docs/contract.md`,
  `docs/brief*.md`, `docs/workflow-*`), caches and generated outputs.
- Every verification payload records `workspace_before`, `workspace_after`,
  `workspace_changed`. A verification whose command mutates the workspace is
  `failed` and cannot mark the outcome verified.
- `finish-goal` re-verifies `workspace_after` from each evidence file against the
  current snapshot; any later change to a non-excluded file blocks completion.
  Evidence predating the binding must be re-run.
- Interrupted reservations: a complete temp payload is validated and published;
  an incomplete one blocks with explicit `--recover-interrupted` guidance.
- Tests: `tests/test_evidence_binding.py` (7).

### WP3 — Runtime provenance and policy floors (`scripts/runtime_trace.py`, `check.py`)

- `verify_native_trace()` cross-checks a trace against the SQLite store it
  names: the source must be a readable local session store, every session must
  match the store's parent/agent rows, skill loads and tool calls must exist
  with a status matching the trace (a completed record is required when the
  trace claims completion), and every task child must match both the session
  row and a controller-session `task` part naming it. Hand-written traces,
  planted files and imported traces fail. The 3,000-event cap exports
  `truncated: true`, which also fails closed.
- Every done write/review dispatch must match a real `task` event
  (`child_session` link, completed status, requested-agent consistency);
  read-only research tasks stay provenance-optional by design. Unknown
  statuses, `failed` tasks, duplicate task IDs, and `satisfied` acceptance
  verdicts on non-done tasks fail.
- Agent matching is exact; disclosed fallback to `general`/`explore`/`scout`
  must be requested and named as such (no substring matching).
- `satisfied` reviewer verdicts require a parseable `result_ref` with `mode`,
  `issues`, `checked_scope`, `not_checked`; any issue or a `pua_acceptance`
  result other than `satisfied` overrides the claim.
- Default requirements (`task-dispatch reviewer`, `review-satisfied-goal`,
  `independence`) are a floor; policy entries extend, never empty, them.
  `allow_independence_downgrade` cannot apply to audited rigor.
- Gate sidecars always bind the goal definition hash and a policy-state
  binding (`path`/`sha256`/`gating`, `path: null` when no policy existed).
  Finish rejects a gate whose goal, trace, dispatch or policy state changed
  after it ran, including a policy created, re-scoped, or (after a passing
  gate) deleted. Deleting a policy that never produced a gate keeps the
  opt-in behavior; a recorded gate must also be removed to disable enforcement.
  Gates produced with an explicit `--policy <path>` stay enforceable because
  the recorded path is revalidated, not assumed to be the default file.
- Tests: `tests/test_runtime_evidence.py` (extended).

### WP4 — UI acceptance evidence lifecycle (`check.py`, protocol docs)

- UI applicability is declared in the goal definition (`goal.ui.required` +
  optional `outcome_ids`); deleting the sidecar or declaring
  `applicability: none` cannot drop a required obligation.
- Required scenarios must be boolean-required, cover at least one real outcome,
  cannot be `not-applicable`, and need non-empty `journey.expected`.
- Passed scenarios require `execution.session_id`, `executed_at` (with
  timezone), `target`, `build`, session-owned completed `native_call_refs`, and
  existing non-empty `observation_refs`/`result_refs`; `runner_refs` are
  required unless the policy configures `ui_tools` (globs). Native refs must
  belong to the declared session.
- `ui-gate --bind` records the identity and `bound_at` once; changed files are
  a failure until the affected scenarios are reset and re-executed. `--rebind`
  refreshes the identity only when every `passed` scenario carries an
  `executed_at` after the previous `bound_at`, so re-labelling old execution
  evidence onto a changed build stays impossible. `finish-goal` recomputes the
  identity and rejects stale assessments; policy state changes invalidate the
  gate (including a policy created after binding).
- Gate refuses non-native or truncated traces.
- Tests: `tests/test_ui_acceptance.py` (43).

### WP1 — Tiering and rule unification (docs/skills)

- Normal: no mandatory worker delegation, test-author, PUA cards or per-slice
  reviewer; goal cards only when tracking/resumption is needed. Guarded: one
  reusable review per version/scope. Audited: unchanged gates.
- Risk is judged by the actual operation (read vs modify vs credential/data vs
  irreversible write), not by topic words.
- PUA is an evidence/recovery discipline for Guarded/Audited gates and failures;
  Normal applies the same questions directly. `applies_when` in
  `stage-routing.json` marks conditional cards.
- Command wrappers and `mvp-delivery` were aligned with these tiers.

### WP7 — Installer / doctor (mechanical fixes)

- `check_runtime.py`: lookback operator fix; Windows `%LOCALAPPDATA%` discovery;
  JSONC trailing commas; deep config merge; `scout` built-in; tree-hash skill
  fingerprints with legacy fallback; `--strict` exit code 3 with
  project-scoped problems.
- `install.py`: `--commands-only` now only touches commands, leaves installed
  engine scripts and agents in place, and preserves prior manifest entries;
  stale engine deletions moved inside the rollback transaction; skill
  fingerprints cover the whole skill tree (`algorithm: tree-sha256/1`).
- Tests: `tests/test_runtime_doctor.py` (10), updated `tests/test_install.py`.

## Review follow-up

An independent read-only review of the first cut found six material holes;
all were fixed and covered by tests:

1. `--commands-only` deleted previously installed engine scripts and rewrote
   the manifest with the deleted entries — deletion is now skipped in that
   mode and tests assert the files survive.
2. Provenance accepted any 16-byte SQLite header — `verify_native_trace()`
   now cross-checks sessions/skills/tasks/tool calls against the named store.
3. `review-satisfied-goal` matched non-done reviewer tasks — the floor now
   requires `status: done`, and satisfied verdicts on non-done tasks fail.
4. The documented reset → re-execute → rebind path was impossible — `--rebind`
   now refreshes the identity only when passed scenarios were executed after
   the previous binding.
5. A policy created after the gate was not detected — every gate sidecar now
   binds the full policy state (`path`/`sha256`/`gating`, including `null`).
6. Residual Normal-tier mandates in `subagent-orchestration.md`,
   `stage-routing.json` and the grill command were aligned with WP1.

A low-severity claim (research dispatches are provenance-optional by design)
was corrected in this document instead of being enforced.

A second fresh review verified the six fixes and found five follow-ups, all
now fixed:

1. `runtime_trace.py validate` (the CLI documented in the README) still
   skipped the store cross-check — it now calls `verify_native_trace()` and a
   test asserts a planted store exits nonzero.
2. The store cross-check matched existence only — skill and tool queries now
   require `state.status = completed` in the store, and each task event must
   match a controller-session `task` part naming the child session.
3. A gate produced with an explicit `--policy` path could never satisfy
   finish — enforcement now revalidates the recorded policy path.
4. One rebind test depended on the wall clock — its fixture now uses a fixed
   past timestamp.
5. The policy-deletion sentence contradicted enforcement — the doc now states
   that deletion after a passing gate blocks until the stale gate is removed.

A third focused review verified those five and found two edge cases plus a
stale test count, now fixed:

1. The store cross-check required a completed row for every skill/tool event,
   including events the trace itself reports as failed — honest sessions with
   unrelated failed calls could never gate. Completed rows are now required
   only for events that claim completion; other events must exist and their
   status must match. Regression: `test_verify_native_trace_accepts_matching_failed_records`.
2. A gate produced with an explicit `--policy` path ignored a default policy
   created later. Enforcement now also compares the default-location binding
   when the recorded path is explicit. Regressions:
   `test_default_policy_created_after_custom_gate_blocks_finish`,
   `test_policy_deletion_after_gate_blocks_finish`,
   `test_policy_rescope_after_gate_blocks_finish`.
3. The verification block and per-file counts now match the suite (175 tests;
   `tests/test_ui_acceptance.py` has 43).

A fourth pass found one remaining edge: a skill loaded twice in one session
(failed then retried) was compared against a single arbitrary store row. The
lookup is now status-aware across all matching rows (skill and tool branches);
regressions:
`test_verify_native_trace_accepts_retry_after_failed_skill_load`,
`test_verify_native_trace_accepts_retry_after_failed_tool_call`.
A fifth verification pass returned `satisfied` for this scope.

## Verification

```powershell
python -B -m unittest discover -s tests -p "test_*.py"   # 175 tests, OK
python -B scripts/check.py --selftest                     # PASS
```

Live reproductions (before/after) were run from the artifacts described above;
the UI/product-change, empty-policy, unlinked-child and interrupted-reservation
cases now fail closed.

## Not done (next work packages)

- **WP5 — Concurrency**: remove the fixed "max 3 subagents" rule, add
  configurable limits and resource-conflict scheduling (write sets, ports,
  browser profiles, desktop session), record task start/end, and add real
  overlap tests. Current rules remain prompt-level only.
- **WP6 — Godot/Blender**: domain references and real scenarios. The current
  `computer-use` remains a generic UI acceptance capability; it does not model
  3D viewports, modal operators, keymaps or engine run states, and no native
  desktop backend has been live-tested here.
- **WP8 — Migration/cleanup**: migrate unfinished legacy goal/dispatch/UI
  artifacts, archive the stale `docs/brief.md` recovery candidate, remove
  remaining keyword-only tests, and add a real-host integration smoke.

Deliberately out of scope: building a sandbox against malicious local writers,
cryptographic identity, or a distributed scheduler.
