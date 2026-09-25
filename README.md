# MVP delivery skills

[English](README.en.md) · 简体中文

这套 OpenCode workflow 把设计和施工分开：**grill 问清需求，plan 设计完整的软件，
build 按具体任务实现与实测**。关键工程判断（架构、接口、依赖顺序、验收标准）
全部前移到 plan；build 只消费一个有界任务包，不重新设计系统。

这样做的直接收益：plan 阶段可以用更擅长设计的模型，build 阶段切换到
DeepSeek / GLM 等较省的模型也能少猜、少返工、少读无关上下文。结构校验只是
辅助工具；最终目标始终是用户真正可用的运行结果。

## 总思维链

直接使用 `/work <目标>` 可由一个命令自动串起需要的阶段；下图仍说明各专业阶段的职责，不再要求用户手动先跑 `/grill` 或 `/plan`。

```text
想法
 ↓  我说得清吗？——说不清 → /grill（拷问）
 ↓  十二维覆盖表全关 + 用户确认 → docs/brief.md
 ↓  /plan：综合需求 → 查证技术 → 组件/接口/数据流 → 全部施工级任务 → 设计走查 → 发布
 ↓  /build：next-step 任务包 → 实现 → 本层验证 → 读实际输出 → observe 反馈
 ↓  组件 → 实际边界 → 集成里程碑（按计划依赖推进）
 ↓    实现错误 → retry（修本步）  缺环境 → blocked  设计假设被证伪 → replan（回 plan）
 ↓  集成里程碑回看原始结果清单——有差距 → 下一任务（循环）
 ↓                          ——无差距 → 验收：证据呢？
  ↓  验收通过 → 目标卡要求时做完整产品黑盒观察（product-observer，模型由 /visibility 选择）
 ↓  观察 gate：v2 报告 + 原生 trace —— 有阻断缺陷 → /fix → 新候选全量重观察
 ↓                                        —— 无阻断缺陷 → delivery
 ↘  出 bug → /fix：复现→隔离→假设→验证
 ↘  会话断了 → /resume：next-step 任务包 → 目标卡 → 代码
```

每一跳的判断依据都持久化在文件里（brief、工程设计、目标卡、cycle 回执、
delivery-log），不依赖聊天记录。下面逐段展开这条链。

## 职责分界

| 阶段 | 回答的问题 | 不做的事 |
|---|---|---|
| grill | 要什么、为什么、什么算成功 | 不决定怎么做 |
| plan | 系统怎么组成、任务怎么排、每步怎么验证 | 不写产品代码 |
| build | 当前任务实现、实际输出观察、反馈分类 | 不重新设计接口/架构 |

## 新增：有依据、有条件的规划

新计划采用 `engineering-plan/3`（目标卡仍为 schema 3）。完整覆盖不等于提前冻结
所有未知实现：关键未实测主张须关联条件，实际探测/用户可接受性/独立设计审查
分别解除对应条件，未满足时仅阻塞相关任务及后继。

- **grill**：说明交互方式、等待/校准/设备占用及失败损失，登记禁令保护对象。
  对高影响陌生路线优先演示或具体场景说明；文字同意有效，但不能扩大确认范围。
- **对话**：owner 以反问回复时先回答事实、再问真正待决点；question 选项简洁单行。
  新 brief 用 topic key + supersedes 检查同一决策的跨轮冲突；最终摘要由
  `brief-confirmation` 从当前 brief 重生成，semantic 编辑会使确认 snapshot 失效。
  人工确认仍需真实交互；snapshot/hash 不认证说话人。若需把决定记录绑定到会话原文，
  `runtime_trace export --include-conversation-text` 是显式隐私选项，只导出项目匹配会话，
  文件应留本地并加入 gitignore；默认 trace 不含聊天正文。

