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
