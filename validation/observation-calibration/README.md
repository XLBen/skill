# Product Observation Calibration Driver（S20B 运行手册）

本目录是新校准驱动的**纯函数核心 + 运行手册**。它只负责"派发前后控制器该做的机械动作"，
不做模型调用、不起服务、不写产品状态。真实模型/浏览器运行属于 S21；本文所有实机步骤
在当前环境一律标注 **BLOCKED / NOT RUN**，执行后必须把原始输出归档回本目录 `runs/`。

- 状态：核心实现 PASS（`driver_core.py` + `tests/test_calibration_driver.py`，39 条）
- 实机运行：**BLOCKED**（需重启后的 OpenCode 插件 + 真实模型）
- 案例执行：**NOT RUN**（见 §6 清单）

## 1. 为什么重写驱动（旧沙箱缺陷 → 本模块对策）

旧驱动 `E:\MISC\代码项目\po-validation-sandbox\driver\val.py` 的问题与替代：

| 旧行为（禁止回归） | 旧位置 | 新对策 |
|---|---|---|
| stdout JSON 与 agent 自写 `*.result.json` **双通道采纳** | `val.extract_json` + `val.adopt_result` 文件扫描 | `result_source_is_single`（单一围栏块；检出 `result.json` 写入声明）+ 仅 `adopt_result`/`adopt_review` 落盘 |
| `sessions[-1]` 绑定 session | `val.latest_session` | `adoption_result` 只接受 controller 传入的 `trace` + envelope 的会话 id；provenance 找不到即拒绝 |
| `stop_reason` 默认 `coverage-completed` | `val.adopt_result` 的 `setdefault` | 禁止默认值：payload 缺字段由合同校验直接拒绝（`test_no_default_stop_reason_is_supplied`） |
| reviewer 走镜像/条件分支（`kind != "reviewer"`、补默认 hash） | `val.adopt_result` | 同一 `adoption_result` 包装器直传；review 用 `adopt_review` 实算 hash |
| fixture 生成假对照（good/bad variant 由 harness 拼装） | `val.cmd_variant`/`cmd_candidate` | 校准只派发真实交付物；种子标签不进 packet（`seed_redaction_problems`） |
| 预检污染（packet/预检失败仍继续） | `run_case` 无 packet 守卫 | `packet_guard`：生成失败即 abort |
| setup 前启动服务 | `val.server_start` 调用顺序无校验 | `server_order_plan`：`setup` 必须先于 `server-start`，否则 ValueError |

## 2. 文件与 API

- `driver_core.py` —— 本模块，Python 3.10 标准库，无副作用。
- 测试：`tests/test_calibration_driver.py`（在仓库根运行）。

| 函数 | 用途 |
|---|---|
| `make_primary_mirror(agent_text)` | 把 agent frontmatter 的 `mode: subagent` 翻成 `primary`；其余字节不变；缺 frontmatter/mode/未知 mode → ValueError |
| `assert_single_channel(agent_text)` | 派发前检查镜像文本声明"单一围栏 json 块、块后无内容" |
| `seed_redaction_problems(seed_config, packet)` | 断言种子案例文本（`seed*`/`defect*`/`expected_findings*` 键）未泄漏进 packet 的任何字符串值 |
| `packet_guard(packet_ok)` | packet 生成失败 → `{"abort": True, reason}`；成功 → `{"abort": False}` |
| `state_reset(paths)` | 删状态文件；返回 `removed`/`missing`/`problems`；目录或删除失败进 problems，不抛 |
| `server_order_plan(steps)` | 校验并规范化步骤顺序；`setup` 必须早于 `server-start` |
| `adoption_result(payload, envelope, trace, cdir, project_root, phase, **kw)` | 薄包装 `observation_results.adopt_result`（延迟 import、参数直传、无默认成功值/文件兜底） |
| `result_source_is_single(text)` | 用 `observation_results.parse_single_payload` 校验单一围栏块，并检出 `*.result.json` 写入声明 |

