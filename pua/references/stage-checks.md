# PUA Stage Checks

本文件定义十类验收的检查卡。每张卡只做主动查漏；实际通过仍由对应的 engine、
reviewer 或 owner gate 决定。

## Card Format

进入检查卡时先记录：`stage_id`、执行角色、目标/切片、当前制品身份、检查范围和已有证据。
随后执行“质询与动作”，返回 `acceptance-protocol.md` 的格式。

## Card Roles And Gate Phases

每张卡区分两类证据，执行者不得混淆：

- **门前证据**（pre-gate）：检查卡执行时必须已经存在的证据。由主控在派发
  前准备，或由卡的执行席位自己产生。
- **门后证据**（post-gate）：卡的检查通过后、由主控执行的 engine/owner
  gate 所产生的证据（release、confirm-plan、verify-step、finish-goal 等）。
  它们只用于最终交付核对，**不作为任何检查卡（包括由 reviewer 执行的卡）
  的必需输入**。

卡的执行角色分两种：

- **执行席位**（grill / mvp-delivery / construction / test-author /
  step-executor 的当前会话或其子代理）：执行质询动作，可运行自己有权运行
  的命令。
- **只读席位**（reviewer 子代理）：只消费门前证据；缺少 gate 输出时通过
  CONTROLLER_ACTION（`../../mvp-delivery/references/subagent-templates.md`）
  请求主控补证，不自行执行 engine 命令，也不把“未来的 gate 输出缺失”
  记为缺口或形成等待循环。

## 1. `brief-final`

**位置**：`grill/SKILL.md` 的 Brief final；`/grill` 命令结束处。

**输入**：当前 brief、JSON item、frontier、用户确认内容。

**质询与动作**：

- “这份 summary 是用户说的，还是你替用户补的？”逐项对照事实、决定、假设、成功信号和非目标。
- 未回答的问题必须仍是 open/deferred，不能为了 final 填 owner decision。
- 向用户展示 `this is what I heard`，取得明确确认后才执行 brief validator、hash 和冻结。
- 核对本轮没有因为追求闭环而偷偷缩小目标或把可选愿望改成必需 BS。
- 由 reviewer 席位执行本卡时，只核对已记录的 owner 确认与 brief 证据；与用户的
  确认交互本身仍由执行席位/主控完成，reviewer 不代答也不因未参与交互而阻塞。

**证据**：brief 校验输出、最终 hash、用户确认记录、frontier 清空状态。

**出口**：未确认是 `待 owner 决定`；结构/语义缺口是 `需修复`；不能交给 contract-review。

## 2. `goal-validation`

**位置**：`mvp-delivery/SKILL.md` 的 Establish The Target 和 goal 校验。

**输入**：当前 goal card、原始请求/brief、outcomes、verification 命令。

**质询与动作**：

- “BS 被悄悄缩水、改名或塞进 deferred 了吗？”逐个检查 source coverage 和 disposition。
- 确认每个 outcome 的 verification 是可执行断言，至少一个 `user_entry: true` 走真实入口。
- 检查 owner 决定、原始边界、目标环境和代表性输入没有被 mock、fixture 或内部 selftest 替换。
- 发现定义变化时按既有全量失效规则清 evidence，不在 PUA 检查中手工置 active/verified。

**证据**：`check.py goal` 输出、source/coverage 对照、用户入口说明和验证命令审查。

**出口**：结构 gate 失败交给 engine；语义覆盖缺口保持 pending/blocked；不能用 PUA 结果完成 goal。

## 3. `contract-release`

**位置**：`contract-review/SKILL.md` 的 Phase 0、Release Gate 和 clean final audit。

**输入**：contract、brief dispositions、Phase 0 evidence、review findings、预算报告、证据 bundle。

**质询与动作**：

- “refuted 就是 refuted，谁允许你乐观编译？”逐项核对 probe verdict、真实边界和 stop condition。
- 检查 reviewer 的幸存 issue 是否真的清空；不能通过改措辞、重复相同实验或消除记录来过门。
- 核对每个用户可见结果都有公共接口旅程、E hash、预算实际值和可复跑 handoff。
- 运行现有 contract/release gate 归主控（门后证据，不作为本卡前置输入）；PUA 不能代替独立 reviewer、owner decision 或 engine event。由 reviewer 席位执行本卡时，只核对已存在的 gate 输出，缺失的经 CONTROLLER_ACTION 请求主控补齐。

**证据**：Phase 0 原始观察、reviewer 结论、contract/release 命令输出、事件和 hash。

**出口**：事实/证据问题为 blocker 或 CR；合法 conditional 仍须绑定 owner 决定和追加 V。

## 4. `plan-confirmation`