运行 `python .opencode/workflow/scripts/check.py brief-confirmation docs/brief.md`
预览当前逐项范围；相同 decision_key 的历史选择需通过 `supersedes` 明确替代，
跨 topic 的语义矛盾仍需人工/审查走查。确认 snapshot 绑定的是内容，不是答复者身份。
- **plan**：证据必须支持当前主张，备用方案未验证不算风险关闭；探针脚本不能由
  需要它的同一步才创建。Guarded/Audited 的正式实施受独立设计 review 条件约束。
- **走查**：尝试找出自举循环、暂停生产者却等结果、重复副作用、混用参考帧、
  回退缩水与不成立的长期预算，而不是再讲一遍正常路径。
- **中途异议**：`request-decision` 持久暂停原尝试；`resolve-decision` 引用实际回复。
  继续不等于测过，改方案返回 plan；回复版本保留。“算了”须澄清，不能自动批准。

详见 [工程反例走查](writing-plans/references/engineering-challenges.md) 与
[待决条件/决定协议](mvp-delivery/references/planning-readiness.md)。引用存在与 hash
匹配不认证用户/评审身份；仍需真实宿主对话、派发和原生证据。模型盲测反例集见
[skill 说明](README.en.md)，不把引擎结构检查当模型能力证明。弱模型实际效果尚未评估。

## 第一步：grill —— “我说得清吗？”

`/grill <idea>` 只做一件事：把模糊想法问成双方都能复述一致的需求简报。

1. **画决策树，只问 frontier**。前置问题已确定的才问；答案解锁后续问题。
2. **每轮通常 3–5 个低风险问题；重大分叉一次问一个**，先吸收答案、分析变化，再推导下一轮。每一轮
   都必须是**真实交互**：优先用 `question` 工具发出，否则以问题结束回合等待
   回复；禁止同一回合自问自答。
3. **十二维覆盖表收口**：用户与场景、公开入口、运行环境、代表性输入、输出与
   获取、**错误与边界**、数据与状态、权限与隐私、非功能、集成、成功信号、
   非目标。每个维度要么有 item、要么显式不适用；全维关闭且一轮无新信息才终止。
4. **事实归 agent**。能从仓库、代码、一手文档查到的不问用户；外部事实按
   research skill 分级，带引用和时效。
5. **定稿三问**：这份 summary 是用户说的还是我替用户补的？每个维度都关闭了
   吗？有没有偷偷缩小范围、把可选愿望标成必需？

反问式回答是新信息，不是替前一个选项作答：先查证回答，再重问真正待决点。
提问格式也影响答案质量：question 工具每题一个决定，选项短标签单行、说明短句；
技术细节放前置 context，不塞多行选项。若客户端渲染乱，退回一条纯文本问题。

产出：经确认冻结的 `docs/brief.md`。下一步 `/plan docs/brief.md`。

## 第二步：plan —— “整个软件怎么组成，每个任务怎么施工？”

`/plan` 是工程设计者，不是访谈纪要整理器。它的产出是一份可独立阅读的
工程设计（默认 `docs/plan.md`，用户可指定任意项目内路径），思维链：

1. **综合需求，不续写问答**。把 grill 条目重组成用户工作流：前置状态 →
   输入/动作 → 状态变化 → 输出取得 → 失败恢复。每条必需结果对应到工作流。
2. **消除最贵的技术不确定性**。先查一手文档、已安装 API、真实代码，确认
   库能否完成目标操作、权限/平台约束是什么。可做只读探查；必须操作真实
   目标才能查明的能力，安排**靠前的有预算验证任务**，后续步骤给出完整的
   条件性设计。不为“方案完整”编造 API。
3. **完整软件设计**：组件职责与状态归属、数据模型、跨组件共享接口（每个
   接口唯一生产者，消费者依赖它）、目录布局、数据流/依赖图。互斥的产品
   分叉问用户；普通工程选型自己给结论和依据。
   高层架构设计/评审或重大架构决定按需加载 `architecture-designer` 上游原文；
   按原文记录重要决定的 ADR，并在定稿前进行真实干系人评审。
