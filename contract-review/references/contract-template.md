# Contract Template

> When to read: while drafting or revising `docs/contract.md` only.

Create `docs/contract.md` as a readable explanation plus one authoritative JSON
contract block. Read `contract-schema.md` first and use
`tests/fixtures/contract-valid.md` as the complete executable example.

## Frontmatter

```yaml
---
project: <name>
status: draft
phase: intake
profile: light
cycle: 0
revision: 0
contract-hash: <empty until passed/conditional>
last-event-id: <empty>
presented-t-id: <empty>
date: <YYYY-MM-DD>
---
```

State changes go through the event engine. Do not use frontmatter as an
independent second state source.

## Explanatory View

Keep prose short and generated from the contract where possible:

```markdown
# <project> contract

## Outcome And Scope
P and B summary.

## Owner Decisions
T summary and pending queue.

## Runtime Flow
F graph summary, including failure terminals.

## Implementation Contract
I/W/D summary and variant boundaries.

## Evidence, Assumptions, And Risk
E/A/R summary.

## Verification
V summary.

## Contract
```json contract
{
  "intake": {
    "mode": "direct"
  },
  "profile": "light",
  "control": { ... },
  "nodes": { ... }
}
```
```

The JSON block, not duplicated prose, is the hash input and construction
contract.

`intake` is mandatory. Use `{"mode":"direct"}` only when the request was
already ready for review. A grilled intake is canonical and hash-bound:

```json
{
  "mode": "grilled",
  "brief_path": "brief.md",
  "brief_hash": "<requirement-brief hash>",
  "dispositions": [
    {"brief_id": "BS-01", "status": "consumed", "contract_ids": ["P-01", "V-01"]}
  ]
}
```

The path is relative to `docs/contract.md`. Every brief item appears exactly
once as `consumed`, `deferred`, or `rejected`; the latter two require a reason.

## Minimum By Profile

All profiles require P/F/I/V/B coverage. D/A/R/W/E/T arrays may be empty when
irrelevant; do not create placeholder nodes merely to look complete.

- `direct`: local reversible change, no unresolved owner trade-off, one
  structural validation. Upgrade on design dispute.
- `light`: one independent semantic audit; research and prototypes only for a
  material dispute.
- `full`: scouting, repeated adversarial review, and clean final audit.

## Migration

Existing prose is not automatically a machine-readable contract. Preserve the
original document, build explicit P/F/I/V/B nodes and relevant D/A/R/W/E/T,
run the engine, then perform the profile's semantic audit.
