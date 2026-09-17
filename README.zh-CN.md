# MVP delivery skills

**[English](README.md)** · 简体中文

这套 OpenCode workflow 的目标是把想法变成真实可运行结果，而不是让 agent 只把
问题问得很好、最后留下大量规划工件。

## 五个命令

公开入口只保留四个动作命令和一个恢复命令：

| 命令 | 什么时候用 | 结果 |
|---|---|---|
| `/grill <idea>` | 想法还模糊，需要把目标问清 | 经确认的 `docs/brief.md` |
| `/plan <goal-or-brief>` | 需要先看实现路径，不立即写代码 | 轻量目标卡；高风险时内部生成严格 PLAN |
| `/build [goal]` | 开始交付；明确的小任务可直接带目标 | 可运行、经真实验证并持续补齐的结果 |
| `/fix <problem>` | 已有功能报错、行为错误或契约与现实冲突 | 根因修复和回归验证 |
| `/resume` | 上次执行中断 | 从持久状态继续到原始目标完成 |

评审、测试作者、CR、终审和复盘仍然存在，但都是内部能力，不再要求用户记住或
手工接力更多命令。

## 推荐路径

需求明确，直接做：

```text
/build <goal>
```

需要先看计划：

```text
/plan <goal>
       ↓
/build
```

想法模糊：

```text
/grill <idea>
       ↓
/plan docs/brief.md
       ↓
/build
```

出现 bug：

```text
/fix <problem or error>
```

会话中断后只需：

```text
/resume
```

## 为什么不会停在 MVP

这里的 MVP 是交付顺序，不是永久缩减目标。`/build` 先实现最薄的真实端到端
切片，验证后重新对照原始结果清单，再自动进入下一片，直到目标全部完成或出现
必须由用户决定的阻塞。

所有被跟踪的任务使用 `.opencode/mvp/<goal>.md` 的 schema-1 `json goal` 保存目标和验证状态，
结果数量不设上限。单次、有界、无需跨会话恢复的 Normal 任务可以无卡执行
（无 goal 卡、无 dispatch record、无 verify-goal/finish-goal gate），此时证据
保存在当次会话与交付报告中，且不能声称持久 `/resume` 支持。运行态（当前切片强度、派发记录、失败计数与验收裁决）保存在
同目录的 `<goal>.dispatch.json`（schema 2），goal JSON 保持纯定义。brief 输入在所有风险档都必须 final、owner-confirmed 并通过
`brief` 校验，且每个 brief ID 都有 coverage。所有 `kind: success`（BS）只能映射为
`outcome`，不能用 constraint/deferred/non-goal/rejected 隐藏必需成功；其它类型保留
既有 disposition。`goal` 校验卡片，`verify-goal`
逐项执行验证并保存引擎证据，`finish-goal` 才可完成；禁止手写 verified/complete。
任意状态的 goal 都至少有一个 `user_entry: true` 结果，且应验证真实产品入口 demo。
界面旅程用可选 `goal.ui`（`{"required": true, "outcome_ids": [...]}`）在目标卡声明，
作为 UI 验收义务的持久来源；没有界面声明时不需要创建 sidecar。
ID 和布尔标记只提供结构约束，不自动证明语义覆盖或真实边界。

