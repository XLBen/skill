# 产品观察工作流修复 — 最终报告（S22 / FINAL-REPORT）

- 日期：2026-09-21
- 步骤：S22（最终审计与交付；只写报告与最小文档修正，不改代码/测试/技能/配置，未 commit）
- 状态权威：修复覆盖状态以 `docs/po-repair/CALIBRATION.md` 为准；宿主实测以
  `docs/po-repair/HOST-COMPATIBILITY.md` 为准；逐步台账以 `docs/po-repair/PROGRESS.md` 为准。
- 本报告不把"单元测试通过"写成"实机已验收"，不编造召回率/误报率/时长/token。

## 1. 执行摘要

S00–S22 在同一工作区完成，产物全部保留在工作区（未 commit）。本轮实际完成：

1. **协议 v2**：冻结 `product-observation/2`、`product-observation-review/2`、
   `product-candidate/2`、`product-audit/2`、`product-audit-gate/2`、
   `workflow-observer-packet/2` 等版本与枚举（S02–S04）。
2. **gate 闭环**：依赖感知全量诊断、证据引用核验、跨轮 `resolution` 绑定、
   gate record 绑定 `trace`（native provenance）与 `goal_definition_hash`，
   `finish-goal`/`check-current` 只读 gate 并重算核验（S05）。
3. **状态分离**：候选 `runtime_state`/`delivered_roots` 从不可变制品中分离；
   `runtime-state-policy/1` 贯通 verification → evidence → workspace binding → finish（S06/S07）。
4. **controller 归档**：单围栏块解析、`run-%03d`/`attempt-%03d` create-only 布局、
   文件锁、`product-audit` sidecar `/2`、`adopt_result`/`adopt_review`（S08a/S08b）。
5. **纠偏**：格式纠偏状态机（首次回答 + 最多 2 次纠偏，语料 21 份全部到 cap）（S09）。
6. **packet/preflight**：observer packet v2（brief 盲化、goal hash 绑定、preflight 嵌入、
   compare 全量校验）（S10）。
7. **visibility**：项目观察模型选择与消歧（`visibility_config.py` + `/visibility` 命令）、
   OpenCode 插件 `workflow-visibility.js`（`visibility_dispatch`/`visibility_status`）（S11/S12）。
8. **权限**：observer bash 命令模式与 deny 顺序、agent 权限声明与回归（S13）。
9. **进程/编码**：argv 直调不经 shell、字节捕获与替换解码、进程树/目录清理（S14）。
10. **批处理**：后端选择、preflight 跳过计划、短旅程 `run_step_sequence`（S15）。
11. **多模态适配面**：视觉适配/能力状态/感知记录（S16）、ffmpeg/ffprobe 媒体采集与判定（S17）。
12. **续跑**：`observation_resume`（续跑判定、覆盖合并、no-progress 熔断、lease）（S18）。
13. **文档与安装器**：观察链路文档同步（S19a–c，含文档一致性测试）、
    `install.py` 打包 23 个脚本 + 插件 + npm 依赖提示（S20A）。
14. **校准驱动**：`driver_core.py` 8 个纯函数 + 运行手册（S20B）；
    确定性矩阵与语料回放核验（S21）。

**测试规模（S22 复跑实测）**：Python 全量 `Ran 1183 tests — OK（skipped=3）`；
Node 插件测试 `tests 23 / pass 23 / fail 0`；`check.py --selftest` PASS。
本轮新增 20 个 Python 测试文件 + 1 个 Node 测试文件（`tests/js/visibility-plugin.test.mjs`）。

**未完成的实机项**：真实模型派发、插件实机加载、浏览器/多模态/桌面案例、真实 trace→gate 闭环、
权限实机拒绝、token/墙钟成本采集全部未执行（BLOCKED / NOT RUN 明细见 §2、§5）。

## 2. 修复覆盖表（CALIBRATION.md §2 状态摘要）

按 `CALIBRATION.md` §2 的 35 行状态（2.1 报告问题 18 行 + 2.2 未测项 7 行 +
2.3 附录 A harness 1 行聚合 + 2.4 S05/S07 关联新发现 9 行）：

