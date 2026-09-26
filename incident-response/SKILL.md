---
name: incident-response
description: Use when there is active or suspected production impact - outage, data corruption or exposure, security compromise, or an alert requiring immediate restoration. Prioritizes severity, containment, evidence preservation, recovery and communication; root-cause repair follows through internal Fix Mode. Conditional: never loaded for ordinary development bugs.
license: MIT
metadata:
  language: "zh-CN"
  called-by: "mvp-delivery (internal fix routing)"
  public-command: "none"
---

# Incident Response (事故响应)

生产事故的第一优先级不是复现根因，而是控制影响、保住证据、恢复服务。先复现
可能扩大损失。本 skill 定义事故响应路径；根因修复在服务恢复或影响受控后回到
`systematic-debugging` 的根因修复流程。

## When To Use

满足任一即加载（普通开发中的报错不要加载）：

- 正在发生的线上故障、不可用或性能崩塌；
- 数据损坏、丢失或疑似泄露；
- 安全事件、凭据暴露、未授权访问；
- 需要立即处置才能止损的告警。

普通 bug、可回滚的本地错误、开发环境问题继续走默认缺陷修复。

## Procedure

```text
定级 → 控制影响 → 保存证据 → 恢复服务 → 根因修复(内部 Fix Mode) → 复盘
```

1. **定级与广播**：影响范围、严重度、谁是 incident commander；owner 立即
   知晓；不可逆或对外披露动作必须 owner 授权。
2. **控制影响**：优先止血（限流、熔断、隔离、回退到上一版本、只读模式）；
   每个动作记录时间、执行者、命令与结果；不确定的动作先问 owner。
3. **保存证据**：在清理/重启前保留日志、指标快照、状态转储与相关 artifact
   identity；禁止为了“先恢复”而销毁唯一证据。
4. **恢复服务**：恢复路径可以是回退、前滚修复或流量切换；恢复后运行真实
   用户路径检查，而不是只看进程存活。
5. **根因修复**：影响受控后创建内部修复任务，携带时间线、证据指针与
   失败签名；回归测试固化根因。
6. **复盘**：时间线、影响、检测盲区、处置得失、行动项与 owner；行动项
   进入 goal/SI 或 issue tracker，不悬空。

## Outputs

- 事故状态与定级；
- 带时间戳的时间线（处置动作 + 证据指针）；
- 控制/恢复计划与执行记录；
- 服务恢复验证；
- 内部 Fix Mode 交接（含失败签名）；
- 复盘与行动项。

## Boundaries

- 生产变更与不可逆动作由授权的 controller/operator 执行，owner 授权；
- 本 skill 不替代根因修复的纪律，也不替代 owner 的对外沟通决策；
- 无法验证恢复时保持明确阻塞状态，不宣布“已恢复”；
- 处置中的每个命令仍受 authorization、证据与回滚纪律约束。

## References

| Need | Read |
|---|---|
| 事件时间线与交接模板 | `references/incident-protocol.md` |
| 恢复分级与熔断 | `../pua/references/recovery-protocol.md` |
