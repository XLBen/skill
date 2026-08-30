# contract-review

规划阶段 skill：把需求评审成机器可校验的 P/F/I/V 契约，契约 passed 后继续
编译确认可执行 PLAN，全程保留甲方对价值与范围的权威。乙方提出最小完备
设计，独立评审只质询实质语义，存活问题集清空才放行。

不是无限辩论：profile 与预算控制仪式与成本；连续两轮无进展安全挂起；
预算耗尽绝不自动变成批准。

## 使用

### 定向触发（斜杠指令）

| 指令 | 何时用 | 做什么 | 产出 |
|---|---|---|---|
| `/评审 <方案>` | 有新需求，动手前先定清楚 | 问答决策 → 起草契约 → 独立挑战 → 终审 | `docs/contract.md`（passed） |
| `/论证 <设计>` | 已有具体设计要检验 | 针对该设计取证攻防，走评审流程 | 契约或问题清单 |
| `/质疑 <想法>` | 无契约，快速找漏洞 | 苏格拉底式追问，不进契约流程 | 问题清单 |
| `/评估 <项目>` | 想知道值不值得做 | 可行性论证 | 评估结论 + 建议 |
| `/规划` | 契约 passed 后变成可执行计划 | 门校验 → 编译 PLAN → 变体确认 | `docs/PLAN.md`（已确认） |

指令可后缀开关：`/评审 用 full，checkpoints`。PLAN 确认后交接给
construction（`/开工`）。

### 非定向触发（自然语言）

"评审方案：……"、"论证方案：……"、"需求评审"、"评估项目"、"苏格拉底式
质疑一下这个想法……"、"规划一下"、"编译 PLAN"。

### 产物

`docs/contract.md`、`docs/PLAN.md`、`docs/review-log.md`、
`docs/evidence/`、`docs/change-orders.md`、`docs/workflow-events.jsonl`。
评审席通过 skill 工具调用 `../reviewer/`。

## Key Files

- `SKILL.md`: orchestration, commands, planning, and skill calls.
- `references/contract-schema.md`: normative engine protocol.
- `references/requirement-protocol.md`: owner authority and FIFO decisions.
- `references/evidence-protocol.md`: primary evidence and prototypes.
- `references/contract-template.md`: contract container.
- `references/plan-template.md`: generated PLAN and confirmation.
- `references/reviewer-protocol.md`: scout/question/review/audit modes.
- `references/verdict-rules.md`: convergence and recovery.
- `../reviewer/`: separated review-seat skill, called via the skill tool.

Install together with the repository `scripts/check.py`; a passed contract
must validate through the engine. After changing skill files, restart
opencode.

Run `python scripts/check.py --selftest` before distribution.
