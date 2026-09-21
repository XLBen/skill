# Delivery Execution Details

> When to read: during `/build` or `/fix` implementation slices, before running
> tests or UI/GUI verification, or when a failure budget or evidence question
> arises. Seat: controller (workers receive only their bounded package; the
> detailed rules here stay with the integrator). Inputs: current slice card,
> dispatch record, verification commands and evidence paths.

## Prerequisites

Before implementation the controller verifies the minimum runtime
prerequisites: working directory, OS/shell, runtime and package manager,
dependencies and existing lock files, configuration variable names, services,
seed data and start method. Reuse repository conventions; do not depend on
undeclared global packages, manually prepared data or agent-private config, and
never record secret values. Installation or external access follows the
authorization boundary. When the test framework cannot run yet, arrange the
minimal authorized setup/harness change first; for Audited work it must be in
the current write set or go through CR. Missing dependencies or services are
not behavior-red; a mock must not impersonate the real boundary.

## Testing And Failure Budget

- Write one acceptance test that fails because the behavior is missing when the
  behavior is clear and automatable; tiny fixes may reuse existing tests. Do not
  force a separate manifest just for role ceremony.
- Run the narrowest relevant test, then the real smoke/demo. Tests must check
  content, state or invariants, not only exit codes, file existence or non-empty
  logs. Missing/empty/zero artifacts fail by default unless the goal declares a
  semantic zero.
- New or repaired behavior tests should reproduce the corresponding gap or
  defect; existing regressions may start green and are recorded as baseline
  passes without fabricated red. Confirm critical scenarios actually execute and
  are not skipped, filtered, empty or bypassed by a replacement script. Success
  markers only after the product assertion passes; also inspect helpers,
  fixtures, runner config and command wrappers for weakened acceptance.
- Failure counting binds the current subgoal plus normalized failure signature
  and accumulates across tasks, seats and resumes: every real execution that
  fails counts; re-reading the same recorded result, expected behavior-red,
  owner/authorization waits, or an unavailable external service do not. Three
  actual failures of the same signature with no new evidence or reduced root
  cause is a no-progress blocker: stop mechanical retries (a fresh seat is not
  retry authorization), summarize attempts/evidence and two concrete options,
  and escalate to the user.
- Before escalating, load `../pua/references/recovery-protocol.md`: the first
  failed experiment is L0, the second same-signature failure is L1 and must
  switch to a materially different method, and the third-failure no-progress
  blocker remains authoritative. PUA L2 is the evidence checklist for that
  escalation, not permission for a fourth ordinary retry.

## UI And GUI Acceptance

When affected outcomes include interface journeys, UI acceptance is a required
part of the acceptance handoff:

- `/plan` declares `goal.ui.required` (optionally `outcome_ids`) and authors the
  scenarios; the controller executes them in the
  `.opencode/mvp/<goal-slug>.ui-acceptance.json` sidecar following
  `../computer-use/references/ui-acceptance-protocol.md` (preflight,
  observe/act/verify).
- Web-only journeys load `../webapp-testing/SKILL.md` first (assertion-first
  browser automation, deterministic scripts preferred); the desktop MCP via
  `../computer-use/SKILL.md` serves native app, OS-dialog and file-picker
  boundaries, under its per-scenario hard budget. References must be real trace
  calls or existing non-empty project-relative files; without policy `ui_tools`
  record the runner output. After the artifact identity changes, re-run
  scenarios instead of re-binding old results.
- The shared desktop/browser is serialized by the controller only; subagents
  return scenario requests instead of controlling input. Missing MCP/permissions
  is reported per `../computer-use/README.md` and the scenario is `blocked` —
  never auto-install, open permissions or record missing capability as passed.
- GUI操作记录是验收证据的组成部分，可执行 outcome 断言仍需通过 goal/step
  gate；Audited human V 仍需真实 owner 决定，不能替代 goal 验证。

Web/service verification is bounded: start the instance under delivery, wait for
readiness, exercise the real client path and assert results, then clean up
processes and temporary resources even on failure/timeout. Do not treat a
long-running start command as full verification, silently reuse an unknown old
listener, or let a UI unit test stand in for interaction/navigation/result
rendering. Missing tools are reported as unverified.

