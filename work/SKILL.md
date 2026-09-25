---
name: work
description: Use for /work <goal> to autonomously infer unclear requirements, dynamically select applicable available skills, and plan, execute, repair, and verify the original goal through completion.
license: MIT
metadata:
  language: "zh-CN"
  public-command: "/work <goal>"
  calls-skills: "runtime-discovered applicable skills"
  produces: "the requested outcome with current verification evidence"
---

# Work：自主推进目标直到有证据地完成

`/work <目标>` 是端到端总控入口。用户给目标；controller 自己理解、补充推断、选择能力、规划、执行、验证、修复和收敛。不要在完成分析、brief、计划、首个切片或第一次失败时停下并让用户再运行 `/plan`、`/build`、`/fix` 或 `/resume`。

## 目标理解：模糊时自主 grill

先区分新目标与恢复目标。无参数时从持久状态恢复唯一活动目标；多个候选无法消歧才询问。检查当前会话和项目事实，避免重复询问已有答案。先判定工作规模：目标明确、局部可逆、无需跨任务交接或正式 gate 的改动，直接执行并做相称验证；其余再进入需求推断与规划。不要用流程准备代替动手。

当目标不清楚且确实影响实施选择时，加载 `grill` 并使用 **Work Inference Mode**：

1. 用 grill 的需求维度检查用户/场景、入口、环境、输入、输出、失败边界、状态、权限隐私、非功能要求、集成、成功信号和非目标。
2. 自行检查仓库、现有产品行为、依赖和可查证资料。事实由 agent 调查；不把可调查事实交给用户猜。
3. 优先保留用户明确表达的目标/约束；其余使用现有上下文与产品惯例，做最小、可逆、最符合目标的假设。
4. 将 agent 推断标为 `assumption`，保留影响和后续证伪方式；不得伪称用户答复、owner 决定、确认 brief 或用户认可。
5. 用简短的内部 `WORKING_GOAL` 总结原始目标、必需结果、明确约束、对实施有影响的假设、完成证据和下一步，然后立即行动；事实已明确时直接从目标提取这些信息，不另走访谈。

Work Inference Mode 是自主需求建模，不是模拟访谈。不得在同一轮自问自答、写入虚构的用户答复，或仅因覆盖维度有空缺就强制提问/生成 `docs/brief.md`。用户明确调用 `/grill` 时仍完全遵守 grill 的真实交互、确认和 brief 规则。

只在以下情况询问：目标对象无法确定且无法从上下文判定；互斥产品选择会实质改变用户结果且无证据可裁决；需要用户决定尚未授权的不可逆/破坏性、隐私/凭据、付费或工作区外副作用；或必须由用户提供的权限、凭据或外部前提缺失。先自行完成可独立调查的部分，再提出最小具体问题。等待期间保留目标和已完成工作；答复后继续原循环。

## 动态技能发现与路由

编码、代码设计、修复和代码评审时通过 skill 工具加载 `ponytail`（原文在 `../ponytail/SKILL.md`）；遇到范围边界、额外加固、过度设计或重复验证时通过 skill 工具加载 `stop-that-shit`（原文在 `../stop-that-shit/SKILL.md`）。不要摘编或改写上游提示词替代实际加载；当前会话无法加载时按现有 capability-unavailable 处理。二者与本地规则冲突时执行上游原文，明确授权、用户已要求的结果及宿主权限仍有效。只读任务不得因加载 skill 获得写权限。

领域选择同时覆盖原版 `skill-creator`（交付物是 skill 或其模型效果评估）、`receiving-code-review`（当前席位收到评审意见）、`frontend-design`（明确的视觉设计）和 `vercel-react-best-practices`（实际相关的 React/Next.js 代码）。仅在匹配时用 skill 工具加载，按当前设计/实施/评审席位分配；不要把几份上游全文一起塞给无关的子代理，或用加载回执冒充验证。

技能目录不是固定白名单。目标建立时、进入新的技术/验收边界时、方案受挫时及最终验收前，按 `../mvp-delivery/references/subagent-orchestration.md` 的 **Skill Applicability Selection** 执行有界选择；同一边界没有变化时复用已作出的适用性判断：

