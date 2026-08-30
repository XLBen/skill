# construction

施工阶段 skill：消费 contract-review 已确认的 PLAN，按依赖序逐步执行。
引擎保证 PLAN 结构不可变（hash），选择与尝试是运行时状态。

执行是 DAG 而不是勾选框猜测。每次尝试记录副作用、幂等与新鲜验证。
阻断 CR 停止普通工作，受限的恢复能力仍可重编译、回滚、失效、重做并
验证批准的变更。规划（契约与 PLAN 编译确认）归 contract-review 的
`/规划`；本 skill 从已确认的 PLAN 开始，PLAN 缺失时委托补齐。

## 使用

### 定向触发（斜杠指令）

| 指令 | 何时用 | 做什么 | 产出 |
|---|---|---|---|
| `/开工` | PLAN 已确认（缺则先委托 `/规划`） | 门校验 → 按依赖序执行步骤、跑 V 留证 | 完成步骤 + 验收证据 |
| `/继续` | 中断后恢复 | 重跑门校验，从事件账本续建 | 续施工 |
| `/竣工` | 全部步骤完成后 | `reconcile` 对账 + `converge-audit` | PLAN 置 `done` + 维护交接 |
| `/复盘` | 竣工后 | 只读证据复盘（见 retro-protocol） | 三张清单建议 |
| `/变更 <事实>` | 契约与现实不符 | 建 CR 阻断 → 评审裁决 → 影响闭包内重做 | CR `verified` |

指令可后缀开关：`/开工 autonomous`。

### 非定向触发（自然语言）

"开工"、"施工"、"继续施工"、"竣工对账"、"复盘一下"；直接陈述事实
（如"接口 X 实际不存在"）即触发变更流程。

## Key Files

- `SKILL.md`: commands, gates, execution and completion.
- `references/step-protocol.md`: attempts, recovery, minimal diff and CR.
- `references/retro-protocol.md`: evidence-based learning after delivery.
- `../step-executor/`: isolated step executor skill, called via the skill tool.
- `../reviewer/`: review gate and converge-audit, called via the skill tool.
- `../contract-review/`: delegated `/规划` and CR adjudication (skill call).

Install with contract-review and repository `scripts/check.py`. Validate with:

```powershell
python scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
```

After changing skill files, restart opencode.
