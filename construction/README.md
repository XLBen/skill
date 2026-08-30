# construction

消费一份已验证的 contract-review 契约：引擎把每个评审过的 I 变体/段
确定性编译成稳定的 S 步骤，对不可变 PLAN 结构做 hash，选择与尝试作为
运行时状态。

执行是 DAG 而不是勾选框猜测。每次尝试记录副作用、幂等与新鲜验证。
阻断 CR 停止普通工作，受限的恢复能力仍可重编译、回滚、失效、重做并
验证批准的变更。

## 使用

### 定向触发（斜杠指令）

| 指令 | 作用 |
|---|---|
| `/开工` | 校验契约门 → 编译 PLAN → 确认 → 施工 |
| `/继续` | 中断后恢复：重跑门校验，从事件账本续建 |
| `/竣工` | 强制 `reconcile` 对账 + `converge-audit`，置 `done` |
| `/复盘` | 竣工后基于证据的复盘（见 retro-protocol） |
| `/变更 <事实>` | 报告契约与现实的偏差，建立 CR 阻断普通施工 |

指令可后缀开关：`/开工 autonomous`。

### 非定向触发（自然语言）

"开工"、"施工"、"按契约开工"、"继续施工"、"竣工对账"、"复盘一下"；
直接陈述事实（如"接口 X 实际不存在"）即触发变更流程。

## Key Files

- `SKILL.md`: commands, gates, compilation, execution and completion.
- `references/plan-template.md`: generated PLAN and runtime separation.
- `references/step-protocol.md`: attempts, recovery, minimal diff and CR.
- `references/retro-protocol.md`: evidence-based learning after delivery.
- `../step-executor/`: isolated step executor skill, called via the skill tool.
- `../reviewer/`: review gate and converge-audit, called via the skill tool.

Install with contract-review and repository `scripts/check.py`. Validate with:

```powershell
python scripts/check.py compile docs/contract.md docs/PLAN.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
```

After changing skill files, restart opencode.
