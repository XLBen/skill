---
name: security-assurance
description: Use when a slice touches authentication, authorization, privacy, secrets, cryptography, untrusted input, multi-tenancy, an externally reachable attack surface or regulated data. Builds a threat/abuse model, maps controls to existing acceptance items, and produces a version-bound security handoff for the final review. Conditional: never loaded for slices without a real trust boundary.
license: MIT
metadata:
  language: "zh-CN"
  called-by: "mvp-delivery, contract-review, construction"
  public-command: "none"
---

# Security Assurance (条件型安全保证)

这不是一个通用检查表，而是把“安全相关切片”从通用 Audited 仪式升级为真实
威胁建模：先明确信任边界与数据流，再决定控制与验证。它不新增产品需求，也不
替代独立 reviewer、owner 决定或任何 engine gate。

## When To Use

满足任一即加载（其余切片不要调用）：

- 认证、会话、授权、权限模型变化；
- 隐私、个人数据、留存或脱敏行为变化；
- 密钥、凭据、加密、签名或随机数使用；
- 处理不可信输入、文件、URL、反序列化或命令拼装；
- 多租户隔离、外部可达接口、webhook/回调等攻击面变化；
- 目标声明了合规、审计或安全风险因子。

边界：scanner、SBOM、依赖漏洞库、DAST、secret scan 是确定性工具职责；
本 skill 负责解释结果、补威胁模型和控制映射，不模拟扫描器输出。

## Inputs

- 固定的 brief/goal/contract 快照与 hash；
- 数据流、信任边界、入口与角色；
- 数据分类、留存与脱敏约束；
- 目标环境、依赖清单、既有控制（若有）；
- 适用标准或合规义务（owner 提供，不由 agent 编造）。

## Procedure

1. **列资产与信任边界**：哪些数据/权限是资产，谁能跨越哪条边界；用一句
   可证伪的滥用场景描述每个威胁（谁、做什么、得到什么）。
2. **只保留真实威胁**：对每条威胁给出可观察的失败条件；无法失败或与本切片
   无关的移入 not-applicable 并写理由。
3. **控制映射到现有验收项**：每条必需控制绑定到 P/I/V 或目标 outcome 的
   Given/When/Then；缺验收项说明契约缺口（走 CR），不静默发明需求。
4. **定义安全测试**：负路径（拒绝/越权/重放/注入）必须有断言；可用的确定性
   扫描结果作为证据引用，不用“已扫描”代替行为断言。
5. **残余风险交 owner**：无法在切片内消除的风险写清影响、概率与缓解，
   由 owner 决定接受或改范围；agent 不替 owner 接受风险。
6. **产出 SECURITY_HANDOFF**（见 `references/assurance-handoff.md`），并随
   最终 artifact 身份在 converge/finish review 中复用；实现变化后重新验证
   受影响威胁，不整包重放。

## Outputs

- 威胁/滥用场景清单（含 not-applicable 理由）；
- 控制到现有验收项的映射；
- 安全测试要求（负路径断言）；
- 残余风险与 owner 决定请求；
- 绑定 artifact 身份的 `SECURITY_HANDOFF` 证据。

## Boundaries

- 只读能力：审查者加载本 skill 后仍是只读席位，执行验证经
  CONTROLLER_ACTION。
- 不替代独立 reviewer；本 skill 的输出是 reviewer 的输入之一。
- 不因加载本 skill 扩张 write scope 或权限。
- 无法验证的控制保持 blocked，不用“看起来安全”通过。

## References

| Need | Read |
|---|---|
| 威胁建模方法与模板 | `references/threat-model.md` |
| 安全交接字段与生命周期 | `references/assurance-handoff.md` |
