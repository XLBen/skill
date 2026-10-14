# OpenCode 工作流：强模型规划，弱模型施工

[English](README.en.md) · 简体中文

```
/grill   →  docs/brief.md   一次一问、每问附推荐答案，把想法问成简报
/plan    →  docs/plan.md    架构、唯一的共享接口、一节错误策略、小任务卡（大项目先写 roadmap 分阶段）
/build   →  逐卡施工          worker 子代理写代码（可并行）；总控复验、审查 diff、失败逐级升级
/change  →  需求变更          追加或重开受影响的任务，跑回归
/ship    →  收尾交付          验收、更新文档、清理、交付说明、合并或开 PR
```

不输入命令也可以：小改动直接做，bug 走 `debug`，大目标自动先 plan 再 build（见 [AGENTS.md](AGENTS.md)）。
已有代码的仓库先用 `codemap` 生成一页仓库地图；需要换会话时用 `handoff` 交接。

## 设计要点

- **弱模型只看一张卡。** `wf.py task T03` 输出背景、约定、共享接口、错误策略和当前卡片，通常 50 行以内。
- **错误处理只在一个地方定义。** 计划的“错误策略”列出要处理的失败，其余一律抛出。worker 有明确的禁止清单，
  `wf.py diffcheck` 会列出每处 try/except、类型和空值守卫、空值回退，由总控逐条对照。
- **任务按纵向切片拆分。** T01 是端到端骨架；每个任务最多改 4 个文件，并且有断言内容的验证命令。
- **总控不相信自述。** `wf.py done` 只认 `wf.py verify` 的通过记录。
- **只有三个审查点**：计划审查（可选）、每个任务的 diff 审查、最终审查（reviewer 实际运行验收样例）。
- **失败逐级升级**：带错误重派 → 总控先诊断再重派 → 换强模型 `worker-strong` → 回到计划或问用户。
- **跨平台**：验证命令以 `python` 开头时，wf 自动换成当前解释器；lint 会提醒 grep/sed 这类 Windows 上没有的命令。

## 目录

| 路径 | 内容 |
|---|---|
| `grill/` `plan/` `build/` `worker/` `review/` `debug/` | 核心流程 |
| `change/` `codemap/` `ship/` `handoff/` | 变更、仓库地图、收尾、跨会话交接 |
| `scripts/wf.py` | 计划执行工具：status / next / task / verify / done / diffcheck / lint / regress / reopen / impact / wt-add / wt-merge / wt-drop |
| `scripts/vendor.py` | 按 `extras/upstream.json` 从上游固定提交引入可选 skill |
| `scripts/install.py` | 安装到目标项目 |
| `models.md` | 模型分工和已知倾向 |
| `extras/` | 可选 skill，来源见下表 |
| `validation/` | 三档基准任务、oracle 和指标脚本 |

## extras 来源

| skill | 来源 | 用途 |
|---|---|---|
| frontend-design、skill-creator | [anthropics/skills](https://github.com/anthropics/skills) | 前端视觉设计；编写 skill |
| vercel-react-best-practices | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | React / Next.js |
| source-driven-development、security-and-hardening、shipping-and-launch、code-simplification | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 按官方文档写框架代码；安全加固；上线检查；简化代码 |
| webapp-testing | 本仓库（参考 anthropics/skills） | Web 验收 |
| computer-use | 本仓库（改编自 computer-use-kit） | 桌面程序验收 |

上游 skill 原样引入，`python scripts/vendor.py check` 核对、`outdated` 查看上游更新。核心流程参考了
[obra/superpowers](https://github.com/obra/superpowers)（计划、子代理施工、升级、收尾）和
[mattpocock/skills](https://github.com/mattpocock/skills)（grill、handoff、prototype）。

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
