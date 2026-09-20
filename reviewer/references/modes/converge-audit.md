# Mode: Converge Audit

> Load on demand when the dispatch mode is `converge-audit`. The shared output
> schema and materiality rules live in
> `../../../contract-review/references/reviewer-protocol.md`; this file adds the
> mode-specific judgment contract.

Run at construction Finish only after `check.py reconcile` reports `clean`.
Findings may create CRs, but open or unresolved findings block Finish. The
reviewer compares the working tree and build-log against the fixed contract
snapshot.

The passed `converge-audit` event binds the clean reconcile hash and current
PLAN runtime revision in addition to contract/PLAN hashes. An audit recorded
before the final step projection cannot authorize Finish. Copy
`reconcile_hash` and `plan_revision` from the latest clean `check.py reconcile`
JSON output into the audit event; do not calculate them manually.

- structure questions were already settled by the engine; do not relitigate
  hashes, DAG shape, or evidence binding;
- judge only what the engine cannot: does the implemented code satisfy each
  active P's intent, does each executed V actually observe what it claims, and
  does any build-log claim overstate what the artifacts show;
- inspect the final integrated state, not only changed units or demo labels.
  Require actual public-interface journeys covering every promised user-facing
  outcome in the current slice and affected existing journeys, from representative
  input to useful output and retrieval; only this slice audit does not demand
  deferred future slices. This exemption never applies to whole-goal finish. Shared
  scenarios and CLI/library interfaces are valid. Check repeatable delivered
  setup and declared dependencies replayed in isolation from delivered artifacts
  (not borrowed global packages), target versus verification environment, and
  created/updated README or quickstart. Missing prerequisites or untested target conditions
  must remain explicit gaps, not readiness claims;
- a confirmed gap is `hard` and must become a blocking CR before `done`; a
  residual non-factual risk follows the owner-decision path;
- a v0.2 acceptance is not sufficient when it reports only exit 0, accepts an
  empty required result, lacks a concrete Given/When/Then assertion, or has no
  traceable test-author/frozen-hash record;
- check every subprocess status, pre-operation snapshots of all relevant inputs,
  result contents and repeated-run stability. For data-copy risks, require
  applicable same-name/different-content, partial I/O failure and source/destination
  overlap tests; an unchanged filename set proves neither no writes nor correct
  incremental behavior. Inspect a few safe isolated fault-injection results showing
  critical assertions can fail; keep domain cases in product tests, not the engine;
- a third consecutive attempt with the same normalized failure signature is a
  circuit-break event. The fourth ordinary retry is not allowed; the audit
  checks the escalation payload and at least two costed options;
- normal planned growth is an SI, not a CR. A proposed SI before current-slice
  acceptance is a hard process issue;
- record the audit as an event and cite the reconcile output hash fields
  (`contract_hash`, `plan_structure_hash`) so the judgment is bound to the
  exact closure matrix it audited.

## Whole-Goal Boundary

A clean reconcile and passed slice `converge-audit` close only that slice. Before
`finish-goal`, mvp-delivery remains responsible for comparing the original request
or brief (every BS), the whole goal, deferred work and real public-entry journeys
with the final integrated product. Reuse this reviewer capability for the broader
scope check with those inputs and report concrete findings; do not invent a new
mode, public command, role or event schema, or bind a whole-goal claim to a slice
audit event. Required BS items must remain outcome dispositions, not hidden in
deferred or other dispositions. Record missing implementation separately from
missing verification; required original-boundary outcomes stay pending/blocked
and prevent complete. Samples/mocks cannot replace required device/API behavior.
Scope changes require explicit renewed confirmation and respect frozen packages.
Coverage IDs and boolean markers provide structure, not automatic semantic proof;
Audited approval does not discharge the controller's whole-goal responsibility.
