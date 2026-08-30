# reviewer

独立评审席，从 contract-review 分离出来的子 skill。由 contract-review /
construction 通过 skill 工具调用，也可被用户直接触发。

## 触发方式

### 定向触发（斜杠指令）

| 指令 | 作用 |
|---|---|
| `/质疑 <想法>` | 直接苏格拉底式质疑（默认 question 模式） |

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
| converge-audit | construction | 竣工对账后的汇聚审计 |

协议见 `../contract-review/references/reviewer-protocol.md`。只读，永不编辑
`docs/` 产物，永不做甲方决策。
