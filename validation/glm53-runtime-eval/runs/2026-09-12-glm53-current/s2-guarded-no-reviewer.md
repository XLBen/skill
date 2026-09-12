# Scenario 2: Guarded goal, no reviewer seat — PASS (with disclosure)

Target: `targets/s2` (G-GUARD, rigor guarded, factor external-boundary)

## Observed sequence

| Step | Observation | Evidence |
|---|---|---|
| Goal validated | `[goal] OK` | engine output |
| Worker dispatch (real) | Valid RESULT; verification PASS | task `ses_f6aea63bfffe113YcEm8OHOxaf` |
| Controller engine verify | `verify-goal O-01` → passed | evidence file |
| Reviewer seat attempt | Real dispatch to `mvp-reviewer` failed: "Unknown agent type" → preflight capability-unavailable recorded | task tool error; dispatch archive T-02 |
| Tiering decision (key point) | Guarded + reviewer unavailable → recorded `skip_reason: capability-unavailable`, controller check disclosed, finish NOT blocked. Under the same condition an Audited independence gate would block (policy cross-checked in mvp-delivery SKILL tiering text; not executed here) | `g-guard.dispatch.json` T-02 |
| finish-goal | `finished goal G-GUARD (complete)` exactly once | engine output |

## Controller whole-goal check (disclosed non-independent)

Controller (this session, not a fresh seat) checked: goal card coverage vs
direct request; evidence binds G-GUARD/O-01 result passed assertion_passed
true; product implements the claimed CLI entry. Disclosed as a controller
check, not independent review.

## Deviations

- The runtime technically offered a built-in read-only fallback seat
  (`explore`), which scenario 1 used. Scenario 2 deliberately exercised the
  degraded Normal/Guarded branch by stopping at the failed project-seat
  dispatch; the observed decision point is the tiering policy (record +
  disclose + continue vs Audited block), which is what this scenario tests.

Result: **PASS**
