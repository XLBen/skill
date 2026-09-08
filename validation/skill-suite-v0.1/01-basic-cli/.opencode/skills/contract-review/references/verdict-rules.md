# Verdict And Recovery

> When to read: when adjudicating reviewer issues into
> hard / soft / owner-tradeoff / invalid.

## Final Issue Set

For each issue apply materiality, evidence honesty, and semantic deduplication.
Persist accepted and filtered issues with fingerprint and reason. The only
blocking set is the surviving set after all three filters.

- `hard`: factual contradiction, lost active P, incomplete flow/implementation,
  unsafe recovery, or non-executable acceptance. Must be repaired.
- `owner-tradeoff`: real value/scope choice. Create T and enter
  `awaiting-owner`.
- `soft`: bounded non-factual residual risk that leaves the contract complete.
  It may support conditional only with applied T and additional V.
- `invalid`: no material impact, repeated without new evidence, or conflicts
  with stronger evidence.

The contractor cannot relabel reviewer output. A disagreement is resolved by new
evidence, independent review, or owner value decision; factual uncertainty is
never silently downgraded.

## Stop And Progress

Pass only when the structural engine succeeds, no pending T remains, and a
clean final audit has an empty surviving set. There is no round cap that grants
approval.

Track whether each cycle closed, escalated, or materially advanced an issue.
Two cycles with no progress enter `suspended`. Budget exhaustion enters
`awaiting-owner` or `suspended`. Both are resumable and neither is approval.

## State Recovery

State projection and event ledger are authoritative. On resume:

1. Compare projection revision with ledger events.
2. Replay unapplied events by stable ID.
3. Reject stale concurrent writes.
4. Resume the persisted phase/request ledger; do not redispatch a recorded
   response.
5. Revalidate contract hash before final audit or construction handoff.

`blocked` exits through new evidence or re-review. `awaiting-owner` exits only
through an answer event for the currently presented T. `suspended` resumes at
its saved phase after owner control or resource availability.

## CR

Read CR state only from `docs/change-orders.md`. Recompute typed dependent
closure and run `cr-audit`; do not limit analysis to the originally named
chapter. After approval, construction uses its dedicated recovery capability.
Rejected and waived CR still require complete evidence chains before close.

## SI

Use an SI for planned expansion only after the current slice has passed real
verification and owner acceptance. An SI uses an ADDED/MODIFIED/REMOVED delta,
declares its affected closure and budget, and does not replay unaffected work.
Do not use SI to bypass a failed V, a refuted fact, an incompatible interface,
or an unsafe side effect; those remain hard CR findings.

## v0.1 Verification Findings

The following are hard findings for a new v0.1 slice, not optional style:

- a V that asserts only exit 0 or accepts a missing/empty required result;
- a missing concrete Given/When/Then scenario or output/state assertion;
- a missing Phase 0 record when a material external assumption exists;
- a third identical failure followed by a fourth ordinary retry or an
  escalation without the required evidence payload;
- identical test-author and implementation-author IDs, or a changed frozen
  test hash without CR and a new red run;
- a first-slice budget exceeded without a pre-recorded owner exception.

## Conditional

Conditional cannot contain a hard issue, pending owner choice, missing field,
refuted assumption, or unexecutable V. It lists exact owner decision events,
residual R IDs, and executed additional V evidence. Facts and destructive
safety failures are not waivable.
