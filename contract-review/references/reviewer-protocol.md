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
returns the normal structured `issues` plus the `pua_acceptance` object —
required whenever `pua_stage_id` was supplied, with a matching `stage_id`;
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

Load exactly one mode file when the dispatched mode has one; the shared output
schema, materiality and evidence rules in this file still apply:

- `final-audit`: `../../reviewer/references/modes/final-audit.md`
- `converge-audit`: `../../reviewer/references/modes/converge-audit.md`

Final audit must not read debate rhetoric. After it returns, the controller
deduplicates against the event ledger by semantic fingerprint.

## Converge Audit

Loaded on demand: see `../../reviewer/references/modes/converge-audit.md`
(mode-specific judgment contract, including the whole-goal boundary). The
dispatch is only valid after `check.py reconcile` reports `clean`; the passed
audit event binds the reconcile hash and current PLAN revision.

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
  "mode": "review",
  "contract_hash": "...",
  "checked_scope": ["what was actually inspected"],
  "not_checked": ["declared gaps, or none"],
  "issues": [
    {
      "id": "ISSUE-01",
      "fingerprint": "stable semantic key",
      "classification": "hard | soft | owner-tradeoff",
      "scope": "contract-item",
      "affected": ["P-01", "F-01", "I-01", "V-01"],
      "failure": "observable consequence",
      "evidence": ["path or command reference"],
      "evidence_needed": [],
      "smallest_repair": "contract change"
    }
  ],
  "resolved": [
    {
      "issue_id": "ISSUE-00",
      "fingerprint": "original semantic key",
      "disposition": "resolved",
      "basis": "evidence reference"
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

Field contract:

- Every review-mode issue carries `classification` (`hard`, `soft`, or
  `owner-tradeoff`) plus its `evidence`; the controller maps this JSON to the
  existing audit events and may not relabel a classification (see
  `verdict-rules.md`).
- A previously raised issue that the answer or new evidence settles goes to
  `resolved` with `disposition: resolved | invalid` and the original
  `issue_id`/`fingerprint` — it is not silently dropped.
- `checked_scope` and `not_checked` are required so an empty `issues` list
  distinguishes "fully inspected, no findings" from "could not inspect". A
  return missing `mode`, `issues`, `checked_scope`, `not_checked`, or a review
  issue's `classification` is needs_context; the controller never infers a pass
  from a malformed or empty return.
- `pua_acceptance` is required when the dispatch supplied `pua_stage_id`, and
  its `stage_id` must equal the supplied one. Empty `issues` alone never passes:
  the controller also checks `not_checked` for material gaps and the
  `pua_acceptance` result before continuing.

Do not use prose-only output when the controller expects an event payload.
When no PUA acceptance handoff was supplied, omit `pua_acceptance` rather than
inventing a stage result.

Envelope mapping: the reviewer JSON is the structured rendering of the
`TASK_RESULT` envelope (`../../mvp-delivery/references/subagent-templates.md`).
It carries `task_id` and `attempt` at top level; `not_checked` is the envelope's
`not_verified`, `issues` is its `issues`, and `checked_scope` is the evidence
scope. `status` is `completed` when the declared scope was fully inspected,
`waiting_controller` when evidence is still pending a CONTROLLER_ACTION, and
`blocked` when an independence or resource prerequisite is missing. `mode`,
`contract_hash`, `resolved` and `pua_acceptance` remain reviewer-specific
payload. Legacy reviewer JSON without envelope fields stays valid and is read
as legacy; controller-action requests inside a review carry the same stable
`action_id` and are deduplicated through the dispatch record's `actions` state.

For contract-bound modes, include `contract_hash` and the applicable contract IDs.
For a Normal/Guarded acceptance handoff without a contract, omit `contract_hash`,
use `scope: acceptance-item`, and bind `affected` to a handoff claim, artifact
identity or user-entry path. This reuses the existing `review` output and does
not create a new mode or event schema.

For the final stable slice, one fresh dispatch may request both scopes in one
return: `verdicts: {"slice_converge": "<verdict>", "whole_goal": "<verdict>"}`,
each with its own checked scope and evidence. Two verdicts in one return are
two separate judgements: a slice convergence verdict never satisfies the
whole-goal gate, and the controller checks each verdict against its own gate.

## Charter

A confirmed `docs/review-charter.md` is owner input, not authority
above the owner's latest explicit decision. Conflicts create T and record which
charter revision was superseded. AI suggestions never enter the charter until
the owner confirms them.