## 3. 运行手册（准备 → 归档）

> 以下命令如涉及真实模型，当前环境 **BLOCKED**；只有在重启 OpenCode 且
> `.opencode/plugins/workflow-visibility.js` 生效、`.opencode` 下
> `@opencode-ai/plugin` 可解析（否则先 `npm install`）后，才能在目标项目执行。

### 3.1 安装目标

二选一（都不得改动本仓库其它文件）：

- **S20A 冒烟目录**（已安装 23 个脚本 + 插件）：
  `C:\Users\24083\AppData\Local\Temp\opencode\s20a-target`
- **新项目**：`python scripts/install.py <target>`，随后按提示重启 OpenCode；
  `.opencode/node_modules/@opencode-ai/plugin` 缺失时在该目录 `npm install`。

### 3.2 生成 primary 镜像（只由 agent 文件生成，不手写）

```python
import sys, pathlib
sys.path.insert(0, r"<repo>/validation/observation-calibration")
import driver_core as dc
agents = pathlib.Path("<target>/.opencode/agents")
for source, dest in (("mvp-product-observer.md", "po-observer.md"),
                     ("mvp-reviewer.md", "po-reviewer.md")):
    text = (agents / source).read_text(encoding="utf-8")
    mirror = dc.make_primary_mirror(text)
    problems = dc.assert_single_channel(mirror)
    assert not problems, problems
    (agents / dest).write_text(mirror, encoding="utf-8", newline="\n")
```

镜像只是校准宿主 `opencode run --agent` 无法派发 subagent 的临时工作区文件；
它不是产品交付物，不修改全局配置。

### 3.3 状态重置

```python
result = dc.state_reset([trace_json, gate_json, *.packet.json, *.result.json, *.attempt.json])
assert result["problems"] == [], result
```

`state_reset` 只删文件、不删目录；`problems` 非空时必须先处理再继续。

### 3.4 步骤顺序（服务启动）

```python
steps = ["setup", "server-start", "candidate-freeze", "packet", "dispatch"]
order = dc.server_order_plan(steps)   # setup 先于 server-start，否则 ValueError
```

顺序即：清项目/装引擎（setup）→ 起本地服务（server-start）→ 冻结候选与 sidecar
（candidate-freeze）→ 生成 packet → 派发。**禁止**先起服务再 setup。

### 3.5 packet 生成与预检

```bash
python <target>/.opencode/workflow/scripts/workflow_packets.py observer \
  <target>/.opencode/mvp/g-obs.md --phase discover \
  --model <provider/model> --preflight <target>/.opencode/mvp/observation/G-OBS/<cid>/preflight.json \
  --out <target>/.opencode/mvp/observation/G-OBS/<cid>/discover.packet.json
python <target>/.opencode/workflow/scripts/workflow_packets.py validate \
  <packet> --goal <target>/.opencode/mvp/g-obs.md
```

派发前控制器必须：

1. `packet_guard(packet_ok)` —— 生成/校验失败立即 abort，不派发；
2. `seed_redaction_problems(seed_config, packet)` —— 空列表才派发；
3. `assert_single_channel(镜像文本)` —— 派发文本必须声明单一交付通道。

### 3.6 observer / reviewer 派发

优先用已加载的插件工具 `visibility_dispatch`（模型取 `.opencode/mvp/visibility.json`，
observer=`mvp-product-observer`、reviewer=`mvp-reviewer`；模型可显式覆盖）。
插件不可用时才 fallback CLI：

```bash
opencode run --auto --model <provider/model> --agent po-observer "<packet 派发提示>"
opencode run --auto --model <provider/model> --agent po-reviewer "<review 派发提示>"
```

派发提示只引用 packet 路径与"最终回复必须是唯一一个 ```json 围栏块"的约束；
不得给出种子标签、goal 卡私有字段或 `result.json` 写入指引。

