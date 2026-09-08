# v0.1 Verification Record

## Commands

| Command | Result |
|---|---|
| `python scripts/check.py brief docs/brief.md` | PASS; brief hash matched `b278196021d23c21edbaa1b01a2765fc20c81ee8ef33be66ced8dd52c4b51e55` |
| `python scripts/check.py --selftest` | PASS; `selftest PASS` |
| `git diff --check` | No whitespace errors; Git reported only LF/CRLF normalization warnings |

## Fixture Hashes

- `tests/fixtures/contract-valid.md`: `62502102da2c7399afec13e93f780d83cc2709d54c16e43f3fc006f254700122`
- `tests/fixtures/plan-valid.md`: `c0e827c9e1342a2352fa0896279238fa32ad55dd2505ac377f0c60c3087eccb2`

## Residual Risks

- `docs/brief.md` remains `status: draft` with `owner_confirmation.confirmed:
  false`; it is not yet a final grilled intake.
- The new rules are prompt-layer controls. The engine does not yet enforce
  GWT assertions, empty-result failure, frozen-test write protection, retry
  limits, or ceremony warnings.
- BA-01 cannot be judged until a real project completes a signed
  `docs/mvp-observation.md`.
- The modified worktree is intentionally uncommitted; inspect the final diff
  before any commit.
