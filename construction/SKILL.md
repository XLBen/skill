---
name: construction
description: Use when the user wants to 开工/施工/执行计划/按论文施工 — trigger words include "施工", "开工", "开始建造", "按论文施工", "执行计划", "继续施工", "construction". Reads the defended thesis (docs/thesis.md, status must be passed/conditional from thesis-defense skill), converts it into a checkbox construction plan (docs/PLAN.md) with per-step acceptance commands, then executes steps strictly in order — each step must pass verification before its checkbox is ticked and the next step starts. Handles interruption resume, change orders (CR-xx) bouncing flawed design back to re-defense. Use ONLY for executing a defended plan; NOT for writing the thesis (use thesis-defense) or unstructured coding tasks.
license: MIT
metadata:
  language: "zh-CN"
  produces: "docs/PLAN.md, docs/build-log.md"
  requires-skill: "thesis-defense"
---

# 施工工程

**成果声明**：把已通过答辩的论文（docs/thesis.md）改写成编号施工计划（docs/PLAN.md），严格串行执行：每一步通过验收 → 在计划文件打勾 → 才进行下一步。验收失败可修复重试；发现设计硬伤则停工登记变更单，回炉重辩后复工。

## 0. 门禁（开工前强制检查，学 stage gating）

读 `docs/thesis.md` frontmatter：

| 状态 | 处理 |
|---|---|
| `passed` | 正常开工 |
| `conditional` | 可开工，但需用户**明确同意一次**：告知《遗留硬伤清单》将注入计划"注意事项"节，受影响步骤加验证；同意后才继续 |
| `redefending` | **拒绝**：回炉重辩进行中，等其完成（出口 passed/conditional）再检 |
| `defending` / `draft` | **拒绝开工**：告知"论文尚未通过答辩（第 k 轮进行中）"，指路 thesis-defense skill |
| 文件不存在 | **拒绝开工**：指路 thesis-defense skill（"先说'答辩'写论文"） |

## 1. 断点恢复（每次启动先做，必须按 status 分支，不许无脑找未勾行）

`docs/PLAN.md` 存在 → **不重新规划**，读 frontmatter `status` 分支：

| status | 动作 |
|---|---|
| `planning` | 计划尚未经用户确认 → 展示计划，重走确认环节（见 references/plan-template.md），不得跳过 |
| `paused` | 用户主动暂停 → 从第一个 `- [ ]` 未勾步骤继续（幂等，已勾不重做） |
| `building` | 先校验 PLAN 记录的 thesis 版本 = docs/thesis.md 当前 version（不一致 → 停下展示两侧版本，走 step-protocol"复工前三步校验"的 b/c 项 + 用户确认后再继续），再从第一个未勾步骤继续 |
| `suspended` | **不复工**：展示未决 CR，指路 thesis-defense 重辩（细则见 references/step-protocol.md 恢复细则） |
| `done` | 告知已竣工；重跑需用户点名 |

同时读 `docs/build-log.md` 末尾恢复上下文。PLAN.md 不存在 → 走 §2 全新流程。恢复对账细则（勾/日志不一致等）以 references/step-protocol.md 为准。

## 2. 全新流程工作流（可复制清单）

```
任务清单：
- [ ] 1. 门禁检查（§0）+ 断点恢复（§1）
- [ ] 2. 读 references/plan-template.md，按 §3 映射把论文改写成 PLAN.md
- [ ] 3. 展示计划（含每步验收命令）请用户确认 → 确认后才开工
- [ ] 4. 循环执行：读 references/step-protocol.md 按 SELECT→EXECUTE→VERIFY→TICK→LOG 走每一步
- [ ] 5. 全部打勾 → 竣工报告 + 交接块（§5）
```

## 3. 论文 → 计划改写映射

| 论文章节 | 计划中的去向 |
|---|---|
| §2 方案总览 | 步骤序列主体（自底向上排序：骨架 → 模块 → 集成） |
| §4 A-[待验证] 假设 | **S0 技术验证步**（spike：最小实验证伪/证实，放在最前） |
| §6 V-xx 验证条目 | 对应步骤的验收命令（逐条落位，不许丢） |
| §5 R-xx 风险 | 对应步骤的"回退方案"字段 |
| §3 D-xx 决策 | 相关步骤的"做法约束"（写代码时必须遵守的选择） |
| §7 B-xx 边界 | 计划头部的"不做清单" |
| conditional 遗留硬伤 + §8 已接受风险 | 计划头部的"注意事项"节 |

