# Reviewer Protocol

> When to read: only when dispatching or adjudicating a reviewer run
> (question / review / final-audit / cr-audit / converge-audit).

Dispatch the reviewer with an explicit mode, fixed contract snapshot/hash, and
output budget. The reviewer never edits artifacts or makes owner decisions.

## Modes

| Mode | Input | Output |
|---|---|---|
| scout | Active P/B, repository, existing W/E | Candidate W, gaps, primary sources |
| question | Current contract and resolved issue fingerprints | New material issues |
| review | Issue, answer, contract diff, evidence | resolved / hard / soft / owner-tradeoff / invalid |
| final-audit | Fixed contract and evidence manifest only | Structural result plus surviving semantic issues |
| cr-audit | CR, typed impact closure, candidate contract | Missing affected nodes or safe approval |
| converge-audit | `check.py reconcile` matrix, working tree, build-log | Whether the built code actually satisfies the contract intent; gaps become hard issues or CRs |

Final audit must not read debate rhetoric. After it returns, the controller
deduplicates against the event ledger by semantic fingerprint.

## Converge Audit

Run at construction Finish, after `check.py reconcile` reports `clean` or the
controller has matched every finding to a CR. The reviewer compares the
working tree and build-log against the fixed contract snapshot:

- structure questions were already settled by the engine; do not relitigate
  hashes, DAG shape, or evidence binding;
- judge only what the engine cannot: does the implemented code satisfy each
  active P's intent, does each executed V actually observe what it claims, and
  does any build-log claim overstate what the artifacts show;
- a confirmed gap is `hard` and must become a blocking CR before `done`; a
  residual non-factual risk follows the owner-decision path;
- record the audit as an event and cite the reconcile output hash fields
  (`contract_hash`, `plan_structure_hash`) so the judgment is bound to the
  exact closure matrix it audited.

## Materiality

Each issue declares one of:

- `contract-item`: affected P/T/B and F/I/V, concrete failure, smallest repair;
- `protocol-invariant`: affected HASH/STATE/CR/AUTH/COMPILER invariant,
  concrete loss of correctness or recovery, smallest repair.

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
  ]
}
```

Do not use prose-only output when the controller expects an event payload.

## Charter

A confirmed `docs/review-charter.md` is owner input, not authority
above the owner's latest explicit decision. Conflicts create T and record which
charter revision was superseded. AI suggestions never enter the charter until
the owner confirms them.
