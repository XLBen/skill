---
name: thesis-defense
description: Use when the user wants to 论证/答辩/评审 a project or feature idea before building it — trigger words include "答辩", "论文", "苏格拉底", "论证这个方案", "评估这个项目", "写立项论文", "thesis", "defense". Runs an autonomous two-AI adversarial loop — the main agent plays the student (writes docs/thesis.md, self-answers, revises) while an examiner subagent plays the advisor — repeating automatically until zero fatal flaws (硬伤) remain or a round cap is hit, producing status: passed / conditional. Improvement-oriented, not win-lose debate: every question must pass a materiality gate (no manufactured objections, steel-man first, trade-off framing), every answer must be evidence-based or legitimately downgraded (no forced rationalizations, four legal answer types). The user is only needed to launch, arbitrate deadlocks, and read the final report. Use ONLY for pre-build argumentation of a project/feature; NOT for writing academic papers for humans, code review, or task execution (执行计划请用 construction skill).
license: MIT
metadata:
  language: "zh-CN"
  produces: "docs/thesis.md, docs/defense-log.md"
  next-skill: "construction"
---

# 答辩与论文（苏格拉底）

**成果声明**：为一个项目/功能写一篇带编号的论证论文，然后由"导师"对抗性质疑，直到找不出明显硬伤才允许通过。产出 `docs/thesis.md`（status: passed）作为施工 skill（construction）的开工凭证。

工作原理一句话：**先立论，再对抗，把返工从施工期提前到最便宜的答辩期。**

→ 断言要么有证据，要么登记为假设，不许裸奔
→ 导师出题必须过实质性门槛；学生只许四种合法回答
→ 修订只动被攻击的章节；状态全部落盘，会话死了能复活

## 0. 何时使用 / 何时不用

**使用**：动手开发前需要论证方案可行性；用户说"答辩/写论文/论证/评估这个方案/苏格拉底式拷问我这个项目"。
**不用**：给人类写的学术论文学术写作；已通过答辩进入执行阶段（用 construction）；单纯代码审查。

## 1. 断点恢复（每次启动先做）

读 `docs/thesis.md` frontmatter（无则全新开始）；`phase` 字段（questioning/answering/reviewing）决定轮内恢复到哪一阶段。**CR 回炉检测：扫描 defense-log 中《CR 回炉请求》且状态：待重辩的条目（由 construction 写入，不要求是末条）**。

- `status: draft | defending` → 按恢复细则（references/verdict-rules.md）从中断阶段继续
- `status: redefending` → 重辩中断，恢复限定范围重辩（范围读 redefense-of 对应 CR 的影响清单）
- `status: passed | conditional`（无待重辩 CR）→ 告知已完成，问是否重辩（升版 v(n+1)）或转施工
- `status: passed | conditional`（有待重辩 CR）→ 自动进入**限定范围重辩模式**（唯一权威描述：references/verdict-rules.md《回炉重辩协议》）
- 文件不存在 → 进入 §2 全新流程

## 2. 全新流程工作流（可复制清单）

```
任务清单：
- [ ] 1. 断点恢复检查（§1）
- [ ] 2. 深度拨盘：frontmatter 已含 depth → 直接沿用；否则问一次用户（§3）
- [ ] 3. 立项访谈：收集项目信息，按模板写论文 v1（读 references/thesis-template.md）
- [ ] 4. 读 references/examiner-protocol.md，按 §4 调度导师
- [ ] 5. 答辩循环（§5）：双 AI 全自动跑到停机条件，每轮判定读 references/verdict-rules.md
- [ ] 6. 收尾：写 status + 答辩报告 + 交接块（§7）
```

## 3. 深度拨盘（开场问一次，不重复问）