| 状态 | 计数 | 关键项 |
|---|---|---|
| FIXED | 21/35 | P1-4（校验器容错 + v2 接入）、P1-5、P1-6、P1-7、P1-8、P1-9、P2-10（合同/计划层）、P2-13、P2-14、P2-15（原语层）；未测项中的续跑/resume、stop_reason 其余枚举 + lease（机械）；§2.4 关联新发现 9 项全部（finish trace、workspace 二次阻断、review hash、证据核验、capability gap、矛盾 review、owner-decision 阻断、known-old-issue、dismissal_reason） |
| PARTIAL | 10/35 | P0-1（插件/声明层，实机 BLOCKED）、P1-3（权限声明层）、P2-11（verdict 机械一致性）、P2-12（`owner_decision_ref` 仅字符串层）、P2-16（编码原语，宿主未复测）、P2-17（绕行原语，宿主未复测）、P2-18（仅通用指标函数，观察成本 0 采集）；`intermittent` 正向值无专门用例；漏面评审（机械规则）；附录 A harness（替代核心已测，端到端未跑） |
| BLOCKED | 3/35 | P0-2（Web 通道 agent-browser）；未测项 Web 检出；seats 会话内派发（均需重启 OpenCode 使插件生效） |
| NOT RUN | 1/35 | token 成本（未采集，不给出任何数值）；另混合行中的 `write: deny` 子项为 NOT RUN（S13 决策未引入该权限键） |

口径说明：

- 多数 FIXED 行仍含实机子项（如 P2-10 探针、P2-15 现场进程树、P2-13 真实子会话 trace），
  行内限制以 `CALIBRATION.md` §2 表格为准。
- `PARTIAL`/`BLOCKED`/`NOT RUN` **均未解决**；本报告不将其表述为已闭环。
- 语料 21 份的终态与 S03/S09 一致：S00 基线 VALID 3 / INVALID 16 / VALIDATOR-CRASH 2；
  S03 legacy 21 / 0 crash；S09 全部 `needs-observation`（attempts=3、repair_count=2）。

## 3. 变更清单

### 3.1 新增脚本（`scripts/`，11 个）

| 文件 | 作用 |
|---|---|
| `observation_contract.py` | v2 合同：版本常量、枚举、payload/review 校验、语义函数（阻断/裁决/跨轮 resolution） |
| `observation_candidate.py` | 候选 `runtime_state`/`delivered_roots` 结构校验与越界扫描 |
| `observation_results.py` | 单围栏块解析、run/attempt 布局、create-only 采纳、sidecar `/2`、文件锁、provenance/证据闸门 |
| `observation_resume.py` | 续跑计划、覆盖合并、no-progress 熔断、lease |
| `observation_vision.py` | 视觉适配面、能力状态、感知记录与主张核验 |
| `observation_media.py` | ffmpeg/ffprobe argv、媒体 probe 解析、capture chain 与静音主张 |
| `observation_process.py` | argv 直调、字节捕获、进程树与目录清理 |
| `observation_backend.py` | 后端选择、preflight 跳过计划、短旅程批处理 |
| `product_observation.py` | 观察 gate/collect：v2 接入、全量诊断、证据核验、state policy 检查 |
| `runtime_state_policy.py` | `runtime-state-policy/1` 加载/校验/快照排除/候选对齐 |
| `visibility_config.py` | 项目观察模型选择（目录解析、消歧、原子落盘、set/show/select/mark） |

### 3.2 新增模块 / 运行手册 / 校准资产

- `validation/observation-calibration/driver_core.py`（8 个校准纯函数）。
- `validation/observation-calibration/README.md`（§3 运行手册、§6 状态汇总）。
- `validation/product-observation/README.md`（状态区分：protocol-pass vs detection-evaluated）。
- `docs/po-repair/**`：`BASELINE.md`、`COVERAGE-MAP.md`、`CONTRACT.md`、
  `HOST-COMPATIBILITY.md`、`CALIBRATION.md`、`PROGRESS.md`、`tools/`（语料收集与 S01 探针）、
  `corpus/`（21 份归档 + INDEX）、`baseline/`（S00–S22 原始输出与 JSON）。

### 3.3 命令 / 插件 / agent

- 新增 `.opencode/commands/visibility.md`；修改 `.opencode/commands/resume.md`。
- 新增 `.opencode/plugins/workflow-visibility.js`（`visibility_dispatch`/`visibility_status` 与命名纯函数）。
- 新增 `.opencode/agents/mvp-product-observer.md`；修改 `.opencode/agents/mvp-reviewer.md`。

### 3.4 技能

- 新增 `product-observer/`：`SKILL.md`、`UPSTREAM.md`、`LICENSE`、
  `references/{observation-protocol,finding-rules,result-contract,format-repair,backend-routing}.md`、
  `upstream/{dogfood,dogfood-report-template,issue-taxonomy}.md`。
