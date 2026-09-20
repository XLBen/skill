---
name: outcome-learning
description: Use when the goal contains an unvalidated user, adoption, workflow-efficiency or business hypothesis, or when success can only be observed after real use. Defines a falsifiable outcome hypothesis, baseline, metric with guardrails and the smallest ethical experiment; does not make the owner's continue/revise/pause decision. Conditional: skip when success is fully observable in delivered behavior.
license: MIT
metadata:
  language: "zh-CN"
  called-by: "grill, mvp-delivery"
  public-command: "none"
---

# Outcome Learning (条件型结果验证)

流程能证明“软件按声明工作”，不证明“真实问题被解决”。当一个目标的价值假设
无法在交付物内观察（采用率、效率、业务指标），本 skill 设计最小、可证伪、
尊重隐私的结果验证。owner 仍决定继续、修正或暂停。

## When To Use

满足任一即加载：

- brief/goal 的成功信号依赖真实用户行为或业务指标；
- 存在未经证据支持的用户/采用假设；
- “做出来”与“有用”之间的差距是本次目标的核心风险。

跳过：成功完全可由交付行为判定（本地工具按规格工作、库 API 行为正确），
且没有未验证的价值假设。

## Procedure

1. **写可证伪假设**：`<人群> 在 <场景> 会 <行为>，因为 <机制>`；给出会否证
   它的观察。
2. **找基线**：现状数据、对照组或历史观测；没有基线就没有“改善”，只有
   噪声。缺失基线时先补最小观测。
3. **定义指标与护栏**：一个主指标 + 至少一个护栏指标（防止以伤害其他维度
   换取数字）；写明数据来源、口径、观察窗口与解释规则。
4. **最小实验**：优先真实使用观察或小范围发布，而不是大规模实验；明确
   退出条件、停止条件与数据最小化/授权要求（隐私优先）。
5. **结论分级**：证据支持 / 证据不足 / 否证；证据不足不等于成功；否证的
   假设交 owner 决定改方向。
6. **归档**：观察结果、指标口径与限制写入交付记录；后续 SI 才可据此扩张，
   `/build` 不因未验证假设自动新增范围。

## Outputs

- 可证伪的结果假设与基线；
- 指标/护栏定义与解释规则；
- 最小实验设计与授权要求；
- 证据支持的结论（support / insufficient / refuted）；
- 给 owner 的继续/修正/暂停建议（不替 owner 决定）。

## Boundaries

- 不伪造用户反馈、指标或实验结果；无法观测时明确 insufficient；
- 观察期长于本次交付时，记录为观察中状态，不偷偷加入本次 finish 条件；
- 涉及个人数据时遵守最小化、目的限制与授权；不得绕过隐私边界收集；
- 建议不是决定；价值取舍与范围变化仍归 owner。

## References

| Need | Read |
|---|---|
| 实验与指标模板 | `references/experiment-protocol.md` |
