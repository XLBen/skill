# construction

Consumes a validated contract-review contract. The engine compiles every
reviewed I variant/segment into a stable S step, hashes immutable PLAN
structure, and keeps selections/attempts as runtime state.

Execution is a DAG, not a checkbox guess. Each attempt records side effects,
idempotency and fresh verification. Blocking CR stops ordinary work while a
restricted recovery capability remains available to recompile, rollback,
invalidate, redo, and verify the approved change.

## Key Files

- `SKILL.md`: gates, compilation, execution and completion.
- `references/plan-template.md`: generated PLAN and runtime separation.
- `references/step-protocol.md`: attempts, recovery, minimal diff and CR.
- `references/retro-protocol.md`: evidence-based learning after delivery.

Install with contract-review and repository `scripts/check.py`. Validate with:

```powershell
python scripts/check.py compile docs/contract.md docs/PLAN.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
```

After changing skill files, restart opencode.
