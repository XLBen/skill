# Security Handoff

> When to read: before a converge audit, whole-goal finish, or a production
> readiness handoff on a security-relevant slice.

```text
SECURITY_HANDOFF
artifact_identity: <artifact/build identity + hash>
spec_snapshot: <contract/SI path + hash>
threat_model: <path + hash>
controls:
  - threat: <TH-ID>
    control: <summary>
    acceptance: <P/I/V or outcome ID>
    evidence: <command/scenario + result + path>
    status: passed | blocked | not-applicable (reason)
residual_risks:
  - risk: <summary>
    owner_decision: <event ID or pending>
scanners:
  - tool: <name/version>
    scope: <what it covered>
    result_ref: <path + hash>
    interpretation: <what it does NOT prove>
gaps:
  - <untested control or unverified environment; none if empty>
```

Lifecycle:

- Bind to the artifact identity; any product change invalidates affected
  controls and requires re-verification of those threats only.
- The handoff is an input to the independent reviewer; it never replaces the
  reviewer verdict, engine gates or owner decisions.
- A `blocked` control or an unowned residual risk prevents finish; it is never
  converted to not-applicable by the executing seat.
