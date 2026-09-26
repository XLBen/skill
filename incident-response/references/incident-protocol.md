# Incident Protocol Template

> When to read: while executing the incident-response skill.

```text
INCIDENT
id: <INC-...>
severity: sev1 | sev2 | sev3
status: active | contained | recovered | closed
commander: <role>
started_at: <timestamp>
owner_notified: <yes/no + time>

impact:
  - <what is broken, for whom, since when>

timeline:
  - <timestamp> <actor> <action> -> <observed result> (<evidence ref>)

containment:
  - action: <limit traffic, isolate component, roll back, read-only>
    executed_by: <role>
    result: <observed>
    reversible: <yes/no + how>

evidence_preserved:
  - <log/metric/dump path + hash before cleanup>

recovery:
  - path: <rollback | forward-fix | failover>
  - verification: <real user-path check + result>
  - residual_degradation: <what remains impaired>

handoff_to_fix:
  - reproduction: <minimal repro or "unknown">
  - failure_signature: <normalized signature>
  - evidence_refs: <paths>

postmortem:
  - detection_gap: <why not caught earlier>
  - what_went_well: <...>
  - actions:
      - <action> owner=<...> due=<...> status=<open/done>
```

Rules:

- Timestamps are recorded as actions happen, not reconstructed from memory.
- Destructive or irreversible containment needs owner authorization; record
  who authorized and when.
- Never declare recovery from a process-alive signal alone; a real user path
  must pass.
- The handoff to internal Fix Mode carries raw evidence pointers, not summaries.