### 3.7 single-channel 采纳

1. 保存模型原始 stdout 到 `runs/<case>/<cid>/<phase>.raw.txt`；
2. `problems = dc.result_source_is_single(raw)` —— 非空即拒绝；
3. `payload, parse_problems = observation_results.parse_single_payload(raw)`；
4. `dc.adoption_result(payload, envelope, trace, cdir, project_root, phase, run_id=...)`
   （review 用 `observation_results.adopt_review`，hash 实算）；
5. 成功只有一条写路径：`<cdir>/<phase>/<run-id>/result.json`；attempt 与 errors 由采纳器归档。

**不得**再使用：stdout+文件双通道、`sessions[-1]`、任何 `setdefault` 默认
`stop_reason`/信封字段/`observer_session_id`。gate 失败就如实失败。

### 3.8 gate 命令

```bash
python <target>/.opencode/workflow/scripts/runtime_trace.py export <target> \
  --out <target>/.opencode/mvp/trace.json
python <target>/.opencode/workflow/scripts/check.py product-audit-gate \
  <target>/.opencode/mvp/g-obs.md --trace <target>/.opencode/mvp/trace.json
```

native trace → gate 通过才能跑 `check-current` / `finish-goal`；退出码与 stdout 原样归档。

### 3.9 归档

- 每次运行的原始 stdout/stderr、packet、trace、gate 输出：
  `validation/observation-calibration/runs/<case>/<cid>/`（不进测试 fixtures）。
- 汇总指标与结论追加到本目录 `runs/<case>/metrics.json`；未执行的案例保持 NOT RUN。

## 4. 与 S21 的边界

- S20B 交付：上述 8 个纯函数、测试、本手册；**不含**真实模型调用、服务进程管理、
  插件加载验证与端到端脚本。
- S21 负责：在重启后的宿主上执行 §3，收集 A–G 与 Web/多模态案例的真实输出，
  核对 recall/false-positive/coverage/证据质量/成本，并决定是否把校准结论写回文档。
- 本仓库不得 commit；所有产物留在工作区。

## 5. 案例清单（引用、不修改 `validation/product-observation/README.md`）

种子矩阵（A–G）与指标定义见 `../product-observation/README.md`：
A 干净构建（假阳性对照）、B 双模式之一静默失效、C 旧入口断连、D 整个入口消失、
E 跨功能状态不一致、F 合理的有意变更（须归 intended-change）、G 间歇性故障
（须保留为 intermittent）。本步骤 **一律 NOT RUN**。

Web / 多模态扩展清单（旧沙箱案例命名，供 S21 对照执行）：

| 案例 | 目标形态 | 关注通道 |
|---|---|---|
| A-web | Duel Blocks 双模式 Web | visual + console |
| B-web | 笔记 + 实时字数 | visual + console |
| C-web | 五分区门户 | visual + console |
| D-web | 主题设置跨面生效 | visual + console |
| E-web | 落地页 + Get started | visual + console |
| F-web | 笔记保存（有意变更） | visual + console |
| 图片/音频/视频 | 多模态感知（probe/vision/media 模块） | image/audio/video |

以上实机执行全部 **BLOCKED**（真实模型 + 重启后的插件）；静态覆盖见
`validation/product-observation/README.md` 的 Status 节。

## 6. 当前状态汇总

| 项 | 状态 |
|---|---|
| `driver_core.py` 8 函数 + 39 条单测 | PASS |
| 全量 `test_*.py` | PASS（见 PROGRESS S20B） |
| `scripts/check.py --selftest` | PASS |
| 真实模型派发 / 插件生效 | BLOCKED（需重启 OpenCode + `npm install`） |
| A–G、Web、多模态案例 | NOT RUN |
| 双通道 / latest-session / 默认 stop_reason | 已禁用并有测试回归 |
