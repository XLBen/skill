# Scenario 6: Defect in a completed package — PASS

Target: `targets/s6`, packages under `docs/audit-slices/g-fix/`

## Observed sequence

| Point | Observation | Evidence |
|---|---|---|
| Completed base package | `S-ORIG/` closed as history (synthetic done marker), contract copied from the validated s3 contract (frontmatter hash af659202…0821, file sha256 71888354…a013 captured pre-FIX) | dir listing |
| Defect reproduced | Base package's delivered `sorter.py` prints `3 2 1`; its own approved spec requires ascending `1 2 3` | observed run output |
| Routing (key point) | Branch 3 of the delta routing: sibling `FIX-01-descending/` replacement package created with `repair.md` naming base package + contract hash + observed mismatch; NOT a same-package CR, NOT an SI, base never reopened | `FIX-01-descending/repair.md` |
| Immutability (key point) | After FIX creation, base contract sha256 unchanged (71888354…a013); base dir still exactly its original 5 files; no engine CR recovery invoked (reserved for active packages) | hash + listing |

## Deviations

- The FIX package's own release/compile/reconcile engine chain was not driven
  (same engine-chain deviation as scenario 3; engine behavior covered by
  selftest PASS). The scenario's registered observation — routing decision +
  base immutability — is fully executed.

Result: **PASS** (routing + immutability); FIX engine chain NOT RUN (disclosed).
