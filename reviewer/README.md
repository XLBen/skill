# reviewer

独立评审席，从 contract-review 分离出来的子 skill。由 contract-review /
construction 调度 fresh subagent 后加载，也可被自然语言触发。它不生成测试；
测试由独立的 test-author 负责，reviewer 只读检查其结果。

## 触发方式

公开命令已移除。用户仍可自然语言说“质疑一下这个想法”；多数时候本 skill 由
主 skill 内部调度，单独触发只走轻量质疑路径。

## 被调用模式

| mode | 调用方 | 输出 |
|---|---|---|
| scout | contract-review | 候选 W、事实缺口、一手来源 |
| question | contract-review | 新的实质性问题 |
| review | contract-review | resolved / hard / soft / owner-tradeoff / invalid |
| final-audit | contract-review | 干净上下文终审结果 |
| cr-audit | contract-review | CR 影响闭包审计 |
| converge-audit | construction | 竣工对账后的汇聚审计，包括 v0.1 观测报告、测试隔离和真实可用性 |

协议见 `../contract-review/references/reviewer-protocol.md`。只读，永不编辑
`docs/` 产物，永不做甲方决策。
