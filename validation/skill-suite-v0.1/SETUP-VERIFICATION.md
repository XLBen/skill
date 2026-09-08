# Benchmark Setup Verification

Preparation date: `2026-09-07`.

## Environment

- OpenCode: `1.18.25`
- Planning model discovered: `zhipuai-coding-plan/glm-5.3`
- Execution model discovered: `zhipuai-coding-plan/glm-5.3-flash`
- Python requirement: 3.10+

## Completed Checks

| Check | Result |
|---|---|
| `python tools/check_setup.py` | PASS; three standalone copies and frozen hashes match |
| L1 copied `check.py --selftest` | PASS |
| L2 copied `check.py --selftest` | PASS |
| L3 copied `check.py --selftest` | PASS |
| `opencode debug skill` from L1/L2/L3 | PASS; each resolved six skills from its own workspace path |
| Python compilation of setup/run/oracle/boundary scripts | PASS |
| L1 oracle before implementation | expected FAIL: product source missing |
| L2 oracle before implementation | expected FAIL: product source missing |
| L3 oracle before implementation | expected FAIL: product source missing |
| HTTP boundary health/auth/rate/success sequence | PASS: 200/401/429/200 observed |
| deterministic circuit gate | PASS: attempts 1-3 failed identically; attempt 4 returned `gate-ready` |
| circuit gate baseline after test | reset to `0` |
| trailing whitespace scan | PASS |

The three negative oracle results are controls: a blank workspace cannot pass by
exit code or empty output. They are setup evidence, not benchmark run results.

## Frozen Fingerprints

- skill tree: `9c46a8f8fa5b3920b2579017acf5d3548e34e01b2d2870be7b2e3c0fc06cf430`
- command tree: `463e99fa5271c3639fbcd9720b6ba088a8e1cba446c72f17acdf8a2d5f113a7e`
- `check.py`: `4cd330352f4a91980c697d61d7210b2b5b6eacc87f0f17210ca6f90bfba07025`
- engine fixtures: `9f4e500ad4238a5667cb89ca828540d180833d765bef802e8b60f74a4a902c04`
