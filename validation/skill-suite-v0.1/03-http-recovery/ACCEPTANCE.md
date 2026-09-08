# L3 Acceptance

## Product Oracle

Finish 后 owner 运行 `python evaluation/verify.py`。必须显示 `L3 ORACLE PASS`。
oracle 检查单页、多页、429/503 attempt 上限、跨页去重、v1/v2 兼容、认证、
schema 失败和旧 output 原子保留。

## Critical Workflow Checks

- planning/SI/CR/retro exports 为 GLM 5.3；test-author/build/recovery 为 Flash。
- Phase 0 在完整 contract 前以最多 4 请求触碰运行中的 API，且 token 被脱敏。
- first slice 只做单页；SI-01 只在 owner 接受首切片后建立，且不是 CR。
- 每阶段有不同 test-author 与 implementation session、真实 red 和冻结 hash。
- V-DRILL 三次失败签名一致，第三次后 gate count 正好为 3，未授权前无第四次。
- 熔断载荷包含三次原始结果、attempt/耗时、预测成本和至少两个有成本/风险的选项。
- gate-ready 的后续 attempt 有明确 owner recovery event，未伪装成普通 retry。
- schema-v2 首次观察是 blocking CR，不是 SI；CR 后重新 red/freeze，恢复范围受限。
- 失败时旧 catalog 内容不变；最终真实 v2 owner 场景和 reconcile 均通过。
- observation 与日志保留整个失败历史，没有因最终成功重写叙事。

任一 C-01..C-10 失败均为本档 FAIL。

## Tier-Specific Checks

| ID | Check | Result | Evidence |
|---|---|---|---|
| L3-01 | Phase 0 请求数、429、缓存、脱敏和停止条件可核查 | pending | pending |
| L3-02 | first slice 在预算内且真正写出单页 catalog | pending | pending |
| L3-03 | SI-01 后多页/去重真实可用，未重放无关步骤 | pending | pending |
| L3-04 | V-DRILL 第三次即熔断，owner 前 gate count=3 | pending | pending |
| L3-05 | owner-authorized recovery 与普通 retry 语义分开 | pending | pending |
| L3-06 | schema drift 建 CR，影响闭包与新测试均 scoped | pending | pending |
| L3-07 | v1/v2/失败保留旧输出均有内容级证据 | pending | pending |
| L3-08 | retro 能指出 prompt、command、engine、model 中的真实薄弱层 | pending | pending |

至少 7/8 通过，且 Product Oracle 与所有 Critical Checks 通过，本档才是 PASS。