## Whole-Product Observation Dispatch

Schema-2 goals with `product_observation.required: true` dispatch the
product-observer once a stable candidate exists (after implementation, engine
verification and planned UI acceptance, before review-verdict/goal-finish):

1. Controller freezes the candidate: write
   `.opencode/mvp/observation/<G-ID>/<candidate-id>/candidate.json`
   (`product-candidate/2`: entry, environment, backend, delivered-file
   manifest with hashes, test data, sensory channels, runtime state, baseline
   refs) and append the round to
   `.opencode/mvp/<goal-slug>.product-audit.json` (`product-audit/2`; legacy
   `/1` sidecars stay readable, engine writes are normalized to `/2`).
2. Generate and archive each blind phase packet
   (`workflow_packets.py observer <goal> --phase discover|compare [--model
   <provider/model>] [--preflight <file>] --out
   <candidate-dir>/<phase>.packet.json`) and dispatch a fresh
   `mvp-product-observer`. Discover packets carry NO diff/tests/acceptance
   material; the controller must not smuggle hints into the purpose text.
3. The observer returns exactly one ```json fenced block
   (`product-observation/2`) and never writes a result or workflow file. The
   controller adopts it with `observation_results.adopt_result`, which
   validates the payload, checks the controller envelope identity
   (goal_id/candidate_id/observer_session_id/model/packet_hash/attempt),
   verifies evidence refs and runtime provenance (`provenance_problems`), and
   writes the accepted result create-only to
   `<candidate>/<phase>/<run-id>/result.json`; rejections leave attempt
   records under `attempts/` and no result. Never fall back to an
   agent-written `*.result.json` — only the controller-adopted result is
   observation evidence. After discover is adopted and bound, generate the
   compare packet the same way and dispatch the second phase against
   goal/history/baselines. The reviewer's `product-observation-review/2`
   return is adopted with `observation_results.adopt_review`, which
   recomputes the discover/compare hashes from the archived results and
   rejects a payload or envelope that disagrees.
4. Dispatch is model-pinned: prefer the project plugin's `visibility_dispatch`
   host tool (it resolves the observer model from
   `.opencode/mvp/visibility.json`; a per-call `model` override is legal).
   The plugin is read at host startup, so the tool appears only after
   OpenCode is restarted; while it is not loaded, report
   `blocked`/capability-unavailable per Failure Branches or use a disclosed
   fallback — never silently inherit the session model. The legacy CLI route
   `opencode run --agent mvp-product-observer` is diagnostic only: the host
   refuses a subagent as a primary agent and silently falls back to a
   different agent (P0-1). Preflight reuse is identity-bound: a probe item
   (`host`/`model`/`candidate`/`session`) may be skipped only when the
   packet's preflight cover is `status: passed` AND every identity field it
   records matches the dispatch context
   (`observation_backend.preflight_skip_plan`); a "controller-verified" label
   alone never exempts a probe.
5. Route critical/high confirmed/intermittent findings to `/fix`; a repair
   creates a NEW candidate id (old observation rounds stay as history) and
   the new candidate must repeat a fresh, complete discover+compare round —
   same-candidate repair re-observation never reuses a partial or previous
   round. Missing backend = `blocked`, never `not-applicable`.
6. Run `check.py product-audit-gate <goal> --trace <trace>` before
   `finish-goal`; `--trace` is mandatory for required observation and the
   engine re-checks everything mechanically.

## Delegation And Ceremony

Independent test-author and reviewer dispatch follow the trigger matrix in
`subagent-orchestration.md`: substantive acceptance is capability-available-
mandatory; mechanical batch work is exempt; do not re-litigate cost. Loading a
skill is not a new identity; never fabricate session IDs, author separation or
audit evidence. Fallbacks and downgrades follow the Failure Branches.

Normal/Guarded create no `contract.md`, `PLAN.md`, ledger, review log,
observation report or ceremony ratio by default; the lightweight card is not a
process log. Follow project rules when they already require such artifacts.
Audited slices borrow the strict gates without giving up this skill's
continuous delivery control.