| 档位 | 轮数上限 | 每轮问题上限 | 攻击面 | 适用 |
|---|---|---|---|---|
| 轻量 | 1 | 3 | 仅 §1 问题、§2 方案、§3 决策 | 原型/小工具 |
| **标准（默认）** | 3 | 5 | 全部章节 | 常规项目 |
| 严酷 | 5 | 7 | 全部章节 + 必含≥2个"反驳级"问题 | 上线/付费/不可逆项目 |

用户不回答 → 标准。写入论文 frontmatter `depth` 字段，恢复时不再问。

## 4. 导师调度（每轮提问与复审前执行）

派发参数：论文文件路径、深度档位、答辩记录路径、**本轮问题数上限**（基线 3/5/7；verdict-rules.md 有灌水惩罚或轮有效性要求时由主代理重算，下限 2）。

1. **优先**：项目存在 `.opencode/agent/examiner.md`（本库 `agents/examiner.md` 复制安装）→ 用 task 工具派发给该 subagent，收回问题清单。子代理是干净上下文，只读不护短。
2. **回退**（未安装 agent 或 task 不可用）：会话内角色切换，发言冠以`【导师】`/`【学生】`。导师答题前**必须重新读 `docs/thesis.md` 全文**（从文件读，不凭记忆），并在输出中注明"已重读论文 v(n)"。
3. 导师禁令与出题规则见 `references/examiner-protocol.md`（出题前必读）。

## 5. 答辩循环（双 AI 全自动）

学生与导师都是 AI：**主代理扮学生**（写论文、自答、修订），**导师 = examiner subagent**（干净上下文出题复审）。循环**自动连续进行，轮与轮之间不停顿等用户**：

```
学生交付 v(n)（写盘 docs/thesis.md，phase: questioning）
→ 主代理用 task 工具派发 examiner（§4），收回问题清单 → phase: answering，提问段即时追加 defense-log
→ 学生逐题自答（来源优先级见下）+ 修订论文对应章节 + changelog → phase: reviewing，答辩段即时追加
→ 再次派发 examiner 复审：逐题判定（标准读 references/verdict-rules.md）→ 主代理逐字转录复审结论追加 log（不得改判严重度）
→ 轮有效性检查 + frontmatter rounds+1 / status 更新（verdict-rules.md《轮有效性门》）
→ 本轮 0 硬伤 → 通过收尾；否则 v(n+1) 下一轮；达轮数上限 → conditional 收尾
```

**学生自答来源优先级**：① 论文自身与项目内材料（代码/文档）② 官方文档与可核实来源（webfetch 抓取验证）③ 最小本地实验（能跑命令就用命令拿证据）④ 均不可得 → 登记为 A-xx 待验证假设，或归入"仅项目所有者可决"清单。

**学生的四种合法回答**（目标不是守住论文，是让论文变好）：

| 型 | 做法 |
|---|---|
| 证据型 | 给可核实证据，维持或强化原主张 |
| 修订型 | 直接改论文：承认表述有误/过强，弱化主张、补前提、改设计 |
| 假设型 | 登记 A-xx（三态），不硬撑论证 |
| IM 型 | 标记该题无实质影响 + 理由，走撤题复核（verdict-rules.md） |

**禁止强行解释**：为保结论扭曲事实、含糊其辞、造"听上去合理"的理由 = 违规，视同未答且计硬伤。对权衡类问题必须给双边权衡表（收益/代价/前提）——答不出代价的决策视为未权衡。导师侧的对称约束（实质性门槛/钢人/IM 撤题）见 references/examiner-protocol.md。

**仅有的三类暂停点（其余全程自动）**：
1. 阻塞性的 owner-only 决策（预算/偏好/法律/产品方向），学生无法以假设形式绕过 → 攒齐后一次性问用户
2. 学生与导师就某条僵持 → 按 verdict-rules.md 仲裁规则处理（用户不在场时记"待仲裁"按软伤计，不阻塞）
3. 答辩结束（passed / conditional）→ 输出答辩报告与交接块（§7）