- 修改 `mvp-delivery/SKILL.md` 及 references：`delivery-execution.md`、`delivery-finish.md`、
  `delivery-recovery.md`、`goal-definition.md`、`stage-routing.json`（schema 3，适配器改为
  direct-multimodal/playwright-cli/midscene/ui-tars + media via ffmpeg）、
  `subagent-orchestration.md`、`subagent-templates.md`。
- 修改 `reviewer/SKILL.md`、`computer-use/SKILL.md` 与
  `computer-use/references/ui-acceptance-protocol.md`、`webapp-testing/SKILL.md`、
  `systematic-debugging/SKILL.md`、`i-have-adhd/SKILL.md`。

### 3.5 测试

- 新增 20 个 Python 测试文件：`test_product_observation.py`、`test_observer_packets.py`、
  `test_observation_contract.py`、`test_observation_malformed.py`、`test_observation_semantics.py`、
  `test_observation_gate.py`、`test_observation_candidate.py`、`test_observation_state_binding.py`、
  `test_observation_results.py`、`test_observation_format_repair.py`、`test_observation_dispatch.py`、
  `test_observation_permissions.py`、`test_observation_process.py`、`test_observation_backend.py`、
  `test_observation_vision.py`、`test_observation_media.py`、`test_observation_resume.py`、
  `test_observation_docs.py`、`test_visibility_config.py`、`test_calibration_driver.py`。
- 新增 `tests/js/visibility-plugin.test.mjs`（23 条 Node 测试）。
- 新增 fixtures `tests/fixtures/product-observation/`（6 份）。
- 修改 `tests/test_install.py`、`tests/test_runtime_doctor.py`、`tests/test_subagent_orchestration.py`。

### 3.6 修改脚本（既有）

- `scripts/check.py`（gate CLI、finish 闭环、workspace binding、state policy 检查）、
  `scripts/evidence_registry.py`（`runtime_state_policy` 进入 IDENTITY_FIELDS）、
  `scripts/install.py`（23 脚本 + 插件 + npm 提示）、`scripts/runtime_trace.py`（session model 导出/校验）、
  `scripts/workflow_packets.py`（observer/validate 子命令与 packet v2）、
  `scripts/workflow_protocol.py`、`scripts/workflow_runtime.py`。

### 3.7 本步（S22）修改/新增

- `docs/po-repair/FINAL-REPORT.md`（本文件，新）。
- `validation/product-observation/README.md`（Status 段最小更新）。
- `README.md`、`README.en.md`（子代理清单 5 → 6，补 `mvp-product-observer`）。
- `docs/po-repair/PROGRESS.md`（追加 S22 记录）。
- `docs/po-repair/baseline/s22/**`（6 份最终检查输出）。

## 4. 验证记录

### 4.1 S22 最终检查（原始输出 `docs/po-repair/baseline/s22/`）

| 检查 | 命令 | 结果 | 输出文件 |
|---|---|---|---|
| 工作区状态 | `git status --short` | 68 行（28 个已改 + 新文件/目录，全部未 commit） | `git-status.txt` |
| 空白错误 | `git diff --check` | 0 个空白错误；仅 CRLF 行尾提示 | `git-diff-check.txt` |
| 变更统计 | `git diff --stat` | 28 files changed, 1427 insertions(+), 169 deletions(-)（未含 untracked 新增） | `git-diff-stat.txt` |
| 全量 Python | `python -m unittest discover -s tests -p "test_*.py"` | 退出码 0，`Ran 1183 tests in 64.351s — OK（skipped=3）` | `test_all.txt` |
| 自检 | `python scripts/check.py --selftest` | 退出码 0，`selftest PASS` | `check_selftest.txt` |
| Node 插件 | `node --test "tests/js/**/*.test.mjs"` | 退出码 0，`tests 23 / pass 23 / fail 0` | `node-test-glob.txt` |

S22 结果与 S21 一致（1183 Python / 23 Node / selftest PASS），无新增失败或回归。

### 4.2 语料 21 份终态（与 S03/S09 一致）

| 阶段 | 口径 | 结果 | 证据 |
|---|---|---|---|
| S00 基线 | 当时校验器直检 | VALID 3 / INVALID 16 / VALIDATOR-CRASH 2 | `corpus/INDEX.json`（未改） |
| S03 终态 | v2 合同接入后逐份判定 | legacy 21 / invalid 0 / valid 0 / crash 0 | `baseline/s03-corpus-regression.json` |
| S09 终态 | 格式纠偏回放 | 21 份全部 `needs-observation`（cap，attempts=3 / repair_count=2），0 采纳 / 0 崩溃 | `baseline/s09-corpus-repair.json` |
| S21 回放 | 只读重定向 | collected=21 / invalid=21 / validator_crash=0 / copy_matches=21/21 | `baseline/s21/corpus-validity.txt`、`corpus-replay/INDEX.json` |

