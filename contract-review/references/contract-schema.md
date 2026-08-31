# Contract And Engine Protocol

> When to read: before drafting or editing the contract JSON, and whenever
> HASH/STATE/CR/COMPILER rules are cited.

This file is the normative protocol for `grill`, `contract-review`, and `construction`.
`scripts/check.py` and its fixtures are the executable definition when prose
and implementation disagree.

## Authority

1. Canonical JSON, engine checks, and fixtures.
2. This protocol and the requirement/evidence protocols.
3. Skill orchestration text.
4. Explanatory README and design documents.

The engine decides deterministic structure only. Reviewer audits decide
whether natural-language conditions are actually mutually exclusive, an
interface is genuinely equivalent, or a rollback is operationally sound.

## Contract Container

`docs/contract.md` contains flat frontmatter and exactly one fenced block:

````markdown
```json contract
{ "intake": { "mode": "direct" }, "profile": "light", "control": { ... }, "nodes": { ... } }
```
````

Use `tests/fixtures/contract-valid.md` as the runnable complete example. Every
node has this common envelope:

```json
{
  "id": "P-01",
  "status": "active",
  "supersedes": [],
  "superseded_by": [],
  "scope": "local"
}
```

Supported node groups are `P/T/W/F/I/D/E/A/R/V/B`. IDs are stable and never
reused. Replacement edges must be bidirectional. Inactive nodes remain for
audit history but do not satisfy current coverage.

`intake.mode` is mandatory. `direct` means the input was already specific
enough for review. `grilled` binds `brief_path`, `brief_hash`, and a disposition
for every typed item in the final brief. The path is relative to the contract
file and must not escape its directory. Consumed items cite concrete contract
IDs; deferred or rejected items carry a reason. Missing coverage blocks
contract release.

## User Control

The contract records:

```json
{
  "profile": "direct | light | full",
  "control": {
    "interaction": "autonomous | checkpoints | stepwise",
    "audit_budget": 2,
    "research_budget": 1,
    "prototype_budget": 1
  }
}
```

`direct` is for local reversible work, `light` for a bounded feature, and
`full` for cross-module or high-risk work. Quality gates stay intact; smaller
profiles omit irrelevant nodes and avoid speculative research. Budget
exhaustion moves to `suspended` or `awaiting-owner`; it never converts an
unresolved issue into `passed`.

Regardless of interaction mode, ask the owner before adding requirements,
expanding scope, incurring cost, exposing private data, or causing an
irreversible external side effect.

## Hashes

The contract hash is SHA-256 over:

```text
"review-contract" + NUL + canonical-json(contract)
```

Canonical JSON is UTF-8, sorted object keys, no insignificant whitespace,
JSON booleans/null, ordered arrays, and no NaN/Infinity. `contract_hash` is
excluded from the projection. Referenced evidence requires `bundle_hash`,
computed with domain `evidence-bundle` over the evidence node excluding
that field.

Requirement brief hashes use domain `requirement-brief` over the authoritative
`json brief` block. A grilled contract stores that hash inside canonical
`intake`, so the brief is transitively bound into the contract and PLAN hashes.
`check.py contract` automatically loads and verifies the referenced brief; the
check cannot be bypassed by omitting a CLI flag.

JSON integers and floating-point values are intentionally distinct (`1` is not
`1.0`); schema-defined counts use integers. This avoids implementation-specific
numeric coercion in the current hash profile.

The plan structure hash uses domain `construction-plan` and covers the
contract hash, unit DAG, all variant steps, and selectors. Runtime
state, selected variants, attempts, and environment bindings are excluded.

## Graph Rules

- Every active P is served by F and covered by V.
- Every active F is realized by a build I.
- I dependencies form an acyclic unit DAG.
- Each I variant has an acyclic segment DAG.
- Build and S0 segments hold only local V.
- Integration, end-to-end, and human V belong to validation I.
- Every fallback W appears in an equivalent variant of each affected I.
- The compiler emits every legal variant as `S-Ixx-variant-segment`; dormant
  variants remain in PLAN and runtime selects exactly one per active I.

