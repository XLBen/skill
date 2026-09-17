# MVP delivery skills

[English](README.en.md) · 简体中文

这套 OpenCode workflow 的目标只有一个：把想法变成**真实验证过的运行结果**，
而不是让 agent 把问题问得很好、最后留下一堆规划工件。本文按这套 skill 的
思维链组织——agent 在每个节点怎么想、怎么判断、什么时候停下来问你。

## 总思维链

```text
想法
 ↓  我说得清吗？——说不清 → /grill（拷问）
 ↓  十二维覆盖表全关 + 用户确认 → docs/brief.md
 ↓  最薄的真切片是什么？风险多高？→ /plan
 ↓  首片：假设清单 → 实现 → 真实验证
 ↓  对照原始结果清单：还有差距吗？——有 → 下一片（循环）
 ↓                                ——无 → 验收：证据呢？→ delivery
 ↘  出 bug → /fix：复现→隔离→假设→验证
 ↘  会话断了 → /resume：delivery-log → goal 卡 → 代码
```

每一跳的判断依据都持久化在文件里（brief、目标卡、dispatch record、
delivery-log），不依赖聊天记录。下面逐段展开这条链。

## 第一步：grill —— “我说得清吗？”

`/grill <idea>` 只做一件事：把模糊想法问成双方都能复述一致的需求简报。

它的思维链：

1. **画决策树，只问 frontier**。前置问题已确定的才问；答案解锁后续问题，
   不按问卷顺序机械遍历。
2. **每轮 5–10 题，按维度分组**。一轮抛出后先吸收答案、分析它们改变了什么，
   再推导下一轮；绝不一次倒出所有问题。每一轮都必须是**真实交互**：优先
   用 OpenCode 的 `question` 工具发出，否则以问题结束回合并等待回复；
   禁止同一回合自问自答——只有用户真实给出的回答才能写进 brief。
3. **十二维覆盖表收口**：用户与场景、公开入口、运行环境、代表性输入、
   输出与获取、**错误与边界**、数据与状态、权限与隐私、非功能、集成、
   成功信号、非目标。每个维度要么有 item、要么显式不适用；全维关闭且
   一轮无新信息才终止。用户说“你决定”= 记录为 owner 决定，不是跳过。
4. **事实归 agent**。能从仓库、代码、一手文档查到的不问用户；外部事实按
   research skill 分级（官方文档/源码为 A 级，社区问答只作线索），带引用
   和时效记录。
5. **定稿三问**：这份 summary 是用户说的还是我替用户补的？每个维度都关闭
   了吗？有没有为了闭环偷偷缩小范围、把可选愿望标成必需？
6. 方案形态存在实质分叉（2+ 架构、build-vs-buy）时，先经 brainstorming
   探索替代方案再收敛，被否方案也记一行理由。

产出：经确认冻结的 `docs/brief.md`。下一步 `/plan docs/brief.md`。

## 第二步：plan —— “最薄的真切片是什么？”

`/plan` 的思维链：

1. **先读仓库再提问**。代码、配置、错误输出、一手文档能回答的，不问。
2. **选最薄可运行切片**：一条具体输入穿过必要层到达真实输出或持久状态；
   一条命令 / 一次浏览器操作 / 一次 API 调用能演示；不用 mock 的成功代替
   真实边界。
3. **按实际副作用判风险档**，不按主题词：
   - Normal：可逆的工作区内改动；
   - Guarded：外部边界、较高返工风险 → 加探针、验收测试、一次独立 review；
   - Audited：资金、隐私、安全、迁移、不可逆 → 契约、PLAN、独立测试作者、
     reconcile gate。
4. 首片 brief 按 **writing-plans** 写成可执行 prompt：Context（为什么）、
   Files（精确路径）、Change（实现草稿）、**Bounds（边界条件：空输入/极端
   规模/并发幂等/编码/失败中途/清理/兼容）**、Verify（命令+断言）、Rollback。
5. 界面旅程只设计场景，不执行。

## 第三步：build —— “实现一片，真验一片”

`/build` 的思维链：

1. **核实最少运行前提**：工作目录、OS/shell、运行时、依赖锁文件、配置
   变量名、服务、启动方式。缺依赖不是行为 red，不能用 mock 冒充。