`/fix` 复用相关 active/blocked 卡片，不创建第二个 active 修复目标；已完成包保持
不可变，没有匹配未完成卡时先建新修复卡，不能用读取旧 complete 卡代替当前卡的
`goal` 校验。产品修改前将受影响 outcomes 置 pending 并清除运行态证据引用/blockers，
保留证据文件；定义变化仍全量失效，不重开 complete。修复基线不明确时先问。
失效处理后同步 JSON/frontmatter 状态：仍有 blocked 结果则保持 blocked，否则置 active，
重新校验后再修改产品。
`/resume` 在没有未完成目标而有 draft brief 时继续 grill revision/frontier，不开始施工。
grill 每次问下一轮（含首轮）或暂停前保存并校验 draft，记录访谈模式，默认 checkpoints
按维度分组提问、每轮 5–10 题（上限 10），回答后分析再出下一轮；stepwise 每轮一题。
访谈由十二维需求覆盖表收口：每维要么有 item、要么显式不适用，全维关闭且一轮无新信息才
终止。方案形态存在实质分叉时先经 brainstorming 收敛。draft 的
`owner_confirmation.confirmed` 必须是 bool，`summary` 必须是 string 但可空；
final 必须 confirmed 为 true 且确认 summary 非空。顶层 summary 仍需真实非空。
frontier ID 唯一且只指 open question，不要求列出全部 open question。

## 按风险增加流程

流程强度按当前切片选择，不让所有任务缴纳相同的文档成本：

- Normal：可逆的工作区内改动；相关测试、真实 demo，需要跟踪或恢复时才建目标卡。
  不强制 worker 委派、独立 test-author、PUA 阶段卡或逐 slice reviewer；涉及独立正确性
  判断、验证盲区或用户要求时派一次 fresh reviewer（无契约 acceptance review）。
- Guarded：外部边界或较高返工风险，增加小探针、验收测试和一次独立 review（同一
  版本同一范围可复用）。
- Audited：资金、隐私、安全、迁移或不可逆副作用，内部调用契约、PLAN、CR、独立
  test-author 和 reconcile gate；风险按实际接触的数据/副作用判断，不按主题词。

无论采用哪一档，公开入口仍是 `/plan`、`/build`、`/fix` 和 `/resume`。严格能力
完成后会把控制权交回交付循环，不要求用户换命令。
但自动接力不是预授权：每个 SI 仍需要 owner 对实际切片结果的验收、增量决定和
新生成 PLAN 的确认；审批或风险命令授权可以暂停执行。新 Audited 契约声明顶层
`workflow_protocol: v0.2`，非 human V 必须通过 `verify-step` 产生证据和事件。
切片 clean 不等于全目标完成。总控制器在 finish 对照原始请求/brief 全部 BS、整个
goal、deferred 和真实入口，按需复用 reviewer，不新增公开命令。缺实现与缺验证分别
记录，原始设备/API 边界不能换成样例目录/mock；必需结果 pending/blocked 阻止 complete。
可选愿望不应假装 BS 再静默删除，范围改变需重新明确确认并尊重冻结包。
交付时缺 README/quickstart 则创建，已有则更新可执行 setup 和依赖，并按声明产物在
隔离环境复跑；借用现有全局依赖不算干净安装。披露所测范围，不用“无局限”掩盖缺口。

## 内部 skills

- `mvp-delivery`：`plan/build/fix/resume` 的总控制器，负责持续收敛到原始目标；
  Guarded/Audited 实质任务默认派发子代理，规则见其 `references/subagent-orchestration.md`。
  完成的 goal 按 `delivery-finish.md` 的规则追加 `docs/delivery-log.md` commit 式条目，
  后续会话与 `/resume` 只加载 delivery-log、active 目标卡与代码，已完成的
  brief/PLAN/包全文停止默认加载（上下文压缩重入点）。
- `grill`：深度需求澄清，只生成 brief；按十二维覆盖表收口访谈。
- `research`：外部事实查证（来源分级、引用、时效），服务 grill 与主控的
  “事实归 agent”规则。
- `brainstorming`：方案形态存在实质分叉时的替代方案探索与收敛，位于 grill
  之后、plan 之前。
- `writing-plans`：把计划写成可执行 prompt（Context/Files/Change/Bounds/
  Verify/Rollback 与边界条件清单），嵌入 PLAN 编译、目标卡首片 brief 与
  各席位派发模板。
- `systematic-debugging`：四阶段根因排查（复现/隔离/假设/验证），服务
  `/fix` 与重复失败场景。
