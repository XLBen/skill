# Threat Model Template

> When to read: while executing the security-assurance skill.

## 1. Assets And Boundaries

| Asset | Sensitivity | Boundary crossed | Who may cross |
|---|---|---|---|
| <data/privilege> | <public/internal/personal/secret> | <process, tenant, network, trust zone> | <role/service> |

## 2. Abusive Scenarios

| ID | Scenario (who does what, gains what) | Observable failure | Slice relevance | Linked P/I/V or outcome |
|---|---|---|---|---|
| TH-01 | <actor + action + gain> | <what would show it happened> | in-scope / not-applicable + reason | <IDs> |

Rules:

- Every retained threat must be falsifiable: name the observation that would
  refute the control.
- Threats outside the slice go to not-applicable with a reason, not into
  silent omission.
- A threat that cannot be tested this slice and cannot be deferred by the
  owner becomes a blocker, not a footnote.

## 3. Controls

| Threat | Required control | Acceptance binding | Security test (negative path asserted) | Status |
|---|---|---|---|---|
| TH-01 | <authz check, rate limit, encryption, input normalization, secret handling> | <P/I/V or outcome ID> | <exact command/scenario> | pending/passed/blocked |

## 4. Residual Risks

| Risk | Impact | Likelihood | Mitigation | Owner decision |
|---|---|---|---|---|
| <risk> | <consequence> | <basis> | <what reduces it> | pending/accepted/rejected |

Scanner/secret-scan/dependency/SBOM/DAST output is referenced as evidence
(`path + hash + tool version`), never paraphrased into "scanned".
