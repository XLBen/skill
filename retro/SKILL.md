---
name: retro
description: 一个项目或一轮评测结束后使用，或用户说“复盘/回顾/总结经验”。根据 wf 的验证记录、返工、裁定和审查意见，找出这套工作流和项目环境可以改进的地方，按严重程度给出建议。Retrospective on a finished build to improve the workflow and project environment, not the code.
---

# Retro：复盘这次施工

目的是让**下一次**施工更顺利：改进检查、计划模板、skill 措辞和仓库地图，而不是修改这次的产品代码。
只提建议，改不改由用户决定。

## 1. 读材料
- `.wf/state.json`：每个任务验证了几次（`attempt`）；`.wf/runs/<任务>-<n>.log`：失败的原始输出。
- `docs/plan.md`：裁定记录、变更记录、被 reopen 过的任务。
- 审查意见（任务审查和最终审查中“必须修”的问题）、worker 的 `done_with_concerns` / `needs_context` / 升级到 worker-strong 的记录。
- 对话里用户纠正过的地方。

## 2. 找问题（只记录有证据的）
| 类别 | 现象 | 建议的方向 |
|---|---|---|
| 可以机械检查的错误 | 审查反复抓到同一类问题（吞异常、类型错、格式） | 加进 `## 检查` 的 lint 规则，或 wf diffcheck 的模式（见 `guardrails`） |
| 任务卡不清楚 | 同一任务验证多次、`needs_context`、升级到 worker-strong | 指出卡片缺了什么（接口、例子、要读的文件），建议改 plan 模板或 plan skill 的措辞 |
| 信息找不到 | worker 或总控花很多步骤找文件、猜命令 | 更新 `docs/codemap.md` |
| 计划本身的错误 | 变更记录里的“设计修正”、错误的 API | 建议 plan 阶段多做的那一步核实 |
| 没起作用的规则 | 某条规则从没影响行为，或者被一再违反 | 建议删除，或者改成检查 |

原则：
- 能写成检查的，不写成提示词规则。
- AGENTS.md 和核心 skill 只能更短：新增一条规则时，同时找一条可以删的。
- 判断类的要求放进 review 的清单，不放进 worker 的规则（worker 的上下文最紧张）。

## 3. 输出
写到 `docs/retro.md`，按严重程度排序，每条一行：
`[高|中|低] <问题> | 证据: <任务 ID、日志路径或审查意见> | 建议: <改哪个文件的什么>`

这是一轮评测时，把最重要的 1-3 条追加到 `validation/RESULTS.md` 对应行的备注。
最后问用户要采纳哪几条；用户同意后，修改的是工作流仓库或项目的配置，不是这次的产品代码。

（思路来自 mattpocock/skills 的 retro，MIT。）