每轮的题目、回答、判定全部追加到 `docs/defense-log.md`（恢复与"换皮检测"的依据）。

## 6. 铁律（违规直接返工）

1. MUST：论文每个关键论断带编号（P-目标 / D-决策 / A-假设 / R-风险 / V-验证 / B-边界），导师问题必须引用编号。
2. MUST：假设条目标注三态之一：已验证（附证据）/ 待验证（施工前 S0 步处理）/ 纯假设（说明为何可接受）。
3. MUST：§6 验证计划的每条 V-xx 是可执行命令或可观察结果，不接受"测试一下就行"。
4. MUST：导师不得接受"以后再处理/上线再说"式回答，除非落为 R-xx 风险 + 缓解措施。
5. MUST：停机判定只依据 verdict-rules.md 的硬伤定义，学生不得自行宣布通过。
6. MUST：循环自动连续（§5），禁止每轮停下来等用户确认；只允许 §5 三类暂停点接触用户。
7. MUST：学生自答必须留证据——写盘的修订、命令输出、抓取的文档；凭记忆口头作答视同未答。
8. MUST：实质性优先（symmetry，双方同规）——导师问题必须过 materiality gate（预期影响写不出不出题），学生禁止强行解释（四种合法回答之外视同未答）。双方唯一目标是让论文变好，不是辩论获胜。
9. MUST：终态硬伤计数逐条采信 examiner 复审的严重度标注，学生只转录写盘；擅自改判（如把"未解决(硬伤)"转记为软伤）视同自答自判，返工。
10. SHOULD：同一会话内不重读本 SKILL.md 本体，按需读 references/。
11. 争议僵持时按 verdict-rules.md 仲裁规则处理；用户（答辩委员会主席）一票裁决，可事后翻案。

## 7. 产出与交接块

`docs/thesis.md` frontmatter 终态：`status: passed`（0 硬伤通过）或 `conditional`（超限，附遗留硬伤清单）；同时记录 `version / rounds / depth / date`。

答辩结束输出**答辩报告**：轮数统计、每轮硬伤数变化、沉淀到 §8 的软伤、待仲裁条目（如有）、遗留硬伤（conditional 时）；随后输出交接块（用户复制即走）：

```markdown
## ✅ 答辩通过 — <项目名> v<n>
- 论文：docs/thesis.md（status: passed，<n> 轮自动对抗，硬伤 0，软伤 <k> 条已记入"已接受风险"，待仲裁 <j> 条）
- 答辩报告与记录：docs/defense-log.md
- 下一步：对 opencode 说"开工"或"施工"，construction skill 将把论文改写为施工计划
```

## 8. 分发索引（何时读什么）

| 场景 | 读 |
|---|---|
| 写论文 / 论文模板与编号规范 | `references/thesis-template.md` |
| 导师出题 / 攻击面矩阵 / 问题阶梯 / 禁令 | `references/examiner-protocol.md` |
| 判定硬伤软伤 / 停机 / 收敛 / 仲裁 / 恢复细则 | `references/verdict-rules.md` |
| 项目有 docs/defense-charter.md | 导师出题前必读（项目自定义硬伤标准） |
| 想给项目建章程 / 领域硬伤模板（Web/CLI/游戏/空白） | `references/charter-templates.md` |

## 9. 示例对照

| 用户说 | 行为 |
|---|---|
| "帮我论证一下要不要用 Rust 写这个 CLI" | 轻量或标准档 → 写论文 v1 → 双 AI 自动答辩跑到收敛 → 答辩报告 |
| "答辩这个项目"（docs/thesis.md 已存在 status: defending, v2, 第 2 轮进行中） | 恢复断点，自动继续剩余轮次，不重问深度 |
| "这个方案有没有问题，狠狠地质疑我" | 严酷档自动答辩循环，全程无需用户逐题回答 |
| "论文通过了，开始施工吧" | 输出交接块指路 construction skill |
