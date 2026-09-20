# Risk-To-Test Technique Matrix

> When to read: when the frozen specification's risks are not fully covered by
> example-based acceptance tests, or when a Guarded slice has a verification
> blind spot. Risk-triggered: use only the rows that match the slice's actual
> risk profile.

The matrix selects test *techniques*; it never adds product requirements.
Every added technique must map to an existing scenario or acceptance item,
and its failure must be observable in the same evidence trail (same manifest,
same protected paths, same pre-change classification).

| Risk | Technique | Minimal shape |
|---|---|---|
| Serialization / transformation invariants | property-based | round-trip and idempotence properties on generated inputs |
| Untrusted or malformed input | fuzz / boundary | parser rejects or normalizes without crashing; error paths asserted |
| Interface or schema change | contract testing | consumer expectation checked against the produced artifact |
| Capacity or latency promises | load / soak | representative load with a stated threshold and stop condition |
| Failure and recovery paths | fault injection | kill/timeout/partial-write case asserted to recover or fail cleanly |
| Concurrency / reentrancy | interleaving | repeated and concurrent execution keeps the stated invariant |
| Data integrity / migration | reconciliation | pre/post row and checksum comparison, forward and rollback paths |
| Accessibility promises | accessibility scan | automated check plus one manual journey assertion |
| Compatibility surface | matrix testing | declared platform/version pairs exercised at least once |
| Security boundary | negative-path testing | unauthorized request is denied and audited |

Rules:

- Technique selection happens before implementation and is frozen in the
  manifest like any other acceptance decision.
- Do not require every row; justify the selected rows and record the excluded
  ones as untested limitations when they are material.
- Execution thresholds and scanners belong to deterministic runners; the
  manifest records the command, the assertion and the boundary policy.
- A technique that cannot fail on the claimed defect is not evidence; keep a
  safe fault-injection sample for the critical assertions.
