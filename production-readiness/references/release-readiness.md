# Release Readiness Template

> When to read: while executing the production-readiness skill.

## Prechecks

| Check | Evidence | Status |
|---|---|---|
| Artifact/build identity recorded | <id + hash> | pending |
| Dependencies locked | <lockfile hash> | pending |
| Config keys present (names only, no values) | <list> | pending |
| Schema/migration compatible with previous version | <compat note + test> | pending |
| Rollback path rehearsed or dry-run | <command + result> | pending |
| Secrets available in target environment | <name-level confirmation> | pending |

## Progressive Rollout

| Stage | Scope | Health criteria | Observation window | Stop condition | Owner |
|---|---|---|---|---|---|
| canary | <1% or one instance> | <latency/error/saturation threshold> | <minutes> | <exact signal> | <role> |
| partial | <10%> | ... | ... | ... | ... |
| full | <100%> | ... | ... | ... | ... |

## Observability

| Promised outcome | Signal (log/metric/trace) | Where verified | Alert rule |
|---|---|---|---|
| <outcome> | <signal> | staging/dry-run evidence | <rule + channel> |

## Post-Deploy Verification

| Check | Command/journey | Expected | Evidence |
|---|---|---|---|
| Health | <command/endpoint> | <assertion> | <path + hash> |
| Key user path | <journey> | <assertion> | <path + hash> |
| Data reconciliation | <count/checksum query> | <assertion> | <path + hash> |

Every evidence row binds the released artifact identity; a later artifact
change invalidates the affected rows.