2. **假设清单**：首片实现前，把准备自作的全部可逆假设一次性列给 owner
   扫认或纠正；不逐条阻塞，清单原样附在交付报告里。
3. Guarded/Audited 实质任务派 worker 子代理；Normal 允许主控直做；
   派发正文按 step brief 组织（见上）。
4. **失败思维**：先读错误修根因；失败签名（V+命令+断言+稳定错误摘要）
   跨 seat/resume 累计，同签名三次无新证据 = no-progress blocker，向用户
   升级而不是机械重试；第二次同签名就必须换本质不同的方法。
5. **每片通过后回看原始清单**：列出仍阻止用户达成目标的差距，选价值最高
   或风险最大的下一薄切片，先重判风险再选执行方式。MVP 是交付顺序，
   不是永久缩水。
6. **边际思维**：每步带 Bounds；reviewer 把“边界条件是否被考虑/测试”当作
   独立检查维度；未测边界是 finding，不是静默通过。

## 验收的思维链 —— “证据呢？”

每个实质交接点的自我质询（PUA 纪律，Guarded/Audited 加载卡，Normal 直接问）：

- **闭环**：说完成了？证据呢？没有当前版本的验证输出，完成不能写进报告。
  命令写出来 ≠ 命令执行过。
- **事实驱动**：说“可能是环境/权限/网络问题”之前，先用工具读错误、查源码、
  跑最小探针。未经验证的归因是甩锅。
- **穷尽但不盲目**：说“无法解决”前，确认换过本质不同的方案、检查过同一
  根因的同类调用点（冰山法则）；真实缺授权/缺工具时证据化升级是正确动作。
- 五种偷懒模式自查：暴力重试、甩锅用户或环境、闲置工具、假忙、被动等待。

界面验收的路由思维：Web-only 旅程 → webapp-testing（断言式浏览器脚本）；
原生应用/OS 对话框 → computer-use（每场景硬预算：≤15 动作、每动作 ≤2 轮
观察、10 分钟；期望连续 2 次不可观测 = failed 交回修复循环，不原地打转）。
截图不是验收通过。

## fix 的思维链 —— 四阶段根因

`/fix <problem>` 按 systematic-debugging 执行：

```text
复现（最小可复现命令）→ 隔离（二分缩小，读真实代码与日志）
→ 假设（至少两个可区分假设，先跑证伪探针再改代码）
→ 验证（原复现转绿 + 受影响回归 + 边界抽查，回归测试固化根因）
```

禁止：无证据甩锅环境、同签名暴力重试、一次改多处“看看好了没”（shotgun）。
契约与现实冲突走 CR，不绕。

## resume 的思维链 —— 不猜进度

`/resume` 的读取顺序：`docs/delivery-log.md` → 当前 active 目标卡 → 代码。
**已完成的 brief/PLAN/包全文停止默认加载**，需要核对具体结论时再按
delivery-log 里的证据指针展开。会话被 OpenCode 自动压缩后，delivery-log
同样是首选重入点。

## 什么时候停下来问用户

只有这些情况：

1. 两个互斥的产品选择会明显改变结果，且仓库和输入都无法裁决；
2. 将执行不可逆或破坏性操作；
3. 涉及凭据、隐私、安全边界、真实付费或工作区外副作用；
4. Audited gate 需要 owner 实际验收；
5. 技术上不可达、每条路只能猜，或连续尝试没有新证据。

其余不确定性由 agent 作最小、可逆、符合现有模式的决定，记录在假设清单和
交付报告中并继续。

## 上下文怎么不被撑爆

每个 goal 完成后向 `docs/delivery-log.md` 追加一条 commit 式条目（变更/
关键决定/验证摘要/证据指针/剩余限制）。文件本体保留——引擎按路径绑定
hash（brief 冻结、证据、artifact identity），被引用的文件不删除；只有确认
未被引用的 draft/中间工件可移入 `docs/archive/`。压缩的是“进入会话的
内容”，不是磁盘上的证据。

## 命令速查