4. **全部任务达到施工精度**——不只第一片。每个任务带：目的、依赖、最少
   必读文件、改动范围、消费/产出接口、有顺序的实现动作、关键代码骨架、
   边界行为、分层检查、失败分支（实现错怎么修/缺什么环境/什么证据意味着
   退回设计）、回退。后续任务不能只是标题。
5. **分层验证设计**：

   | 层 | 时机 | 证明什么 |
   |---|---|---|
   | component | 组件就绪 | 组件行为；不要求完整应用已建成 |
   | boundary | 适配器就绪、扩张上层前 | 真实接触目标文件/设备/窗口/API 并回读 |
   | journey | 阶段接通后 | 经交付公开入口完成用户动作 |
    | final | 完整候选 | 全部承诺 + 目标卡要求时的独立产品观察 |

   负向对照只放在有意义的故障点，不强制每个组件配非零退出码脚本。
6. **发布与自动记账**：

   ```powershell
   python .opencode/workflow/scripts/check.py prepare-plan <goal> <design-path>
   python .opencode/workflow/scripts/check.py next-step <goal>
   ```

   `prepare-plan` 自动算 hash 绑定、从 browser/desktop 旅程推导 UI 验收义务、
   使过期证据失效，并生成完整**可读计划** `<design>.readable.md`（逐步标题、
   独立代码块、命令、失败处理，保留逻辑图）——用户不用读转义 JSON，也不维护
   两份规格。`next-step` 预览 build 实际收到的任务包。
7. **发布前设计走查**：拿一个正常输入和一个失败输入逐步模拟施工——输入穿过
   哪些文件/接口/边界？后续任务单独交给无历史会话能否开工？有无断开的调用、
   虚构 API、组件测试过早依赖完整 UI？通过结构检查 ≠ 设计正确；走查负责内容。

完整参考：[设计模板与任务字段](writing-plans/references/design-template.md) ·
[工程计划示例](writing-plans/references/engineering-plan-example.md)。

## 第三步：build —— “实现当前任务，实测后推进”

`/build` 是有界执行者。核心循环只有五个命令：

```text
python .opencode/workflow/scripts/check.py next-step   <goal>   # 当前任务包
python .opencode/workflow/scripts/check.py begin-cycle <goal>   # 只探测本步前提
#   按 implementation/change 实现本步；不改共享接口，不提前做后续任务
python .opencode/workflow/scripts/check.py verify-cycle <goal>  # 运行本步检查
#   读 observed 里的真实 stdout/stderr/退出码（截断时展开原始回执）
python .opencode/workflow/scripts/check.py observe-cycle <goal> --decision <d> --interpretation "<实际 vs 预期>"
#   再 next-step：工具自动选择下一个依赖就绪任务
```

- **任务包**：当前步骤 + 必要全局约定 + 本步消费/产出的合同 + read_files +
  检查。未来任务、无关合同、全部历史默认不进入上下文。
- **原始输出自动捕获**：observe-cycle 附带本尝试的真实回执；模型只写解释和
  决定，不手填 actual JSON，也不能用预测文本替代。
- **失败分流**（先归因再行动）：

  | 证据 | 决定 |
  |---|---|
  | 本步实现不满足既定接口/断言 | `retry`：最小修复本步后新尝试 |
  | 缺设备/驱动/服务/权限 | `blocked`：报具体前提；不换 mock 通过 |
  | 接口、状态模型、驱动能力等设计假设被证伪 | `replan`：带证据回 plan；旧设计锁定，修订发布后才能继续 |

- **分层执行**：组件检查不要求未建成的完整应用；真实边界检查先于依赖它的
  集成里程碑；`cycle-gate` 检查全部步骤及版本绑定，接入 `finish-goal`/
  `check-current`。固定样例的检查之外还需变化输入与状态回读——校准实验中，
  一个能通过固定正/负样例的假实现仍被随机内容检查拒绝。
