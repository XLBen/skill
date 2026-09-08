# v0.1 MVP Observation Report

> Use for the first real project run after the v0.1 prompt-layer changes. This
> report measures whether the workflow was actually followed; it is not a
> replacement for `check.py` or the append-only event ledger.

## Run Identity

| Field | Value |
|---|---|
| Project | `<name>` |
| Workflow protocol | `v0.1` |
| Run ID | `<stable run ID>` |
| First-slice contract hash | `<hash>` |
| PLAN structure hash | `<hash>` |
| Phase 0 record | `docs/evidence/phase-0-<id>.md` or `not-needed` |
| Observation status | `draft` / `supported` / `refuted` / `undetermined` |
| Owner acceptance event | `<event ID, or pending>` |

## Gate Results

Mark each row with `pass`, `fail`, or `not-observed`. Every result needs an
event, file, command output hash, or explicit owner record.

| Criterion | Result | Evidence | Notes |
|---|---|---|---|
| Highest-cost assumption touched before full construction |  |  |  |
| Phase 0 budget and side-effect discipline respected |  |  |  |
| First slice stayed within its declared budget |  |  |  |
| First slice reached a real user/downstream observable path |  |  |  |
| Every new V has concrete Given/When/Then data |  |  |  |
| Every new V has a content/state assertion beyond exit 0 |  |  |  |
| Empty required output was rejected |  |  |  |
| Same failure signature stopped after its third consecutive failure |  |  |  |
| No fourth ordinary retry occurred after that circuit break |  |  |  |
| Circuit-break escalation included two costed options |  |  |  |
| Test author and implementation author were different |  |  |  |
| Frozen test files were not modified by implementation |  |  |  |
| Red evidence preceded implementation and green evidence |  |  |  |
| Real data path completed |  |  |  |
| Owner accepted the usable result in a real scenario |  |  |  |

## Slice Budget

| Measure | Budget | Actual | Evidence |
|---|---:|---:|---|
| Active P |  |  |  |
| Active F |  |  |  |
| Active I |  |  |  |
| Active V |  |  |  |
| PLAN segments |  |  |  |
| Contract non-blank lines |  |  |  |
| Estimated product-code increment |  |  |  |

An exception must name the owner decision event and why the wider slice was
necessary. Do not silently replace the declared budget with the actual value.

## Test And Implementation Separation

| Field | Value |
|---|---|
| Test manifest | `docs/test-manifests/<slice-id>.md` |
| Spec source | `<contract/SI path and IDs>` |
| Spec hash | `<hash>` |
| Test author ID | `<subagent/session ID>` |
| Implementation author ID | `<subagent/session ID>` |
| Frozen test files | `<paths>` |
| Frozen test hashes | `<path=hash>` |
| Red evidence | `<event/output hash>` |
| Green evidence | `<event/output hash>` |
| Test-file diff after freeze | `none` / `<CR and evidence>` |

## Failure History

| Step/V | Attempt | Normalized failure signature | Result | Elapsed | Cost | Escalated? |
|---|---:|---|---|---:|---:|---|
| `<S/V>` | 1 | `<signature>` | failed/passed |  |  |  |

The signature removes timestamps, absolute paths, random IDs, and stack line
numbers. A changed attempt ID or error wording alone does not reset the count.

## Real Scenario Acceptance

```text
Given: <real input, account/data state, and environment>
When: <exact user action or command>
Then: <observable content, invariant, schema, count, or user-visible result>
Observed: <raw result or bounded excerpt/hash>
Owner: <name or redacted owner reference>
Decision: accepted | rejected | pending
```

## Ceremony Ratio Warning

```text
manually maintained workflow-document non-blank lines in this diff /
product-code-and-test non-blank lines in this diff = <ratio or N/A>
```

Exclude `node_modules`, `vendor`, generated files, caches, and binaries. If the
denominator is zero while workflow documents were added, record a direct
warning. This is advisory and does not override the owner or machine gates.

## BA-01 Decision

Choose exactly one:

- `supported once`: no BC-02 failure was observed and BS-01 was achieved;
- `refuted`: at least one BC-02 failure occurred;
- `undetermined`: required evidence or owner acceptance was missing.

List every supporting or refuting evidence ID. A single supported run does not
make BA-01 permanently true; it only justifies continuing observation.