- `contract-review`：Audited 切片的契约评审和 PLAN 编译。
- `construction`：执行并收尾 Audited PLAN，处理 CR 恢复。
- `task-worker`：由 fresh subagent 调度时执行一个有界 Normal/Guarded 实现工作包。
- `test-author`：由 fresh subagent 调度时独立生成和冻结验收测试。
- `reviewer`：由 fresh subagent 调度时进行只读评审，含轻量验收与 whole-goal 检查；
  边界条件覆盖是独立检查维度。
- `step-executor`：由 fresh subagent 隔离执行一个严格 PLAN 步骤。
- `webapp-testing`：Web-only 界面旅程的专用浏览器自动化验收（断言式脚本优先），
  产出与 computer-use 相同的 `ui-acceptance/1` 证据。
- `computer-use`：主控制器按需执行真实桌面 GUI 路径（原生应用、OS 对话框），
  观察、操作、验证；Web 旅程优先 webapp-testing，桌面按场景硬预算执行；
  UI 义务由 `goal.ui` 声明，需要另行授权的 MCP。
- `pua`：Guarded/Audited 验收与失败恢复时的主动质询、证据闭环和有界恢复；Normal
  直接执行同样的问题，不替代 engine gate 或 owner 决定。
- `i-have-adhd`：用户沟通层，先给行动和状态；在验收交接前输出 preview，验收后输出
  delivery/blocker；不删除交给 reviewer/PUA 的完整事实。

用户看到的是 `i-have-adhd` 的短视图，reviewer/PUA 收到的是完整
`ACCEPTANCE_HANDOFF`。Guarded/Audited 的实质验收交接自动尝试派 fresh reviewer，并传入
`pua_stage_id`；Normal 由改动风险决定是否派发。没有既有 mode 时使用通用 read-only
acceptance review，不新增角色或
event schema。先 preview、再 PUA/reviewer、最后 delivery 或 blocker。Normal 的普通
进度不制造 reviewer 仪式，且任何简洁格式都不能替代 engine、owner 或独立性 gate。
`i-have-adhd` 不提供公开命令、hook 或全局状态。

安装器会把 `mvp-researcher`、`mvp-worker`、`mvp-reviewer`、`mvp-test-author`、
`mvp-step-executor` 五个项目子代理安装到目标项目 `.opencode/agents/`，分别绑定
调研、轻量实现、只读评审、测试冻结和严格步骤执行，并带各自的最小权限边界
（reviewer 无写入；子代理禁止再派发）。主控按触发矩阵选择席位：实质任务默认
派发，机械小改例外。加载 skill 只会加入说明，不会自动创建独立身份；安装的
agents 才提供真实独立 session。需要作者隔离但子代理能力不可用时，记录
independence unavailable 并阻断 Audited release，不能用 waiver 冒充独立评审；
Normal/Guarded 可在明确披露后由主控降级执行。ID 只是声明，没有密码学身份验证。

## 并发与交回

子代理统一返回 `TASK_RESULT`（schema `task-result/1`）公共外壳，角色专用内容放在
`payload`；主控按字段校验，并按稳定的 `action_id` 去重 CONTROLLER_ACTION，未决或
状态未知的动作不会被自动重放。Normal/Guarded 的独立工作包可在 Git worktree 中并行
写入：`scripts/worktree_tasks.py` 负责准入检查、建立、收集实际改动、`write_scope`
越界核对、补丁预检/集成和清理；共享工作区仍只有一个写入者，所有任务集成后对最终
稳定版本统一验证。Audited 严格步骤沿用既有执行语义，不进入该分支。

## 安装

需要 Python 3.10+。在本仓库根目录运行：

```powershell
python scripts/install.py "E:/path/to/target-project"
```

