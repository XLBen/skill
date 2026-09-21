---
name: mvp-delivery
description: Use when the user types /plan, /build, /fix, or /resume, or asks to plan, implement, repair, or continue a project. Plans right-sized work, delivers the thinnest runnable slice first, verifies real behavior, and keeps adding slices until the original goal is met.
license: MIT
metadata:
  language: "zh-CN"
  commands: "/plan <goal>, /build [goal], /fix <problem>, /resume"
  produces: "working product code and verification evidence"
  calls-skills: "i-have-adhd, pua, grill, contract-review, construction, task-worker, reviewer, computer-use, webapp-testing, writing-plans, systematic-debugging, brainstorming, research"
---

# MVP Delivery

把 MVP 当作交付顺序，不当作缩减用户目标的借口：先尽快做出一条真实可运行的
端到端路径，再按价值逐片补齐，直到原始目标达成、用户暂停或出现真正阻塞。

## Default Behavior

收到 `/build <goal>` 后，在同一会话中持续执行：

```text
理解目标 -> 选最薄可运行切片 -> 实现 -> 真实验证
        -> 稳定候选的全产品观察（schema 2 目标：discover/compare）
        -> 发现重大问题 -> 修复 -> 新候选 -> 重新观察
        -> 对照原始目标 -> 下一切片 -> ... -> 完成
```

不要把内部评审、测试、施工和终审能力重新暴露成一串用户命令。不要在每片之间问
“是否继续”。用户请求交付目标时，默认授权的是可逆的工作区内实现与测试，而
不是只交付第一片。

主控是协调者，实现席位按档位解析（权威规则见 `references/stage-routing.json`
的 `responsibilities.implementation_seat`）：**Normal 默认主控同会话直接
实现**；**Guarded 的实质实现默认派 worker 子代理**；**Audited 严格步骤按
seat table 解析为 controller 或 step-executor，从不派 task-worker**。
涉及独立正确性判断或验证盲区时派 fresh reviewer；机械小改由主控直接处理。
正式 `verify-step` 只由主控执行，执行席位只交接实现与诊断结果。所有派发
决定、并发限制、角色映射、失败分支和恢复记录统一遵循
`references/subagent-orchestration.md`，派发与返回格式遵循
`references/subagent-templates.md`。阶段→能力→席位的权威映射是
`references/stage-routing.json`：每个实质交接按其确定 implementation seat、
semantic check owner、reviewer mode、`pua_stage_id` 与必读 skill，其他
文档只引用不另立规则。专业验收 skill 经 Skill Applicability Selection 按
验收边界选择。每个 goal 维护
`.opencode/mvp/<goal-slug>.dispatch.json`。

档位差异只改变仪式与席位，不降低证据要求：

- **Normal**：不改变交付行为的任务（纯说明文档、用户不可观察的仓库内部
  整理）可无卡执行；仍需真实验证和诚实交付报告，且不得声称持久
  `/resume` 支持。**凡是会改变交付行为或用户体验的改动（产品代码、
  资源、配置、依赖、影响使用的启动说明）一律建卡**（schema 2，默认
  `product_observation.required: true`），走 verify-goal/finish-goal 与
  product-audit gate；未完成的 schema 1 产品目标在下次改产品前显式迁移
  到 schema 2（定义变化按既有规则使证据失效）。一旦需要跟踪、跨多个
  工作包、跨会话、属于 Guarded/Audited 或用户要求建卡，就先建卡并
  校验再改产品。
  相关测试与真实 demo 必需；worker 委派、独立 test-author、PUA 阶段卡、
  逐 slice reviewer 都不是必需；涉及独立正确性判断、验证盲区或用户要求时
  派 fresh reviewer。
- **Guarded**：必须有卡；加有预算探针、受影响范围验证和一次独立 review；
  同一版本同一范围的结论可复用，不逐阶段重复。
- **Audited**：契约、PLAN、独立 test-author、逐步/收敛审计与 PUA 卡按既有
  规则执行。

只有以下情况停下来问：

