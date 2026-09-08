# Architecture Decision Record

Use an ADR only for a durable architecture or operational choice. Do not
create an ADR for every implementation step or duplicate the full contract.
Store it at `docs/adr/ADR-<nnn>-<slug>.md`.

```markdown
# ADR-<nnn>: <decision title>

- Status: proposed | accepted | superseded | rejected
- Date: <YYYY-MM-DD>
- Owner decision event: <event ID or pending>
- Related contract/SI: <hash or ID>

## Context
<The problem and the evidence that makes a decision necessary.>

## Decision
<The selected option, stated in observable terms.>

## Alternatives Considered
- <option>: <why rejected or deferred>

## Consequences
- Positive: <consequence>
- Negative/risk: <consequence and mitigation>

## Verification
- Given: <specific context>
- When: <decision is exercised>
- Then: <observable result>
```

The decision remains subordinate to the latest explicit owner decision. A
changed architecture opens a new ADR or supersedes the old one; do not edit a
historical accepted ADR in place.
