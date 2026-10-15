# 致谢与来源

核心 skill 是本仓库自己写的，下列项目的思路被拆开、改写后放进了对应位置（没有逐字复制原文）。
`extras/` 中原样引入的 skill 见 `extras/upstream.json` 和各目录的 UPSTREAM.md。

| 来源 | 许可 | 借用的内容 | 放在哪里 |
|---|---|---|---|
| [obra/superpowers](https://github.com/obra/superpowers)（Jesse Vincent） | MIT | 计划写给无上下文的执行者；每任务一个新子代理；失败升级到更强模型；系统化排查；收到审查意见先核实；收尾时选择合并方式 | plan、build、debug、review、ship |
| [mattpocock/skills](https://github.com/mattpocock/skills)（Matt Pocock） | MIT | 一次一问的访谈（grill-me）；任务依赖图、随时取可开工的一批、实现与合并分开（to-tickets、implement-spec）；术语表与“三条都满足才记录决定”（domain-modeling）；跨会话交接（handoff）；一次性原型回答设计问题（prototype）；复盘与“能机械检查的就写成检查”（retro）；先红后绿、避免同义反复的测试（tdd） | grill、handoff、plan、retro、guardrails、worker |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills)（Addy Osmani） | MIT | 框架代码以官方文档为准（source-driven-development） | plan |
| [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | MIT | “先问需不需要、仓库里有没有、标准库能不能”的递进顺序；在所有调用方经过的地方修根因；不能省略的保护；给有意的简化标注上限 | worker、debug、plan |
| [lennney/stop-that-shit](https://github.com/lennney/stop-that-shit) | MIT | 把失败变成空结果的捕获是缺陷；已有保护在弄清作用前不删 | review、worker |
| [tanweai/pua](https://github.com/tanweai/pua) | MIT | 放弃前的 7 项检查；换参数不算换方法；什么才算一次失败 | debug、build |
| [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd)（Ayoub Ghriss） | MIT | 汇报第一行给结果、编号、只给一个下一步、阻塞格式 | AGENTS.md |
| [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) | Apache-2.0 | 以第一次使用者的身份试用、问题分级（dogfood）；agent-browser 的使用循环；Electron 程序走 CDP | review、extras/webapp-testing、extras/computer-use |
| [trailofbits/skills](https://github.com/trailofbits/skills) | CC BY-SA 4.0 | 只借思路、用自己的话重写：自定义 semgrep 规则要先写测试且包含“不该报”的例子（semgrep-rule-creator）；uv/ruff/ty 的工具选择（modern-python）；性质测试的规律表、强弱顺序和两种无效写法（property-based-testing） | guardrails、plan/references/test-techniques.md |
| [github/spec-kit](https://github.com/github/spec-kit) | MIT | plan 阶段产出接口契约；先做阻塞所有人的基础阶段，之后各条线并行；契约测试先写并确认失败；“改不同文件、无依赖才能并行” | plan（第 3.5 步）、build、wf contracts |
| [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) | MIT | 按角色分工、每个故事交给对应角色执行的思路（只做成任务卡上的“执行者”字段，不引入角色人格和流程） | plan、build、.opencode/agents |
| [supabase/agent-skills](https://github.com/supabase/agent-skills) | MIT | Postgres 规则的分类和优先级（supabase-postgres-best-practices） | extras/postgres |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 的 frontend-ui-engineering | MIT | 组件与状态、避免 AI 默认风格、无障碍、四种数据状态、响应式 | extras/frontend-engineering |