“停下来问”是真实交互：优先通过宿主的交互询问（OpenCode 的 `question`
工具）发出，否则以明确问题结束当前回合并等待用户下一条消息；禁止替用户
作答后继续，也不把 agent 自己的推断记成 owner 决定。

- 两个互斥的产品选择会明显改变结果，且仓库和用户输入都无法裁决；
- 将执行不可逆或破坏性操作；
- 涉及凭据、隐私、安全边界、真实付费或工作区外副作用；
- Audited gate 需要 owner 实际验收、生成后的 PLAN 确认或真实独立评审；
- 原始目标在技术上不可达、每条前进路径都只能猜，或连续尝试没有产生新证据。

其余不确定性由 agent 作最小、可逆、符合现有代码模式的决定，简短记录在最终
报告中并继续。

## Communication And Acceptance Handoff

用户沟通默认加载 `../i-have-adhd/SKILL.md`。它只改变展示方式，不决定派发、
不改变目标、证据、engine gate、owner 决定或 reviewer 独立性。用户看到的是
短视图，reviewer 收到的是完整交接包。每个有实质结果的阶段交接：

1. 主控制器先建立完整 `ACCEPTANCE_HANDOFF`（原始目标、完成声明、验收项、
   当前产物身份、证据、已知缺口、owner 决定、真实用户入口）。字段定义见
   `../i-have-adhd/SKILL.md`。
2. 受影响 outcomes 包含界面旅程时，执行 UI 验收：目标卡声明
   `goal.ui.required`，主控在 `.opencode/mvp/<goal-slug>.ui-acceptance.json`
   （schema `ui-acceptance/1`）记录并执行必需场景，规则见
   `../computer-use/references/ui-acceptance-protocol.md`。Web-only 旅程优先
   加载 `../webapp-testing/SKILL.md`（专用浏览器自动化与断言式脚本）；
   原生桌面/OS 对话框走 `../computer-use/SKILL.md`。缺后端/权限置
   `blocked`，不得判不适用，也不得删除 sidecar；产物变化后重跑并重新绑定。
3. 用 `acceptance-preview` 告知用户正在验收什么；不能在 reviewer 返回前宣布
   阶段通过或整个目标完成。普通实现中的无实质进展不发送重复消息。
4. 按 `references/stage-routing.json` 决定本交接点是否派 fresh reviewer：
   Guarded/Audited 实质验收点能力可用即必须派发（不受成本裁量豁免），传入
   `pua_stage_id` 与完整交接包（含 UI sidecar 摘要）；Normal 只在独立正确性
   判断、验证盲区或用户要求时派发；无既有 mode 时使用通用 read-only
   acceptance review，不新增角色或 event schema。同一版本、同一范围的结论
   可复用。加载 skill 不能冒充独立身份。
5. 控制器核对 reviewer 证据：`repair` 修复并复验受影响范围（含受影响 UI
   场景），`owner` 保留 owner gate，`blocked` 停止并报告；只有既有 engine/
   owner gate 和 reviewer 结果都满足后才继续。
6. 用 `delivery` 输出结果、关键验证、位置、限制和一个下一步；未满足时用
   `progress` 或 `blocker`。完整交接包不能被五项展示上限裁剪。

没有可用 fresh reviewer seat 时，Guarded/Audited 记录 capability-unavailable
或按路由阻塞；Audited 的独立性要求不能降级。不为 Normal 的每条进度消息制造
reviewer 或 PUA 仪式；唯一豁免是 mechanical-batch（机械小改合并）。

## Command Modes

- **Plan Mode (`/plan`)**：检查仓库，把参数或明确指定的 `docs/brief.md` 转成
  `.opencode/mvp/<goal-slug>.md`；只规划，不写产品代码。Normal/Guarded 使用
  轻量目标卡，其首片 brief 按 `../writing-plans/SKILL.md` 写成可执行 prompt
  （Context、精确 Files、Change 草稿、Bounds、Verify、Rollback）；方案形态
  存在实质分叉时先加载 `../brainstorming/SKILL.md` 与 owner 收敛。Audited 在
  内部加载 `contract-review`。界面旅程只设计不执行。
