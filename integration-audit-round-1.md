# 统一方法论方案：第一轮硬伤排查

日期：2026-08-30

审查对象：整合前的 `integration-plan.md`（v3）、旧机制稿、现有 thesis-defense / construction 全部 SKILL、references、examiner 与 README。

判定标准：会导致流程不可执行、不可恢复、状态歧义、需求失权、无法直接施工或 CR 闭环失效的问题记为硬伤。

## 结论

整合前方案存在硬伤，不能直接实施。第一轮初审确认 15 组设计硬伤，两次闭环复核又发现 8 组缺口；统一稿 `integration-plan.md` 已逐项补齐设计级修复。现有两个 skill 尚未实施这些修复，因此**当前代码仍不满足统一方案**，必须按原子版本整体改造后才能宣称通过。

## 硬伤清单

| ID | 硬伤 | 后果 | 统一稿处置 |
|---|---|---|---|
| H-01 | 方案取消轮数上限，但现有 SKILL、verdict、模板和 README 均固定 1/3/5 轮 conditional | 设计与可执行规则相反 | §8–§9：轮数只计审计历史；无上限；全部权威文件原子更新 |
| H-02 | 现有“至少两题才是有效轮”没有定义恰好一题时如何前进 | 单一关键硬伤可使循环空转 | §8.4：任意正数异议均有效，零题只进入终局候选 |
| H-03 | 动态循环需要 intake/scout/evidence/prototype/owner/final 状态，旧 phase 只有 questioning/answering/reviewing；派发前后还有 crash window | 会话中断后可能丢题、重复派发或跳阶段 | §8：细化 status/phase、request/event ID 和写前日志顺序 |
| H-04 | 需求方权威仅存在于对话，P 无来源/确认/可变性；取舍 T 未纳入编号契约 | AI 可替用户改需求，恢复后无法证明谁决定了什么 | §4–§5：稳定 P/T schema、owner quote、authority 与 awaiting-owner |
| H-05 | conditional 同时表示轮数耗尽的硬伤、用户接受风险和可施工状态 | construction 可能带事实错误开工 | §8.1：conditional 只容纳完整可编译契约上的非致命签署风险；其余 blocked/awaiting-owner |
| H-06 | F 是运行流程，S 是施工步骤，F→S 一对一不可成立 | 共享设施、跨流程模块和构建依赖需要 construction 重新设计 | §7：增加 I 实现绑定；F↔I 多对多，I 确定性编译 S |
| H-07 | F/V 使用自由文本，分支完备性、终态、循环、验证阶段不可机械校验 | “直接施工”只停留在口号 | §7：结构化 F/I/V schema；唯一 contract-schema；local/integration/e2e/human 分类 |
| H-08 | research 要求双方写 D 前侦察，但 examiner 只在论文 v1 后出题，且只有 question 输出格式 | 反方无法在需要的时点拿成熟轮子；复审/终审无契约 | §6、§9：examiner 增加 scout/question/review/final-audit/cr-audit 五种 mode |
| H-09 | prototype 一面作为权威证据，一面被要求丢弃或只留指针 | 结论不可复现，后续审计只能相信摘要 | §6.3：丢弃仅指不进生产；E evidence bundle 保留环境、命令、输入、输出和结论 |
| H-10 | S0 可“换候选轮子”，但 handoff 又规定放弃 D 必须 CR | construction 可静默改设计 | §6.1、§10.5：只有预答辩 fallback-order 可自动切换，否则 blocking CR |
| H-11 | CR 状态散落 PLAN/build-log/defense-log/frontmatter；回炉只审点名章节和引用，不审传递语义影响 | 状态冲突；已完成步骤可能基于失效设计继续保留 | §3.2、§11：单一 change-orders 台账、P/F/I/.../S 传递闭包、受影响 S invalidated、全量终审 |
| H-12 | construction 未勾步骤中断后一律重跑，未要求幂等、postcondition 或补偿 | 迁移、远程调用、部分写入可能重复造成破坏 | §10.4：步骤状态机、attempt ID、side-effect、idempotency 和 compensation |
| H-13 | 新契约宣称 F 必填，但旧方案又承诺字段可选、状态机不变 | 旧 passed thesis 会被误当成可编译 v4 | §3.1、§13：contract-version/hash；旧契约必须显式迁移和重审 |
| H-14 | PLAN 恢复时并非所有状态都核对 thesis；无 contract hash/compiler version | planning 或 paused 可继续执行过期契约 | §10.1–§10.2：所有非 done 状态校验 thesis/hash/schema/compiler/CR |
| H-15 | “用户强行复工”可绕过被证伪事实；charter 又可能高于用户最新决定 | 要么事实可被签字推翻，要么需求方并非真正权威 | §5.2、§8.1、§11.3：事实阻塞不可豁免；charter 是有版本的 owner 约束，最新明确决定触发记录化替代 |
| H-16 | T 只要求“已决定”，没有证明用户选项已落实进契约 | 记录了用户决定却可能按另一方案通过 | §5.4、§7.5：T 增加 decided→applied、applies-to 与 applied hash；完整性门只接受 applied |
| H-17 | I split-point 没有逐段动作、产物、验证和回滚 | 无法确定性编译多个 S | §7.3、§10.2：改为完整 variant/segment；每 segment 精确定义并生成一个 S |
| H-18 | S0 和跨 I 验证没有统一 ID / 所有者 | PLAN 会出现无法追溯、无法恢复的特殊步骤 | §7.3、§10.2：使用 kind:s0 / validation 的 I，统一编译、DAG、状态与恢复 |
| H-19 | S0 换 W 会使 hash 锁定的 I/PLAN 失真 | 执行状态与论文契约不一致 | §6.1、§7.3、§10.5：所有 fallback 是已答辩的等价 I variant；S0 只选择 variant，不改 contract hash |
| H-20 | CR 虽有单一文件，但没有阻塞语义、权限和安全关闭条件 | CR 可被任意关闭/拒绝/豁免，门禁无法可靠判断 | §11.1：完整 transition table、writer authority、blocking 集合、E/T/V 和 hash 审计前置 |
| H-21 | negotiable P 只因不是 anchor 就可能不被 F/V 覆盖 | 用户需求可在无裁决时静默消失 | §5.3、§7.5：所有 active P 必须覆盖；排除须 applied T + withdrawn/superseded + B/R |
| H-22 | CR 表格把 verified 标成阻塞，但 blocking 集合又排除它 | 两个实现会对能否复工得出相反结论 | §11.1：verified 明确非阻塞；修复验证完成即可继续，closed 只做台账收尾 |
| H-23 | CR 要求 PLAN hash，但执行状态持续变化且无 hash 投影 | CR 永远无法稳定闭合或恢复时频繁误判 | §10.2、§11.1：定义不可变 plan-structure-hash，排除 state/attempt/log，CR 只引用该 hash |

## 非硬伤但需监控的风险

| 风险 | 控制 |
|---|---|
| 无上限答辩可能消耗不可控 | 换皮检测、诚实异议门、最小实验、单轮上限；不能用总轮数掩盖硬伤 |
| 用户取舍可能长时间未回应 | awaiting-owner 可恢复；T 可排队，但按 grill-me 一次只向用户呈现一个问题，不得替用户默认选择 |
| v4 schema 过重 | 用模板与渐进展示降低填写负担；轻量档降低证据深度，不省略最终完整性必填字段 |
| contract hash 和编译器引入实现复杂度 | contract-schema 必须定义唯一语义投影、规范化算法和正反 fixtures，再改两个 skill；必须原子发布 |
| 证据包可能泄露敏感信息 | E schema 与全部日志 / handoff 强制脱敏；密钥与 PII 只记录类型或安全引用，不落原值 |

## 本轮判定

- 整合前方案：**有硬伤，不可实施**。
- 统一设计稿：初审与复核共 23 组硬伤均已有明确设计处置；尚待实际文件改造与 dry-run 验证。
- 当前 thesis-defense / construction：仍执行旧协议，**不得视为已修复**。