## 5. 关闭 BLOCKED 的精确前提与步骤

前提与实机清单依据：`docs/po-repair/HOST-COMPATIBILITY.md`（§7 BLOCKED、§8.2 依赖、§8.3 重启、§8.5 待实机验证清单）
与 `validation/observation-calibration/README.md`（§3.1–§3.9 运行与归档）。

1. **重启 OpenCode**：关闭全部 OpenCode 实例后重启，使项目级插件
   `.opencode/plugins/workflow-visibility.js` 被加载；确认 `visibility_dispatch`/`visibility_status`
   出现在工具列表（HOST-COMPATIBILITY §8.3：插件只在启动时读取）。
2. **安装插件依赖**：在目标项目 `.opencode` 内执行 `npm install`
   （`package.json` 已固定 `@opencode-ai/plugin: 1.18.25`）；缺失时安装器会打印
   `plugin dependency missing: run "npm install" in <target>/.opencode`（HOST-COMPATIBILITY §8.2）。
3. **选择并记录模型**：用 `scripts/visibility_config.py`（或 `/visibility`）写入
   `.opencode/mvp/visibility.json`；每次运行如实记录 provider/model 身份，工具与文档不得硬编码模型名。
4. **Web/浏览器**：把 `agent-browser` 固定到 `product-observer/UPSTREAM.md` 记录的版本，
   并在实际宿主上通过 `product-observer/references/backend-routing.md` 的后端探针；
   然后执行 Web 案例 A-web~F-web（visual + console）。
5. **多模态-图片**：确认所选模型具备 `image_read`；用 `observation_vision.make_color_probe`
   生成纯色 PNG 并记录期望色 → 真实派发 → `build_perception_record` /
   `perception_claim_problems` 核 sha256 与证据范围（HOST-COMPATIBILITY §8.5 第 7 条）。
6. **多模态-音频/视频**：`ffmpeg`/`ffprobe` 在 PATH；设置
   `MEDIA_MODEL_BASE_URL` / `MEDIA_MODEL_API_KEY` / `MEDIA_MODEL_NAME` 三键；
   执行 `probe_media`（真实 runner）→ `extract_frames_argv`/`extract_audio_argv` →
   `capture_chain_verdict` → `silence_claim_problems`。
7. **桌面（可选）**：midscene/UI-TARS 实际安装且探针 `passed`；`adapter_status` 的
   `status_hint` 或已安装包不得冒充 `verified`。
8. **执行校准全流程**：按 `validation/observation-calibration/README.md` §3：
   `make_primary_mirror` → `state_reset` → `server_order_plan` →
   `workflow_packets.py observer --model ... --preflight ...` → `visibility_dispatch`（或
   fallback `opencode run --auto --model ... --agent po-observer`）→
   `result_source_is_single`/`adopt_result`/`adopt_review` → `runtime_trace.py export` →
   `check.py product-audit-gate <goal> --trace <trace>`；失败如实失败，禁止双通道 /
   `sessions[-1]` / 默认 `stop_reason`。
9. **归档与判定**：原始 stdout/packet/trace/gate 输出归档到
   `validation/observation-calibration/runs/<case>/<cid>/`（§3.9）；核对 HOST-COMPATIBILITY §8.5
   的 7 条（工具出现、子会话 model == selection、resume 不新建会话、未配置 fail closed、
   `metadata.session_id` 一致、status 与 visibility.json 一致、感知探针证据回填）。
10. **回填状态**：把实测结果写回 `CALIBRATION.md`（届时才允许把对应 BLOCKED/NOT RUN 改判）；
    未执行的案例保持 NOT RUN。

## 6. 边界声明（硬性）

1. **原始沙箱只读未改**：`E:\MISC\代码项目\po-validation-sandbox` 全程仅作只读参考
   （S00 复制语料、S21 回放均未写入；S22 未触碰）。
2. **未 commit**：所有改动留在工作区（`git status --short` 可复核），仓库历史未变。
3. **真实检出能力未在本轮实机验收**：S00–S22 的绿测只证明协议/机械层；
   不得据此宣称"已解决 P0-2 / P0-1 的实机闭环"，也不得给出任何未采集的召回率、
   误报率、墙钟或 token 数值。
4. **未解决项保持原状**：PARTIAL 10 行、BLOCKED 3 行、NOT RUN 1 行（另 1 子项）以
   `CALIBRATION.md` §2 为准，待 §5 步骤执行后方可改判。
