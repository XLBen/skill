# thesis-defense — 答辩与论文（苏格拉底）skill（opencode）

为一个项目/功能写带编号的论证论文，再由"导师"对抗性质疑，直到找不出明显硬伤（或轮数上限）才通过。产出的 `docs/thesis.md`（status: passed）是 [construction](../construction/) 施工 skill 的开工凭证。

## 机制一览

- **双 AI 全自动对抗**：主代理扮学生（写论文、自答、修订），examiner subagent 扮导师（按攻击面×章节矩阵 + L1-L5 问题阶梯出题）。轮与轮之间不停顿，自动跑到 0 硬伤或轮数上限；用户只在启动、僵持仲裁、收报告三类时点介入
- **反灌水（导师侧）**：问题必须过实质性门槛——每题标注"若成立改什么"，写不出影响不出题；钢人先行（先复述论文最强立场再攻击）；权衡式提问（对比选择句式优先）；每轮附 0–2 条可直接采纳的强化建议。单轮 ≥2 题被撤题/判 IM → 下一轮问题上限自动减 2
- **反强行解释（学生侧）**：只有四种合法回答——证据型/修订型/假设型/IM 撤题型；强行解释视同未答且计硬伤；权衡类问题必须给双边权衡表（收益/代价/前提），答不出代价的决策视为未权衡
- **学生自答有据**：来源优先级 = 项目材料 → 官方文档核实 → 最小实验 → 登记为待验证假设；凭记忆口头作答视同未答
- **论文 7 章 + 条目编号**（P-目标/D-决策/A-假设/R-风险/V-验证/B-边界），全链路可追溯
- **停机规则**：一轮 0 硬伤 → passed；轮数上限（轻量1/标准3/严酷5）→ conditional；换皮问题不计新硬伤，收敛可提前停；**有效轮门槛**（每轮 ≥2 道实质题，0 题轮重派，重派仍无则判收敛——防导师空转放水）
- **终态防自判**：硬伤计数逐条采信 examiner 复审标注，学生只转录；phase 字段落盘轮内阶段，断点精确恢复
- **深度拨盘**：轻量/标准/严酷，写进 frontmatter 后不再问
- **断点恢复**：状态全在 thesis.md frontmatter + defense-log.md，会话死了重开接着辩
- **防谄媚**：导师是干净上下文 subagent 且必须重读论文文件；禁令（不接受"以后再处理"、必须引用原文编号）；僵持记"待仲裁"不阻塞，用户可事后翻案
- **领域章程模板**：Web 服务 / CLI / 游戏 / 空白四套可判定硬伤标准（`references/charter-templates.md`），复制进目标项目 `docs/defense-charter.md` 裁剪后，导师叠加执行；严酷档 V-xx 支持 `（tdd）` 标记（施工须先红后绿）

## 目录结构

```
thesis-defense/
├── SKILL.md                     # 主入口（工作流、铁律、分发索引）
├── agents/examiner.md           # 导师 subagent（可选安装，强烈推荐）
└── references/
    ├── thesis-template.md       # 论文模板 + frontmatter + 编号规范
    ├── examiner-protocol.md     # 攻击面矩阵 + 问题阶梯 + 导师禁令
    ├── verdict-rules.md         # 硬伤/软伤判定 + 停机 + 恢复 + 仲裁
    └── charter-templates.md     # 领域章程模板（Web/CLI/游戏/空白）
```

## 安装（项目级）

```powershell
# 1. 复制 skill 本体
Copy-Item -Recurse "本目录\thesis-defense" "<目标项目>\.opencode\skills\"

# 2.（推荐）安装导师 subagent：干净上下文、只读、不护短
Copy-Item "本目录\thesis-defense\agents\examiner.md" "<目标项目>\.opencode\agent\examiner.md"
```

或在 `opencode.json` 用 `skills.paths` 指向本仓库目录。装完**重启 opencode**。

不装 examiner agent 也能用：skill 会回退为会话内【导师】/【学生】角色切换。

## 部署后自检

1. 在目标项目对 opencode 说："帮我答辩论证一下 <某方案>"
2. 应看到：深度拨盘（frontmatter 已含 depth 则跳过）→ 论文 v1 写入 `docs/thesis.md` → 自动答辩循环轮次推进（无需逐题回答）→ 结束输出答辩报告
3. 中途关掉会话重开再说"继续答辩"，应从断点恢复而非重头开始

## 与其他 skill 的关系

- 通过后 → 说"开工"，交给 [construction](../construction/) 把论文改写成施工计划逐步执行
- 施工中发现设计硬伤 → construction 会登记变更单（CR-xx）并切回本 skill 重辩对应章节

## License

MIT
