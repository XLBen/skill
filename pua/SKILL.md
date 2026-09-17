---
name: pua
description: Use internally at Guarded/Audited workflow acceptance gates, when completion is claimed without evidence, when a repeated failure needs a different approach, or when a handoff needs active gap checking. Normal work applies the same questions directly and does not require loading this skill. Apply evidence-first, fact-driven, try-harder discipline without bypassing gates or fabricating success.
license: MIT
metadata:
  language: "zh-CN"
  called-by: "mvp-delivery, contract-review, construction, test-author, reviewer, step-executor"
  public-command: "none"
  stages: "goal-validation, contract-release, plan-confirmation, test-freeze, step-verification, slice-acceptance, review-verdict, goal-verification, goal-finish"
  handoff: "ACCEPTANCE_HANDOFF"
  user-view: "i-have-adhd"
  source: "tanweai/pua adapted at e6e6cd237ad17750d179674bff52f8184abea8fd"
---

# PUA 验收纪律

这是一个内部验收能力，用于 Guarded/Audited 验收、证据缺失或失败恢复；它不是新的
公开命令，也不是把压力话术当作通过条件，Normal 工作直接执行同样的检查问题即可。
它把 [tanweai/pua](https://github.com/tanweai/pua) 的主动性、闭环和失败恢复方法
适配到本仓库已有的 goal、contract、PLAN、reviewer、owner 和 engine gate。

**先记住：狠话必须绑定动作。** 每次进入验收前，先确定 `stage_id`、当前产物、
验收范围和已有证据，然后按 `references/stage-checks.md` 索引读取对应 stage 的卡文件。不要只说
“我已经自检”；要运行适用的验证、阅读实际输出、记录缺口和下一步。

## Runtime Contract

1. 在 Guarded/Audited 阶段验收前加载本 skill，并按 `stage_id` 读取对应检查卡；
   Normal 工作直接执行同样的问题，不要求加载。子代理不会因为父代理
   加载过本 skill 而自动获得它；派发任务时必须显式要求子代理加载并执行检查卡。
2. 用一行外部诊断绑定事实和动作，不输出隐藏思考过程：

   ```text
   [PUA-ACCEPTANCE] stage=<stage-id> | 事实/来源=<evidence> | 缺口=<gap-or-none> | 下一步=<action>
   ```

3. 质询只检查当前阶段已约定的验收项、受影响范围和真实交接条件。它不能创造新的
   产品要求，也不能因为“更努力”而无限追加随机测试或复核。
4. 通过 PUA 检查不等于阶段通过。仍须执行已有的 `check.py`、测试、reviewer 或
   owner gate；PUA 只能把缺证据、漏范围和假完成暴露出来。
5. 检查结果只返回 `已满足`、`需修复`、`待 owner 决定` 或 `外部阻塞`，不直接手写
   goal、PLAN、ledger 或 engine 状态。

## Acceptance Handoff

当控制器派 fresh reviewer 做阶段验收时，任务正文必须带完整的
`ACCEPTANCE_HANDOFF`，并带 `pua_stage_id`。reviewer 不能只接收 ADHD 的短摘要；它
必须检查原始目标、当前声明、产物身份、实际证据、真实用户入口和已知缺口。

reviewer 的既有结构化结果继续放在 `issues` 中，并在有 `pua_stage_id` 时附加：

```json
{
  "pua_acceptance": {
    "stage_id": "goal-finish",
    "result": "satisfied|repair|owner|blocked",
    "scope": "checked scope",
    "evidence": ["path, command, event, or output reference"],
    "gaps": ["material gap or none"],
    "next": "one controller action"
  }
}
```

`pua_acceptance` 是 reviewer 返回的验收摘要，不是新的 engine event，也不能替代
`check.py`、测试、owner gate 或独立性证明。控制器负责核对它的证据，再用
`i-have-adhd` 把结果压缩为用户可执行的 preview、delivery 或 blocker；reviewer 不
负责对用户宣布完成。

## 三条红线

🚫 **闭环。** 你说完成了？证据呢？没有当前版本的验证输出、评审依据或 owner
   决定，不能把完成写进报告。命令写出来不等于命令执行过。

🚫 **事实驱动。** 说“可能是环境问题”“接口不支持”“权限有问题”之前，用工具
   读错误、查源码、核配置或跑最小探针。未经验证的归因不是诊断，是甩锅。

🚫 **穷尽，但不盲目。** 说“无法解决”前，确认已完成适用的方法步骤、换过真正不同
   的方案并保留原始结果。真实缺授权、缺工具、需 owner 决定或外部边界不可用时，
   证据化升级是正确动作，不是失败伪装。

## 3.25 还是 3.75

| 被动 3.25 | 主动 3.75 |
|---|---|
| 修完一个点就宣布完成 | 修完后检查同一根因、接口或受影响调用链的同类问题 |
| 只读最后一条错误 | 检查每个关键子进程、输入快照、输出内容和重复运行稳定性 |
| 说“用户再手动看看” | 先完成 agent 能完成的验证，再把真正需要 owner 的决定列清楚 |
| 没跑测试就说通过 | 执行适用验证并贴出与当前制品绑定的结果 |
| 缺信息就停 | 先查仓库、工具和一手资料，只询问会改变结果的事实 |

主动不等于扩大范围。冰山法则的边界是同一根因、同一接口、共享实现或受影响调用
链；相关缺口处理完、复验通过且没有新证据时停止。

## 五种偷懒模式

验收时逐项检查有没有这些模式：

- **暴力重试**：同一失败签名重复跑，输出没有新信息。
- **甩锅用户或环境**：没有验证就要求用户手动处理，或把问题归因给权限、网络、版本。
- **闲置工具**：已有 Read、搜索、测试、日志或探针，却只凭记忆下结论。
- **假忙**：改参数、改措辞、增加工件数量，却没有缩小根因或提高验收覆盖。
- **被动等待**：修了表面症状就停，不查同类问题、不跑交付路径、不说明剩余边界。

发现模式时必须绑定一个动作：换本质不同的方法、运行区分性探针、检查同类范围、
补当前版本证据，或带事实等待 owner。不要用更多旁白替代动作。

## 压力升级

失败计数只统计**同一子目标的一次实际方案未达到预先定义验收**。命令退出码、
读文件成功、预期的 behavior-red、等待 owner、搜索无匹配和仍在运行的任务不能机械
计数。按已有工作流的同一失败签名和 no-progress 口径计数：

| 历史失败数 | PUA动作 | 本仓库动作 |
|---:|---|---|
| 0 或 1 | L0：读事实、修根因、完成当前验证 | 正常继续 |
| 2 | L1：换本质不同的方法，列出可区分的假设并执行一个探针 | 不重复原方案 |
| 3 且为同一签名 | L2：搜索、读源码、列三假设、准备七项检查 | 触发 construction 既有三连败熔断或 mvp no-progress 升级 |
| 4 或更多 | 不增加普通重试 | 只按既有 owner/CR/blocked 恢复流程处理 |

第三次不是继续试第四次的许可证。L2 清单用于整理证据和两个具体方案；不能绕过
既有熔断、预算、CR、owner 或安全授权。

## L2/L3 检查清单

在重复失败或高风险验收升级前，逐项给出结果：

- 是否逐字阅读失败信号和完整相关输出？
- 是否搜索过错误原文、官方文档或仓库中的同类用法？
- 是否阅读了失败位置的原始上下文，而非只看摘要？
- 关键前置假设是否已用工具确认？
- 是否尝试过相反的假设，而不是只微调原方案？
- 是否能在最小安全范围复现？
- 是否换过工具、方法、角度或技术路径？

不能执行的项目必须说明原因和替代证据，不得伪造勾选。

## 子代理与权责

派发 `test-author`、`step-executor` 或 `reviewer` 时，在任务正文中传入 `stage_id`、
检查范围、输入工件和以下要求：

```text
加载 pua skill，按 references/stage-checks.md 索引读取 <stage_id> 对应的卡文件。
返回 [PUA-ACCEPTANCE]、事实证据、缺口和下一步；不要只返回“通过”。
不要越过自身角色修改产品、降低严重度、替 owner 决定或宣布整个目标完成。
```

父控制器必须核对返回中是否有真实检查对象和证据引用。加载 skill 不会创造独立
身份；reviewer 仍须由 fresh subagent 或真实独立 session 执行。

## 边界

- PUA 不替代 `check.py`、测试、`verify-step`、`verify-goal`、reconcile、reviewer 或 owner。
- PUA 不允许编辑冻结测试、评分器、验证器、权限、状态或契约来制造通过。
- PUA 不代答 brief 确认、PLAN 确认、切片验收、SI 决定或人类 V。
- 缺少授权、MCP、凭据、真实外部边界或用户决定时，保持阻塞并提交最小下一步。
- 正常通过时不要为了展示 PUA 而制造额外仪式；满足既有验收且证据覆盖当前制品即可交付。
- ADHD 输出不改变 PUA 的检查范围；展示最多五项不允许隐藏 material gap、owner gate
  或未验证的真实边界。

## References

| Need | Read |
|---|---|
| 通用验收顺序、结果路由和输出格式 | `references/acceptance-protocol.md` |
| 九类阶段检查卡 | `references/stage-checks.md` |
| 失败计数、换方法、熔断和冰山范围 | `references/recovery-protocol.md` |
| 上游来源、适配范围和许可证说明 | `UPSTREAM.md` |
