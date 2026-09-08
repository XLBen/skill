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

## Relation To OpenSpec

This protocol intentionally mirrors the useful part of OpenSpec's
change-folder and delta-spec model: proposed changes stay separate until
verified, then become the next source-of-truth revision. It does not copy
OpenSpec's tools or remove this repository's existing CR and hash gates.