**位置**：`contract-review/SKILL.md` 的 Plan (Compile And Confirm)。

**输入（门前）**：固定 contract hash、生成 PLAN、选择项、owner 展示摘要。

**质询与动作**：

- “你确认的是刚生成的 PLAN，还是聊天里某个旧版本？”核对 contract hash、PLAN 结构和展示摘要。
- 预算、variant、风险和人工 V 的影响必须显式展示；口头“嗯”不算确认事件。
- 不得因想尽快施工而手写、重编译或静默修改 compiler output。
- `confirm-plan`/`plan --require-building` gate 由主控执行（门后证据），确认后才交给 construction。由 reviewer 席位执行本卡时，只核对已存在的输出。

**证据**：门前——生成文件 hash、展示摘要、owner 决定记录；门后——`confirm-plan` 和 `plan` 输出（主控执行 gate 后补记，不作为本卡前置输入）。

**出口**：缺 owner 确认是 `待 owner 决定`；hash/结构不一致是 `需修复` 或 CR。

## 5. `test-freeze`

**位置**：`test-author/SKILL.md` Invariants/Procedure；`construction/SKILL.md` 的 test-author dispatch。

**输入**：冻结规格、场景、test manifest、pre-change 输出、保护路径和 hash。

**质询与动作**：

- “永远绿的测试也是交付？”确认新行为有真实 behavior-red，回归基线绿有明确分类。
- 检查断言内容/状态/schema/不变量，而不是只看 exit 0、进程存在、日志非空或文件存在。
- 核对每个关键场景真实执行，没有 skip、todo、过滤、空套件、假 fixture 或弱化 wrapper。
- 测试语义或边界变化必须走 CR、独立 test-author 重验、reviewer 和 manifest hash 刷新。

**证据**：逐场景 pre-change 结果、命令/输出 hash、冻结文件 hash、boundary/mock policy。

**出口**：意外绿、基线红、setup blocker 或保护路径变更均不能进入实现，返回具体 blocker。

## 6. `step-verification`

**位置**：`step-executor/SKILL.md`、`construction/SKILL.md` 的 exact V 和 `verify-step`。

**输入**：单步 spec、精确 V、manifest、attempt、原始 V 输出和 failure signature。

**质询与动作**：

- “这一步是真的跑了，还是你手写了一个 passing event？”只接受 engine 生成的 evidence/event。executor 席位只检查自己持有的证据（manifest、保护路径、诊断运行）；engine 生成的 `verify-step` evidence/event 属门后证据，由主控在 construction 侧执行本卡时核对。
- 检查所有 manifest-required 场景、子进程状态、输入快照、内容断言、重复运行和 cleanup。
- 失败一次读根因；第二次同类失败换实质方法；第三次按既有熔断，不做第四次普通重试。
- executor 只返回原始结果、偏差和 blocker；不宣布 step complete、不写 ledger、不修改冻结测试。

**证据**：`verify-step` 输出、engine event/evidence、原始 V、attempt 和 signature。

**出口**：通过交给 controller；失败交 recovery/CR；不允许用 PUA 文字覆盖机器 gate。

## 7. `slice-acceptance`

**位置**：`construction/SKILL.md` Finish 后和 mvp-delivery 的 SI handoff。

**输入**：clean reconcile、converge-audit、切片观察、真实用户路径、goal 剩余 outcomes。

**质询与动作**：

- “clean 了当前 slice，整件事也交付了吗？”明确当前切片边界和未完成 goal-level 限制。
- 向 owner 展示真实输入、输出、环境、限制和已执行命令，不能以截图或内部标签替代结果。
- owner 必须实际验收观察到的 slice，并分别决定是否进入 SI、范围如何变化、下一 PLAN 是否确认。
- 原始 goal approval 不是未来验收或施工预授权；缺 owner 决定就暂停，不继续猜。

**证据**：reconcile/converge hash、观察记录、真实入口结果、owner acceptance、SI/PLAN 决定。

**出口**：slice done 只关闭当前切片；pending outcomes 返回 mvp-delivery，不宣布 whole goal complete。

## 8. `review-verdict`

**位置**：`reviewer/SKILL.md` Invariants，以及 contract/construction dispatch。

**输入**：review mode、contract-bound 时的固定 snapshot/hash，或无契约 handoff 的
artifact identity、范围和证据；test manifest、工作树 diff、reconcile 和作者记录
按 step/converge 或产品行为适用时提供。

**质询与动作**：

