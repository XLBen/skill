---
description: Resume the active goal from its durable state and continue to completion
agent: build
---

Load the `mvp-delivery` skill in Resume Mode:

$ARGUMENTS

Load `i-have-adhd` for resumed progress, acceptance-preview, delivery and
blocker output. Reconcile the durable goal/dispatch state per
`mvp-delivery/references/subagent-orchestration.md` before any re-dispatch,
starting from its minimal recovery read set. Ask only when multiple targets or
an unclear repair base make routing ambiguous; continue at the first pending or
blocked outcome until the original goal is complete.

If this goal was started through `/work`, restore its autonomous orchestration:
rediscover currently available applicable skills and continue through any
planning, implementation, repair and final acceptance without returning an
intermediate `/plan`, `/build` or `/fix` handoff to the user.

## 工程循环续跑（schema 3）

- 有 owner-decision 时先读取持久问题和真实回复来源；resolve-decision 后继续原尝试，
  不是把未完成的输入测试补记通过。未回答/拒绝的请求不能靠重新发布计划跳过。

- 先运行 `check.py next-step <goal>`：重放循环历史，返回当前任务包、必要合同和
  implement/observe/retry/blocked/replan/final-acceptance 动作，不重读全部历史。
- 有未观察尝试时，先读该尝试的回执再 `observe-cycle`；中断的运行只能
  `retry`/`blocked`，不能补记为通过。绝不删除或改写历史记录来解锁进度。
- replan 先交回规划者；修订并 prepare-plan 后旧证据失效。已正确实现的代码复验
  即可，不因恢复或切模型而重新生成整个工程。

## 观察续跑

- 续跑判据：同一 candidate、同一 phase 且同一 model/环境。只有
  `budget-exhausted` 且带合法 `continuation` 的 result 才可 resume；
  model 或 environment 变化 → 新 run；candidate 变化 → 新轮，旧观察只作历史，
  绝不重放到新 candidate。
- 重派 observer 前先确认原子任务（packet/result/evidence/lease）的真实状态，
  不从聊天记录猜进度。
- 旧 packet/result/evidence 永不覆盖；续跑只消费 `continuation` 游标并重新
  校验候选身份，判定逻辑见 `scripts/observation_resume.py`。
