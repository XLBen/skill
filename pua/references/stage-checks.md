# PUA Stage Checks (index)

本目录定义十类验收的检查卡。每张卡只做主动查漏；实际通过仍由对应的 engine、
reviewer 或 owner gate 决定。加载时只读当前 stage 对应的一张卡，不要整目录
读入。

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

## Cards

| # | stage_id | 何时读 | Card |
|---|---|---|---|
| 1 | `brief-final` | grill 定稿与主控核对 | [`01-brief-final.md`](stage-checks/01-brief-final.md) |
| 2 | `goal-validation` | 目标卡建立与校验 | [`02-goal-validation.md`](stage-checks/02-goal-validation.md) |
| 3 | `contract-release` | Audited contract 释放 | [`03-contract-release.md`](stage-checks/03-contract-release.md) |
| 4 | `plan-confirmation` | Audited PLAN 编译与确认 | [`04-plan-confirmation.md`](stage-checks/04-plan-confirmation.md) |
| 5 | `test-freeze` | Audited 验收测试冻结 | [`05-test-freeze.md`](stage-checks/05-test-freeze.md) |
| 6 | `step-verification` | Audited 步骤执行与 verify-step | [`06-step-verification.md`](stage-checks/06-step-verification.md) |
| 7 | `slice-acceptance` | Audited 切片收尾与 owner SI | [`07-slice-acceptance.md`](stage-checks/07-slice-acceptance.md) |
| 8 | `review-verdict` | reviewer 返回结论前（被派发时） | [`08-review-verdict.md`](stage-checks/08-review-verdict.md) |
| 9 | `goal-verification` | 每个 outcome 的 verify-goal | [`09-goal-verification.md`](stage-checks/09-goal-verification.md) |
| 10 | `goal-finish` | finish-goal 前的 whole-goal 检查 | [`10-goal-finish.md`](stage-checks/10-goal-finish.md) |

## Cross-Stage Branches

- Normal/Guarded 轻量切片验收使用 `review-verdict` 的无契约 handoff 分支，范围
  限当前切片及受影响范围，不要求 reconcile、converge-audit、test manifest 或
  SI 工件；不要把 Audited 专用工件升级为轻量验收要求。Guarded 传
  `pua_stage_id: review-verdict`；**Normal 的风险触发 review 不加载 PUA 卡、
  也不传 `pua_stage_id`**。卡内容描述的“无契约 handoff”分支只适用于被派发
  `review-verdict` 卡的席位。
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