安装器会复制五个 command wrapper、五个子代理定义（`.opencode/agents/`）、校验
引擎与运行时工具（`check.py`、`runtime_trace.py`、`check_runtime.py`、
`workflow_protocol.py`、`worktree_tasks.py`）以及 `stage-routing.json`，在
manifest 中记录 skills 指纹与已安装文件摘要（供 doctor 检测 skill 文本更新
或安装副本被改动后的漂移），并在 `opencode.json` 分别注册本仓库当前顶层
skill 目录，避免扫描 `validation/` 的冻结旧版同名 skill。升级时替换原先
精确匹配的仓库根 skills path，保留其他配置。旧命令仍未被本地修改时会删除；本地改过的旧命令会保留并提示，
显式使用 `--force` 才会移除。

使用 `opencode.jsonc` 时，安装器保留注释并提示手工添加 skills path。安装或修改
skill 后必须重启 OpenCode。

### 可选桌面验证

已融合 [computer-use-kit](https://github.com/ILoveMyJay/computer-use-kit) 的操作规程，
保留 MIT 授权并适配本项目的风险、证据和子代理边界。无需新增命令，`/build`、`/fix`
或 `/resume` 遇到需要 GUI 的路径时内部加载；纯 Web 旅程优先加载 `webapp-testing`
（Playwright 等专用浏览器自动化，断言式脚本优先），原生桌面/OS 对话框才走
`computer-use`。

安装 skill 不会自动安装或启用桌面 MCP，也不会更改全局权限。建议使用 Cua Driver，
具体接入、默认禁用的配置示例和非敏感窗口 smoke 见 [computer-use/README.md](computer-use/README.md)。
桌面由主控制器独占，子代理不同时操作。截图不等于验收通过，已有引擎 gate 保持不变。
本仓库尚未验证真实桌面后端；缺少工具/权限或可执行验收 runner 时会明确阻塞，不报假成功。

## 验证

```powershell
python scripts/check.py --selftest
python -B -m unittest discover -s tests -p "test_*.py"
python scripts/check.py hash <file> [<file> ...]   # 供 brief/test manifest 等记录哈希；不手工计算
python scripts/check_runtime.py doctor <target-project>   # 静态+宿主能力诊断
python scripts/check_runtime.py doctor <target-project> --strict  # 静态问题或安装副本被改动时退出码 3
python scripts/check_runtime.py doctor <target-project> --strict --strict-freshness  # 额外把 skill 源树漂移视为失败
python scripts/runtime_trace.py export <target-project> --out trace.json
python scripts/runtime_trace.py validate trace.json --dispatch <goal>.dispatch.json
python .opencode/workflow/scripts/check.py check-current .opencode/mvp/<goal>.md  # 只读检查已完成卡的证据是否仍对应当前工作区
```

skill 源树 freshness 默认只是诊断：纯文档改动不会阻塞 `--strict`；已安装引擎/
agents 副本与 manifest 摘要不符会阻塞。需要把源树漂移也当作失败时加
`--strict-freshness`。已完成卡重复运行 `finish-goal` 只代表“历史上已完成”，
不会重新核验当前工作区；需要当前状态时运行 `check-current`。

运行时门禁（可选启用）：在目标项目 `.opencode/mvp/runtime-policy.json` 写
`{"schema": "runtime-policy/1", "goals": "all"}` 后，`finish-goal` 会要求
先运行 `check.py runtime-gate <goal>.md --trace <trace.json>` 并通过——
它用原生会话证据（真实子会话、成功完成的 skill 加载、父子 provenance、
与 trace 中的 task 调用事件关联的 dispatch）核验 dispatch 声明。只有
本机 session store 导出的原生 trace 可以通过；手写/导入 trace、截断导出、
缺证据、席位回退违规、reviewer 返回与 `satisfied` 声明不符，或证据过期
（trace/dispatch/policy 文件 hash 或 goal 定义变化）都会阻塞完成。默认
requirements 是最低要求，策略只能追加不能清空；`allow_independence_downgrade`
对 audited 目标无效。策略文件不存在时保持既有行为；历史完成卡不受影响。

UI 验收门禁：界面旅程由目标卡 `goal.ui.required`（可带 `outcome_ids`）声明，
主控执行 `.opencode/mvp/<goal>.ui-acceptance.json`
（schema `ui-acceptance/1`）中的必需场景并记录真实执行证据（Web-only 旅程用
`webapp-testing`，原生边界用 `computer-use`）；`check.py ui-gate
<goal>.md --trace <trace.json> --bind` 首次绑定产物身份，之后核验场景状态、
computer-use/webapp-testing 真实加载、会话一致的已完成原生调用、存在的
observation/result
文件、policy `ui_tools` 匹配（或 runner 证据）与产物身份。产物变化后必须重置
受影响场景、重跑并重新绑定，`--bind` 不会给旧结果贴新构建；`finish-goal`
重新计算身份并拒绝过期评估。删除 sidecar 或把必需场景标成 not-applicable
不能取消义务；缺后端/权限的场景为 blocked。

严格流程的单项排查命令仍可直接运行 `scripts/check.py`；合法示例位于
`tests/fixtures/`。

在目标项目根目录运行安装后的 `.opencode/workflow/scripts/check.py`；目标验证
命令示例见 `mvp-delivery/SKILL.md`，步骤验证见 `construction/references/step-protocol.md`。
验证命令通过 Python `shell=True` 使用系统 shell，Windows 是 `cmd.exe`，不是
OpenCode 的 PowerShell。执行前检查命令，对破坏、付费、凭据/隐私或外部写入等风险
取得明确授权；引擎不是沙箱。`verify-step` 使用调用者 cwd，必须从项目根运行。

引擎检查结构、绑定、退出/超时和 goal stdout 断言；测试命令仍须真正检查产品行为。
`verify-goal` 记录当前工作区内容快照，`finish-goal` 复算：验证后改动任何非排除
文件都会使结果失效，直到重新验证；验证命令自身改动工作区时结果判为失败。快照
排除 VCS、`.opencode/**`、workflow 工件、缓存和生成目录。hash 不能防止有写权限者
伪造工件，也不证明身份、独立性或真实可用性。`--selftest`
只检验引擎，不是产品 usability 证明。读取 source brief 时，引擎已有拒绝 draft 或
未确认来源的规则，控制器仍需显式验证 final brief 并核对语义，不能把它说成仅提示层约束。

更严格的 confirmation 类型、frontier 唯一/open、任意状态 user-entry 和 BS
disposition 校验可能拒绝旧 active/blocked 卡或 draft。schema 1 和 hash 算法不变，
不自动重写历史卡：继续工作前显式修正未完成工件，定义变化按全量失效规则重新验证；
涉及冻结输入则走 CR/新包。complete 卡和冻结历史保持不可变，即使不满足新规则也不能
伪造“已按新规则重验”，后续修复另建当前卡并保留历史证据。
工作区快照检测“验证后被改动”，但不证明产品语义正确，也不能识别快照排除目录内的
变化。测试仍须检查每次
子进程状态、操作前相关输入 snapshot、结果内容和重复运行稳定性，并按风险用少量故障
注入验证断言能失败；不能把文件名集合未变当作未写入或正确增量。Audited approval
依然不能替代 controller 对最终版本、原始范围、真实入口及安装可复现性的核实职责。

## 设计参考

- [GitHub Spec Kit](https://github.com/github/spec-kit)：独立可验证的 MVP story。
- [OpenSpec](https://github.com/Fission-AI/OpenSpec)：progressive rigor 和增量规格。
- [Superpowers](https://github.com/obra/superpowers)：continuous execution 和真实
  subagent 隔离；本仓库的 writing-plans、systematic-debugging、brainstorming
  适配自其方法论（见各自 UPSTREAM.md）。
- [Anthropic skills](https://github.com/anthropics/skills)：webapp-testing 的
  方法论来源（见其 UPSTREAM.md）。
- [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD)：按任务规模选择流程。

## License

MIT.
