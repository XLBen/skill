# skill — opencode 技能库

面向 [opencode](https://opencode.ai) 的中文 skill 集合。每个 skill 一个独立文件夹，复制进目标项目的 `.opencode/skills/` 或通过 `opencode.json` 的 `skills.paths` 注册即可使用。

## 本库包含的 skill

| Skill | 目录 | 一句话 | 何时触发 |
|---|---|---|---|
| **答辩与论文（苏格拉底）** | [thesis-defense/](thesis-defense/) | 双 AI 全自动答辩：AI 学生写编号论文、AI 导师对抗质疑，循环到 0 硬伤才放行 | "答辩""写论文""论证这个方案""苏格拉底式质疑" |
| **施工工程** | [construction/](construction/) | 把通过的论文改写成施工计划，逐步执行、验收打勾、失败回炉 | "开工""施工""按论文施工""继续施工""执行计划" |
| **Unity 6 2D 游戏开发** | [unity-engine/](unity-engine/) | Unity 6（6000.x）2D 项目中文参考库 + 预置 Editor 脚本 | Unity 项目的 C# 脚本、场景、Tilemap、性能等 |

## 核心流水线：答辩 → 施工

`thesis-defense` 与 `construction` 设计为一对，通过 `docs/thesis.md` 的 frontmatter 状态衔接：

```
用户提出项目想法
   ↓ thesis-defense：论文 7 章（P/D/A/R/V/B 编号）→ 双 AI 自动对抗：
   ↓   AI 学生（主代理）自答修订 × AI 导师（examiner subagent）L1-L5 问题阶梯攻击
   ↓   停机：一轮 0 硬伤 → status: passed（轮数上限 → conditional）
docs/thesis.md（status: passed）
   ↓ construction：门禁检查 → 论文改写为 PLAN.md（假设→S0 验证步，V-xx→验收命令）
   ↓                SELECT→EXECUTE→VERIFY→TICK→LOG 逐串行执行
   ↓                验收失败分流：实现问题修复 / 设计硬伤 → CR-xx 变更单
   └── 硬伤回炉 ──→ thesis-defense 重辩该章 → 更新计划 → 复工
全部打勾 → 竣工：论文承诺 vs 实际交付对照表
```

两个 skill 的状态全部落盘（thesis.md / defense-log.md / PLAN.md / build-log.md），会话中断后可从断点恢复。

## 安装（任选目标项目）

```powershell
# 方式一：复制进项目
Copy-Item -Recurse "本仓库\thesis-defense" "<目标项目>\.opencode\skills\"
Copy-Item -Recurse "本仓库\construction" "<目标项目>\.opencode\skills\"

# 方式二：注册本仓库路径（库更新项目同步生效）
# <目标项目>/opencode.json:
# { "skills": { "paths": ["E:/MISC/代码项目/skill"] } }

# 可选（推荐）：安装答辩导师 subagent（干净上下文、只读）
Copy-Item "本仓库\thesis-defense\agents\examiner.md" "<目标项目>\.opencode\agent\examiner.md"
```

装完**重启 opencode** 生效。

## 部署后自检

1. 在目标项目分别说"帮我答辩论证一下某方案"（应触发深度拨盘 + 写论文）与"开工"（应被门禁检查拦下或正常生成计划）
2. 中断会话重开，说"继续答辩"/"继续施工"，应从断点恢复而非重头开始

## 设计参考

本库的机制借鉴了社区成熟项目：spec-driven development（[github/spec-kit](https://github.com/github/spec-kit) 的阶段门禁与 converge）、[genkovich/sdd](https://github.com/genkovich/sdd) 的苏格拉底问答 + devil's-advocate 子代理 + 任务 DAG 执行引擎、[m4vic/socratic](https://github.com/m4vic/socratic) 的停机规则与渐进披露，以及 [anthropics/skills](https://github.com/anthropics/skills) 的 skill 编写规范。

## License

各 skill 独立 MIT，见各自目录下 LICENSE。
