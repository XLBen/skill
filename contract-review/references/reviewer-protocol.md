# Reviewer Protocol

> When to read: before every reviewer dispatch and when adjudicating a run
> (scout / question / review / final-audit / cr-audit / converge-audit).

Dispatch a fresh reviewer subagent (prefer the installed `mvp-reviewer`
project agent; run the dispatch preflight and follow the failure branches in
`../../mvp-delivery/references/subagent-orchestration.md`), then have it load
the `reviewer` skill (skill tool, `name: reviewer`). Supply an explicit mode,
fixed contract snapshot/hash when the mode is contract-bound, or the artifact
identity from the full handoff for a Normal/Guarded acceptance review without
a contract, and an output budget. Loading a skill in the controller is not
dispatch or independence; if no fresh subagent is available, use a real separate
session with recorded provenance or block Audited release.
For v0.2 (and existing v0.1) first-slice and construction audits, also pass the
Phase 0 record, slice-budget report, test-author manifest, and implementation
diff when they exist. The reviewer never edits artifacts or makes owner
decisions.

When the dispatch is an acceptance handoff, also pass the complete
`ACCEPTANCE_HANDOFF` and `pua_stage_id`. The handoff includes the original goal,
claims, acceptance gate, artifact identity, evidence, known gaps, owner decisions
and real user entry. The short ADHD preview is only a user-facing view and never
replaces this input. The reviewer loads `pua`, reads the matching stage card and
returns the normal structured `issues` plus the optional `pua_acceptance` object;
the controller owns repair, revalidation and the final user-facing result.

## Modes

| Mode | Input | Output |
|---|---|---|
| scout | Active P/B, repository, existing W/E | Candidate W, gaps, primary sources |
| question | Current contract and resolved issue fingerprints | New material issues |
| review | Issue, answer, contract diff, evidence, or mvp acceptance handoff | resolved / hard / soft / owner-tradeoff / invalid |
| final-audit | Fixed contract and evidence manifest only | Structural result plus surviving semantic issues |
| cr-audit | CR, typed impact closure, candidate contract | Missing affected nodes or safe approval |
| converge-audit | `check.py reconcile` matrix, working tree, build-log | Whether the built code actually satisfies the contract intent; gaps become hard issues or CRs |

Final audit must not read debate rhetoric. After it returns, the controller
deduplicates against the event ledger by semantic fingerprint.

## Converge Audit

Run at construction Finish only after `check.py reconcile` reports `clean`.
Findings may create CRs, but open or unresolved findings block Finish. The reviewer compares the
working tree and build-log against the fixed contract snapshot:

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

### Whole-Goal Boundary

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

## Materiality

Each issue declares one of:

- `contract-item`: affected P/T/B and F/I/V, concrete failure, smallest repair;
- `protocol-invariant`: affected HASH/STATE/CR/AUTH/COMPILER invariant,
  concrete loss of correctness or recovery, smallest repair.
- `acceptance-item`: no-contract Normal/Guarded handoff claim, artifact identity,
  user-entry path or evidence binding, concrete failure and smallest repair.

Reject preference, style, speculative future architecture, repeated resolved
issues without stronger evidence, and objections that weaken confirmed owner
requirements. Any positive number of surviving issues is valid; never invent a
second issue to make a round look substantial.

## Evidence Honesty

An issue conflicting with stronger primary evidence is invalid unless it
provides stronger counter-evidence. Observable disputes become a falsifiable
experiment within the contract budget. An unavailable resource produces a
blocked/suspended result, not a guessed verdict.

## Output

```json
{
  "mode": "question",
  "contract_hash": "...",
  "issues": [
    {
      "id": "ISSUE-01",
      "fingerprint": "stable semantic key",
      "scope": "contract-item",
      "affected": ["P-01", "F-01", "I-01", "V-01"],
      "failure": "observable consequence",
      "evidence_needed": [],
      "smallest_repair": "contract change"
    }
  ],
  "pua_acceptance": {
    "stage_id": "review-verdict",
    "result": "satisfied|repair|owner|blocked",
    "scope": "checked scope",
    "evidence": ["path or command reference"],
    "gaps": ["material gap or none"],
    "next": "one controller action"
  }
}
```

Do not use prose-only output when the controller expects an event payload.
When no PUA acceptance handoff was supplied, omit `pua_acceptance` rather than
inventing a stage result.

For contract-bound modes, include `contract_hash` and the applicable contract IDs.
For a Normal/Guarded acceptance handoff without a contract, omit `contract_hash`,
use `scope: acceptance-item`, and bind `affected` to a handoff claim, artifact
identity or user-entry path. This reuses the existing `review` output and does
not create a new mode or event schema.

## Charter

A confirmed `docs/review-charter.md` is owner input, not authority
above the owner's latest explicit decision. Conflicts create T and record which
charter revision was superseded. AI suggestions never enter the charter until
the owner confirms them.
