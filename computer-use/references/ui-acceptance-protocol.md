# UI Acceptance Protocol

> When to read: when a goal/slice outcome includes a user interface journey,
> before executing UI acceptance scenarios, and before validating the UI
> acceptance sidecar. Authoritative scenario rules for `computer-use`;
> SKILL.md defines control, safety and evidence collection.

## Applicability Decision

UI applicability is declared in the goal definition (`goal.ui`), not by the
existence of a sidecar file:

- `goal.ui.required: true` means the goal's outcomes include interface
  journeys. The sidecar must declare executed scenarios, and deleting it or
  marking `applicability: none` blocks completion.
- `goal.ui.required: false` (or no `goal.ui` field) means no interface journey
  is claimed. No sidecar is required; if one exists anyway, it must still pass
  the gate. `goal.ui.outcome_ids`, when present, lists the outcomes that need
  required-scenario coverage.
- `/plan` writes the goal-level decision and designs scenarios; only
  `/build`, `/fix` and `/resume` execute them.

A missing backend, denied permission, or unreadable window produces
`blocked` — never `not-applicable`, and never a silent applicability change.
`not-applicable` is reserved for "the affected scope contains no interface
journey" with a concrete basis, and a `required: true` scenario cannot use it.

## Sidecar Schema (`ui-acceptance/1`)

Location: `.opencode/mvp/<goal-slug>.ui-acceptance.json`, maintained by the
controller next to the goal card.

```json
{
  "schema": "ui-acceptance/1",
  "goal_id": "G-NAME",
  "applicability": "declared",
  "applicability_reason": null,
  "files": ["relative/paths/bound/to/this/assessment"],
  "artifact_identity": "<filled by check.py ui-gate --bind on first binding>",
  "scenarios": [
    {
      "scenario_id": "UI-01",
      "outcome_ids": ["O-01"],
      "required": true,
      "backend": "browser",
      "journey": {
        "precondition": "start the delivered build and open the export page",
        "input": "test data with two records",
        "actions": ["open export", "choose destination", "confirm save"],
        "expected": ["success message is displayed", "file contains the two records"]
      },
      "status": "pending",
      "not_applicable_reason": null,
      "execution": {
        "session_id": "ses_...",
        "executed_at": "2026-09-15T10:00:00+00:00",
        "target": "delivered app window / URL and title",
        "build": "artifact identity or build label exercised",
        "native_call_refs": ["ses_...:call_..."],
        "runner_refs": ["ui-evidence/export-run.log"],
        "observation_refs": ["ui-evidence/export-observed.md"],
        "result_refs": ["ui-evidence/export-result.json"]
      },
      "limitations": null
    }
  ]
}
```

Field rules:

- `applicability`: `"declared"` (scenarios follow) or `"none"` (reason
  required; only legal when `goal.ui.required` is not true).
- `files`: product files whose content defines the delivered UI being
  accepted; `artifact_identity` is computed by the engine (`ui-gate --bind`)
  as sha256 over the sorted file list and their bytes.
- `scenario_id` unique; `required` must be a boolean; `outcome_ids` must
  reference real goal outcomes and be non-empty for every scenario that is
  not `not-applicable`; `journey.expected` must be a non-empty list of
  observable results.
- `status`: `pending | passed | failed | blocked | not-applicable`.
- `execution.native_call_refs`: `"session_id:call_id"` references to native
  tool calls recorded in the runtime trace. Every reference must belong to
  the declared `execution.session_id` and be completed in the trace.
- `execution.executed_at` (ISO-8601 with timezone), `target` and `build` are
  required for `passed` scenarios.
- `execution.runner_refs`, `observation_refs` and `result_refs` must resolve
  to non-empty project-relative files. `observation_refs` and `result_refs`
  are required for a `passed` scenario; `runner_refs` is required when the
  runtime policy does not declare `ui_tools` (the controller cannot otherwise
  show which runner produced the UI evidence).
- A runtime policy may declare `ui_tools` (tool-name globs such as
  `["browser_*", "playwright_*"]`). When present, at least one native call
  reference of every `passed` scenario must match a pattern; a plain shell
  receipt or unrelated tool call does not satisfy it.
- A `passed` scenario also requires a completed `computer-use` skill load in
  the executing session when a trace is supplied.

## Execution Order In The Workflow

```text
implementation done -> automated/engine verification
  -> UI applicability decided in the goal definition (scenarios designed)
  -> controller loads computer-use, executes each required scenario
     (observe -> act -> verify; one bounded journey per scenario)
  -> first ui-gate --bind records the artifact identity
  -> ACCEPTANCE_HANDOFF includes the sidecar summary
  -> fresh reviewer + PUA check UI evidence with the other acceptance items
  -> failures repaired and affected scenarios re-executed
  -> check.py ui-gate (with runtime policy) -> existing engine/owner gates
```

`/fix` reproduces through the affected interface journey before editing and
re-executes the same scenario after repair. `/resume` re-observes the current
window/app state; it never replays stale clicks or reuses observations of a
build that no longer matches `artifact_identity`.

## Reuse And Invalidation

- Same artifact identity + same scenario + same scope: a recorded `passed`
  result may be reused; do not re-execute for ceremony.
- Any change to a bound file (`files`) invalidates all scenario results for
  this assessment. `ui-gate --bind` never re-labels old results onto changed
  files: reset the affected scenarios to `pending`, re-execute them, record
  the new execution evidence, then re-run `ui-gate --bind` (which is
  idempotent when the identity has not changed).
- `finish-goal` recomputes the artifact identity and rejects a gate whose
  delivered files changed after the assessment; a changed runtime policy
  invalidates the gate as well.
- Scope growth adds scenarios; it does not silently mark them covered.
- A failed scenario blocks the acceptance handoff until repaired and
  re-executed; a blocked scenario blocks with the missing prerequisite
  named; both surface in `ui-gate` failures.

## Reviewer Duties

The independent reviewer (read-only) checks, for each scenario in the
handoff: applicability decision and reasons, version binding, whether
observed results actually satisfy `journey.expected`, whether result evidence
is content/state based rather than "clicked OK", and unresolved
failed/blocked scenarios. Missing controller-side execution can be requested
via CONTROLLER_ACTION; awaiting it is a round-trip, not a blocker. The
reviewer never operates the UI and never converts a `blocked` scenario into
`not-applicable`.

## Trust Boundary

`ui-gate` accepts only traces whose `source` is the local OpenCode session
store (native provenance) and rejects truncated exports. Hand-written or
imported traces can be inspected structurally but cannot pass the gate.
Raw tool receipts, observation files and runner logs remain acceptance
evidence for the reviewer; they are not engine verification events, not a
human owner's acceptance, and not a substitute for `verify-goal`.
