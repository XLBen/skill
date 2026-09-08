# Evidence Protocol

> When to read: when a material fact is disputed and research or prototype
> work is about to start.

Research only a claim that can change P/W/D/A/F/I/V or close a surviving
issue. Prefer official specifications, official documentation, source and
maintainer records, then reproducible experiments. Secondary sources locate
primary evidence but do not settle a critical claim.

An E node records claim, source revision, checked time, environment, command,
fixed inputs, output summary, verdict, redaction metadata, and a mandatory
`bundle_hash`. Prototype code is excluded from production unless separately
adopted, but its reproducibility bundle remains available for audit.

## Phase 0 Evidence

Before the first-slice contract, use `phase-0-protocol.md` to record the
highest-cost assumption and the smallest safe real probe. The record must
include a predeclared request/call budget, cache key and hit/miss status,
backoff, side effects, cleanup, raw observation, and a falsifiable verdict.
Save it under `docs/evidence/phase-0-<id>.md`. `blocked` is not `passed`, and a
cached observation is not a new real-world validation.

## Acceptance Evidence

For each new v0.1 acceptance V, preserve the following in the test manifest or
build log:

- Given: concrete initial data and environment;
- When: the exact command or user action;
- Then: a content, invariant, schema, count, or user-visible assertion;
- empty-result policy: default failure for missing/empty/zero-row output unless
  an explicit semantic zero is asserted;
- raw output or a content hash plus enough excerpt to reproduce the claim.

An exit code is an execution signal, not a content assertion. A command that
returns 0 while producing no required result does not pass.

Never persist credentials, tokens, passwords, or unnecessary PII. Record only
the environment variable or secret-manager reference and the redaction type.

When two agents dispute observable behavior, convert it into one falsifiable
experiment with a predeclared outcome interpretation. Stop when the configured
research/prototype budget is exhausted and request owner control; do not keep
browsing because more evidence might exist.
