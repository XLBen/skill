---
name: production-readiness
description: Use when the accepted outcome includes production deployment, a long-running service, remote persistent state, a data migration, availability objectives or externally operated infrastructure. Plans release, rollout, observability, rollback and post-deploy verification, and binds them to the released artifact. Conditional: never loaded for local CLI/library deliveries.
license: MIT
metadata:
  language: "zh-CN"
  called-by: "mvp-delivery, contract-review, construction"
  public-command: "none"
---

# Production Readiness (条件型发布与运维)

本地“可运行”不等于生产“可发布”。本 skill 为目标包含生产交付的切片补齐发布
计划、推进策略、可观测性、回退与部署后验证。实际构建、签名、部署、健康探测
和回退执行必须由确定性流水线/工具完成，本 skill 负责设计与核验证据。

## When To Use

满足任一即加载：

- 交付物要部署到真实环境（服务、容器、定时任务、网关配置）；
- 长期运行进程、远程持久状态或队列；
- 数据迁移、schema 变更或需要回填；
- 声明了可用性、延迟或恢复目标（SLO/RTO/RPO）；
- 外部基础设施或第三方运行时由本切片改变。

不适用（记录 `applicability: none` 及理由）：纯本地 CLI、库、离线脚本，
且目标未声明生产交付。

## Inputs

- 最终 artifact 与依赖身份（build id/hash）；
- 目标环境、拓扑与推进路径（dev → staging → prod）；
- 配置项与 secret 名称（不含值）；
- 迁移与兼容约束（前后版本共存、回退窗口）；
- SLO/RTO/RPO、服务归属与告警渠道。

## Procedure

1. **发布前置检查**：版本标识、依赖锁定、配置项齐备、迁移可逆性与
   schema 兼容（旧版本在迁移后仍能读取）。
2. **渐进推进与停止条件**：定义每阶段（如 1% → 10% → 100%）的健康标准、
   观察窗口和自动/人工停止条件；写明谁有权暂停。
3. **可观测性验收**：每个承诺结果至少有一个可观测信号（日志/指标/追踪）
   与一条告警规则，并在 staging 或 dry-run 中确认信号真实出现。
4. **回退演练**：回退步骤、数据回滚（或前滚修复）和验证命令必须预演或
   dry-run；没有演练的回退计划标注为未验证。
5. **部署后验证**：对已发布 artifact 运行真实入口检查（健康端点、关键
   用户路径、数据对账），证据绑定 artifact 身份。
6. **交接**：runbook、备份/恢复、on-call 归属与已知限制写入
   `references/operations-handoff.md` 格式，随 artifact 身份交付。

## Outputs

- 发布与推进计划（含停止条件和回退）；
- 可观测性与告警验收项；
- 迁移/回退演练证据；
- 部署后验证证据（绑定 artifact 身份）；
- runbook 与 ownership 交接。

## Boundaries

- 不执行真实生产变更；由授权的 controller/operator 通过部署工具执行，
  owner 授权不可逆影响。
- 缺凭据/权限是 blocked 并披露，不得用本地模拟冒充部署验证。
- 不把“本地复跑通过”描述为已部署或生产就绪。
- 本 skill 不新增公开命令；由 mvp-delivery 在 planning 与 finish 阶段按需加载。

## References

| Need | Read |
|---|---|
| 发布就绪检查与推进模板 | `references/release-readiness.md` |
| 运维交接字段 | `references/operations-handoff.md` |
