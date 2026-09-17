---
name: writing-plans
description: Use when compiling a PLAN, writing a lightweight goal card's first-slice brief, or drafting any step/task dispatch that another session or seat will execute. Turns plans from structural checklists into execution-grade prompts: every step carries context, exact paths, an implementation sketch, boundary conditions, verification, and rollback, so a context-free executor succeeds without guessing.
license: MIT
metadata:
  language: "zh-CN"
  called-by: "contract-review, mvp-delivery, construction"
  public-command: "none"
---

# Writing Plans (计划即 Prompt)

一份能被无上下文执行者正确完成的计划，必须写得像给一位热情但没有判断力、
没有项目记忆、讨厌测试的 junior 工程师的 prompt。计划不是给人看的提纲，而是
执行席位的直接输入。本 skill 适配自
[obra/superpowers](https://github.com/obra/superpowers) 的 writing-plans 方法
（见 `UPSTREAM.md`），嵌入本仓库的 PLAN 编译、目标卡与派发模板。

## When To Use

- contract-review 编译/确认 Audited PLAN 的每一步规格；
- mvp-delivery `/plan` 写轻量目标卡的首片执行 brief；
- construction/step-executor 的单步派发正文；
- task-worker 的工作包交接。

## Step Brief 格式

每个步骤/任务的派发正文必须包含以下字段。缺任何一项，执行者就会自行假设——
而假设就是边际问题的来源：

```text
<step-id> <一句话目标>

Context: 为什么做这一步；它服务于哪个结果/验收项；上下游步骤如何衔接。
Files:   精确的文件路径列表（新增/修改/删除分开标注）；不许出现“相关文件”。
Change:  实现草稿——关键函数签名、数据结构、要复用的既有工具；不确定处
         写“调查后定”，并列出调查对象，而不是留空。
Bounds:  边界条件清单（见下）。
Verify:  可执行验证命令 + 预期输出/断言；先于实现写好。
Rollback: 该步骤不成立时如何安全退回（删除的文件、可逆的迁移、开关）。
```

## 边界条件清单（Bounds）

编写每一步时逐项过一遍，适用的写入步骤，不适用的显式标注不适用：

- 空输入 / 空结果（是否 semantic zero，还是失败）
- 极端规模（大文件、大列表、长字符串）
- 并发 / 重入 / 幂等（重复执行两次会怎样）
- 编码与国际化（非 ASCII 路径与内容、时区、locale）
- 失败中途（写到一半崩溃后，状态是否可恢复）
- 清理（测试数据、临时进程、生成物谁负责删除）
- 既有行为兼容（哪些旧路径不能被破坏）

## 计划粒度

- 每个步骤是一个可独立验证的工作单元；验证命令失败时能定位到唯一步骤。
- 不为远期故事铺路；只计划当前切片（与本仓库“最薄切片”原则一致）。
- 步骤顺序按依赖排列；无依赖的步骤标注可并行（供 worktree 派发）。
- 计划里的代码草稿允许在执行中被更好实现替换，但接口、边界行为和验证
  语义不可单方面变更——那要走 CR。

## 反模式

- “实现用户模块”（无路径、无边界、无验证）；
- “后续优化”（没有验证命令的步骤）；
- 把整份契约原文粘贴进派发正文（执行者要的是本步的 Context 摘录，不是全部）；
- 隐式假设环境（未声明运行前提、依赖版本、工作目录）。

## 与既有工件的关系

本 skill 不新增工件类型：字段写进 PLAN 步骤规格、目标卡首片 brief 或派发
模板的既有结构。引擎校验（structure hash、verify-step）不变；它提高的是
prompt 质量，不替代任何 gate。

## References

| Need | Read |
|---|---|
| Audited PLAN 结构与确认 | `../contract-review/references/plan-template.md` |
| 单步派发与验证 | `../construction/references/step-protocol.md` |
| 上游来源与适配范围 | `UPSTREAM.md` |
