# 完整工程设计的组织（不是填空问卷）

规划者按 `writing-plans/SKILL.md` 完成判断后，用下面结构让人和执行模型读懂同一设计。
章节可合并，不以章节数量验收；简单项目可以很短，但所有任务必须明确。

## 1. 软件做什么

从 grill 综合出目标用户、主流程、输入输出、必需功能、非目标和约束。
给正常/失败的具体场景。保留原始 brief ID → outcome ID，不把问题列表直接改成任务。

## 2. 技术路线与可行性

选择的技术/版本/复用项目、选用理由、一手依据。标记证据究竟是文档确认、环境
只读探查，还是尚需运行验证。列出足以推翻架构的假设：哪步验证，失败影响哪些任务。
不列一串未裁决的技术候选给 build；有分叉要在 plan 内得出决定或具体 blocker。

## 3. 架构、数据与接口

- 组件表：职责/状态归属/文件/依赖。
- 数据结构：字段、约束、生命周期和序列化/单位/坐标/编码。
- 跨组件合同：精确签名与类型、错误语义、调用时序；每项只定义一次。
- 数据流/组件图，必要的时序/状态机。图节点要落到实际组件和接口。
- 环境与启动：初始化、依赖安装、配置键（无密钥值）、代表数据、清理方法。

## 4. 完整实施路线

任务依赖图，以及每个里程碑完成后用户/集成者能真实做什么。
所有目标内必需能力有实施位置。先探测高风险连接，再有序扩张。

## 5. 全部施工卡（权威执行索引）

一个 `json engineering-plan` 块，schema `engineering-plan/2`。它包含：

| 范围 | 字段与含义 |
|---|---|
| 全局 | `goal_id`, `architecture`, `data_flow`, `shared_context`（全局不变量字符串数组） |
| 技术决定 | `decisions[]`: `decision`, `reason`, `evidence`（真实引用及确认程度） |
| 组件 | `components[]`: `id`, `responsibility`, `files`, `interfaces` |
| 共享合同 | `contracts[]`: `id: K-NN`, `owner: C-NN`, `signature`, `definition`（类型/代码/错误约定） |
| 外部边界 | `boundaries[]`: `id`, `kind: cli/api/browser/desktop/filesystem`, `external`, `target`, `driver`; external=true 时含 `probe` 命令及断言 |
| 用户旅程 | `journeys[]`: `id`, `outcome_ids`, `boundary_ids`, `entry`, `preconditions`, `actions`, `expected`, `verification`; `negative_control` 按需 |
| 每个任务 | `id`, `context`, `depends_on`, `component_ids`, `read_files`, `files`, `consumes`, `produces`, `implementation`, `change`, `bounds`, `rollback`, `failure_routes`, `preflight_boundary_ids`, `checks`, `journey_ids` |

每步的 `implementation` 是有顺序的具体实现动作；`change` 是关键代码/伪代码，
不能只写功能名称。`read_files` 可为空；不会要求新建项目预先存在源码。
`consumes/produces` 引用 K-ID；每个合同有唯一 producer，消费者依赖生产者。
生产者可以先创建签名/类型和真实实现，不能把永远成功的占位实现当作边界已接通。

`checks[]` 每项为 `id: T-NN`, `level: component|boundary`, `boundary_ids`,
`command`, `assertion`, 可选 `timeout_seconds`、`negative_control`。
组件检查不声明边界覆盖；boundary 检查必须触及实际目标，`boundary_ids` 非空。
普通断言/测试命令退出 0 并断言正确失败行为即可；不一律强制 negative_control。
当使用显式负对照时，它含 `command`, `assertion`, `expected_exit_code`（具体非零）,
`reason`；它捕获什么缺陷须在说明中可理解。

`preflight_boundary_ids` 只列本步实现前必须就绪的边界，不每一步探测全部环境。
`journey_ids` 在组件/探测步骤为空，仅在接通阶段列出。外部旅程的里程碑依赖
此前成功的对应 boundary 检查步骤。`checks` 和 `journey_ids` 至少一个非空。

`failure_routes` 是 `implementation`, `environment`, `design` 三个具体处理说明。
明确哪些错在本步修，哪些缺前提，哪些接口/架构冲突要返还设计，减少无效重试。

## 6. 需求追踪与设计走查

需求 → 实现任务 → 组件/真实边界/旅程验证的表。程序只核结构关联，规划者需确认
命令和断言真的对应需求。说明正常输入和失败输入如何穿过系统，记录修正的缺口、
仍待实测的假设及其阻断范围。设计文档不是运行报告。

## 分阶段游戏交互示例（说明粒度，不是已实测方案）

1. 确定窗口/坐标/画面/动作结果的共享类型，测试坐标转换等纯逻辑。
2. 接真实截图适配器：读窗口身份、分辨率与有效帧；记录真实环境限制。
3. 用已确认驱动经套件接口执行一次允许的可逆动作，并回读预期状态变化。
4. 只有 2/3 成立后再扩张上层操作和状态流程；逐条接通后验证对应旅程。

如果第 3 步失败，反馈输入是否送达/焦点/权限/结果判定的实际证据，不继续写一百个
假驱动测试。未确认驱动 API 时，计划必须标明调查依据/验证任务，不能伪造调用签名。
