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

## 观察续跑

- 续跑判据：同一 candidate、同一 phase 且同一 model/环境。只有
  `budget-exhausted` 且带合法 `continuation` 的 result 才可 resume；
  model 或 environment 变化 → 新 run；candidate 变化 → 新轮，旧观察只作历史，
  绝不重放到新 candidate。
- 重派 observer 前先确认原子任务（packet/result/evidence/lease）的真实状态，
  不从聊天记录猜进度。
- 旧 packet/result/evidence 永不覆盖；续跑只消费 `continuation` 游标并重新
  校验候选身份，判定逻辑见 `scripts/observation_resume.py`。
