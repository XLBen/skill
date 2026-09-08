# Slice Increment Protocol

> When to read: after a first slice has passed real verification and owner
> acceptance, or when planning the next bounded product increment.

An SI (`slice increment`) is a planned change to a working baseline. It is not
an incident record and must not be represented as a blocking CR. A CR remains
the path for a contract/reality mismatch, refuted fact, incompatible
interface, missing acceptance criterion, or unsafe side effect.

## Lifecycle

```text
proposed -> owner-confirmed -> implementing -> verifying -> accepted -> archived
```

An SI can be proposed only after the current slice has passed its real V and
the owner has accepted the observable result. If the current slice has not
passed, repair the current slice or open a CR; do not use an SI to hide the
failure.

Automatic delivery means internal routing, not automatic approval. Record the
owner's actual acceptance of the observed base result, the SI delta decision,
and confirmation of the newly generated PLAN before implementation. Initial
goal approval cannot preauthorize future acceptance or unseen PLANs. Pause at
these gates if necessary; no new slash command is required after approval.

## Required Record

Store each increment in `docs/slice-increments/SI-<nn>-<slug>.md`:

```markdown
# SI-<nn>: <short name>

| Field | Value |
|---|---|
| Base contract hash | <exact hash> |
| Base slice | <slice ID> |
| Status | proposed |
| Owner decision | <event or pending> |
| Budget | <P/F/I/V/segment/line limits> |
| Test author | <subagent/session ID> |
| Implementation author | <subagent/session ID> |

## ADDED Requirements
- <new observable behavior, or `None`>

## MODIFIED Requirements
- <changed observable behavior, or `None`>

## REMOVED Requirements
- <retired observable behavior, or `None`>

## Affected IDs
- P: <IDs>
- F: <IDs>
- I: <IDs>
- V: <IDs>

## Verification
- Given: <specific data and environment>
- When: <exact action or command>
- Then: <content/invariant/count assertion>
- Empty-result policy: <why empty is failure, or explicit semantic zero>

## Archive Evidence
- New contract revision/hash: <value>
- Passed V output/hash: <value>
- Owner acceptance event: <value>
```

Use ADDED/MODIFIED/REMOVED sections so a reviewer can see the delta without
re-reading an unchanged full contract. Do not copy the full contract into the
SI record.

## Scope And Replay

The SI must name its affected closure before implementation. Only affected
steps receive new work. Unaffected steps are not replayed for ceremony, and
their existing evidence remains attached to the base revision. If the delta
changes an interface, a fact, or the meaning of an existing V, stop and route
it through CR instead of silently widening the SI.

For the five-command workflow, every Audited slice has an immutable package:

```text
docs/audit-slices/<goal-slug>/<slice-id>/
  contract.md
  PLAN.md
  change-orders.md
  workflow-events.jsonl
  workflow-state.json
  evidence/
```

After Finish, do not overwrite that package or compile a cumulative contract
containing its completed steps. The current compiler initializes every selected
step in a new PLAN as pending and cannot import prior runtime evidence safely.
Instead, materialize the SI as a new package whose contract and PLAN contain
only the affected increment. Record the base package path, contract hash, clean
reconcile hash, and accepted goal-card outcomes as external baseline evidence.
The goal card is the cumulative delivery index; each package remains the
auditable proof for one slice. Re-run a prior behavior only when the new delta
can regress it, and record that regression V in the new package without
re-executing the old implementation step or side effect.

A post-completion contract/reality mismatch uses the same immutable packaging
mechanism but a `FIX-<nn>-<slug>` replacement package, not an SI record and not
engine CR recovery. Its `repair.md` points to the base package/hash. Its
standalone affected-only contract is released as a normal new Audited slice and
compiled without `--previous-contract`; the PLAN contains only the correction
and regression verification. The goal card records which accepted evidence the
clean replacement supersedes, while the base package stays immutable. Engine CR
recovery remains reserved for a mismatch in the currently active package.
Reuse the matching unfinished goal card for a fix; do not create a second
active fix goal. If multiple completed packages could be the repair baseline,
ask the owner which one instead of selecting by recency.

## Relation To OpenSpec

This protocol intentionally mirrors the useful part of OpenSpec's
change-folder and delta-spec model: proposed changes stay separate until
verified. Here, the goal card indexes accepted slice packages rather than
merging runtime histories into one cumulative PLAN. It does not copy OpenSpec's
tools or remove this repository's existing CR and hash gates.