| 命令 | 什么时候用 | 结果 |
|---|---|---|
| `/grill <idea>` | 想法模糊，需要问清 | 经确认的 `docs/brief.md` |
| `/plan <goal-or-brief>` | 先看路径，不写代码 | 轻量目标卡；高风险内部生成严格 PLAN |
| `/build [goal]` | 开始交付 | 可运行、真实验证、持续补齐的结果 |
| `/fix <problem>` | 报错、行为错误、契约冲突 | 根因修复 + 回归验证 |
| `/resume` | 上次中断 | 从持久状态继续到原始目标完成 |

推荐路径：明确 → `/build`；先看计划 → `/plan` → `/build`；模糊 →
`/grill` → `/plan` → `/build`；bug → `/fix`；中断 → `/resume`。

## 内部 skills 速查

| Skill | 思维链角色 |
|---|---|
| `mvp-delivery` | 总控制器：切片循环、风险判档、收敛到原始目标 |
| `grill` | 需求拷问：决策树 + 十二维覆盖表 |
| `research` | 外部事实查证：来源分级、引用、时效 |
| `brainstorming` | 方案分叉：替代探索与收敛 |
| `writing-plans` | 计划即 prompt：六字段 step brief + 边界清单 |
| `systematic-debugging` | 根因四阶段：复现/隔离/假设/验证 |
| `contract-review` | Audited 契约评审与 PLAN 编译 |
| `construction` | Audited PLAN 施工与 CR 恢复 |
| `task-worker` | 有界实现工作包（fresh subagent） |
| `test-author` | 独立生成并冻结验收测试 |
| `reviewer` | 只读评审；边界覆盖是独立维度 |
| `step-executor` | 隔离执行单个严格 PLAN 步骤 |
| `webapp-testing` | Web 旅程：断言式浏览器自动化 |
| `computer-use` | 桌面旅程：硬预算 GUI 操作与验证 |
| `pua` | 验收质询：闭环/事实驱动/穷尽不盲目 |
| `i-have-adhd` | 用户沟通：短视图，不删完整事实 |

安装器另会部署 `mvp-researcher`、`mvp-worker`、`mvp-reviewer`、
`mvp-test-author`、`mvp-step-executor` 五个项目子代理到
`.opencode/agents/`，带最小权限边界（reviewer 无写入；子代理禁止再派发）；
fresh 子代理提供真实独立 session，加载 skill 本身不创造独立性。

## 安装

需要 Python 3.10+，在本仓库根目录：

```powershell
python scripts/install.py "E:/path/to/target-project"
```

安装器复制 command wrapper、子代理定义、校验引擎与运行时工具
（`check.py`、`runtime_trace.py`、`check_runtime.py`、
`workflow_protocol.py`、`worktree_tasks.py`）及 `stage-routing.json`，在
manifest 记录指纹供 doctor 检测漂移，并在 `opencode.json` 注册本仓库顶层
skill 目录。安装或修改 skill 后必须重启 OpenCode。桌面验证为可选：不自动
安装 MCP、不改全局权限，接入见
[computer-use/README.md](computer-use/README.md)。

## 验证

```powershell
python scripts/check.py --selftest
python -B -m unittest discover -s tests -p "test_*.py"
python scripts/check.py hash <file> [<file> ...]   # 记录哈希；禁止手工计算
python scripts/check_runtime.py doctor <target-project> [--strict [--strict-freshness]]
python scripts/runtime_trace.py export <target-project> --out trace.json
python .opencode/workflow/scripts/check.py check-current .opencode/mvp/<goal>.md
```

运行时门禁（可选）：目标项目写 `.opencode/mvp/runtime-policy.json` 为
`{"schema": "runtime-policy/1", "goals": "all"}` 后，`finish-goal` 要求先过
`check.py runtime-gate`——用原生会话证据（真实子会话、完成的 skill 加载、
父子 provenance）核验 dispatch 声明；手写/导入 trace 一律拒绝。
UI 门禁：`check.py ui-gate ... --bind` 核验场景状态、真实
computer-use/webapp-testing 加载、原生调用与产物身份绑定；产物变化必须
重跑重绑，`--bind` 不给旧结果贴新构建。

引擎检查结构、绑定、退出/超时与断言；快照排除 VCS/`.opencode/**`/缓存/
生成目录；hash 检测“验证后被改动”，不证明语义正确，更不是沙箱。完整规则
见各 skill 的 `SKILL.md` 与 `references/`。

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
