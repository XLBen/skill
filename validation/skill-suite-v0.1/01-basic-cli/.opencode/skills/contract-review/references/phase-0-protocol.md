# Phase 0 Risk Probe Protocol

> When to read: before drafting the first-slice contract for a `grilled`,
> `light`, or `full` project.

Phase 0 is a decision-quality probe, not a miniature implementation and not a
second full test suite. Its purpose is to learn the most expensive fact early,
using the smallest safe contact with the real boundary.

## Select The Risk

Create a short ranked list of unverified assumptions. For each assumption,
record:

- `assumption_id`: the BA or risk ID;
- `statement`: what must be true;
- `invalidates`: the P, F, I, or V that becomes unusable if it is false;
- `probability`: low, medium, or high;
- `impact`: low, medium, or high;
- `cost_of_wrong`: time, money, data loss, access loss, or other concrete cost;
- `refutation`: an observable result that would prove the assumption false.

Rank by the cost of being wrong. Do not rank by convenience or by the order of
the requirements document.

## Probe Budget

Before running a probe, declare all of the following:

```yaml
probe_id: P0-<id>
assumption_id: BA-01
max_requests: 1
max_duration_minutes: 15
max_spend: "0"
cache_key: <stable-input-and-environment-key>
cache_path: docs/evidence/cache/<key>.json
backoff: "exponential; stop after the declared request budget"
side_effects: "none | described effect"
cleanup: "specific cleanup or not applicable"
stop_conditions:
  - "refutation observed"
  - "budget exhausted"
  - "unsafe or ambiguous side effect"
```

Use the smallest request/call count that can distinguish the declared
outcomes. The defaults above are guidance, not an excuse to contact a remote
service without an owner-approved limit. A higher request, duration, or spend
budget is an owner checkpoint.

Cache only observations whose inputs, relevant environment, and source
revision match the cache key. A cache hit must be recorded as a hit, including
the original observation time; it is not a new real-world validation.

For remote or rate-limited boundaries, use exponential backoff and stop when
the request budget is spent. Do not compensate for an unclear result by
repeating a full smoke suite. If the probe itself creates an unsafe side
effect, stop, inspect the postcondition, and report `blocked`.

## Probe Record

Save one record at `docs/evidence/phase-0-<id>.md`:

```markdown
# Phase 0 Probe: <assumption>

| Field | Value |
|---|---|
| Probe ID | P0-<id> |
| Assumption | BA-01 |
| Invalidates | P-01 / I-01 |
| Source revision | <brief or contract hash> |
| Environment | <safe, redacted description> |
| Budget | <requests / minutes / spend> |
| Cache | <key, hit/miss, source time> |
| Side effects | <none or declared effect> |
| Cleanup | <action or N/A> |

## Given
<specific real input and starting state>

## When
<exact command, user action, or boundary call>

## Then
<specific observable result and the assertion that distinguishes outcomes>

## Raw Observation
<relevant output, redacted but not paraphrased beyond recognition>

## Verdict
`passed` | `blocked` | `refuted` | `not-needed`

## Interpretation
<What may proceed, what must stop, and the next owner decision if any>
```

`passed` means the named assumption survived this probe; it does not mean the
whole product is complete. `refuted` means do not draft a dependent slice as if
the assumption were true. `blocked` means the evidence is unavailable or the
side effect is unsafe, not that the assumption passed. `not-needed` is only
legal for a local reversible direct change with no material external
assumption, and must name the reason.

## Handoff Gate

The contract reviewer may draft the first slice only when:

1. the highest-cost assumption has a record;
2. the record includes a raw observation and a concrete assertion;
3. the verdict is `passed` or a justified `not-needed`;
4. the first slice names the remaining assumptions it does not close; and
5. no probe budget, safety issue, or owner checkpoint is silently converted to
   approval.
