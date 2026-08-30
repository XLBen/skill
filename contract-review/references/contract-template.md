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
{ ... }
```
```

The JSON block, not duplicated prose, is the hash input and construction
contract.

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
