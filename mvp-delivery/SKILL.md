---
name: mvp-delivery
description: Use for /build, /fix and /resume, or the engineering handoff from /plan. Executes a complete planner-authored design one bounded task at a time, checks components, real boundaries and integration milestones at the correct stage, and returns design conflicts to planning instead of asking an implementation model to redesign.
license: MIT
metadata:
  language: "zh-CN"
  commands: "/plan <brief>, /build [goal], /fix <problem>, /resume"
  produces: "working product code and observed verification evidence"
  calls-skills: "writing-plans, systematic-debugging, task-worker, reviewer, computer-use, webapp-testing, contract-review, construction, i-have-adhd, pua"
---

# Delivery：按设计施工，用实际结果推进

主路径：**grill → plan 完成工程设计 → build 执行当前任务 → 观察反馈 → 下一任务**。
MVP 是交付顺序，不缩减原始目标。让规划阶段承担跨模块判断，让实现模型做有界工作。

## 最少上下文

- `/plan`：加载 `writing-plans` 为主流程，不加载整个施工/审计体系后才开始设计。
  发布阶段才读 `references/goal-definition.md`。完整计划必须能独立阅读。
- `/build`：本文件 + `references/engineering-delivery.md` 读一次；之后主要读
  `check.py next-step <goal>` 给出的任务包、其中的源码和实际输出。
- `/fix`：当前任务包 + `systematic-debugging`；不重走全部 grill。
- `/resume`：delivery-log（若有）→ 当前目标/设计绑定 → next-step；不默认重读
  所有历史计划、已完成任务、审计报告和全部 skill。
- 专用 skill 按实际边界加载。只有进入 Audited/派发/最终验收时才展开相关协议。
  技能多不等于质量好；重复分析与无关上下文会增加较弱模型的负担。

## Plan Mode：工程设计者

需求输入为实际确认的 brief；没有 brief 但需求已清楚时直接建立对应结果，不强制
重做采访。需求不清才用 grill。`writing-plans` 负责：
1. 综合用户工作流，核实环境、真实依赖与高风险技术假设。
2. 设计组件、状态/数据模型、共享接口与逻辑图，明确复用方案。
3. 为**全部任务**写依赖、最少输入、文件职责、实现步骤、关键代码和分层验证。
4. 正常/失败输入走查、跨任务接口一致性检查，消除留给 build 的架构决定。
5. 发布完整设计和可执行任务索引；给用户设计链接，不仅是 grill 回答摘要。

默认 `docs/plan.md`，用户指定项目内路径可直接用。新设计使用 engineering-plan/3；
`prepare-plan` 自动绑定目标、推导 UI 义务和版本信息。无需用户或 build 手填 hash。
计划本身不执行产品实现。探测发现设计条件不成立时，修订设计后再交接。
新计划采用 engineering-plan/3：只放行条件成立的步骤；探针前提不允许依赖本步
新建脚本。完整路线可以条件性发布，不代表架构可行性与用户可接受性都已通过。

## Build Mode：有界执行者

复用唯一匹配的 active/blocked 目标；不另造一个活动目标。无计划先执行完整 plan
阶段，不能用一句“最薄首片”代替。新产品用 schema-3 目标与工程设计，完成历史
保持只读；旧工件处理见恢复协议，不把迁移工作当作新项目主流程。

### 每步的固定循环

```text
next-step → 当前任务包
    ↓ begin-cycle：仅探测本步必要外部前提
按合同实现本步 → 少量相关测试 → verify-cycle
    ↓ 组件检查 / 真实边界检查 / 本阶段旅程（由计划指定）
看实际输出 → observe-cycle：advance / retry / blocked / replan
    ↓
next-step 选择下一依赖就绪任务，直到 final-acceptance
```

- 主控不重新划分模块/换技术栈/改接口；任务包固定 read_files、files、consumes、
  produces、implementation、change、checks。局部实现细节按仓库习惯处理。
- 一次只推进一个未观察任务。先写并运行少量关键行为测试，再实现/修正；不用为
  每一行代码写测试，不在第一次接触真实目标前铺完所有新测试/实现。
- component 通过只表示组件成立；boundary 必须用实际目标；journey 经交付入口
  完成用户动作并回读结果。普通组件不强制启动尚未完成的完整 UI。
- 负向对照按计划选择关键故障，不是每步必须另写非零退出码脚本。已有回归可批跑。
- verify-cycle 回传真实 stdout/stderr/退出码；读取完整输出引用（截断时必须展开）。
  observe-cycle 的原始观察由工具附加，模型只写预期/实际的解释和决策。
- 缺设备/驱动/服务就是 blocked；不能换成 mock 后通过。截图、点击成功、测试
  文件数量都不能单独证明用户目标成立。UI 的可见变化/持久结果才是成功信号。
- 未知结果不等于动作失败：外部写入后回读失败，先核对是否已生效再决定重试。
  不能把“发送无异常”当成功或把“标签未找到”直接归因为输入注入失败。

### 失败分类（先归因再行动）

| 证据 | 动作 |
|---|---|
| 本步实现不满足既定接口/断言 | retry：最小修复本步，重跑相关检查 |
| 环境/目标不可达，有真实错误 | blocked：给具体前提；不扩大实现或削弱断言 |
| 接口、状态模型、驱动能力等设计假设被证伪 | replan：附实际结果，停止受影响路线，返还 planning 修订 |
| 测试配置错/零用例/导入失败 | 修复验证环境；不把它算业务 red 或产品通过 |

