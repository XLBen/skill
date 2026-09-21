# 宿主兼容性报告（S01）

日期：2026-09-21
主机：Windows 10，OpenCode 1.18.25（`C:\Users\24083\AppData\Roaming\npm\opencode.ps1`）
解释器：Python 3.10.7

本报告只记录**实测**结果；未实测项明确标注 NOT RUN / BLOCKED。

## 1. CLI 面（实测）

`opencode run --help`（原文 `baseline/s01/opencode-run-help.txt`）确认支持：
`--model provider/model`、`--agent`、`--file`、`--format default|json`、`--session`、
`--continue`、`--fork`、`--attach`、`--auto`、`--pure`、`--variant`。

`opencode models`（原文 `baseline/s01/models-list.txt`）可直接列出目录，实测包含：

- `openai/gpt-5.6-luna`（本项目 `/visibility` 的默认目标，**确实存在**）
- `deepseek/deepseek-v4-flash-vision-exp`、`zhipuai-coding-plan/glm-4.6v`（视觉候选）
- `openai/gpt-5.6-sol`、`openai/gpt-6-astra`、`zhipuai-coding-plan/glm-5.3` 等

模型列表**不含**能力元数据（图片/音频/视频），能力必须实测（见 §4）。

## 2. Session store 与原生 task 溯源（实测）

- 数据库：`C:\Users\24083\.local\share\opencode\opencode.db`（只读查询）。
- `session` 表含：`id, parent_id, agent, model, directory, time_created, ...`；
  `model` 为 JSON，如 `{"id":"deepseek-flash","providerID":"deepseek","variant":"max"}`。
- 真实派发证据（`baseline/s01/store-probe.txt`）：父会话 `ses_f3d2fda4...` 的
  `task` 工具 part 输出 `<task id="ses_f3bf8ca2...">`，对应子会话行
  `parent_id=ses_f3d2fda4..., agent=general, model=deepseek-flash`。
- 历史 mvp-* 席位派发同样可核验（`mvp-reviewer`、`mvp-researcher`、`mvp-worker`）。
- **结论：原生 task 派发的父子会话、agent、实际模型均可从宿主记录核验。**
  S12 的“实际模型从宿主记录读取”有原生依据，无需插件即可验证子会话模型。

## 3. 子会话模型的真实来源（实测，决定 S12 路径）

`task` 工具输入实测只有：`description`、`prompt`、`subagent_type`（部分含 `task_id`），
**从无 `model` 字段**（`baseline/s01/model-dispatch-probe.txt`，40 条历史派发全查）。

对照父会话逐消息模型（`baseline/s01/message-model-probe.txt`）与子会话 `model` 列：

| 子会话 | 派发时间 | 子会话模型 | 同时刻父会话消息模型 |
|---|---|---|---|
| `mvp-reviewer` `ses_f41a25b3a` | 1789900203205 | gpt-5.6-sol | gpt-5.6-sol |
| `mvp-reviewer` `ses_f41756f4f` | 1789903147184 | glm-5.3 | glm-5.3（1789903065 起切换） |

**结论：子会话继承派发时会话的当前模型；内置 task 工具不支持逐次指定模型。**
因此 `/visibility` 不能通过内置 task 输入切换 observer 模型。

## 4. 能力探针（实测）

- 图片输入：`opencode run --auto --model openai/gpt-5.6-luna "What is the dominant color ..." --file red.png`
  → stdout `red`，rc=0，10.7s。**图片链路实测可用（CLI 路径）**。
- CLI 席位回落：`opencode run --agent mvp-product-observer "..."` →
  stderr `! agent "mvp-product-observer" is a subagent, not a primary agent. Falling back`，
  rc=3，实际回复仍生成（经回落 agent）。**P0-1 在 1.18.25 实测复现**。
- 音频/视频输入、工具调用能力清单：NOT RUN（S16/S17 负责，不得以此报告冒充已验收）。

## 5. 动态模型派发的可行路径（评估）

| 路径 | 机制 | 状态 |
|---|---|---|
| A. 插件自定义工具 | 插件在运行时读 `.opencode/mvp/visibility.json`，用 SDK `client.session.prompt` 提交带 `SubtaskPartInput.model` 的子任务 | SDK 类型存在（v2 `types.gen.d.ts`）；**未实测**，插件加载需 OpenCode 重启，子任务 part 是否与 `runtime_trace.py` 现有 `task` part 兼容**需重启后验证** |
| B. agent frontmatter `model:` | `/visibility` 写 observer agent 文件 `model:` 字段 | OpenCode 官方支持该字段；**配置期加载，需重启生效**，且是项目级静态选择 |
| C. CLI 嵌套派发 | `opencode run --model X --agent <primary镜像>` | 已实测可用（S01 §4 图片探针 + 沙箱经验）；但仅限测试/自动化，不能作为生产会话内席位 |

