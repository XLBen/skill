---
name: handoff
description: grill 或 plan 进行到一半要换会话、换模型，或者上下文快满时使用。把当前状态压缩成 docs/handoff.md，让新会话能直接接着做。Compact the current session's state so another session or model can continue.
---

# Handoff：交接给下一个会话

build 阶段不需要这个 skill：进度在 plan.md 的复选框和 git 提交里，新会话运行 `/resume` 即可。
这个 skill 用于状态还只存在于对话里的时候（grill 问到一半、plan 写到一半、debug 查到一半）。

## 写 docs/handoff.md

```markdown
# 交接（<日期>，<当前阶段: grill / plan / debug / 其他>）

## 目标
一两句话。

## 已经确定的
- <决定>（来源：用户原话 / 【代定】 / 实测）

## 还没确定的
- <问题>（我的推荐：...）

## 已经排除的
- <做法或原因>：<为什么排除，依据>

## 下一步
1. 具体的下一个动作（例如“问用户第 4 个问题：...”或“写 T05–T08 的任务卡”）

## 关键文件
- 路径：为什么重要
```

规则：
- 只写新会话需要的信息，不要复述对话过程。整份不超过 60 行。
- 区分“用户说的”和“你推测的”，推测的放进“还没确定的”。
- 写完告诉用户：新会话里说“读 docs/handoff.md 继续”即可。

新会话读完 handoff.md 后，按“下一步”继续；交接的内容被吸收进 brief 或 plan 后，删除 handoff.md。
