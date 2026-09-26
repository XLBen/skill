---
name: brainstorming
description: Use during /grill or before /plan when genuinely competing solution shapes change the user's experience, long-term constraints or acceptance. Compares concrete alternatives and their consequences; records owner choices only after real replies, while ordinary technical choices stay with the planner. Skip conventional bounded changes.
license: MIT
metadata:
  language: "zh-CN"
  called-by: "grill, mvp-delivery (plan mode)"
  public-command: "none"
---

# Brainstorming (方案探索)

需求问清了不等于方案定了。当存在多个会显著改变结果的方案形态时，先探索
再规划。本 skill 适配自 [obra/superpowers](https://github.com/obra/superpowers)
的 brainstorming 方法（见 `UPSTREAM.md`）。本地只在实质分叉时使用，
可在 grill 中或 PLAN/目标卡之前触发；不继承上游“所有创意改动都先停下等批准”的 gate。

## When To Use

满足任一条件时，grill 在 brief 定稿前、或 mvp-delivery `/plan` 在建卡前
加载本 skill：

- 存在两条以上可信的整体路线，且用户体验、运营负担或验收结果不同；
- build-vs-buy / 自研-vs-现成库或数据模型分叉，确实改变成本、迁移或长期承诺；
- 用户请求比较方案（“帮我想想怎么做”“有没有别的方案”）；
- **只有一个看似常规的候选，但它带来长期接口、跨模块耦合、数据模型迁移、
  性能/可靠性约束或不可逆的运营后果**：至少写出该方案的质量属性场景
  （延迟、可用性、可演化性、成本）与耦合/迁移影响；只有找到可信替代
  才作对比，不为凑数发明激进方案。

Skip：需求已明确、实现路径常规、无长期后果且仓库已有既定模式。此时直接进入
`/plan`。

## 流程

1. **先理解再发散**：从 brief/对话和仓库事实概括目的、成功信号与约束，
   标出用户说的和 agent 推断的；仅当目的会改变路线且无法推断时才追问。
2. **比较真实可行的候选**：通常两三个；每个给出入口、组件、数据流与关键
   前提。包括最少改动路线和一个有理由的不同路线，排除违背既有禁令或没有
   能力依据的选项；没有可信分叉就明确推荐单一路线，不造对立面。
3. **逐方案列 trade-off**：实现成本、返工风险、对既有代码的侵入、
   验证难度、可逆性，以及质量属性场景（代表性负载下的延迟/吞吐、可用性、
   故障恢复、可演化性、运行成本）。基于仓库真实状态（读代码），不凭空假设。
4. **记录架构后果**：长期接口、耦合、迁移路径与落选理由写入既有 brief、
   ADR 或计划的决策处；需持续保证的质量属性写成可执行 fitness 检查，
   纳入已有 V/验证任务，不另造工件。
5. **按决策粒度呈现**：交互式 `/grill` 的高影响分叉分节讨论并等真实答复；
   方案形态经用户确认只代表该形态，不预先批准未展示的设计/施工产物。
   无命令 work 方法只在用户价值取舍、授权或无法裁决的互斥结果上询问；一般工程
   选型给出依据并继续。不得同回合自问自答或把推断写成 BD。
6. **记录与交接**：owner 真正选过的路线和理由写为 BD；agent 工程选择
   记在计划，未确认的产品分叉保持待决。独立 `/plan` 接收结论；由无命令 work 方法
   调用时返回总控继续，不要求用户重新发命令。

## 边界

- 探索的是方案，不是需求范围：目标、验收、非目标仍归 grill/owner。
- 推荐意见允许（技术选型在用户理解需求后），价值取舍归用户。
- 比较充分且已能裁决就停止；缺关键事实时先做有界查证，真实 owner 分歧
  保留待决，不能靠重复生成选项或更多确认轮次制造收敛。
