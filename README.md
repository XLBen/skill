# MVP delivery skills

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

所有任务使用 `.opencode/mvp/<goal>.md` 的 schema-1 `json goal` 保存目标和验证状态，
结果数量不设上限。运行态（当前切片强度、派发记录、失败计数与验收裁决）保存在
同目录的 `<goal>.dispatch.json`（schema 2），goal JSON 保持纯定义。brief 输入在所有风险档都必须 final、owner-confirmed 并通过
`brief` 校验，且每个 brief ID 都有 coverage。所有 `kind: success`（BS）只能映射为
`outcome`，不能用 constraint/deferred/non-goal/rejected 隐藏必需成功；其它类型保留
既有 disposition。`goal` 校验卡片，`verify-goal`
逐项执行验证并保存引擎证据，`finish-goal` 才可完成；禁止手写 verified/complete。
任意状态的 goal 都至少有一个 `user_entry: true` 结果，且应验证真实产品入口 demo。
ID 和布尔标记只提供结构约束，不自动证明语义覆盖或真实边界。

`/fix` 复用相关 active/blocked 卡片，不创建第二个 active 修复目标；已完成包保持
不可变，没有匹配未完成卡时先建新修复卡，不能用读取旧 complete 卡代替当前卡的
`goal` 校验。产品修改前将受影响 outcomes 置 pending 并清除运行态证据引用/blockers，
保留证据文件；定义变化仍全量失效，不重开 complete。修复基线不明确时先问。
失效处理后同步 JSON/frontmatter 状态：仍有 blocked 结果则保持 blocked，否则置 active，
重新校验后再修改产品。
`/resume` 在没有未完成目标而有 draft brief 时继续 grill revision/frontier，不开始施工。
grill 每次问下一轮（含首轮）或暂停前保存并校验 draft，记录访谈模式，默认 stepwise
每轮一题，checkpoints 最多三题，绝对不超过五题。draft 的
`owner_confirmation.confirmed` 必须是 bool，`summary` 必须是 string 但可空；
final 必须 confirmed 为 true 且确认 summary 非空。顶层 summary 仍需真实非空。
frontier ID 唯一且只指 open question，不要求列出全部 open question。

## 按风险增加流程

流程强度按当前切片选择，不让所有任务缴纳相同的文档成本：

- Normal：可逆的工作区内改动，只需目标卡、相关测试和真实 demo。
- Guarded：外部边界或较高返工风险，增加小探针、验收测试和必要的独立 review。
- Audited：资金、隐私、安全、迁移或不可逆副作用，内部调用契约、PLAN、CR 和
  reconcile gate。

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
  实质任务默认派发子代理，规则见其 `references/subagent-orchestration.md`。
- `grill`：深度需求澄清，只生成 brief。
- `contract-review`：Audited 切片的契约评审和 PLAN 编译。
- `construction`：执行并收尾 Audited PLAN，处理 CR 恢复。
- `task-worker`：由 fresh subagent 调度时执行一个有界 Normal/Guarded 实现工作包。
- `test-author`：由 fresh subagent 调度时独立生成和冻结验收测试。
- `reviewer`：由 fresh subagent 调度时进行只读评审，含轻量验收与 whole-goal 检查。
- `step-executor`：由 fresh subagent 隔离执行一个严格 PLAN 步骤。
- `computer-use`：主控制器按需执行真实桌面 GUI 路径，观察、操作、验证；需要另行授权的 MCP。
- `pua`：每个阶段验收前的主动质询、证据闭环和有界失败恢复；不替代 engine gate 或 owner 决定。
- `i-have-adhd`：用户沟通层，先给行动和状态；在验收交接前输出 preview，验收后输出
  delivery/blocker；不删除交给 reviewer/PUA 的完整事实。

用户看到的是 `i-have-adhd` 的短视图，reviewer/PUA 收到的是完整
`ACCEPTANCE_HANDOFF`。每个实质验收交接都自动尝试派 fresh reviewer，并传入
`pua_stage_id`；没有既有 mode 时使用通用 read-only acceptance review，不新增角色或
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

## 安装