`selected-when` prose is explanatory only. Runtime selection requires a
structured selector and evidence event.

## Verification Nodes

Automated V carries the exact acceptance `command`. It may additionally carry
`red_command`: the same observable behavior expressed as a test that fails
before implementation. When `red_command` exists, construction runs red first
and records `tdd-red`/`tdd-green` evidence events bound to the current hashes
(see step-protocol). `red_command` is valid only on non-human V and is
optional; a V without it never requires TDD ceremony.

## State And Events

The authoritative event ledger is append-only JSONL. `workflow-state.json` is
an atomic projection with `revision`, status, phase, and applied event IDs.
Writers supply `expected-revision`; stale writes fail instead of overwriting
another session. Append the event and fsync it before atomically replacing the
projection. Replaying an existing event ID is idempotent.

`passed`/`conditional` are release proofs, not editable labels. Their workflow
transition names the exact contract hash and a passed `final-audit` event; the
engine replays the ledger from draft and compares `workflow-state.json` before
compile. A conditional release additionally binds an accepted owner decision,
active residual R IDs, and passed `release-verification` events for its V IDs.

Supported contract statuses include `draft`, `reviewing`, `awaiting-owner`,
`blocked`, `suspended`, `re-reviewing`, `passed`, and `conditional`.
`conditional` requires a structurally valid contract and only owner-signed,
non-factual residual risks with executed additional verification.

## CR Recovery

Normal construction is blocked by `proposed`, `reviewing`, `approved`,
`applying`, or `verifying`. A dedicated `cr-recovery` capability remains
available and may perform only the affected recompile, invalidation, rollback,
redo, and additional V:

```text
proposed -> reviewing -> approved -> applying -> verifying -> verified -> closed
                       -> rejected -------------------------------------> closed
                       -> waived-pending-verification -> waived-verified -> closed
```

There is no user override for a refuted fact, destructive safety failure, or
missing acceptance criterion.

## Commands

```powershell
python .opencode/workflow/scripts/check.py brief docs/brief.md
python .opencode/workflow/scripts/check.py contract docs/contract.md
python .opencode/workflow/scripts/check.py init docs/contract.md docs/workflow-state.json
python .opencode/workflow/scripts/check.py compile docs/contract.md docs/PLAN.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py confirm-plan docs/PLAN.md selection.json --contract docs/contract.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py plan-event docs/PLAN.md event.json --contract docs/contract.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py finish-plan docs/PLAN.md finish-event.json --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py reconcile docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py impact docs/contract.md A-01
python .opencode/workflow/scripts/check.py event docs/workflow-state.json docs/workflow-events.jsonl event.json --expected-revision 3
python .opencode/workflow/scripts/check.py release docs/contract.md docs/workflow-state.json docs/workflow-events.jsonl release-event.json --expected-revision 3
python .opencode/workflow/scripts/check.py record docs/workflow-events.jsonl verification-event.json
python .opencode/workflow/scripts/check.py cr-event docs/change-orders.md docs/workflow-events.jsonl event.json --contract docs/contract.md --expected-revision 3 --capability cr-recovery
python .opencode/workflow/scripts/check.py --selftest
```

Do not hand-edit compiled PLAN structure. Runtime fields may change through the
engine; semantic changes return to contract-review through CR.

Variant-selection, attempt, and step-verification events bind the current
contract hash, plan-structure hash, and canonical step hash. `tdd-red` and
`tdd-green` events bind the same triple and record the failing/passing run of
`red_command`; a red event must carry `result: failed`, a green event
`result: passed`. Attempt events from isolated step-executor dispatch carry the
executor's `subagent_id`. Evidence from an older plan cannot complete a
recompiled step. CR recovery compilation and plan validation also require
`--previous-contract`; contract-node and PLAN-structure diffs must remain
inside that CR's typed impact closure.
