# MVP delivery skills

[English](README.en.md) · 简体中文

这套 OpenCode 工作流把**需求澄清、工程设计、施工验收**分开，同时允许用户直接用自然语言提出目标或报告缺陷。agent 会根据意图加载实际可用、适用的 skill；无需记住 skill 名称，也无需先运行阶段命令。

## 入口

| 入口 | 行为 |
|---|---|
| 普通目标（无命令） | 内部 `work`：按需推断、规划、实现、验证；小而明确的任务可直接做，正式门禁仍适用。 |
| 缺陷或失败（无命令） | `systematic-debugging`：复现、隔离、证伪、修复、复验；受管目标复用 `mvp-delivery` Fix Mode。 |
| “继续” | 从唯一匹配的持久目标恢复，候选不唯一时询问。 |
| `/grill <想法>` | 交互澄清并确认需求简报，不伪造用户回复。 |
| `/plan <目标或简报>` | 设计整个目标，发布可施工计划，不改产品代码。 |
| `/build [目标]` | 执行**已有有效计划**；缺计划时提示 `/plan`，不擅自施工。 |
| `/resume` | 根据持久状态继续未完成的目标。 |
| `/visibility [模型名]` | 选择或查看本项目的产品观察模型；不改变主聊天模型。 |

显式阶段命令优先于无命令路由。设计假设被事实推翻时回到规划；当前实现错先修当前步骤；设备或服务缺失时报告具体阻塞。完成以原始结果和真实边界的证据为准，不以结构检查或截图代替产品验收。风险、独立席位及 UI/产品观察门禁见 [mvp-delivery](mvp-delivery/SKILL.md) 与 [阶段路由](mvp-delivery/references/stage-routing.json)。

## 安装

需要 Python 3.10+。在本仓库根目录运行：

```powershell
python scripts/install.py "E:/path/to/target-project"
```

安装器复制五个命令、默认路由、运行引擎与子代理定义，并将本仓库 skill 目录及默认路由注册到目标项目的 `opencode.json`。它不会覆盖目标项目的 `AGENTS.md`；目标只有 `opencode.jsonc` 时会打印手动合并提示。旧版升级请使用完整安装：`--commands-only` 不安装默认路由，不能单独替代旧 `/work`、`/fix` 入口。安装或修改后**重启 OpenCode**。

`/visibility` 的动态观察派发依赖目标项目 `.opencode` 能解析 `@opencode-ai/plugin`；安装器会在依赖缺失时提示，在目标项目的 `.opencode` 中执行 `npm install` 并重启。桌面 MCP、模型与权限由使用者的 OpenCode 环境配置，安装器不会自动修改全局设置。

## 验证与详细规则

```powershell
python scripts/check.py --selftest
python scripts/check_runtime.py doctor <target-project> [--strict [--strict-freshness]]
python .opencode/workflow/scripts/check.py next-step .opencode/mvp/<goal>.md
python .opencode/workflow/scripts/check.py check-current .opencode/mvp/<goal>.md
```

按需阅读：[grill](grill/SKILL.md) · [writing-plans](writing-plans/SKILL.md) · [work](work/SKILL.md) · [mvp-delivery](mvp-delivery/SKILL.md) · [systematic-debugging](systematic-debugging/SKILL.md) · [computer-use](computer-use/SKILL.md) · [webapp-testing](webapp-testing/SKILL.md)。`check.py` 核对结构和证据绑定，不能单独证明真实模型、设备或完整产品可用；需要时仍须运行相应公开入口旅程。

## License

MIT.
