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
结果数量不设上限。brief 输入在所有风险档都必须 final、owner-confirmed 并通过
`brief` 校验，且每个 brief ID 都有 coverage。`goal` 校验卡片，`verify-goal`
逐项执行验证并保存引擎证据，`finish-goal` 才可完成；禁止手写 verified/complete。
至少一个 `user_entry: true` 结果必须验证真实产品入口 demo。

`/fix` 复用相关 active/blocked 卡片，不创建第二个 active 修复目标；已完成包保持
不可变，修复基线不明确时先问。`/resume` 在没有未完成目标而有 draft brief 时继续
grill frontier，不开始施工。

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

## 内部 skills

- `mvp-delivery`：`plan/build/fix/resume` 的总控制器，负责持续收敛到原始目标。
- `grill`：深度需求澄清，只生成 brief。
- `contract-review`：Audited 切片的契约评审和 PLAN 编译。
- `construction`：执行并收尾 Audited PLAN，处理 CR 恢复。
- `test-author`：由 fresh subagent 调度时独立生成和冻结验收测试。
- `reviewer`：由 fresh subagent 调度时进行只读评审。
- `step-executor`：由 fresh subagent 隔离执行一个严格 PLAN 步骤。
- `computer-use`：主控制器按需执行真实桌面 GUI 路径，观察、操作、验证；需要另行授权的 MCP。

加载 skill 只会加入说明，不会自动创建独立身份。需要作者隔离时必须真实调度
fresh subagent 或真实独立 session；不可用时记录 independence unavailable 并阻断
Audited release，不能用 waiver 冒充独立评审。ID 只是声明，没有密码学身份验证。

## 安装

需要 Python 3.10+。在本仓库根目录运行：

```powershell
python scripts/install.py "E:/path/to/target-project"
```

安装器会复制五个 command wrapper 和校验引擎，并在 `opencode.json` 分别注册本仓库
当前顶层 skill 目录，避免扫描 `validation/` 的冻结旧版同名 skill。升级时替换原先
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
python -B -m unittest discover -s tests -p test_install.py
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
只检验引擎，不是产品 usability 证明；goal 引用 draft brief 目前仍需控制器显式阻断。

## 设计参考

- [GitHub Spec Kit](https://github.com/github/spec-kit)：独立可验证的 MVP story。
- [OpenSpec](https://github.com/Fission-AI/OpenSpec)：progressive rigor 和增量规格。
- [Superpowers](https://github.com/obra/superpowers)：continuous execution 和真实
  subagent 隔离。
- [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD)：按任务规模选择流程。

## License

MIT.