需要 Python 3.10+。在本仓库根目录运行：

```powershell
python scripts/install.py "E:/path/to/target-project"
```

安装器会复制五个 command wrapper、五个子代理定义（`.opencode/agents/`）和校验
引擎，并在 `opencode.json` 分别注册本仓库当前顶层 skill 目录，避免扫描 `validation/` 的冻结旧版同名 skill。升级时替换原先
精确匹配的仓库根 skills path，保留其他配置。旧命令仍未被本地修改时会删除；本地改过的旧命令会保留并提示，
显式使用 `--force` 才会移除。

使用 `opencode.jsonc` 时，安装器保留注释并提示手工添加 skills path。安装或修改
skill 后必须重启 OpenCode。

### 可选桌面验证

已融合 [computer-use-kit](https://github.com/ILoveMyJay/computer-use-kit) 的操作规程，
保留 MIT 授权并适配本项目的风险、证据和子代理边界。无需新增命令，`/build`、`/fix`
或 `/resume` 遇到需要 GUI 的路径时内部加载；纯 Web 优先使用专用浏览器自动化。

安装 skill 不会自动安装或启用桌面 MCP，也不会更改全局权限。建议使用 Cua Driver，
具体接入、默认禁用的配置示例和非敏感窗口 smoke 见 [computer-use/README.md](computer-use/README.md)。
桌面由主控制器独占，子代理不同时操作。截图不等于验收通过，已有引擎 gate 保持不变。
本仓库尚未验证真实桌面后端；缺少工具/权限或可执行验收 runner 时会明确阻塞，不报假成功。

## 验证

```powershell
python scripts/check.py --selftest
python -B -m unittest discover -s tests -p "test_*.py"
```

严格流程的单项排查命令仍可直接运行 `scripts/check.py`；合法示例位于
`tests/fixtures/`。

在目标项目根目录运行安装后的 `.opencode/workflow/scripts/check.py`；目标验证
命令示例见 `mvp-delivery/SKILL.md`，步骤验证见 `construction/references/step-protocol.md`。
验证命令通过 Python `shell=True` 使用系统 shell，Windows 是 `cmd.exe`，不是
OpenCode 的 PowerShell。执行前检查命令，对破坏、付费、凭据/隐私或外部写入等风险
取得明确授权；引擎不是沙箱。`verify-step` 使用调用者 cwd，必须从项目根运行。

引擎检查结构、绑定、退出/超时和 goal stdout 断言；测试命令仍须真正检查产品行为。
hash 不能防止有写权限者伪造工件，也不证明身份、独立性或真实可用性。`--selftest`
只检验引擎，不是产品 usability 证明。读取 source brief 时，引擎已有拒绝 draft 或
未确认来源的规则，控制器仍需显式验证 final brief 并核对语义，不能把它说成仅提示层约束。

更严格的 confirmation 类型、frontier 唯一/open、任意状态 user-entry 和 BS
disposition 校验可能拒绝旧 active/blocked 卡或 draft。schema 1 和 hash 算法不变，
不自动重写历史卡：继续工作前显式修正未完成工件，定义变化按全量失效规则重新验证；
涉及冻结输入则走 CR/新包。complete 卡和冻结历史保持不可变，即使不满足新规则也不能
伪造“已按新规则重验”，后续修复另建当前卡并保留历史证据。
当前引擎没有自动产品源码 fingerprint，也没有真实边界的自动语义证明。测试仍须检查每次
子进程状态、操作前相关输入 snapshot、结果内容和重复运行稳定性，并按风险用少量故障
注入验证断言能失败；不能把文件名集合未变当作未写入或正确增量。Audited approval
依然不能替代 controller 对最终版本、原始范围、真实入口及安装可复现性的核实职责。

## 设计参考

- [GitHub Spec Kit](https://github.com/github/spec-kit)：独立可验证的 MVP story。
- [OpenSpec](https://github.com/Fission-AI/OpenSpec)：progressive rigor 和增量规格。
- [Superpowers](https://github.com/obra/superpowers)：continuous execution 和真实
  subagent 隔离。
- [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD)：按任务规模选择流程。

## License

MIT.