replan 可以由同一会话切回设计职责完成，但必须完成影响分析、更新所有受影响
合同/任务/验证再发布；不能让较弱执行者边猜边打补丁。需要更强模型时明确交接包，
不虚构可用模型、不擅自配置 provider。用户切模型后仍从持久任务包恢复。

同一失败签名第二次必须换证伪方法；三次无新证据停止机械重试，执行
`../pua/references/recovery-protocol.md`。新 task/session 不清零失败历史。

### 用户中途改变判断

用 request-decision 记录问题/影响并暂停新操作，保留当前 attempt；明确答复后
resolve-decision 引用实际原话与演示/审查证据。accept 恢复原任务，不冒充测试
通过；revise 回 plan；reject 保持阻塞。含糊回答不能擅自解释，价值决定不能只
埋在 lessons 文档。已有 blocked/replan 足以表示技术阻塞，新增的是决定记录
与恢复路径；细节见 `references/planning-readiness.md`。不因缺 result 就宣称
技术失败；active 且未验证可能只是中断。复盘区分执行回执、转述和未知。

## 风险、席位与上下文成本

风险按实际副作用判，不以主题词决定设计深度。组件复杂度决定计划细度；资金、
隐私、安全、迁移、不可逆操作决定额外审批/审计强度。

- **Normal 默认主控同会话直接**实现；不为每一轮造 reviewer/test-author。
- **Guarded 的实质实现默认派 worker 子代理**，一次派当前任务包，主控集成并运行
  正式验证。一次独立 review 放在有意义的集成/验收点，同版本同范围不重复。
- **Audited** 用 contract-review/construction；按 seat table 选择 controller 或
  step-executor，**从不派 task-worker**。独立 test-author/编译 PLAN/CR 保留。
- Guarded/Audited 新计划在 implementation 开始前还需解除独立设计 review 条件；
  未就绪时允许最小 probe 采集证据，不能靠结构 PASS 提前施工。
- Guarded/Audited 实质验收独立 review 能力可用即必须；不可用按
  capability-unavailable 披露/阻塞，不能拿本会话自审冒充独立判断。
- mechanical-batch 豁免和具体权限按 `references/stage-routing.json` 与
  `references/subagent-orchestration.md`。派发正文按
  `references/subagent-templates.md`，可附 next-step 任务包而非整套大计划。

**任务内验证不等于阶段验收。**除明确独立正确性/风险触发，不把每个组件测试都
升级成一次完整产品观察、独立审查和 owner 确认。

## 原始目标与最终验收

每个集成里程碑回看原始结果清单：已接通什么、哪些仍缺实现/验证；继续既定依赖
路线。不能因为首片可跑就结束，也不临时加入可选愿望。计划/目标变更显式发布，
不把必需结果塞进 deferred。交付前在最终同一版本完成：

1. cycle-gate：计划任务都已检查并观察；缺步骤不能完成。
2. verify-goal：每个必需 outcome 经真实入口覆盖，受影响回归及 lint/build。
3. 适用 UI 场景（Web 用 webapp-testing，原生用 computer-use）：真实后端、
   产物绑定及原生调用证据；缺后端保持 blocked。
4. required 全产品观察在**完整稳定候选**执行 discover/compare，
   `product-observation/2` 及 reviewer 的 `product-observation-review/2` 结果通过
   product-audit-gate；缺原生 trace、能力缺口、未解决阻断发现均不放行。
5. 既有 runtime/owner gate 满足后 finish-goal，追加 delivery-log。

具体命令、UI/观察版本失效见 `references/delivery-finish.md`，不在普通任务反复
读取其完整规则。修复使候选变化后重跑受影响任务和完整最终观察，不能覆盖旧证据。

## Communication And PUA Acceptance

用 i-have-adhd 展示短进度；设计正文和证据不裁剪。实质验收点的
ACCEPTANCE_HANDOFF 含原始目标、完成声明、版本、分层验证、真实入口、缺口。
先 acceptance-preview，reviewer/门禁通过后才 delivery。
阶段路由需要时传 `pua_stage_id`；`goal-validation`、`goal-verification`、
`goal-finish` 的卡按风险加载，Normal 直接检查同样事实；Audited 的
`slice-acceptance` 保留真实 owner 接受。记录格式不是产品正确性的替代。

最终报告分开说明：组件/mock 检查、实际边界、公开旅程、未验证范围。不要只报
“1200 个测试通过”。哈希只证明版本一致，结构 PASS 不是产品/模型质量认证。

## 什么时候问用户

产品选择相互排斥且无法由已知需求裁决；不可逆/破坏性动作；凭据/隐私/真实付费
或工作区外副作用；Audited owner gate；技术不可达或无进展阻塞。
使用真实 question 或等待回复，不替用户作答。其余局部可逆决定记录后继续。

## 按需引用

| 需要 | 读取 |
|---|---|
| 设计流程、模板、走查 | `../writing-plans/SKILL.md` |
| 任务包、分层检查、自动记账命令 | `references/engineering-delivery.md` |
| 条件性设计、前置工具、设计审查、用户中途决定 | `references/planning-readiness.md` |
| goal/brief 定义、来源与覆盖 | `references/goal-definition.md` |
| 运行前提和失败预算细节 | `references/delivery-execution.md` |
| 最终验收与交付记录 | `references/delivery-finish.md` |
| 版本失效和恢复 | `references/delivery-recovery.md` |
| 审计阶段与委派 | `references/stage-routing.json`, `references/subagent-orchestration.md` |
