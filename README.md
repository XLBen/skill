# OpenCode 工作流：强模型规划，弱模型施工

[English](README.en.md) · 简体中文

```
/grill   →  docs/brief.md   一次一问、每问附推荐答案，把想法问成简报
/plan    →  docs/plan.md    架构、唯一的共享接口、一节错误策略、小任务卡（大项目先写 roadmap 分阶段）
/build   →  逐卡施工          worker 子代理写代码（可并行）；总控复验、审查 diff、失败逐级升级
/change  →  需求变更          像 /plan 一样为变更写任务卡，只追加或重开受影响的任务
/ship    →  收尾交付          验收、更新文档、清理、交付说明、合并或开 PR
```

已有项目加需求：`/grill <想法>`（变更访谈，写成简报里的“变更 N”）→ `/change` → `/build`；需求很清楚时可以直接 `/change`。

不输入命令也可以：小改动直接做，bug 走 `debug`，大目标自动先 plan 再 build（见 [AGENTS.md](AGENTS.md)）。
已有代码的仓库先用 `codemap` 生成一页仓库地图；需要换会话时用 `handoff` 交接；项目结束后用 `retro` 复盘。

## 设计要点

- **弱模型只看一张卡。** `wf.py task T03` 输出背景、约定、共享接口、错误策略和当前卡片，通常 50 行以内。
- **错误处理只在一个地方定义。** 计划的“错误策略”列出要处理的失败，其余一律抛出。worker 有明确的禁止清单，
  `wf.py diffcheck` 会列出每处 try/except、类型和空值守卫、空值回退，由总控逐条对照。
- **任务按纵向切片拆分。** T01 是端到端骨架；每个任务最多改 4 个文件，并且有断言内容的验证命令。
- **总控不相信自述。** `wf.py done` 只认 `wf.py verify` 的通过记录。
- **只有三个审查点**：计划审查（可选）、每个任务的 diff 审查、最终审查（reviewer 实际运行验收样例）。
- **失败逐级升级**：带错误重派 → 总控先诊断再重派 → 换强模型 `worker-strong` → 回到计划或问用户。
- **跨平台**：验证命令以 `python` 开头时，wf 自动换成当前解释器；lint 会提醒 grep/sed 这类 Windows 上没有的命令。
- **机械检查优先于提示词**：`guardrails` 为项目建立一条 lint/类型检查命令（包括抓吞异常的规则），写进计划的 `## 检查` 节，每个任务 verify 时自动运行。
- **契约优先的多人分工**：设计涉及多个组件时，计划定好 `## 接口契约`（签名、示例、契约测试），T00 由 `test-author` 建骨架和契约测试，
  各条线分别交给 `backend-worker`、`frontend-worker` 等子代理并行施工，`wf verify` 自动跑契约测试，只看输出是否达标。
- **按项目类型启用 skill**：extras 分成档案，只启用需要的，其余对 agent 不可见；worker 只能看到 `worker` 一个 skill。

## 目录

| 路径 | 内容 |
|---|---|
| `grill/` `plan/` `build/` `worker/` `review/` `debug/` | 核心流程 |
| `change/` `codemap/` `ship/` `handoff/` `guardrails/` `retro/` | 变更、仓库地图、收尾、跨会话交接、机械检查、复盘 |
| `scripts/skills.py` | 按档案启用 extras（安装为 `.opencode/skills.py`） |
| `scripts/wf.py` | 计划执行工具：status / next / task / verify / done / diffcheck / lint / regress / reopen / impact / contracts / lanes / wt-add / wt-merge / wt-drop |
| `scripts/vendor.py` | 按 `extras/upstream.json` 从上游固定提交引入可选 skill |
| `scripts/install.py` | 安装到目标项目 |
| `models.md` | 模型分工和已知倾向 |
| `extras/` | 可选 skill，来源见下表 |
| `validation/` | 三档基准任务、oracle 和指标脚本 |

## 按项目类型启用 extras

每个 skill 的名称和描述都会占用上下文，描述写得宽泛的还会被误加载，所以 extras 默认全部隐藏，按档案启用：

| 档案 | 启用的 skill |
|---|---|
| `backend` | source-driven-development、api-and-interface-design、security-and-hardening、deprecation-and-migration、performance-optimization、observability-and-instrumentation、postgres |
| `frontend` | frontend-design、frontend-engineering、vercel-react-best-practices、webapp-testing、source-driven-development、performance-optimization |
| `automation` | computer-use、webapp-testing |
| `ai` | mcp-builder、skill-creator、writing-for-agents、source-driven-development |
| `release` | shipping-and-launch、security-and-hardening、ci-cd-and-automation、code-simplification |

```bash
python .opencode/skills.py list
```
```bash
python .opencode/skills.py use backend frontend
```
安装时也可以直接指定：`python scripts/install.py <项目> --profile backend,frontend`。切换后重启 OpenCode。
实现方式是写项目 `opencode.json` 的 `permission.skill`，不修改任何 skill 文件；你自己加的条目会保留。

## extras 来源

| skill | 来源 | 用途 |
|---|---|---|
| frontend-design、skill-creator | [anthropics/skills](https://github.com/anthropics/skills) | 前端视觉设计；编写 skill |
| vercel-react-best-practices | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | React / Next.js |
| source-driven-development、security-and-hardening、shipping-and-launch、code-simplification、api-and-interface-design、deprecation-and-migration、performance-optimization、observability-and-instrumentation、ci-cd-and-automation | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 按官方文档写框架代码、安全、上线、简化代码、接口设计、迁移、性能、可观测性、CI |
| mcp-builder | [anthropics/skills](https://github.com/anthropics/skills) | 编写 MCP server |
| writing-for-agents | [mattpocock/skills](https://github.com/mattpocock/skills) | 编写 skill 和 AGENTS.md |
| webapp-testing | 本仓库（参考 anthropics/skills、vercel-labs/agent-browser） | Web 验收，一次性检查用 agent-browser |
| computer-use | 本仓库（改编自 computer-use-kit） | 桌面程序验收；Electron 程序优先走 agent-browser |
| postgres | 本仓库（整理自 supabase/agent-skills） | Postgres 表结构、索引、查询、RLS、迁移规则 |
| frontend-engineering | 本仓库（整理自 addyosmani 的 frontend-ui-engineering） | 组件、状态、无障碍、响应式、加载/空/错误状态 |

上游 skill 原样引入，`python scripts/vendor.py check` 核对、`outdated` 查看上游更新。核心流程借鉴了 superpowers、
mattpocock/skills、ponytail、stop-that-shit、pua、i-have-adhd 等项目的思路，详见 [CREDITS.md](CREDITS.md)。

## 安装

需要 Python 3.10+。

```bash
python scripts/install.py /path/to/project
```

安装后在 `.opencode/agents/worker.md` 和 `reviewer.md` 里设置 `model:`（见 [models.md](models.md)），然后重启 OpenCode。
skill 通过路径引用本仓库，修改 skill 不需要重新安装。从 v1 升级时，安装器会删除 v1 写入且没有被修改过的文件。
`--no-extras` 不注册 `extras/`。

## 验证

```bash
python -m unittest discover -s tests -v
python validation/setup.py 01-basic-cli ~/bench/l1
```

真实效果以 [validation/](validation/README.md) 的三档基准为准，结果记在 [validation/RESULTS.md](validation/RESULTS.md)。

## License

MIT。`extras/` 中的上游 skill 保留各自的许可与来源说明。