- **Build Mode (`/build [goal]`)**：解析并复用已有目标卡；无参数时读取唯一
  active 目标卡或严格 PLAN。持续实现、验证并自动收尾，直到原始结果清单
  verified。
- **Fix Mode (`/fix <problem>`)**：复用相关目标卡，按
  `../systematic-debugging/SKILL.md` 的四阶段（复现/隔离/假设/验证）完成
  复现、定位根因、最小修复，加回归测试并验证；严格契约与现实冲突时内部执行
  CR 恢复。
- **Resume Mode (`/resume`)**：从持久状态恢复，不从聊天猜进度；读取顺序与
  上下文压缩规则（delivery-log 优先、已完成工件停止默认加载）见
  `references/delivery-finish.md`，最小恢复读取集见
  `references/subagent-orchestration.md`，失效与续跑规则见
  `references/delivery-recovery.md`。

## Establish The Target

先读仓库、现有文档、测试和最近相关实现，再决定是否提问。不要问能从代码、
配置、错误输出或一手文档查到的事实。明确谁在什么环境下、从哪个公开入口
输入什么、在哪里取得可用结果；库的公开调用、CLI、API 消费者都是有效入口。
需求已明确时不提问，直接宣布首片并开始；一次只问使最终成功可观察所必需的
问题。用户明确要求深度澄清时加载 `grill`。

目标卡与校验规则见 `references/goal-definition.md`（卡片 schema、source/
coverage、`user_entry`、brief 校验、engine 命令、证据失效）。核心不变量：

- 改产品前先解析 `.opencode/mvp/<goal-slug>.md`：复用匹配的 active/blocked
  卡（含 `/fix`），绝不创建第二个 active 卡；仅对真正的新目标建卡。完成卡与
  历史包保持不可变，不重开历史来满足 gate。
- Normal 无卡任务按上面的档位规则执行；建卡后必须成功校验当前未完成卡再改
  产品。
- 需求/定义变化触发全量失效；改产品前按受影响 outcomes 置 pending 并清除
  运行态证据引用/blockers（保留证据文件）。
- Audited 包路径与 contract/PLAN/reconcile hash 只存 dispatch record，不写进
  goal JSON。

Guarded 建卡或续跑前执行 PUA `goal-validation` 卡（Normal 直接问同样的问题，
不加载卡）；Audited 建卡走 contract-review 的 contract-release/plan-confirmation。
规则见 `references/goal-definition.md`。

## Rigor By Slice

按当前切片风险选择最轻但足够的强度，不把整个项目粗暴分成“零流程”或“全流程”：

- Normal：可逆的工作区内改动；相关测试、真实 demo，以及需要跟踪时的卡片。
- Guarded：外部边界、兼容性或较高返工风险；有预算探针、验收测试和一次独立
  review（能力可用即必须；不可用记录 capability-unavailable 并披露）。
- Audited：资金、隐私、安全、迁移、不可逆副作用或用户明确要求；加载
  `contract-review` 建立只覆盖当前片的不可变契约、PLAN、ledger 和 CR 文件，
  按既有规则执行 test-author、逐步审计与 PUA 卡。本 skill 仍是总控制器，
  完成 gate 后自动继续实现、验证和后续切片。

风险按实际操作判断，不按主题词判断。风险下降后的下一片可以回到较轻强度；
goal 顶层 `rigor`/`risk` 是累计风险下限，不等于当前切片强度。当前切片的
强度、依据与活动包指针持久化在 dispatch record 的 `active_slice`，每次切片
结束先重判下一片风险；`/resume` 用同一记录恢复，不因历史出现过 Audited
切片而永久锁档。

## Choose A Walking Skeleton