- **席位**：Guarded 实质任务派 worker（一次一个任务包，不给整个会话历史）；
  Normal 可主控直做；Audited 按严格席位表。独立 review 放集成里程碑/验收点，
  不为每个组件测试造评审仪式。
- **失败预算**：同一失败签名第二次必须换证伪方法；三次无新证据 = no-progress
  blocker，向用户升级而不是机械重试。新 task/session 不清零失败历史。

执行协议：[任务包与分层反馈](mvp-delivery/references/engineering-delivery.md)。
可以用更擅长设计的模型做 plan，再切换 DeepSeek/GLM 等模型 build；工具不替你
虚构或自动切换模型。**成本与稳定性改善需要真实模型任务评估，不能从引擎单元
测试数推导**；此前曾做安装后确定性 CLI/file 校准，但测试脚本和报告依用户要求
从仓库移除。真实 DeepSeek/GLM 端到端评估未做。

## 验收的思维链 —— “证据呢？”

每个实质交接点的自我质询（PUA 纪律，Guarded/Audited 加载卡，Normal 直接问）：

- **闭环**：说完成了？证据呢？没有当前版本的验证输出，完成不能写进报告。
  命令写出来 ≠ 命令执行过。
- **事实驱动**：说“可能是环境/权限/网络问题”之前，先用工具读错误、查源码、
  跑最小探针。未经验证的归因是甩锅。
- **穷尽但不盲目**：说“无法解决”前，确认换过本质不同的方案、检查过同一
  根因的同类调用点（冰山法则）。
- 五种偷懒模式自查：暴力重试、甩锅用户或环境、闲置工具、假忙、被动等待。

最终报告分开列出：单元/mock 检查、真实边界、公开入口旅程、未验证/阻塞项。
不用测试总数概括产品可用性。界面验收路由：Web-only 旅程 → webapp-testing；
原生应用/OS 对话框 → computer-use（每场景硬预算：≤15 动作、每动作 ≤2 轮观察、
10 分钟）。截图不是验收通过。

## 产品观察的思维链 —— “完整产品真用过了吗？”

实现和引擎验证只证明“命令能跑”；目标卡要求观察时，交付前还要有人第一次接触产品那样把完整
产品真用一遍。`/build` 在固定候选版本后派发 `mvp-product-observer` 独立席位，
它拿到的是公开简报与真实入口——不是 diff、测试或实现说明。

1. **两个阶段**：`discover` 盲态独立探索；`compare` 对照原始目标、历史产品
   地图与基线，专门找“消失了、退化了、只在某些模式里活着”的能力。
2. **观察模型**：`/visibility [模型名]` 选择，默认 `gpt 5.6 luna`；写入项目内
   `.opencode/mvp/visibility.json`，只作用于本项目观察派发，不改主聊天模型。
   派发由插件工具 `visibility_dispatch` 完成（需重启 OpenCode）。模型不支持
   图片时按 capability gap 记录，绝不假装看过。
3. **只观察，不修复**：observer 不写产品代码/goal/gate；宿主双层权限兜底。
   有状态产品正常写盘由 `.opencode/mvp/<goal>.runtime-state.json` 策略排除。
