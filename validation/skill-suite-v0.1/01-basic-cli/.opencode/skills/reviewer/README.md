# reviewer

独立评审席，从 contract-review 分离出来的子 skill。由 contract-review /
construction 通过 skill 工具调用，也可被用户直接触发。它不生成测试；
测试由独立的 test-author 负责，reviewer 只读检查其结果。

## 触发方式

### 定向触发（斜杠指令）

| 指令 | 作用 |
|---|---|
| `/challenge <idea>` | 直接轻量质疑一个已经说清的想法；不伪造契约或 hash |

### 非定向触发（自然语言）

"苏格拉底式质疑一下这个想法……"。多数时候本 skill 由主 skill 定向/非定向
触发后间接调用，单独触发只走轻量质疑路径。

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
