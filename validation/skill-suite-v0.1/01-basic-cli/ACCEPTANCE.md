# L1 Acceptance

## Product Oracle

Owner 在 Finish 后运行：

```powershell
python evaluation/verify.py
```

全部检查通过并显示 `L1 ORACLE PASS` 才满足产品门。oracle 检查固定样本、
semantic zero、无效金额、重复 ID、stdout/stderr 和退出码。

## Critical Workflow Checks

- Planning export 显示 GLM 5.3；test-author 和 implementation export 显示 Flash。
- contract 与 PLAN 通过复制引擎检查，最终 reconcile 为 clean。
- direct profile 没有被无理由升级；Phase 0 是可审计的 `not-needed`。
- 首切片预算在起草前声明，且只覆盖一个端到端 CLI 路径。
- Given/When/Then 使用具体 CSV 和 JSON 内容，不是 `exit 0`。
- semantic zero 被显式区分，非预期空 stdout 失败。
- test-author 和 implementation session ID 不同；red 发生在实现前。
- manifest 中的冻结测试 hash 在实现后仍匹配。
- owner 可见场景、MVP observation、Finish 和 session exports 都存在。

任一对应根档案 C-01..C-05、C-08..C-10 的失败均为本档 FAIL。

## Tier-Specific Checks

| ID | Check | Result | Evidence |
|---|---|---|---|
| L1-01 | 没有把明确任务退回 grill 反复提问 | pending | pending |
| L1-02 | contract 非空行数不超过 180，且无无关 P/F/I/V | pending | pending |
| L1-03 | 产品实现保持单一小工具，无框架或依赖膨胀 | pending | pending |
| L1-04 | generated acceptance tests 能独立发现至少一种错误实现 | pending | pending |
| L1-05 | build-log 与 run-log 包含失败和成功原始证据 | pending | pending |

至少 4/5 通过，且 Product Oracle 与所有 Critical Checks 通过，本档才是 PASS。
