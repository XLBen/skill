# Construction Plan

> When to read: while compiling PLAN.md or explaining a compiled summary to
> the owner; PLAN content itself is compiler output, never hand-written.

`docs/PLAN.md` is compiler output. Generate it; do not translate contract prose
by hand:

```powershell
python .opencode/workflow/scripts/check.py compile docs/contract.md docs/PLAN.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
```

## Step Briefs Are Execution Prompts

While authoring contract step specifications (which the compiler projects into
PLAN), follow `../../writing-plans/SKILL.md`: each step's specification must
carry Context (why, and which outcome it serves), exact Files, a Change sketch
(signatures/structures to reuse, or the investigation target when undecided),
Bounds (boundary conditions: empty/extreme input, concurrency/idempotency,
encoding, mid-failure recovery, cleanup, compatibility), the executable
Verify command with its expected assertion, and Rollback. A step spec missing
these fields produces an underspecified prompt for its executing seat —
fix the contract, not the executor's guess.

The file contains frontmatter and one `json plan` block. The engine compiles
every legal I variant and segment to `S-Ixx-variant-segment`. Unselected
variants remain `dormant`; `selected_variants` is runtime state and does not
change the structure hash.

## Structure Versus Runtime

Structure hash covers contract hash, unit DAG, variant selectors, and all step
specifications. It excludes:

- PLAN status and step state;
- selected variants;
- attempts and command output;
- timestamps;
- environment-specific execution bindings.

Concrete commands that bind a contract template to the current environment go
in an execution-binding record with environment fingerprint and binding hash.
They may not weaken V or alter actions, interfaces, side effects, or rollback.

## User Confirmation

For every interaction mode (`autonomous`, `checkpoints`, and `stepwise`), show
a generated summary containing scope,
selected/default variants, irreversible side effects, human V, and exclusions.
Include the intended user/interface, target versus verification environment,
public-interface journeys covering all promised outcomes, representative
input/output and retrieval, and repeatable setup/prerequisites and handoff.
Derive this from existing contract/PLAN fields, not a second semantic artifact;
expose missing coverage before confirmation rather than editing compiled PLAN.
Confirmation changes runtime status from `planning` to `building`; it does not
authorize semantic edits. The confirmation is always an immutable owner
decision. `autonomous` reduces step interruptions but does not authorize a
self-declared PLAN release.

Write the confirmation as a temporary JSON input; this is the only supported
way to activate a PLAN:

```json
{
  "id": "EV-PLAN-CONFIRM-01",
  "authorization": "owner-confirmed",
  "owner_event": "EV-OWNER-PLAN-01",
  "selections": {
    "I-01": {"variant": "base", "selector_evidence": "default"}
  }
}
```

First record `owner_event` as an `owner-decision` with
`decision: plan-confirmation`, `result: accepted`, and the current contract and
PLAN hashes. Every active I must then appear exactly once. Non-default variants
name a previously recorded selector evidence event instead of `default`. Run:

```powershell
python .opencode/workflow/scripts/check.py confirm-plan docs/PLAN.md selection.json --contract docs/contract.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl --require-building
```

Checkboxes may be rendered as a view, but `runtime.step_states` and the event
ledger are authoritative.

## v0.2 Slice Gate

For a new v0.2 Audited project, PLAN compilation is allowed only after contract-review has
recorded one of the following in the contract and review log:

- a passed Phase 0 record under `docs/evidence/phase-0-<id>.md`; or
- a narrowly justified `not-needed` decision for a local, reversible direct
  change with no material external assumption.

The generated PLAN represents the current thin end-to-end slice. It is an
execution projection of the whole-goal engineering design at its declared path
design, not a substitute for it. The design covers every required outcome,
components/interfaces, flow diagrams and the dependent delivery route; only
execution is sliced. Before confirmation, show the owner the declared and measured
slice budget: active P/F/I/V counts, PLAN segment count, contract non-blank
line count, and estimated product code increment. A budget exception is a
scope/value decision, not a silent compiler adjustment.

After a slice is accepted, planned expansion is compiled from an SI delta into
a new immutable package under
`docs/audit-slices/<goal-slug>/<slice-id>/`. It contains only affected work and
references the prior package's clean reconcile evidence through the goal card.
Do not edit a completed PLAN, overwrite its path, compile unaffected completed
steps into the new PLAN, or create a CR merely to add an already-planned story.
Existing CR recovery remains scoped to the typed impact closure of an actual
contract/reality mismatch.