**给 S11/S12 的结论**：S11 只负责项目设置解析与消歧（纯函数 + 文档），
S12 按路径 A 实现插件与引擎侧校验；**真实端到端验证标记为 BLOCKED-待重启**，
在用户重启 OpenCode 后作为 S21 的独立验收项执行。路径 B 可作为降级，
但必须在文档中写明“需重启 + 静态生效”，不得宣称动态切换。

## 6. 复现命令索引

- `python docs/po-repair/tools/s01_store_probe.py`
- `python docs/po-repair/tools/s01_model_dispatch_probe.py`
- `python docs/po-repair/tools/s01_message_model_probe.py`
- 原始输出：`docs/po-repair/baseline/s01/`

## 7. 未完成 / BLOCKED

1. 插件路径 A 的真实派发与其 part 形态：BLOCKED（需重启 OpenCode，S21 验收）。
2. 会话内图片附件传递（非 CLI）：未验证；S13/S16 的席位 tools 需要另行确认真实链路。
3. `opencode run --format json` 的结构稳定性：未测（P2-17 已知 session list JSON 曾非法）；
   S14 要求不依赖该通道。

## 8. OpenCode 插件 workflow-visibility（S12b，实现完成；实机待重启验证）

### 8.1 插件路径与加载方式

- 文件：`.opencode/plugins/workflow-visibility.js`（项目级插件；OpenCode 启动时加载
  `<project>/.opencode/plugins/*.js`）。
- 导出：命名纯函数 `parseModelRef` / `resolveSelection` / `buildDispatchBody` / `extractOutput` /
  `AGENT_BY_ROLE`，以及默认导出
  `async ({client, directory}) => ({tool: {visibility_dispatch, visibility_status}})`。
- 只读取 `<directory>/.opencode/mvp/visibility.json`（S11 写入的选择），不修改任何全局配置，
  不改主聊天模型。

### 8.2 依赖前提

- 插件 `import { tool } from "@opencode-ai/plugin"`，模块解析相对插件文件位置，因此必须在
  `.opencode/node_modules` 可解析该包（本仓库 `.opencode/package.json` 固定
  `@opencode-ai/plugin: 1.18.25`）。缺失时在 `.opencode` 内执行 `npm install`。
- 已实测（本机 Node v24.19.0）：从 `.opencode/plugins/` 可解析到 `.opencode/node_modules`，
  `node --test` 能 import 插件（Node 的模块语法检测处理了 `.opencode/package.json` 无
  `"type":"module"` 的 `.js`）。

### 8.3 重启要求

- OpenCode 只在启动时读取插件文件；新增/修改后必须重启 OpenCode，两个工具才会出现。
- S12b **未**重启、**未**在真实会话调用；实机可用性不得宣称已通过。

### 8.4 Node 测试命令（本机实测）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `node --test tests/js/` | 1 | Node v24.19.0 把位置参数当 glob，不递归展开目录，报 `Cannot find module ...\tests\js` |
| `node --test "tests/js/**/*.test.mjs"` | 0 | 23 tests，23 pass / 0 fail |

结论：使用 glob 形式；`node --test <目录>` 在 Node 24 已不可用。原始输出
`docs/po-repair/baseline/s12b/{node-test-dir,node-test-glob}.txt`。

### 8.5 待实机验证清单（S21；当前全部 BLOCKED）

1. 重启 OpenCode 后 `visibility_dispatch` / `visibility_status` 出现在工具列表。
2. 新建派发：`parentID` 为当前会话；子会话 `session.model` 等于
   `selection.provider_id/model_id`（用 S12a `runtime_trace.py export` +
   `observation_results.model_mismatch_problems` 核对）。
3. resume 路径（传 `session_id`）不新建子会话、模型不变。
4. 未配置/未选中时工具报错且不派发（fail closed），不回落默认模型。
5. 返回的 `metadata.session_id` 与宿主 session store 一致。
6. `visibility_status` 输出与 `.opencode/mvp/visibility.json` 一致。
7. 感知探针（S16 交付造图器，S21 执行）：用 `scripts/observation_vision.py` 的
   `make_color_probe` 生成纯色 PNG 并记录期望色，让 `selection` 选中的模型回答主色；
   用 `build_perception_record`/`validate_perception_record`/`perception_claim_problems`
   校验记录与图片 sha256。适配器能力（midscene/UI-TARS 的 image_read、visual_grounding、
   desktop_control）必须用真实探针证据回填 `adapter_status` 的 `probes`；`status_hint` 或
   已安装包不得冒充 `verified`。