首片必须让用户或下游系统观察到一个有意义结果：一份具体输入穿过必要层到达
真实输出或持久状态；能用一条命令、浏览器操作或 API 调用演示；包含最少基础
设施；不用 mock 的成功代替目标声明的真实边界；通常一个工作会话内完成。
外部假设可能让方向作废时，先做有预算的小探针再进入首片，默认不创建 Phase 0
模板、契约节点或 event ledger。

## Build Continuously

实施前主控核实最少运行前提：工作目录、OS/shell、运行时与包管理器、依赖及
锁文件、配置变量名、服务、初始化数据和启动方式。复用仓库约定，不依赖未声明
的全局包或手工准备的数据，不记录密钥值。缺依赖或服务不是行为 red，不能用
mock 冒充真实边界。详细执行规则见 `references/delivery-execution.md`。

1. 为当前切片创建少量可执行 todo，不为完整远期路线展开大计划。
2. 首片实现前，把为推进而准备自作的全部可逆假设（brief 未覆盖、仓库无法
   裁决的边缘选择）列成一份简短假设清单，一次性给 owner 扫认或纠正；
   未获回应时按“最小可逆决定”继续并把清单原样附在交付报告中。假设清单
   是一次确认动作，不逐条阻塞，也不新增持久工件。
3. Guarded 的实质实现默认派 worker 子代理；Audited 严格步骤按 seat table
   解析（controller 或 step-executor，禁止 worker）；Normal 允许主控直接
   实现。主控负责拆解、交接、集成与复验，不把 worker 的返回当作验证
   通过。机械小改合并后主控直接处理。派发给执行席位的任务正文按
   `../writing-plans/SKILL.md` 的 step brief 组织。
4. 先实现最短正确路径，遵循仓库现有结构；避免无关重构和预防性抽象。
5. 测试策略与风险相称；不要为了角色仪式强制生成独立 manifest。
6. 运行最窄相关测试，再运行真实 smoke/demo；测试必须检查内容、状态或不变量。
7. 必要产物缺失、为空或为零时默认失败；只有目标明确 semantic zero 才通过。
8. 失败时先读错误并修根因；失败计数绑定“子目标 + 归一化失败签名”跨
   seat/task/resume 累计，同签名三次无新证据即 no-progress blocker，向用户
   升级而不是机械重试。恢复分级见 `../pua/references/recovery-protocol.md`。

独立测试作者仅在 Audited 流程（contract-review/SI/FIX 包）触发；reviewer 在
Guarded/Audited 实质验收能力可用即必须派发，Normal 仅风险触发；两者都由
`references/subagent-orchestration.md` 的触发矩阵与 `stage-routing.json` 的
`responsibilities.semantic_checks` 统一决定，mechanical-batch 豁免；不按
“风险值得成本”裁量。Normal/Guarded 默认不创建 contract/PLAN/ledger/
observation/ceremony 工件；Audited 切片按规则借用严格 gate，但本 skill 保留
连续交付控制权。

## Converge On The Original Goal

每个切片通过真实验证后，更新目标卡并回看最初的 Goal、结果清单和 Deferred：

1. 列出仍阻止用户达成原始目标的差距。
2. 选择价值最高或风险最大的下一条薄切片。
3. 保留已通过行为，增量实现并验证下一片，先重判下一片风险再选执行方式。
4. 重复，直到原始目标满足或命中明确停止条件。

Audited 切片的 finish 只关闭该片；随后由主控重判下一片风险：Normal/Guarded
继续轻量执行，只有 Audited 下一片才走 contract-review 的新包/SI 流程，且
SI 需要 owner 对已观察切片的实际验收、增量决定和新 PLAN 确认（进入 SI 前
执行 PUA `slice-acceptance` 卡，见 `references/delivery-recovery.md`）。
实现中发现的新想法默认不扩张目标；原始目标内被延后的内容必须继续处理。必需成功结果不能
藏入 `deferred`，也不能把真实设备/API 目标改成样例目录或 mock；缺实现与缺
验证分别记录。可选愿望不应假装成 BS 后静默删除；范围改变需重新明确确认。
完整失效、修复与续跑规则见 `references/delivery-recovery.md`。

