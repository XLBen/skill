# 自检型 skill / 工作流：高星项目对比分析

日期：2026-08-30（星数为当日 GitHub 页面读数，动态数据）
对比基准：本库统一方案 `integration-plan.md`（三方苏格拉底答辩 × F/I 契约编译施工，经 `integration-audit-round-1.md` 一轮硬伤排查）

---

## 1. 检索口径

"自检型"指工作流内置**规范化质疑 / 一致性校验 / 收敛门禁**，而非事后人工 code review。按此口径筛出 5 个高星代表 + 3 个方法论近亲（本库 README 已收录来源）。

## 2. 高星项目总览

| 项目 | 星数 | 形态 | 自检机制核心 |
|---|---|---|---|
| [obra/superpowers](https://github.com/obra/superpowers) | 279.4k | 技能集 + 全流程方法论 | brainstorming（苏格拉底式设计打磨）→ writing-plans → subagent-driven-development（每任务两阶段评审：先规范符合性、后代码质量）→ TDD 红绿重构 → requesting-code-review（按严重度阻塞）→ verification-before-completion / systematic-debugging（4 阶段根因） |
| [anthropics/skills](https://github.com/anthropics/skills) | 172.5k | 官方技能规范 + 示例库 | 本身不是自检方法论，但定义了 SKILL.md 标准（本库遵循）；说明"生态位在规范层而非流程层" |
| [github/spec-kit](https://github.com/github/spec-kit) | 132.2k | SDD 工具链（CLI + 命令） | constitution → specify → plan → tasks → implement → **converge（循环到 Converged）**；自检命令：/clarify（欠指定区澄清）、/analyze（**跨制品一致性与覆盖分析**）、/checklist（"给英语写单元测试"——需求完整性/清晰性/一致性检查单）、bug 扩展（assess→fix→test）、assess 扩展（intake→research→define→shape→**decide: go/clarify/kill**） |
| [Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec) | 66.6k | 轻量 SDD | /explore → propose（proposal/specs/design/tasks）→ apply → archive；**增量 delta 规范**（ADDED/MODIFIED/REMOVED Requirement + WHEN/THEN Scenario），人审计划后才写码；哲学"fluid not rigid"，无刚性阶段门 |
| [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) | 52.5k | 多代理敏捷方法 | 交付环 Clarify→Plan→Build&verify→**Learn&adjust**；**right-sizing**（小改动直通 build）；持久上下文 briefs；PM/架构/UX/开发/测试**角色代理多视角**；BMad Loop 无人值守构建-验证-复盘 |

方法论近亲（低星但机制相近，本库设计参考）：genkovich/sdd（苏格拉底问答+魔鬼代言人子代理+DAG 执行）、m4vic/socratic（停机规则）、RobMitt/grill-me-skill（361★，决策树访谈）、Matt Pocock skills（research/prototype/handoff，stanislavfor 镜像收录）。

## 3. 逐项差异对照（他们 vs 我们）

| 维度 | superpowers | spec-kit | OpenSpec | BMAD | 本库统一方案 |
|---|---|---|---|---|---|
| 质疑对象 | 任务完成的代码（两阶段评审） | 制品间一致性（analyze）+ 实现与规范的收敛（converge） | 人审计划（无自动质疑） | 多角色评审 | **方案论证本身**（对抗性质疑到诚实异议清零） |
| 需求方地位 | 用户在 brainstorm/检查点出现 | 用户写 constitution + 各阶段确认 | 用户审 proposal | 用户做决策 | **独立第三方席位**，P/T 锚点 + 需求守恒门 + awaiting-owner 状态 |
| 停机规则 | 评审严重度清零 | converge 报告 Converged | 无显式停机门 | 交付环持续 | **无轮数上限 + 诚实异议门 + 终局干净审计** |
| 产物结构 | design doc + plan（自由格式） | spec/plan/tasks（模板化 markdown） | **delta 规范（结构化但轻量）** | briefs/specs | **P/T/W/F/I/D/E/A/R/V/B 全编号 + schema 校验 + contract-hash** |
| 施工衔接 | plan→任务（执行者自行理解） | tasks 即清单 | tasks 即清单，apply 执行 | 计划→代理执行 | **I variant/segment 确定性编译 S，禁止施工侧再设计** |
| 偏差处理 | code review 打回重做 | converge 把差距**追加为新任务** | 手工改制品 | Learn 环节 | **CR 台账 + 传递影响闭包 + 受影响 S invalidated** |
| 状态可恢复 | worktree/commit 粒度 | 制品文件 | 制品文件 + archive | briefs | **frontmatter 状态机 + phase + request/event ID 幂等恢复 + 步骤 attempt/补偿** |
| 事实争议 | —（靠 TDD） | assess 扩展 research 正反证据 | — | — | **争议转最小实验 E 证据包（可复现、脱敏、保留）** |
| 复用优先 | YAGNI/DRY（原则级） | 无 | 无 | 无 | **W 轮子台账 + 四级复用顺序 + fallback variant** |
| 体积控制 | 任务 2–5 分钟 | 无 | "lighter"卖点 | **right-sizing 拨盘** | 深度拨盘 + 范围最小论证到底 |

## 4. 关键差异分析

### 4.1 我们独有、且他们都没有的

1. **需求方作为有权威的第三方席位**：五家的用户都是"确认者/决策者"，没有一家把"需求不可在论证中被优化掉"做成守恒门 + 状态（awaiting-owner）+ 追溯格式（T: decided→applied）。
2. **论证层的无限收敛**：spec-kit 的 converge 是"实现 vs 规范"收敛（发现差距→补任务），不是"规范 vs 诚实异议"收敛。我们的停机定义（再反对只能忽略证据/重复旧题/虚构需求）在检索范围内没有先例。
3. **可机械编译的 F/I 契约 + hash 锁定**：spec-kit/OpenSpec 的 tasks 是"给 agent 看的清单"，允许执行时重新理解；我们禁止施工侧补设计，缺口只能退回答辩。
4. **CR 传递影响闭包**：他们的偏差处理是"追加新任务"（向前修），我们是"闭包作废 + 回炉重辩"（向后追溯）。各有代价，我们的更严，他们的更轻。

### 4.2 他们有、我们缺或弱的

| 差距 | 来源 | 严重度 | 说明 |
|---|---|---|---|
| **工具化执行器** | spec-kit（CLI）、OpenSpec（npm CLI）、BMAD（npx 安装器） | 高 | 我们全部靠 markdown 纪律由 agent 自觉执行，schema 校验 / hash 计算 / 状态机目前没有脚本兜底，最脆弱的一环 |
| **技能行为测试** | superpowers（drill eval harness）、spec-kit（fixtures/tests 目录） | 高 | 我们的 contract-schema 只有文字规定，没有正反 fixtures；应要求"hash 算法与 fixtures 写入 contract-schema.md"落地 |
| **多平台分发** | superpowers（15+ harness 插件市场）、anthropics/skills（官方市场）、BMAD（web bundles） | 中 | 我们只面向 opencode，安装靠复制目录 |
| **上手减重** | OpenSpec（"fluid not rigid"）、BMAD（right-sizing） | 中 | 我们 v4 契约字段多，虽有深度拨盘，但完整性门必填项不随档位缩减——这是审计中有意的取舍，代价是轻量项目嫌重 |
| **学习/复盘环** | BMAD（Learn & adjust、retro）、spec-kit（converge 报告沉淀） | 中 | 我们竣工只有"维护交接"，没有**方法论自我改进**环节（本轮答辩哪些问题该沉淀为 charter/模板更新） |
| **差距向前吸收路径** | spec-kit converge（差距→新任务，不回炉） | 低 | 我们所有设计级偏差都走 CR 重辩，小差距也重；可考虑"不影响 P/F/I 语义的差距直接追加 segment"的轻路径（需防滥用，仍需审计豁免口径） |
| **社区与生态** | 全部五家 | — | 客观差距，不在方法论层 |

### 4.3 相互印证的设计（说明方向没错）

- 我们的"诚实异议门 + 换皮检测" ≈ spec-kit converge 的收敛判定 + superpowers 评审严重度清零。
- 我们的 contract 完整性门 ≈ spec-kit /checklist（"unit tests for English"）——但他们生成**自定义**检查单，我们是固定 schema，可借鉴其按项目类型（Web/游戏/CLI）出 charter 模板。
- 我们的深度拨盘 ≈ BMAD right-sizing；均为"按项目体量调流程深度，不调最终质量"。
- 我们的 TDD 义务弱于 superpowers（其红线级），我们的 V 类型分层（local/integration/e2e/human）在粒度上更细，但没有把 RED-GREEN 定为铁律。

## 5. 定位结论

- **共同赛道**：五个高星项目全部收敛于"写码前先规范 + 制品化 + 门禁化"，证明本库方向正确；其中三家（spec-kit/OpenSpec/BMAD）与本库流水线同构（spec→plan→tasks→implement→check）。
- **我们的生态位**：检索范围内唯一的 **"论证深度最深 + 需求权威最强 + 状态可恢复性最严"** 的重型方案；代价是**无工具化、重、单平台**。
- **他们的生态位**：轻量、工具化、多平台、社区大；代价是需求保护弱（用户只是确认者）、论证无收敛保证（tasks 可被执行侧重新理解）、偏差只向前修不向后溯。
- **一句话**：他们解决"让 AI 按规范写码"，我们额外解决"规范本身值不值得信、需求有没有被论证过程偷走、施工敢不敢不改设计"。

## 6. 可吸收机制 → 行动建议

| # | 机制 | 来源 | 去向 | 优先级 |
|---|---|---|---|---|
| 1 | contract-schema 校验脚本 + 正反 fixtures | spec-kit tests / superpowers evals | 落实 integration-plan §14 的 contract-schema.md，附最小校验器（hash 规范化即脚本） | 高 |
| 2 | converge 式轻量差距吸收 | spec-kit | 施工侧：不影响语义的差距记"待议→追加 segment"而非一律 CR；需在 step-protocol 定义豁免边界 | 中 |
| 3 | 项目类型 charter 模板库 | spec-kit checklist | examiner-protocol 的 defense-charter 预置 Web/CLI/游戏模板 | 中 |
| 4 | 竣工复盘（Learn 环） | BMAD | construction 竣工交接后加"答辩-施工复盘"：哪些新问题应沉淀进 charter/模板 | 中 |
| 5 | RED-GREEN 铁律（可选档） | superpowers TDD | V-xx 增加 tdd 标记，严酷档要求实现 segment 附红绿证据 | 低 |
| 6 | 多 harness 打包 | superpowers / anthropics skills 标准 | 保持 SKILL.md 符合 agentskills 规范，未来可直接进市场 | 低 |

---

## 7. 落实记录（2026-08-30）

按"叙述风格照抄高星项目、缺失全补上"的要求，本轮已落地到仓库（v4 统一协议的实施仍待单独批准，见 `integration-plan.md` §15）：

| # | 机制 | 落点 | 状态 |
|---|---|---|---|
| 1 | 结构校验器（工具化执行器，当前协议版） | `scripts/check.py`（frontmatter / 编号普查 / A-xx 三态 / V-xx 可执行 / PLAN 串行与来源闭包） | ✅ selftest 通过；v4 contract-schema 校验器待 v4 实施时升级 |
| 2 | 正反 fixtures（技能行为测试） | `tests/fixtures/` 合法×2 + 非法×2，`--selftest` 回归 | ✅ |
| 3 | 领域章程模板库 | `thesis-defense/references/charter-templates.md`（Web/CLI/游戏/空白） | ✅ |
| 4 | 竣工复盘环（Learn & adjust） | `construction/references/retro-protocol.md`；SKILL.md §2/§5/§7 接线 | ✅ |
| 5 | converge 式轻量差距吸收 | `step-protocol.md`《轻量差距吸收》+ SKILL.md §4 + plan-template 来源写法 | ✅ |
| 6 | TDD 红绿标记 | thesis-template §6 `（tdd）` + plan-template 验收占位规则 | ✅ |
| 7 | 多平台分发说明 | 根 README《多平台》（opencode / Claude Code / agentskills 兼容 harness） | ✅ 文档级；未做插件市场发布 |
| 8 | 叙述风格对齐 | 两个 SKILL.md 顶部"工作原理一句话 + 箭头哲学块"（OpenSpec 式）；新文件按 spec-kit/superpowers 祈使句风格 | ✅ |

尚未落地（依赖 v4 实施）：contract-hash、F/I 契约、三方席位、无轮数上限状态机、CR 单一台账——见 `integration-plan.md`。
