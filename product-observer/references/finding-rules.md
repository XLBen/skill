# Finding Rules

> When to read: while recording any observation finding, while triaging
> findings into the repair loop, and while reviewing observation evidence.
> Severity ladder and categories are adopted verbatim from
> `../upstream/issue-taxonomy.md`; the deltas below are local rules.

## Finding Format

Every finding must contain (v2 fields per
`result-contract.md` §3.4 — unknown fields are rejected):

```text
id                     F-NNN, unique within the round
surface_ids            references to product-map surface ids
severity               critical | high | medium | low
category               visual | functional | ux | content | performance | console | accessibility
                       | continuity   (local addition: cross-mode/cross-state consistency)
confidence             observed | likely | uncertain
observed               what the observer actually saw (facts only)
expected_basis         why this is wrong: public docs, original goal, the product's
                       own feedback elsewhere, historical behavior, or an internal
                       state contradiction
reproduction           replayable action transcript / script reference / numbered
                       steps tied to evidence files
evidence_refs          required and non-empty; real files under the candidate
                       evidence directory: every ref is a relative path that
                       exists there (no absolute paths, no "..", no fabricated
                       names)
status                 suspected | confirmed | intermittent | resolved | dismissed | owner-decision
difference_classification  compare only, REQUIRED there and forbidden in discover:
                       intended-change | confirmed-defect | known-old-issue
                       | under-investigation | owner-decision
dismissal_reason       non-empty when status == dismissed
owner_decision_ref     non-empty string when present; required to dismiss or to
                       justify an intended-change at critical/high
resolution_ref         required when resolved: {candidate_id, finding_id}, binding
                       the fix to a historical verified round
notes                  optional non-empty string
```

`expected_basis` is mandatory. "Feels ugly" is not a finding basis; a real
basis names where the expectation comes from. Aesthetic preferences belong
in `low` severity with an explicit preference note, never `critical/high`.
Evidence refs that do not exist on disk are rejected by the gate; a claim
with no real evidence file is not a finding, it is an assertion.

## Severity To Blocking

- `critical` / `high` findings with status `suspected`, `confirmed`,
  `intermittent` or `owner-decision` **block** `finish-goal` (engine-enforced).
- `medium` / `low` are recorded and reported; they do not block by default
  (an owner may escalate per project).
- A `critical`/`high` finding closed as `dismissed` does not block
  mechanically, but the dismissal is only valid with evidence and — for
  these severities — a cited owner decision (see Status Rules and Authority
  Order); the semantic gate rejects a dismissal justified only by README or
  implementer claims.
- Blocking may rely on solid runtime evidence alone (repro + captures).
  Writing an automated regression test is the preferred permanent fix, but
  is NOT a precondition for blocking — an obvious severe problem is not
  downgraded because it is hard to assert automatically.

## Status Rules

- `suspected`: observed once, evidence captured, not yet re-verified.
- `confirmed`: reproduced from a clean state, or the evidence is
  unambiguous (e.g. console exception tied to the action).
- `intermittent`: failed to reproduce on retry but was genuinely observed
  with evidence. **Never discarded** (delta from upstream); critical/high
  intermittent findings keep blocking until investigated.
- `resolved`: a later round on a NEW candidate verified the fix; resolution
  binds to the verifying round's result — `resolution_ref` must name the
  historical `candidate_id` (never the current candidate) and a
  `finding_id` that exists in that round, plus non-empty `evidence_refs` —
  never to an implementer claim. The engine confirms the structure; the
  cross-round binding is the gate's job.
- `dismissed`: requires a non-empty `dismissal_reason` plus either evidence
  or an `owner_decision_ref` (e.g. environment artifact reproduced absent).
  A `critical`/`high` dismissal ALSO requires a non-empty
  `owner_decision_ref`: an implementer's "works as intended", a README
  statement, or an in-code comment cannot dismiss a blocking-severity
  finding.
- `owner-decision`: genuine product-choice fork; surfaced to the owner,
  not silently closed. **Blocking is preserved** until the owner decides —
  `owner-decision` stays in the blocking set (engine-enforced).

## Difference Classification (compare only)

`difference_classification` is required in `compare` and forbidden in
`discover`. It records what a difference IS relative to the approved goal and
history; `status` records where the finding sits in its handling lifecycle.
They are independent: a `resolved` finding can be a `confirmed-defect` (a
fixed defect), and a `dismissed` finding can be an `intended-change`.

| classification | meaning |
|---|---|
| `intended-change` | The difference matches an explicitly approved change. |
| `confirmed-defect` | The difference contradicts the approved goal or promised behavior. |
| `known-old-issue` | The difference predates this candidate and is already tracked; needs non-empty `evidence_refs`. |
| `under-investigation` | Observed, not yet diagnosed; keeps its finding status and severity. |
| `owner-decision` | The difference exists because of, or requires, an owner choice; needs `notes` or a non-empty `owner_decision_ref`. |

A `critical`/`high` finding classified `intended-change` must cite a non-empty
`owner_decision_ref`; until then it cannot pass the gate as "just intended".

## Authority Order

When `expected_basis`, a dismissal, or an intended-change claim is checked,
the authority order is:

1. the approved goal and explicit owner decisions (`owner_decision_ref`);
2. the candidate's own README / user-facing documentation claims;
3. historical behavior and legacy versions of the product.

Historical behavior is diagnostic evidence, never an authority. README or
implementer statements cannot downgrade, waive or reinterpret an approved-goal
promise; they can explain a difference only once an owner decision is cited.
For `critical`/`high` findings the engine enforces this: `dismissed` and
`intended-change` require a non-empty `owner_decision_ref`, and README or
implementer prose alone is rejected.

## Discovery Discipline (from upstream, unchanged)

- Repro-first: interactive issues get stepwise screenshots (+ video when
  ffmpeg is available; otherwise screenshot sequences + trace), static
  issues get one annotated screenshot.
- Record findings incrementally; never delete evidence mid-session.
- Check console/errors/network at each material surface — silent failures
  live there.
- Never read the target product's source code.

## Local Deltas

1. No issue-count quota (upstream "find 5-10 then stop" removed). Stop on
   coverage + unresolved findings.
2. Intermittent findings retained (upstream discards non-reproducible).
3. Findings feed `/fix`, re-observation on the new candidate, and the
   reviewer's `findings_validity` check; upstream stops at a report.
4. Historical/legacy problems inside the delivered product are recorded
   and routed the same way; "not introduced by this change" never dismisses
   a critical/high finding on its own. Mutually exclusive product choices
   go to the owner; everything else with clear intent enters repair.

## Repair Loop Contract

1. Controller routes `confirmed`/`intermittent` critical/high findings to
   the existing `/fix` path (Audited work keeps its CR/FIX boundaries).
2. After repair: rerun the finding's reproduction, relevant deterministic
   tests, then a **new candidate round with the full representative
   discover+compare sweep** — not a single-issue retest.
3. Same-root-cause symptoms are linked (one fix, one verification) to keep
   reports honest.
4. Observation evidence from the old candidate is invalidated by the new
   candidate id; rounds are appended, never rewritten.