### PUA Acceptance: `goal-verification` and `goal-finish`

Audited 目标（或证据缺失/可疑时）在 `verify-goal` 前加载 `../pua/SKILL.md`
执行 `goal-verification` 卡；`finish-goal` 前执行 `goal-finish` 卡，对照原始
请求/每个 brief BS、整个 goal、deferred、最终集成路径、隔离复跑和剩余限制。
Normal/Guarded 的同一比较是主控直接职责，不强制 PUA 卡仪式。缺实现、缺验证、
owner 决定和外部阻塞保持区分。

## Finish With Evidence

在最后一次产品/依赖/配置改动后，对同一待交付版本运行关键用户路径集成验证、
受影响回归和适用的 lint/build；每个承诺的用户可见结果都需实际入口覆盖。
`finish-goal` 前建立 `ACCEPTANCE_HANDOFF` 并对照原始请求或 brief（每个 BS）、
整个 goal、deferred 和真实用户旅程；slice clean 不能替代 whole-goal。按需
复用 reviewer 做范围检查。细节、engine 命令、runtime/UI gate 和最终报告
格式见 `references/delivery-finish.md`。核心边界：

- 用新的 evidence 路径重新 `verify-goal`；完成卡/历史包不重开。
- schema 2 且 `product_observation.required` 的目标，`finish-goal` 前必须
  通过 `check.py product-audit-gate <goal>.md --trace .opencode/mvp/trace.json`
  （必须带原生 trace）：独立 observer 的 discover 与 compare 结果由
  controller 采纳（`product-observation/2`，采纳时校验并绑定身份、写入
  不可变 result；observer 只回一个 json 围栏块、不写结果文件）并绑定当前
  候选版本、phase packet 归档且 hash 匹配、reviewer 充分性结论
  （`product-observation-review/2`，findings_validity/coverage_adequacy，
  verdict `sufficient`，discover/compare hash 由 controller/引擎绑定）齐全、
  无未解决 critical/high 发现、无未解决能力缺口。修复产生新候选并使旧
  观察失效；观察后端缺失是 `blocked`，绝不转 not-applicable，也不得由
  controller 复述冒充观察结果。协议见
  `../product-observer/references/observation-protocol.md`。
- 检查实际 diff，确认没有为跑绿而弱化测试、硬编码样例、吞错或未接通路径。
- 新产品缺 README/quickstart 时创建，已有则更新可执行 setup 与依赖，并按
  声明产物在隔离环境复跑；借用全局依赖不算干净安装。
- 引擎不可用时在所有档位报告 blocker；不伪造成功。hash 只检测旧绑定，不证明
  产品正确性或身份；ID 只是声明。selftest 不是产品可用性证明。
- 完成后按 `references/delivery-finish.md` 的 Delivery Log And Context
  Compaction 追加 `docs/delivery-log.md` 条目，压缩会话上下文。

## References

| Need | Read |
|---|---|
| 目标卡 schema、source/coverage、brief 校验、engine 命令、证据失效 | `references/goal-definition.md` |
| 构建循环细节：依赖准备、测试策略、失败预算、UI/GUI、Web 验证 | `references/delivery-execution.md` |
| Finish 细节：集成验证、README、隔离复跑、runtime/UI gate、报告格式 | `references/delivery-finish.md` |
| 恢复与续跑：resume、失效、CR/FIX 包、deferred 与范围变化 | `references/delivery-recovery.md` |
| 阶段→能力→席位权威路由（stage、reviewer mode、pua_stage_id） | `references/stage-routing.json` |
| 委派触发矩阵、角色映射、并发、失败分支、dispatch record、最小恢复读取集 | `references/subagent-orchestration.md` |
| 派发/返回/返修模板（TASK_RESULT、CONTROLLER_ACTION） | `references/subagent-templates.md` |
| 独立评审协议（reviewer modes 与输出 schema） | `../contract-review/references/reviewer-protocol.md` |
| 轻量实现席位（worker 子代理加载） | `../task-worker/SKILL.md` |
