# CU Report: computer-use integrated as the UI acceptance gate

Date: 2026-09-14. Host: opencode 1.18.25 headless, GLM-5.3.
Target: `C:/Users/24083/AppData/Local/Temp/opencode/wp6b-target` (isolated,
outside the skill repo). Policy enabled: `runtime-policy/1` with an explicit
`{"kind": "ui-acceptance"}` requirement — both runtime-gate and ui-gate
enforce `finish-goal`.

## What was built

- `computer-use` repositioned as the **UI acceptance capability** (SKILL.md,
  README): applicability matrix, mandatory-when-applicable, blocked-not-waived.
- New protocol: `computer-use/references/ui-acceptance-protocol.md` — sidecar
  `ui-acceptance/1` (scenarios, states, evidence, reuse/invalidation).
- Routing: `stage-routing.json` gained a `ui_acceptance` block plus per-stage
  entries (design in goal-validation, execute before review-verdict and
  slice-acceptance, final recheck at goal-finish); mvp-delivery/orchestration/
  PUA cards/reviewer/build-fix-resume wrappers all wired.
- Engine: `check.py ui-gate <card> --trace <trace.json> [--bind]` validates
  scenario statuses, the executing session's completed `computer-use` load,
  native call references against trace `tool_events`, and artifact-identity
  binding (sha over bound files; `--bind` records, later runs detect drift).
  `finish-goal` enforces it whenever the sidecar exists or policy requires it.
- `runtime_trace.py` exports `tool_events` (call_id/status, context tools
  excluded) and validates `native-tool-calls` / recognizes `ui-acceptance`
  policy requirements.
- Tests: `tests/test_ui_acceptance.py` (23) + existing suites — 112/112 green,
  engine selftest PASS.

## Real end-to-end run (positive path, real browser)

Goal: Save button in `index.html` shows "Saved" on click. The headless GLM run:

1. goal card validated; implementation delegated to a real `mvp-worker`
   child session (loaded `task-worker`)
2. `verify-goal` O-01/O-02 passed with fresh evidence
3. **UI acceptance executed by the controller**: loaded `computer-use`
   (completed, controller session `ses_f603b7547ffej4QRolxw61uSYb`), drove a
   real Edge browser via puppeteer-core (`ui-acceptance.js` runner,
   observe → click → verify), evidence under `.opencode/mvp/ui-evidence/`
4. fresh `mvp-reviewer` (loaded `reviewer`+`pua`) returned `repair` with 3
   issues; 2 soft fixed, 1 hard = an engine defect it found
5. `ui-gate` PASS; `runtime-gate` PASS; `finish-goal` → G-UI-SAVE complete

Independent verification (our tools, not model self-report): 3 sessions,
computer-use completed in the controller session, worker/reviewer provenance
2/2 verified, UI-01 `passed` with a real native call ref, ui-gate 0 failures.

## Fail-closed behavior demonstrated in real conditions

Mid-run, the model hit `runtime-gate: unknown requirement kind
'ui-acceptance'` — a genuine defect in the first engine cut (chain validator
rejected the ui requirement kind). The model did NOT fake completion: it
kept every other gate green, diagnosed the stale engine copy (checked file
mtimes and the actual code path), refused `finish-goal`, and reported the
exact repair. After the repo-side fix (`ui-acceptance` recognized as
chain-neutral) and a genuine engine refresh, the continued session re-ran
runtime-gate → pass → finish-goal → complete. This is precisely the
"缺证据/坏工具必须阻塞而不是绕过" behavior the gate exists to force.

Negative matrix (deterministic tests): pending/failed/blocked required
scenarios, not-applicable without reason, applicability none without reason,
passed without session/result/native-call evidence, fabricated call refs,
missing computer-use load, changed artifact after binding, unknown outcomes,
wrong schemas, policy-requirement-without-sidecar, stale ui-gate — all block.

## Known limits (reported, not faked)

- The browser journey ran through a controller-executed puppeteer-core
  runner (serialized interactive control per protocol) because no browser
  MCP server is configured in this environment; raw MCP browser tool calls
  were not exercised. Desktop (native app) journeys remain untested here.
- Deleting the ui sidecar on a non-policy project would drop the obligation;
  full anti-deletion needs a goal-schema change (documented, out of scope).
- Engine files installed into targets are copies: mid-run engine updates
  require re-running `install.py` (the run proved detection of stale copies
  is reliable).