## 4. 执行循环（每一步）

```
SELECT：读 PLAN.md 第一个 - [ ] 步骤
EXECUTE：做这一步（遵守其 D-xx 约束；不做清单外的事）
VERIFY：跑该步验收命令，留存输出摘要
  ├─ 通过 → TICK：编辑 PLAN.md 把该步 - [ ] 改 - [x]（附日期）→ LOG：build-log.md 追加记录 → 下一步
  └─ 失败 → 同思路重试 ≤2 次 → 换思路再 ≤1 次 → 仍失败 → 分流：
       a) 实现问题：说明卡点，请用户决策（继续/换方案/暂停）
       b) 设计硬伤（论文该章被证伪）→ 停工，登记 CR-xx 变更单，指路 thesis-defense 重辩该章
```

- **默认连续施工**：一路打勾到底；遇到"人工验收"步骤自动暂停展示检查点；用户说"暂停/停下"即挂起（status → paused，状态在 PLAN.md，随时可恢复）。
- **禁止跳步**：只能按顺序打勾；确需调整顺序 → 走变更单流程改 PLAN.md 并留痕。
- 详细规则（防假打勾、人工验收、变更单格式、恢复对账）读 `references/step-protocol.md`。

## 5. 竣工与交接块

全部步骤打勾后（无 `- [ ]` 且无作废行未处理）：**PLAN.md status → done**，并把对照表与交接块追加落盘到 `docs/build-log.md`（铁律 4：状态必须落盘，不许只存在于会话）。

对照表生成规则：先从 `docs/thesis.md` 枚举**全部** P-xx 与 V-xx 条目，再按每步"来源"字段机械汇总落位——**覆盖必须完整**，没有任何步骤落实的条目显式列"未落实 + 原因"（如"经 CR-01 作废"），不许静默省略：

```markdown
| 论文条目 | 承诺 | 落实步骤 | 状态 |
|---|---|---|---|
| P-01 ... | ... | S-03 | ✅ |
| V-02 ... | `npm test` | S-07 | ✅ 3 用例通过 |
| V-04 ... | ... | （无） | ❌ 未落实：经 CR-01 作废，替代方案随 CR-02 待重辩 |
```

竣工报告同时附：**待议清单**（EXECUTE 中累积的全部"待议"条目及去向）、遗留变更单（如有）、建议的后续动作。然后输出交接块：

```markdown
## ✅ 竣工 — <项目名>
- 计划：docs/PLAN.md（<n>/<n> 全部完成）
- 施工日志：docs/build-log.md
- 论文承诺对照：全部落实 / <k> 条经 CR-xx 变更
```

## 6. 铁律（违规直接返工）

1. MUST：论文 status 不为 passed/conditional 不开工（§0 门禁无条件执行；redefending 同样拒绝）。
2. MUST：每步的验收命令必须实际执行且通过，才允许改 `- [x]`；"人工验收"步骤必须用户明确确认后才可打勾。
3. MUST：写不出可执行验收命令的步骤 → 拆分该步骤，或显式标"人工验收"——不许含糊通过。
4. MUST：所有进度只记录在 PLAN.md / build-log.md 两个文件里（会话死活不影响状态）。
5. MUST：发现设计硬伤走变更单回炉，不许边施工边悄悄改设计。
6. SHOULD：每步规模 ≤ 半天工作量；超出必拆。
7. 不主动 git commit；用户要求时按其指定的粒度提交。

## 7. 分发索引（何时读什么）

| 场景 | 读 |
|---|---|
| 生成计划 / PLAN.md 格式 / 步骤字段 / 不做清单 | `references/plan-template.md` |
| 执行步骤 / 验收失败分流 / 变更单 CR-xx / 防假打勾 / 恢复细则 | `references/step-protocol.md` |
| 论文细节（各章条目含义） | `docs/thesis.md`（目标项目内） |

## 8. 示例对照

| 用户说 | 行为 |
|---|---|
| "开工"（docs/thesis.md status: passed） | 生成 PLAN.md → 用户确认 → S0 开始连续施工 |
| "继续施工"（会话中断后） | 读 PLAN.md 第一个未勾步骤接着干 |
| "施工"（thesis.md status: defending） | 拒绝：论文答辩进行中，先完成答辩 |
| 验收失败 3 次，判定论文 §3 D-02 的库不支持所需功能 | CR-01 变更单 → 指路重辩 §3 |
