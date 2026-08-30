# Construction Plan

> When to read: while compiling PLAN.md or explaining a compiled summary to
> the owner; PLAN content itself is compiler output, never hand-written.

`docs/PLAN.md` is compiler output. Generate it; do not translate contract prose
by hand:

```powershell
python scripts/check.py compile docs/contract.md docs/PLAN.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
```

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

For `checkpoints` and `stepwise`, show a generated summary containing scope,
selected/default variants, irreversible side effects, human V, and exclusions.
Confirmation changes runtime status from `planning` to `building`; it does not
authorize semantic edits. `autonomous` may skip this confirmation only when no
mandatory owner checkpoint from requirement-protocol applies.

Checkboxes may be rendered as a view, but `runtime.step_states` and the event
ledger are authoritative.