1. 先看当前 OpenCode 会话实际提供的 skill 清单/skill 工具能力；若当前会话提供不了清单，再检查当前项目与已注册 skill roots 中可读的 `SKILL.md` frontmatter 和 description。不能仅凭文件存在声称 skill 已加载或可用。
2. 从运行时实际可见的**全部现有 skill**中筛选匹配本目标或当前边界的能力。新加入且当前会话可见的 skill 自动纳入候选；禁止维护一份需要手工更新的 work skill 名称清单。
3. 阅读候选 skill 的 description 与适用规则，只加载对当前工作包或边界有实际职责的能力，并执行其职责；不适用者不加载，只有有意义的交接才需记录跳过原因。不要为了“调用全部 skill”运行与目标无关的流程。
4. 每次阶段/边界改变，重新检查此前排除的技能是否变得适用。安装或修改后宿主尚未加载的新技能属于 capability-unavailable；如重启能使其出现则如实说明，不得假装使用。
5. `stage-routing.json` 是具体工程阶段和条件领域能力的强制最低路由，不限制其他动态发现的匹配 skill。角色必需 skill、独立席位及其权限边界不得被动态选择绕过。

需要专业席位时，遵守 `../mvp-delivery/references/subagent-orchestration.md`。加载 skill 不等于形成独立判断或通过验收；reviewer、observer、worker、Audited step-executor 等席位按现有协议派发，父会话不可冒充独立席位。

每个有意义的工作交接用精简 `SKILL_USE` 记录必需/所选能力、用途、实际结果证据及跳过原因；仅加载回执不算结果证据。调用全部可用 skill 不是目标，覆盖所有实际适用能力才是。

## 规划、执行与产物

- 有界、可逆且目标明确的小改动直接做：定位受影响处 → 最小修改 → 运行相关检查或观察实际结果 → 对照原目标收口；不为其强制创建 goal、brief 或 plan 文件，也不为了走流程拆成多个施工包。
- 多步骤、跨模块或高不确定工作加载 `writing-plans` 制定可执行路线。仅在需要跨任务交接、持久恢复或正式 gate 时发布工程计划和目标卡；否则路线留在会话中。目标变化或设计假设被证伪时，带新证据重规划，然后由本 `/work` 循环自动恢复执行；重规划本身不要求用户重新发命令。
- 当现有 goal-card、工程计划、Audited contract/PLAN、UI acceptance、product-observation、owner decision 或 runtime gate 是目标/严谨级别的要求时，按 `mvp-delivery`、`contract-review`、`construction` 及其引擎流程保存必要产物。不得为了“无文件”绕过正式 gate。
- 其他情况不因访谈/计划/内部状态而新建文档。首先用会话中的 `WORKING_GOAL` 与简短进度视图；只有目标本身要求文件、已有流程必须持久化、跨会话恢复需要，或用户要求交付计划/记录时才写对应文件。不得生成没有目标价值的第二套状态机或重复需求清单。
- 执行每个工作包后运行适当检查，读取真实输出并与预期比较。根据证据继续下一个结果，不以测试数量或产物数量代替用户目标。
- 发现实现错误，加载 `systematic-debugging` 并最小修复；接口/架构/关键前提被证伪，进入 `writing-plans` 修订。重复失败遵循 PUA 与既有 no-progress / failure-signature 熔断；新计划、新会话或新席位不得清零失败计数。
- 结果未知的外部副作用先回读目标状态再重试。没有真实边界、权限、后端或审批时诚实阻塞，不用 mock 冒充真实通过。

## 继续条件、完成与报告

每次操作后回到原始 `WORKING_GOAL`，核对仍未满足的必需结果并继续。新发现的可选项不自动加入范围；明确目标不能通过改名、降级或塞进 deferred 来缩水。agent 假设可被事实修正，用户明确约束不能被静默改写。

完成必须有与当前候选版本绑定的实际证据，并执行适用的全目标验证、UI 旅程、独立 review/product observation 和正式 gate。候选修改使证据失效时重跑受影响及最终检查；阻断观察先修复再对新候选重新观察。

仅在以下任一条件成立时停下：

- 所有原始必需结果均已验证，完成适用的最终验收；
- 需要真实 owner 决定、授权或外部前提，已完成可独立进行的工作并保留恢复信息；
- 宿主缺失不可替代的能力，或既有 failure budget/no-progress gate 已触发。

报告清楚区分已完成证据、假设/未验证项、实际阻塞和最小下一步。不要把计划、意图、skill 加载、截图或结构 gate 单独说成目标完成。用户答复解除阻塞后，从持久状态接着完成，不重新开始访谈。