- “审出一个问题就收工？”用冰山法则检查同一根因、接口、共享实现和受影响调用链。
- 评审结论必须有具体证据；不能为凑问题发明要求，也不能为了让 contractor 通过降低严重度。
- 对 step/converge 或实际产品行为检查作者独立性、冻结 hash、行为红先于实现、
  内容/状态断言和 whole-goal 边界；对无产品行为或不适用 acceptance test 的 direct
  路径记录 `not-applicable` 及理由，不伪造 manifest、behavior-red 或作者隔离。
- 无契约 Normal/Guarded handoff 只检查声明、artifact identity、范围、实际证据和
  user-entry；不得把 Audited 的契约字段或 construction 专用工件升级为新要求。
- reviewer 只读，只返回发现；controller 负责裁决、修复路由、owner 和 engine 状态。

**证据**：结构化 reviewer JSON、发现对应的路径/ID/输出、独立派发 provenance。

**出口**：有 material issue 返回需修复；独立性不可用阻断 Audited release；零 issue 也要有完整范围依据。

## 9. `goal-verification`

**位置**：`mvp-delivery/SKILL.md` 的每 outcome `verify-goal`。

**输入**：当前 goal、outcome、真实入口、验证命令、fresh evidence 路径和当前制品身份。

**质询与动作**：

- “你验证的是当前版本，还是过去某个曾经绿过的版本？”核对 evidence 路径、输入、环境和版本身份。
- 每个 outcome 都必须有内容/状态/schema/count/user-visible 断言；不以 exit 0、label 或旧 hash 代替。
- 修复一个 outcome 后检查同一根因和受影响 outcomes；影响不确定时按现有规则全量重跑。
- 真实 boundary 缺失时保持 pending/blocked，不能用 sample/mock 改写目标。

**证据**：每个 outcome 的 fresh `verify-goal` 输出、evidence hash、失败原文和用户入口结果。

**出口**：失败由 engine 置 blocked 并保留 evidence；不能手工写 verified/complete。

## 10. `goal-finish`

**位置**：`mvp-delivery/SKILL.md` Finish With Evidence、`finish-goal` 前；build/fix/resume wrapper。

**输入**：原始请求或 brief、全部 BS、整个 goal、deferred、所有 fresh evidence、README/quickstart、隔离复跑结果。

**质询与动作**：

- “所有结果都拿到了，还是只把首片包装成 MVP 完成？”逐项对照原始范围、每个 outcome、deferred 和真实用户旅程。
- 检查最后版本的集成路径、受影响回归、setup/use 隔离复跑、README、依赖和环境差异。
- 再跑一次主动查漏：测试是否被弱化、是否硬编码样例、吞错、漏接线、同类问题未扫。
- 只有 PUA 检查、适用 Audited gate、owner acceptance 和 `finish-goal` 全部满足，才允许完成；engine 不可用一律 blocker；独立席位不可用按 mvp-delivery 验收章节分档（Audited 独立性 gate 阻塞，Normal/Guarded 记录 capability-unavailable 后按控制器检查披露收尾）。

**证据**：门前——最终版本身份、integrated/user-entry 输出、隔离复跑、reviewer 范围检查；门后——`finish-goal` 输出（主控执行 gate 后补记，不作为本卡前置输入，reviewer 席位不得因它缺失而阻塞）。

**出口**：缺实现与缺验证分别记录；阻塞不能包装完成，完成不能只靠流程工件数量证明。

## Cross-Stage Branches

- Normal/Guarded 轻量切片验收使用 `review-verdict` 的无契约 handoff 分支
  （`pua_stage_id: review-verdict`，范围限当前切片及受影响范围），不要求
  reconcile、converge-audit、test manifest 或 SI 工件；不要把 Audited 专用
  工件升级为轻量验收要求。
- brief 定稿交接（`brief-final`）与轻量计划/目标定义交接（`goal-validation`）
  同样是实质验收交接：能力可用即派 fresh reviewer 执行对应卡；`/grill` 尚无
  goal 时该派发记录保存在 dispatch archive 或等价的 handoff 记录中，不为一次
  评审伪造 goal 卡。
- Phase 0 检查属于 `contract-release`，不要另造一个 release 状态。
- reconcile/converge-audit 检查属于 `slice-acceptance` 和 `review-verdict` 的证据分支。
- GUI 观察属于对应的 `step-verification`、`goal-verification` 或 `slice-acceptance`，截图不是 engine pass。
- `/fix` 复用受影响的检查卡，并额外执行 `recovery-protocol.md` 的同类根因范围检查。
- `/resume` 从持久状态定位当前未完成 `stage_id`，不从聊天里的“已通过”推断。
- 同一 stage、同一范围、同一制品身份下已记录的 PUA 结果可复用；制品实际
  改动、受影响范围扩大或新失败信号才触发重查（见 `acceptance-protocol.md`
  结束条件），不重复制造验收仪式。
