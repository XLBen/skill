# 评测

修改 skill 之后，用这里的三档任务实际跑一遍，再根据数据调整措辞。**没有跑过的改动，不算改进。**

| 档 | 任务 | 测什么 |
|---|---|---|
| L1 | `01-basic-cli`：收据汇总 CLI | 小任务是否走最短路径；校验错误是否按规格输出 |
| L2 | `02-sqlite-increment`：SQLite 账本，两轮 | 第二轮需求能否增量完成，不重写第一轮 |
| L3 | `03-http-recovery`：HTTP 同步，四轮 | 真实外部边界、分页、反复失败时是否停下来、上游 schema 变化 |

每个任务的 `evaluation/verify.py` 是黑盒 oracle，会对最终产品逐条检查。agent 的读权限里屏蔽了它。

## 运行一次

```bash
python validation/setup.py 01-basic-cli ~/bench/l1-v2
```

1. 在 `~/bench/l1-v2/.opencode/agents/worker.md` 和 `reviewer.md` 里设置 `model:`（见 `models.md`）。
2. 用强模型打开 OpenCode：`opencode ~/bench/l1-v2 -m <强模型>`
3. 输入 `/plan TASK.md`，确认计划后输入 `/build`。只按 TASK.md 回答 agent 的问题。
4. 有 ROUND 文件的任务：上一轮完成后，输入 `/change ` 加上 `validation/tasks/<任务>/ROUND2.md` 的内容，依此类推（ROUND3 是排查类，直接粘贴，不加 `/change`）。
   每轮完成后看一眼 agent 有没有运行 `wf regress`。
5. 全部完成后运行：`python validation/metrics.py ~/bench/l1-v2`，把表格行贴进 `RESULTS.md`。
6. 导出会话（`opencode export`），保存到工作区外面，供复查。

L3 额外步骤：
- 开始前在另一个终端运行：`python boundary/control.py normal`、`python boundary/transient_gate.py --reset`、
  `python boundary/server.py --port 8765`，并在 OpenCode 的终端里设置 `CATALOG_TOKEN=benchmark-token`。
- ROUND3（反复失败的检查）：期望 agent 在同一失败出现 3 次后停下来报告。
  在 OpenCode 外运行 `python boundary/transient_gate.py --count`，结果应为 `3`（`4` 表示多试了一次）。
  然后回复“授权再试一次”，命令应输出 `gate-ready`。
- ROUND4 之前，先在 OpenCode 外运行 `python boundary/control.py schema-v2`，再粘贴 ROUND4.md。
- 结束后运行 `python boundary/control.py normal` 恢复。

### 和 v1 对比
把 v1 检出到另一个目录（`git worktree add ../skill-v1 main`），然后：
```bash
python validation/setup.py 01-basic-cli ~/bench/l1-v1 --skills-repo ../skill-v1
```
v1 没有 `docs/plan.md` 这种格式，metrics 里的任务数和额外验证次数会显示 `-`，其余指标可以直接比较。

## 指标怎么看

| 指标 | 含义 | 期望 |
|---|---|---|
| oracle | 黑盒验收 | 必须 PASS |
| 任务数 | 计划拆了几个任务 | L1 约 2-3，L2 每轮约 2-4，L3 每轮约 3-5 |
| 额外验证次数 | `wf verify` 失败后重跑的次数 | 越少说明任务卡越清楚 |
| 最大文件行 | 产品代码最大的文件 | 一般不超过约 300 |
| 防御信号 / 每百行 | try/except、类型和空值守卫、空值回退、重试 | 和 v1 对比；L3 有真实的网络边界，数值会高一些 |

除了这些数字，还要人工看这些事：
1. 会话里 agent 问了几个问题，有没有问 TASK.md 已经写清楚的事。
2. 防御信号逐条看：能对应到计划的错误策略吗？
3. worker 的汇报有没有贴原始输出；总控有没有亲自 verify。
4. 变更轮次里，agent 是追加/重开了受影响的任务，还是重写了整个计划；worker 失败时有没有按升级顺序处理。

## grill 评测

用强模型新开会话，分别输入下面三个模糊需求，由人扮演用户（只回答被问到的问题，尽量简短，可以回“你定”）：

1. `/grill 我想做个工具帮我整理下载文件夹`
2. `/grill 给我们团队做个记录每周周报的东西`
3. `/grill 我想让 AI 帮我自动玩一个网页小游戏`

每次记录：

| 需求 | 问题数 | 每题有推荐答案吗 | 跑题次数 | 简报中用户没提过、也不是【代定】的要求数 | 有几条具体验收样例 |
|---|---|---|---|---|---|

好的结果：问题数不超过 8 个；简报中没有凭空出现的要求；至少 2 条具体验收样例。
