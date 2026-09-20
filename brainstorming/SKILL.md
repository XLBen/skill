---
name: brainstorming
description: Use before /plan or during /grill when an idea still has competing solution shapes - multiple architectures, build-vs-buy, data-model alternatives - and the choice materially changes the result. Explores 2-4 concrete alternatives with trade-offs, converges with the user in reviewable sections, and records the chosen design rationale. Skip it when the requirement is already specific and the implementation path is conventional.
license: MIT
metadata:
  language: "zh-CN"
  called-by: "grill, mvp-delivery (plan mode)"
  public-command: "none"
---

# Brainstorming (方案探索)

需求问清了不等于方案定了。当存在多个会显著改变结果的方案形态时，先探索
再规划。本 skill 适配自 [obra/superpowers](https://github.com/obra/superpowers)
的 brainstorming 方法（见 `UPSTREAM.md`），定位在 grill 之后、
PLAN/目标卡之前。

## When To Use

满足任一条件时，grill 在 brief 定稿前、或 mvp-delivery `/plan` 在建卡前
加载本 skill：

- 存在 2 个以上合理的整体架构/技术栈选择，且选择改变后续大部分工作；
- build-vs-buy / 自研-vs-现成库的分叉；
- 数据模型或存储形态有实质不同的候选；
- 用户说“帮我想想怎么做”或“有没有别的方案”；
- **只有一个看似常规的候选，但它带来长期接口、跨模块耦合、数据模型迁移、
  性能/可靠性约束或不可逆的运营后果**：此时至少写出该方案与一个替代方案
  的质量属性场景（延迟、可用性、可演化性、成本）与耦合/迁移影响，不必凑满
  2–4 个方案。

Skip：需求已明确、实现路径常规、无长期后果且仓库已有既定模式。此时直接进入
`/plan`。

## 流程

1. **先理解再发散**：从 brief/对话复述问题约束（谁用、入口、边界），
   确认没有误解再开始探索。
2. **生成 2–4 个具体方案**：每个方案给出一段可想象的具体形态
   （组件、数据流、入口），不是抽象名词。刻意包含一个保守方案和
   一个激进方案，避免锚定。
3. **逐方案列 trade-off**：实现成本、返工风险、对既有代码的侵入、
   验证难度、可逆性，以及质量属性场景（代表性负载下的延迟/吞吐、可用性、
   故障恢复、可演化性、运行成本）。基于仓库真实状态（读代码），不凭空假设。
4. **记录架构后果**：长期接口、跨模块耦合、迁移路径与被否方案理由写入 ADR
   或 brief 的 BD 条目；需要持续保证的质量属性写成一个可执行的 fitness 检查
   （放入既有 V 字段），不新增架构工件类型。
5. **分节收敛**：每次只给用户看一节（问题复述 → 方案对比 → 推荐 +
   理由），每节可独立确认，避免一次抛出长文档。每节的确认是真实交互：
   优先用宿主的交互询问（OpenCode 的 `question` 工具），否则以明确问题
   结束回合等待用户回复；禁止同回合自问自答或替用户选型。
6. **记录决定**：选型结果与理由写回 brief 的 BD（decision）条目或
   目标卡依据；被否方案记一行否决理由，供后续 `/fix` 时回看。
7. **交接**：设计确定后交给 `/plan`；本 skill 不写实现计划。

## 边界

- 探索的是方案，不是需求范围：目标、验收、非目标仍归 grill/owner。
- 推荐意见允许（技术选型在用户理解需求后），价值取舍归用户。
- 最多一轮探索 + 一轮收敛修正；分歧仍在时列出待决项交 owner，
  不无限循环。
