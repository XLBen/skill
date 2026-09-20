# Operations Handoff

> When to read: before finishing a slice that ships to a production
> environment, and when handing ownership to an operator.

```text
OPERATIONS_HANDOFF
artifact_identity: <id + hash>
environment: <target + topology>
runbook:
  - start/stop/restart: <commands>
  - health check: <command + expected>
  - common failure: <symptom -> action>
configuration:
  - key names: <list, no values>
  - secret source: <vault/secret manager reference, no value>
migrations:
  forward: <command + expected>
  rollback: <command + expected, or explicit forward-fix statement>
observability:
  dashboards: <links/ids>
  alerts: <rule -> channel>
  key signals: <signal -> meaning>
backup_restore:
  backup: <schedule + scope>
  restore rehearsal: <date/result or unverified>
ownership:
  service owner: <role/person>
  support horizon: <duration or condition>
limitations:
  - <untested environment, known gap; none if empty>
```

Rules:

- Never include secret values, tokens or credentials.
- An unverified rollback or restore path is recorded as a limitation, not as
  readiness.
- Ownership handoff is required for a long-running service; a missing owner
  is an open item for the goal card, not an assumption.
