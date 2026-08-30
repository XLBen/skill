# contract-review

把需求评审成机器可校验的 P/F/I/V 契约，同时保留甲方对价值与范围的权威。
乙方提出最小完备设计，独立评审只质询实质语义，存活问题集清空才放行。

不是无限辩论：profile 与预算控制仪式与成本；连续两轮无进展安全挂起；
预算耗尽绝不自动变成批准。

## 使用

### 定向触发（斜杠指令）

| 指令 | 作用 |
|---|---|
| `/评审 <方案>` | 完整评审：问答 → 契约 → 独立挑战 → 终审 |
| `/论证 <设计>` | 论证一个既有设计，产出契约或问题清单 |
| `/质疑 <想法>` | 苏格拉底式质疑（轻量，可无契约直接开质） |
| `/评估 <项目>` | 评估项目可行性，同 `/评审` 流程 |

指令可后缀开关：`/评审 用 full，checkpoints`。

### 非定向触发（自然语言）

"评审方案：……"、"论证方案：……"、"需求评审"、"评估项目"、"苏格拉底式质疑一下这个想法……"。

### 产物

`docs/contract.md`、`docs/review-log.md`、`docs/evidence/`、
`docs/change-orders.md`、`docs/workflow-events.jsonl`。评审席通过 skill
工具调用 `../reviewer/`。

## Key Files

- `SKILL.md`: orchestration, commands, and skill calls.
- `references/contract-schema.md`: normative engine protocol.
- `references/requirement-protocol.md`: owner authority and FIFO decisions.
- `references/evidence-protocol.md`: primary evidence and prototypes.
- `references/contract-template.md`: contract container.
- `references/reviewer-protocol.md`: scout/question/review/audit modes.
- `references/verdict-rules.md`: convergence and recovery.
- `../reviewer/`: separated review-seat skill, called via the skill tool.

Install together with the repository `scripts/check.py`; a passed contract
must validate through the engine. After changing skill files, restart
opencode.

Run `python scripts/check.py --selftest` before distribution.