4. **输出与采纳**：observer 只回一个 ```json 围栏块（`product-observation/2`）；
   controller 校验后绑定真实 session/模型/packet hash 写不可变 `result.json`。
5. **门禁**：`check.py product-audit-gate <goal> --trace <trace>`。critical/high
   未解决、未解释的 capability gap、无原生 trace 都阻断 `finish-goal`。独立
   reviewer 分别判断 `findings_validity` 与 `coverage_adequacy`。
6. **修复循环**：阻断发现路由 `/fix`；修复产生新候选后必须全量重跑
   discover+compare，旧证据按候选 id 失效，不覆盖不改写。

真实模型校准结果见 [docs/po-repair/CALIBRATION.md](docs/po-repair/CALIBRATION.md)。

## fix 的思维链 —— 四阶段根因

`/fix <problem>` 按 systematic-debugging 执行：

```text
复现（最小可复现命令）→ 隔离（二分缩小，读真实代码与日志）
→ 假设（至少两个可区分假设，先跑证伪探针再改代码）
→ 验证（原复现转绿 + 受影响回归 + 边界抽查，回归测试固化根因）
```

通过受影响旅程复现，用 next-step 拿到任务和 failure_routes：实现错误局部修，
先跑本层检查再跑受影响边界/里程碑；接口/架构假设被证伪走 replan 修订计划，
不让执行模型边猜边打补丁。只跑 mock 的回归测试不能关闭在真实边界观察到的
缺陷。禁止：无证据甩锅环境、同签名暴力重试、shotgun 式一次改多处。

## resume 的思维链 —— 不猜进度

`/resume` 先运行 `check.py next-step <goal>`：它重放 cycle 历史，返回当前
任务包和 implement/observe/retry/blocked/replan/final-acceptance 动作，不需要
重读全部历史计划。有未观察尝试时先读回执再 observe；中断的运行只能
retry/blocked，不能补记成功。replan 交回规划者，修订并重新 prepare-plan 后
旧证据失效；已正确实现的代码复验即可，不因恢复或切模型而重写。多个候选
目标关系不明时问用户，不按 mtime 猜。

## 什么时候停下来问用户

1. 两个互斥的产品选择会明显改变结果，且仓库和输入都无法裁决；
2. 将执行不可逆或破坏性操作；
3. 涉及凭据、隐私、安全边界、真实付费或工作区外副作用；
4. Audited gate 需要 owner 实际验收；
5. 技术上不可达、每条路只能猜，或连续尝试没有新证据。

其余不确定性由 agent 作最小、可逆、符合现有模式的决定，记录后继续。

## 上下文怎么不被撑爆

build 每次只读当前任务包；不默认加载全部历史计划、dispatch archive 或
findings。每个 goal 完成后向 `docs/delivery-log.md` 追加 commit 式条目。
文件本体保留——引擎按路径绑定 hash；压缩的是“进入会话的内容”，不是磁盘
上的证据。会话被 OpenCode 自动压缩后，delivery-log 同样是首选重入点。

## 命令速查

`/work <目标>` 是一站式入口：目标模糊时自动用 `grill` 做自主需求推导，把推断标成假设，然后按当前实际可用的 skill 动态选择能力，规划、执行、修复并验证到完成。默认不为分析或规划单独生成 brief/计划文档；目标交付物或正式验收/恢复流程要求的文件仍照常生成。它不伪造用户确认，只有真实产品决策、授权或外部前提阻塞时才询问。新安装的 skill 在被当前 OpenCode 会话加载后会自动成为候选，无需维护 `/work` 名单。

| 命令 | 什么时候用 | 结果 |
|---|---|---|
| `/work <goal>` | 希望 agent 自主理解并推进目标 | 动态选择技能、规划/执行/验证，直到原目标有证据地完成或遇到真实阻塞 |
| `/grill <idea>` | 想法模糊，需要问清 | 经确认的 `docs/brief.md` |
| `/plan <goal-or-brief>` | 先看完整设计，不写代码 | 全目标工程设计 + 可读计划 + schema-3 目标卡；高风险另有编译 PLAN |
| `/build [goal]` | 开始交付 | 按任务包推进、实测观察、直到原始结果 verified |
| `/fix <problem>` | 报错、行为错误 | 根因修复 + 分层复验 |
| `/resume` | 上次中断 | next-step 任务包恢复到原始目标完成 |
| `/visibility [模型名]` | 选/看本项目观察模型 | 写入 `.opencode/mvp/visibility.json` |

推荐路径：一站式 → `/work`；需要先确认需求 → `/grill` → `/plan` → `/build`；明确 → `/plan` → `/build`；
bug → `/fix`；中断 → `/resume`。

## 内部 skills 速查

| Skill | 思维链角色 |
|---|---|
| `work` | 自主总控：模糊需求推导、动态技能发现、执行循环和目标验收 |
| `writing-plans` | 工程设计者：综合需求 → 组件/接口/数据流 → 全部施工级任务 → 设计走查 |
| `architecture-designer` | 上游原文：高层系统架构设计/评审、架构决策、ADR 与干系人评审（按需） |
| `mvp-delivery` | 施工控制器：任务包循环、分层验证、失败分流、收敛到原始目标 |
| `grill` | 需求拷问：决策树 + 十二维覆盖表 |
| `research` | 外部事实查证：来源分级、引用、时效 |
| `brainstorming` | 方案分叉：替代探索与收敛 |
| `systematic-debugging` | 根因四阶段：复现/隔离/假设/验证 |
| `contract-review` | Audited 契约评审与 PLAN 编译 |
| `construction` | Audited PLAN 施工与 CR 恢复 |
| `task-worker` | 有界实现工作包（fresh subagent，消费 implementation-packet） |
| `test-author` | 独立生成并冻结验收测试 |
| `reviewer` | 只读评审：设计走查验收、入口/断言语义、边界覆盖 |
| `step-executor` | 隔离执行单个严格 PLAN 步骤 |
| `webapp-testing` | Web 旅程：断言式浏览器自动化 |
| `computer-use` | 桌面旅程：硬预算 GUI 操作与验证 |
| `product-observer` | 目标卡要求时全产品黑盒观察：discover + compare；模型由 `/visibility` 选择 |
| `ponytail` | 上游原文：编码、代码设计及评审的最小正确实现选择 |
| `stop-that-shit` | 上游原文：范围、无用途防御及重复验证的条件型判断 |
| `skill-creator` | 条件型：创建、修改或实测 skill 的行为与触发条件 |
| `receiving-code-review` | 条件型：收到评审反馈后核实、澄清与有据采纳 |
| `frontend-design` | 条件型：用户明确要求视觉设计或界面改版 |
| `vercel-react-best-practices` | 条件型：适用的 React/Next.js 代码与性能规则 |
| `pua` | 验收质询：闭环/事实驱动/穷尽不盲目 |
| `i-have-adhd` | 用户沟通：短视图，不删完整事实 |
| `security-assurance` | 条件型：信任边界/认证/隐私/密钥的安全保证与威胁建模 |
| `production-readiness` | 条件型：生产发布、渐进推进、回退与运维交接 |
| `incident-response` | 条件型：线上事故定级、控制影响、恢复与复盘 |
| `outcome-learning` | 条件型：用户/业务结果假设、基线与最小实验 |

安装器另会部署 `mvp-researcher`、`mvp-worker`、`mvp-reviewer`、
`mvp-test-author`、`mvp-step-executor`、`mvp-product-observer` 六个项目子代理到
`.opencode/agents/`，带最小权限边界（reviewer 无写入；子代理禁止再派发）；
fresh 子代理提供真实独立 session，加载 skill 本身不创造独立性。

## 安装

需要 Python 3.10+，在本仓库根目录：

```powershell
python scripts/install.py "E:/path/to/target-project"
```

安装器复制 command wrapper、子代理定义、校验引擎与运行时工具（`check.py`、
`engineering_delivery.py`、`runtime_trace.py`、`workflow_protocol.py` 等）及
`stage-routing.json`，在 manifest 记录指纹供 doctor 检测漂移，并在
`opencode.json` 注册本仓库顶层 skill 目录。安装或修改 skill 后必须重启
OpenCode。桌面验证为可选：不自动安装 MCP、不改全局权限，接入见
[computer-use/README.md](computer-use/README.md)。

`ponytail/SKILL.md` 与 `stop-that-shit/SKILL.md` 是按固定上游提交逐字复制的原文（各目录 `UPSTREAM.md` 记录来源）；安装器将它们注册为本套件的 skill。按阶段加载的是原始提示词；不会自动安装 Ponytail 常驻插件、`/ponytail` 命令或 Stop That Shit Guard，不能把指令式边界宣称为宿主工具拦截。

新增五个条件型 skill 也保留固定上游提交的原文与引用文件（各目录 `UPSTREAM.md`）。`/work`、`/plan`、`/build`、`/fix`、`/resume` 仅在真实任务边界选择适用能力，不会为普通产品工作默认运行 skill 评估、视觉重设计、架构评审或 React 优化。`skill-creator` 的 Claude 专用评估/展示命令在 OpenCode 不会自动可用，须先确认实际后端并报告真实结果。

如需 `/visibility` 的动态观察模型派发：目标项目 `.opencode` 需能解析
`@opencode-ai/plugin`（安装器检测缺失时会提示，在该目录执行 `npm install`），
重启 OpenCode 后由插件提供 `visibility_dispatch` / `visibility_status`。

## 验证

```powershell
python scripts/check.py --selftest
python -B -m unittest discover -s tests -p "test_*.py"
python .opencode/workflow/scripts/check.py engineering-plan .opencode/mvp/<goal>.md
python .opencode/workflow/scripts/check.py next-step .opencode/mvp/<goal>.md
python .opencode/workflow/scripts/check.py cycle-gate .opencode/mvp/<goal>.md
python scripts/check_runtime.py doctor <target-project> [--strict [--strict-freshness]]
python scripts/runtime_trace.py export <target-project> --out trace.json
python .opencode/workflow/scripts/check.py product-audit-gate .opencode/mvp/<goal>.md --trace trace.json
python .opencode/workflow/scripts/check.py check-current .opencode/mvp/<goal>.md
```

运行时门禁（可选）：`runtime-policy.json` 启用后 `finish-goal` 要求先过
`runtime-gate`——用原生会话证据核验 dispatch 声明；手写/导入 trace 一律拒绝。
UI 门禁：`ui-gate ... --bind` 核验场景状态、真实工具加载、原生调用与产物
身份绑定；产物变化必须重跑重绑。观察门禁：schema-2/3 且 `product_observation.required: true` 的目标在 `finish-goal`
前必须过 `product-audit-gate`（必须带原生 trace）。

引擎检查结构、绑定、退出/超时与断言；hash 检测“验证后被改动”，不证明语义
正确，更不是沙箱。完整规则见各 skill 的 `SKILL.md` 与 `references/`。

## 能力边界（如实）

- 引擎只在**调用它的命令时**强制顺序，不能阻止模型在计划外先写一百个文件；
  这部分靠 reviewer 与原生 trace 核验。
- observe-cycle 校验观察字段与结果绑定，不判断文字是否诚实；负向对照只排除
  特定假成功，不能普遍证明实现没有伪造。
- 校准实验覆盖 CLI/文件系统边界；**未在桌面游戏、浏览器或真实模型上验证**。
  炉石类项目仍需 Airtest/computer-use 等真实后端，且后端能力必须实测。
- 旧 schema 1/2 完成历史保持可读；新项目直接使用 engineering-plan/3，旧工程
  迁移不是主流程。

## 设计参考

- [GitHub Spec Kit](https://github.com/github/spec-kit)：独立可验证的 MVP story。
- [OpenSpec](https://github.com/Fission-AI/OpenSpec)：progressive rigor。
- [Superpowers](https://github.com/obra/superpowers)：continuous execution、
  subagent 隔离；writing-plans / systematic-debugging / brainstorming 的
  方法论来源（见各自 UPSTREAM.md）。
- [Anthropic skills](https://github.com/anthropics/skills)：webapp-testing 的
  方法论来源（见其 UPSTREAM.md）。
- [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD)：按任务规模
  选择流程。

## License

MIT.
