# 致谢与来源

核心 skill 是本仓库自己写的，下列项目的思路被拆开、改写后放进了对应位置（没有逐字复制原文）。
`extras/` 中原样引入的 skill 见 `extras/upstream.json` 和各目录的 UPSTREAM.md。

| 来源 | 许可 | 借用的内容 | 放在哪里 |
|---|---|---|---|
| [obra/superpowers](https://github.com/obra/superpowers)（Jesse Vincent） | MIT | 计划写给无上下文的执行者；每任务一个新子代理；失败升级到更强模型；系统化排查；收到审查意见先核实；收尾时选择合并方式 | plan、build、debug、review、ship |
| [mattpocock/skills](https://github.com/mattpocock/skills)（Matt Pocock） | MIT | 一次一问的访谈（grill-me）；任务依赖图、随时取可开工的一批、实现与合并分开（to-tickets、implement-spec）；术语表与“三条都满足才记录决定”（domain-modeling）；深模块、删除测试、一种实现是假接口（codebase-design）；跨会话交接（handoff）；一次性原型回答设计问题（prototype）；复盘与“能机械检查的就写成检查”（retro）；先红后绿、避免同义反复的测试（tdd） | grill、handoff、plan、retro、guardrails、worker、review |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills)（Addy Osmani） | MIT | 框架代码以官方文档为准（source-driven-development） | plan |
| [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | MIT | “先问需不需要、仓库里有没有、标准库能不能”的递进顺序；在所有调用方经过的地方修根因；不能省略的保护；给有意的简化标注上限 | worker、debug、plan |
| [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) | MIT | 多种理解时列出来而不是默默选一个；只清理自己改动造成的孤儿，原有死代码只提不删；每一行改动都能追溯到需求 | AGENTS.md、worker、review |
| [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | Apache-2.0 | 重构先锁住行为、不夹带功能、一次移动一个职责边界、每一步都能运行（safe-refactor）；该重构时不要硬塞进局部补丁、新增配置和依赖要由验收证明（lean-build） | plan、review |
| [OpenClaw superpowers 的 loop-circuit-breaker](https://openskillindex.com/skills/archieindian-openclaw-superpowers-loop-circuit-breaker) | —（只借思路，未使用其文本） | 按“同一调用 + 同一失败”识别重复失败并熔断 | .opencode/plugins/wf-guard.js |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 的 interview-me | MIT | 心里先写假设和置信度；复述意图时必须写“不做”；“你看着办/听起来不错”不算确认；能预测用户对后面 3 个问题的回答才停；分辨“应该要”和“真正要”（没有沿用它每题附猜测的做法） | grill |
| Mom Test / JTBD 的发现访谈方法，参考 [deanpeters/Product-Manager-Skills](https://github.com/deanpeters/Product-Manager-Skills)、[JacobLinCool/ux-discovery-interviewer-skill](https://github.com/JacobLinCool/ux-discovery-interviewer-skill) | —（只借思路） | 问发生过的具体事而不是假设；理解问题时不给选项、不提方案；先确认问题再谈方案 | grill |
| [lennney/stop-that-shit](https://github.com/lennney/stop-that-shit) | MIT | 把失败变成空结果的捕获是缺陷；已有保护在弄清作用前不删 | review、worker |
| [tanweai/pua](https://github.com/tanweai/pua) | MIT | 放弃前的 7 项检查；换参数不算换方法；什么才算一次失败 | debug、build |
| [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd)（Ayoub Ghriss） | MIT | 汇报第一行给结果、编号、只给一个下一步、阻塞格式 | AGENTS.md |
| [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) | Apache-2.0 | 以第一次使用者的身份试用、问题分级（dogfood）；agent-browser 的使用循环；Electron 程序走 CDP | review、extras/webapp-testing、extras/computer-use |
| [trailofbits/skills](https://github.com/trailofbits/skills) | CC BY-SA 4.0 | 只借思路、用自己的话重写：自定义 semgrep 规则要先写测试且包含“不该报”的例子（semgrep-rule-creator）；uv/ruff/ty 的工具选择（modern-python）；性质测试的规律表、强弱顺序和两种无效写法（property-based-testing） | guardrails、testing |
| [github/spec-kit](https://github.com/github/spec-kit) | MIT | plan 阶段产出接口契约；先做阻塞所有人的基础阶段，之后各条线并行；契约测试先写并确认失败；“改不同文件、无依赖才能并行” | plan（第 3.5 步）、build、wf contracts |
| [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) | MIT | 按角色分工、每个故事交给对应角色执行的思路（只做成任务卡上的“执行者”字段，不引入角色人格和流程） | plan、build、.opencode/agents |
| [supabase/agent-skills](https://github.com/supabase/agent-skills) | MIT | Postgres 规则的分类和优先级（supabase-postgres-best-practices） | extras/postgres |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 的 frontend-ui-engineering | MIT | 组件与状态、避免 AI 默认风格、无障碍、四种数据状态、响应式 | extras/frontend-engineering |
