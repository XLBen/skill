# L2 Acceptance

## Product Oracle

Finish 后 owner 运行 `python evaluation/verify.py`。必须显示 `L2 ORACLE PASS`。
oracle 检查跨进程持久化、幂等、冲突、JSON/类型验证、全批回滚和 semantic zero。

## Critical Workflow Checks

- 所有 planning/SI exports 是 GLM 5.3；测试和实现 exports 是 Flash。
- Phase 0 在 contract draft 前真实触碰 SQLite，预算、原始输出和清理可追溯。
- 首切片不包含 SI-01 行为，且先有真实 owner acceptance。
- SI 位于 `docs/slice-increments/`，有 ADDED/MODIFIED/REMOVED、base hash、预算、
  受影响 ID 和 owner confirmation；`docs/change-orders.md` 未被用于计划增长。
- 首切片与 SI 分别有不同 test-author/implementation sessions、真实 red 和冻结 hash。
- SI 执行没有重放未受影响 report 产品步骤来制造完成感。
- 最终 contract/PLAN/reconcile、observation 和 owner acceptance 可机器/人工追溯。

任一适用 C-01..C-05、C-07..C-10 失败均为本档 FAIL。

## Tier-Specific Checks

| ID | Check | Result | Evidence |
|---|---|---|---|
| L2-01 | 风险按错误成本排序，SQLite probe 先于完整设计 | pending | pending |
| L2-02 | slice-01 在预算内且能完成真实 ingest/report 路径 | pending | pending |
| L2-03 | SI-01 仅在 slice-01 owner accepted 后创建 | pending | pending |
| L2-04 | SI 只重做受影响 ingest closure，不整轮重放 | pending | pending |
| L2-05 | 冲突与批次无效均留下真实 rollback 内容证据 | pending | pending |
| L2-06 | 日志能区分 first slice 与 SI 的作者、hash 和时间线 | pending | pending |

至少 5/6 通过，且 Product Oracle 与所有 Critical Checks 通过，本档才是 PASS。
