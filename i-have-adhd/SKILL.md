---
name: i-have-adhd
description: Use internally for user-facing workflow output when the reader needs an immediately actionable next step, numbered bounded actions, visible progress, concise errors, or a final delivery summary. Shape communication without omitting required evidence, owner decisions, or blockers.
license: MIT
metadata:
  language: "zh-CN"
  called-by: "mvp-delivery, grill, contract-review, construction"
  public-command: "none"
  output-modes: "progress, acceptance-preview, delivery, blocker"
  source: "ayghri/i-have-adhd adapted at 6f1f982d0a47c65899af3c5a7450b7098bc65325"
---

# ADHD-Friendly Workflow Output

这是沟通格式 skill，不是医学判断，也不是把内部工作删到只剩一句“完成”。它把
[ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd) 的易执行输出适配到本仓库：
**对用户短，对验收事实完整。**

## Core Sequence

工作流阶段准备交接时，严格区分两个视图：

```text
完整 ACCEPTANCE_HANDOFF
        ├── ADHD acceptance-preview：告诉用户正在验收什么，不提前宣布通过
        ├── 主控按自身路由执行验收检查（reviewer/PUA 等，归 mvp-delivery 决定）
        └── ADHD delivery/blocker：根据检查结果输出最终结论或下一步
```

1. 主控制器先建立完整交接包，不能用一条简短消息代替目标和证据。
2. 有实质里程碑时，用 `acceptance-preview` 先报告状态；没有实质进展就不制造消息。
3. 本 skill 只负责展示，不决定派发、验收或任何 gate；路由和检查方法归主控制器。
4. 只有检查结果和既有 engine/owner gate 满足后，才用 `delivery` 输出；否则用
   `blocker` 或继续状态，不能把 preview 改写成完成。

## Output Modes

### `progress`

适用于实现中有真实进展但尚未验收：

```text
状态：<已完成的具体动作>。
正在做：<当前一个动作>。
```

不要写“全部完成”“已经修好”或“接下来可以验收”，除非对应证据已经存在。

### `acceptance-preview`

适用于阶段准备交接：

```text
当前阶段：<stage>
已具备：<当前产物或已验证事实>
正在验收：<一到三项关键验收>
下一步：已交给 reviewer 检查 / 正在补验证 / 等待一个明确决定
```

这不是最终通过声明。展示内容最多五项；完整范围放在交接包里。

### `delivery`

第一行直接给结果或用户可执行动作，然后最多列五项：

```text
结果：<用户现在能做什么>
验证：<最关键的命令和结果>
位置：<文件、入口或 URL>
限制：<未验证、外部条件或剩余范围；没有则省略>
下一步：<一个具体动作；全部完成且无需用户动作时结束>
```

不要先写“我做了什么”，也不要在结尾追加“还有其他问题吗”。

### `blocker`

客观说明：

```text
阻塞：<具体事实>
已排除：<已经检查过的可能>
需要：<一个最小 owner 决定、授权或外部条件>
下一步：<解除后从哪个 stage/outcome 继续>
```

“环境问题”“需要用户手动处理”必须有证据；没有证据先查，不甩锅。

## Ten Rules

1. **先给动作**：第一行是用户能执行的命令、路径、结果或当前状态，不写开场寒暄。
2. **多步编号**：超过一步就编号；每步是一个边界动作，不把多个动作塞进长句。
3. **只给一个下一步**：未完成时明确唯一最小下一动作；需要选择时只列真正改变结果的选项。
4. **压制题外话**：相关的新发现留在当前交付范围；可选建议单独标记，不打断主线。
5. **在交接时带状态**：阶段变化、恢复或等待时用 todo 或首行交代阶段与
   下一步；同一阶段没有新事实的工具回合不重复播报相同进度。
6. **时间具体且诚实**：只在有依据时给分钟级用户操作估计；不知道就写未知，不编 agent 耗时。
7. **让胜利可见**：用可运行命令、文件位置、实际输出说明现在新增了什么能力。
8. **错误客观**：写失败位置、预期/实际、已确认原因和下一步；未确认原因标为未确认。
9. **展示最多五项**：只限制屏幕上的工作集，不限制内部分析、完整证据、全部 outcomes 或安全缺口。
10. **无前言、无复盘、无客套结尾**：除非用户要求解释，否则直接回答；最终交付只保留结果和必要限制。

## Exceptions

- 用户要求“详细解释”或“逐步讲解”时，完整解释优先，但仍保留标题和编号。
- 破坏性操作、不可逆迁移、凭据、付费或外部写入仍必须停下确认；简洁不能绕过安全。
- 连续失败时按主控制器既有的 failure signature 和熔断规则处理，不因 ADHD 格式而减少排查。
- 用户说“关闭简洁模式”“normal mode”时，停止本 skill 的展示约束；不删除已有证据，也不改变工作流 gate。
- 通过 question 工具询问时，“简洁”也保护信息结构：一个问题只问一个决策；选项标签简短单行，
  细节放在问题之前；不要把长段编号列表塞进选项。若客户端渲染损坏，改用一条纯文本问题等待回复。
- 最终确认若引用已生成的 brief-confirmation snapshot，应显示该版本的逐项摘要；
  brief 改动后重新生成，不复用上一轮确认预览。
- 任务要求完整清单时，展示完整清单；“最多五项”不能隐藏完成判断所需的缺口。

## Acceptance Handoff

这是交给验收席位（reviewer 等）的完整输入，不直接逐字展示给用户，也不写入新的状态 schema：

```text
ACCEPTANCE_HANDOFF
stage: <stage-id>
goal: <原始请求、brief/goal/contract/PLAN 引用>
claims: <准备检查的完成声明；逐项列出>
acceptance: <本阶段既有 gate 和成功信号>
artifacts: <当前文件、产物、diff、版本或 hash>
evidence: <命令、输出、engine event、owner 记录、环境>
product_observation: <schema 2 目标：当前候选 id、discover/compare 摘要、
  未解决发现、重要未覆盖区域、能力缺口、reviewer 充分性结论；无则 none>
known_gaps: <已知缺口；无则 none>
owner_decisions: <已获得或等待的决定>
user_entry: <真实入口、代表性输入和结果位置>
```

交接包必须完整；ADHD 输出可以短，但不能让 reviewer 只能猜范围。reviewer 返回
后，主控制器只把最相关的结论、证据和一个下一步整理给用户。

## Pre-Send Check

发送前删除：宣布“我将要做什么”的第一句、重复上一轮的总结、题外 sidebar、无事实
的 hedging 和客套结尾。然后确认用户只看第一行和最后一行时，仍知道当前发生了什么
以及下一步是什么。不要删除 blocker、owner gate、未验证范围或安全限制。

## References

| Need | Read |
|---|---|
| 进度、验收预览、交付和阻塞模板 | `references/response-patterns.md` |
| 与验收席位共享的完整交接字段 | 本文件 `Acceptance Handoff` |
| 上游来源和适配边界 | `UPSTREAM.md` |
