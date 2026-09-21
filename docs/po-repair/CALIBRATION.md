# 观察修复校准与核验报告（S21 / CALIBRATION）

- 日期：2026-09-21
- 步骤：S21（报告与核验；只读运行测试与语料回放 + 文档归档；未改任何代码/测试/技能文档，未 commit）
- 前置：S00–S20B 已全部完成（见 `PROGRESS.md`）
- 环境（本轮实测，原始输出 `docs/po-repair/baseline/s21/env.txt`）：
  - Windows 10.0.19045（win32）、PowerShell 5.1.19041.6456
  - Python 3.10.7（`python` → `D:\python\python.exe`）
  - Node v24.19.0
  - OpenCode 1.18.25（CLI 面与能力探针实证见 `HOST-COMPATIBILITY.md` §1/§4）
- 结论口径（硬性）：
  - **机械验证** = 仓库内可复现的确定性证据（单元测试、纯函数断言、只读回放）；
  - **实机验证** = 真实模型 / 浏览器 / 音频视频设备上的行为，本轮只有 S01 的历史实测，S21 未执行；
  - 本文不把"单元测试通过"写成"实机已验收"，不含任何编造缺陷召回率、误报率、时长或 token 数。

## 1. 本轮实际运行记录

原始输出全部位于 `docs/po-repair/baseline/s21/`。

| # | 命令 | 退出码 | 实测结果 | 原始输出 |
|---|---|---|---|---|
| 1 | `python -m unittest discover -s tests -p "test_*.py"` | 0 | Ran 1183 tests in 71.529s — OK（skipped=3，0 fail/error） | `test_all.txt` |
| 2 | `python scripts/check.py --selftest` | 0 | `selftest PASS` | `check_selftest.txt` |
| 3 | `node --test "tests/js/**/*.test.mjs"` | 0 | tests 23 / pass 23 / fail 0 / duration 397.0996ms | `node-test-glob.txt` |
| 4 | 14 个分测试文件逐个运行（见 §1.1） | 均 0 | 合计 Ran 642 tests，全 OK（skipped 3） | `test_*.py.txt`（14 份） |
| 5 | 语料回放：`collect_corpus.py` 原样导入、输出目录改指 `baseline/s21/corpus-replay/` | 0 | collected=21 valid=0 invalid=21 validator_crash=0 copy_matches=21/21 handmade=3 | `corpus-validity.txt`；明细 `corpus-replay/INDEX.json` |

说明：第 5 项用 `docs/po-repair/baseline/s21/replay_corpus.py` 导入原脚本并仅重定向 `CORPUS` 输出目录，未写 `docs/po-repair/corpus/`（其 `INDEX.json` mtime 13:56:20 在本轮前后未变），也未写沙箱只读源。

### 1.1 分测试文件结果（命令 `python -m unittest discover -s tests -p "<file>" -v`）

| 测试文件 | Ran | 结果 | 原始输出 |
|---|---|---|---|
| test_product_observation.py | 31 | OK（0.538s） | `test_product_observation.py.txt` |
| test_observation_gate.py | 33 | OK（1.598s） | `test_observation_gate.py.txt` |
| test_observation_semantics.py | 41 | OK（0.196s） | `test_observation_semantics.py.txt` |
| test_observation_candidate.py | 40 | OK（skipped=2，1.103s） | `test_observation_candidate.py.txt` |
| test_observation_state_binding.py | 26 | OK（skipped=1，1.806s） | `test_observation_state_binding.py.txt` |
| test_observation_results.py | 94 | OK（1.650s） | `test_observation_results.py.txt` |
| test_observation_format_repair.py | 20 | OK（0.084s） | `test_observation_format_repair.py.txt` |
| test_observation_backend.py | 49 | OK（0.020s） | `test_observation_backend.py.txt` |
| test_observation_vision.py | 76 | OK（0.161s） | `test_observation_vision.py.txt` |
| test_observation_media.py | 73 | OK（0.011s） | `test_observation_media.py.txt` |
| test_observation_resume.py | 63 | OK（0.005s） | `test_observation_resume.py.txt` |
| test_observation_docs.py | 15 | OK（0.068s） | `test_observation_docs.py.txt` |
| test_visibility_config.py | 59 | OK（0.251s） | `test_visibility_config.py.txt` |
| test_install.py | 22 | OK（2.261s） | `test_install.py.txt` |

## 2. 确定性矩阵（S21 时点）

- 状态取值：**FIXED** = 该行所述机制有能真实变红的测试覆盖；**PARTIAL** = 只覆盖声明层/构造层/纯函数层，不能覆盖报告中的真实失败模式；**BLOCKED-需重启** = 依赖重启 OpenCode 后的插件/权限生效；**NOT RUN-需模型或设备** = 需要真实模型/浏览器/音视频设备，本轮未执行。
- "实现位置"为 S21 工作区行号，后续漂移以函数名为准。证据统计见 §1。

### 2.1 报告问题 P0-1 ~ P2-18

| 项 | 状态 | 实现位置 | 测试证据 | 限制说明 |
|---|---|---|---|---|
| P0-1 CLI 派发 subagent 席位静默回落 build | PARTIAL | `.opencode/plugins/workflow-visibility.js`（`visibility_dispatch`/`visibility_status`/`resolveSelection`）；`scripts/visibility_config.py`；`scripts/runtime_trace.py:163`；`scripts/observation_results.py:351` | `test_visibility_config.py` 59 OK；`node --test "tests/js/**/*.test.mjs"` 23/23；`test_observation_dispatch.py` 27 OK；`test_subagent_orchestration.py` 9 OK | 宿主回落行为只在 S01 实测复现（rc=3，`HOST-COMPATIBILITY.md` §4）；插件未在重启后的真实会话调用，子会话 `session.model` 一致性未核验 → BLOCKED-需重启 |
| P0-2 Web 通道（agent-browser）不可行 | BLOCKED-需重启 | `scripts/observation_backend.py:136/162/259/348`；`scripts/observation_process.py:109` | `test_observation_backend.py` 49 OK（假 runner）；`test_observation_process.py` 20 OK | 全部为规划/argv/批处理纯函数测试，无浏览器旅程；8 次 Web 派发零产出的真实故障模式未复测 → 还需设备/环境 |
| P1-3 `edit: deny` 拦不住 Write；compare 覆写 discover 证据 | PARTIAL | `.opencode/agents/mvp-product-observer.md`（bash 命令模式）、`.opencode/agents/mvp-reviewer.md` | `test_observation_permissions.py` 9 OK（含 `test_bash_default_allows_and_every_deny_pattern_is_present`、`test_deny_patterns_come_after_the_top_level_allow`） | 声明层/静态顺序断言；实机拒绝对话框未触发（S13 §S21 清单 5 条全部未执行）→ BLOCKED-需重启 |
| P1-4 schema 词表/结构漂移 18/21 | FIXED（校验器/纠偏层） | `scripts/observation_contract.py:234/560`；`scripts/observation_results.py:42/1236/1290` | `test_observation_contract.py` 49 OK、`test_observation_malformed.py` 14 OK、`test_observation_format_repair.py` 20 OK；语料回放 0 崩溃（§3） | 21 份 v1 语料在纠偏路径上只能到 `needs-observation`（cap），未用真实模型按 v2 重观察 → 该部分 NOT RUN-需模型 |
| P1-5 有状态应用写自身目录被误判篡改 | FIXED | `scripts/runtime_state_policy.py:151/199/223`；`scripts/observation_candidate.py:242/342/420` | `test_observation_state_binding.py` 26 OK（skipped=1）、`test_observation_candidate.py` 40 OK（skipped=2） | symlink 越界用例当前账户无权限 skip；真实状态型产品未跑 → 实机部分 NOT RUN-需模型 |
| P1-6 结果交付通道未定义（stdout vs 写文件） | FIXED | `scripts/observation_results.py:42/524/1041`（`parse_single_payload`/`adopt_result`/`adopt_review`）；`validation/observation-calibration/driver_core.py:267/297` | `test_observation_results.py` 94 OK；`test_calibration_driver.py` 39 OK（`ResultSourceSingleTests` 6、`AdoptionResultTests` 4） | 无真实模型产生双通道样本；纠偏 round-trip 未接真实 `send` → NOT RUN-需模型 |
| P1-7 校验器被畸形输入弄崩（TypeError） | FIXED | `scripts/product_observation.py` + `scripts/observation_contract.py`（元组安全枚举判定） | `test_observation_malformed.py` 14 OK；语料回放 21/21 无崩溃 | 无剩余机械限制；真实畸形输出形态采样更广属可选 |
| P1-8 gate 早退掩盖后续问题 | FIXED | `scripts/product_observation.py:579`（依赖感知全量收集） | `test_observation_gate.py` 33 OK（`FullDiagnosisTests` 5，含多类诊断并存） | 诊断仍以结构/语义规则为限，不代表检测质量 |
| P1-9 上一轮证据被覆写与采纳歧义 | FIXED | `scripts/observation_results.py`（create-only + `run-%03d`/`attempt-%03d` 布局 + sidecar `/2`） | `test_observation_results.py` 94 OK（`RunLayoutTests` 8、`AdoptCreateOnlyTests` 3、`SidecarUpdateTests` 11） | 文件锁为同机咨询锁；跨机/并发压力只做本机 ×50/×30 压测（S08b） |
| P2-10 技能仪式无 preflight 豁免 | FIXED（合同/计划）；探针 NOT RUN | `scripts/workflow_packets.py:611/854`；`scripts/observation_backend.py:136` | `test_observer_packets.py` 23 OK（preflight 5 类）；`test_observation_backend.py` 49 OK（`PreflightSkipPlanTests` 10） | 真实 host/model/candidate/session 探针未产出 `preflight.json` → NOT RUN-需模型/设备 |
| P2-11 reviewer 判断错误 + 表达欲越界 | PARTIAL | `scripts/observation_contract.py:742`（`review_verdict_consistency_problems`）；`reviewer/SKILL.md` 决策表 | `test_observation_semantics.py` 41 OK（`ReviewVerdictConsistencyTests` 12，含 `test_open_blocking_with_sufficient_verdict_is_a_problem`） | 机械一致性已锁定；`notes` 多原因仍为文档要求不解析；真实 reviewer 判断质量未评估 → NOT RUN-需模型 |
| P2-12 goal 与随产品 README 权威冲突 | PARTIAL | `scripts/observation_contract.py:600/616`（阻断级 dismissed/intended-change 必须 `owner_decision_ref`）；`product-observer/references/finding-rules.md` | `test_observation_semantics.py` 41 OK（`test_readme_only_dismissal_keeps_blocking`、`test_intended_change_high_without_owner_decision_is_a_problem`） | `owner_decision_ref` 只校验非空字符串，未解析真实 owner decision 工件；真实权威判定 NOT RUN-需模型 |
| P2-13 观察者无法自知 session id | FIXED | `scripts/observation_results.py:388`（`provenance_problems` 强制 trace 绑定）；`scripts/runtime_trace.py:163` | `test_observation_results.py` 94 OK；`test_observation_dispatch.py` 27 OK | 控制器的 trace 导出/补绑未在真实子会话上核验 → 该环节 BLOCKED-需重启 |
| P2-14 词表不一致（known-old-issue、dismissal_reason） | FIXED | `scripts/observation_contract.py`（枚举 + `dismissed` 需 `dismissal_reason`；`known-old-issue` 需证据） | `test_observation_contract.py` 49 OK（`test_dismissed_requires_dismissal_reason`、`test_known_old_issue_needs_evidence`）；语义 41 OK | 旧语料按设计不再被接受，只能重观察迁移 |
| P2-15 孤儿进程树与目录锁 | FIXED（原语）；实机 NOT RUN | `scripts/observation_process.py:83/278/314`（`kill_process_tree`/`session_cleanup`/`cleanup_directory`） | `test_observation_process.py` 20 OK（`KillProcessTreeTests` 2、`CleanupDirectoryTests` 4、`SessionCleanupTests` 3） | 真实 agent-browser 进程树/目录锁场景未复测 → NOT RUN-需设备 |
| P2-16 Windows 编码三连 | PARTIAL | `scripts/observation_process.py:109/207`（字节捕获 + `text_of` 替换解码） | `test_observation_process.py` 20 OK（`test_non_utf8_output_does_not_raise`、`test_text_of_replaces_invalid_bytes`）；`check.py --selftest` 在 GBK 控制台 PASS | 真实宿主管道（`opencode`/`agent-browser`）的 GBK/管道形态未复测 → NOT RUN-需设备 |
| P2-17 opencode / agent-browser CLI 摩擦 | PARTIAL（绕行原语）；宿主行为 NOT RUN | `scripts/observation_process.py`（argv 直调、不经 shell）；`scripts/runtime_trace.py`（export） | `test_observation_process.py` 20 OK（`test_shell_string_argv_is_rejected`）；`test_observation_dispatch.py` 27 OK | `--file` 吞提示词、`session list` 非 JSON、管道杀进程均为宿主缺陷；本轮无实机复测 → NOT RUN-需设备 |
| P2-18 成本 | PARTIAL / 未采集 | `tests/test_workflow_metrics.py`（通用 token/cost 聚合） | `test_workflow_metrics.py` 13 OK（`ExportTests` 7、`CompareTests` 3） | 未运行真实派发，观察流程 token/墙钟指标为 0 采集；旧基线"25 次 run ≈ 3.5h"是报告历史记录，非本轮测量（见 §5） |

### 2.2 报告未测项（报告 §3 共 7 项）

| 项 | 状态 | 实现位置 | 测试证据 | 限制说明 |
|---|---|---|---|---|
| Web 检出 | BLOCKED-需重启 | 同 P0-2 | `test_observation_backend.py` 49 OK | 无浏览器实机 |
| seats 会话内派发 | BLOCKED-需重启 | `.opencode/plugins/workflow-visibility.js`；`scripts/visibility_config.py` | `tests/js` 23/23；`test_visibility_config.py` 59 OK；`test_observation_dispatch.py` 27 OK | 插件未在真实会话加载；模型一致性未核验 |
| intermittent 保留 | PARTIAL | `scripts/observation_contract.py:49/57`（枚举）；`scripts/product_observation.py:156`（计入阻断集合） | 无专门用例构造 `status="intermittent"` 的 finding；枚举负例矩阵（`test_result_enum_fields_never_raise`）不覆盖该正向值 | 机制存在但无专门回归；真实间歇性故障保留 NOT RUN-需模型 |
| 续跑 / resume | FIXED（机械） | `scripts/observation_resume.py:61/175/265/316/400`；`.opencode/commands/resume.md` | `test_observation_resume.py` 63 OK（`ResumePlanTests` 17、`MergeCoverageTests` 13、`NoProgressBreakerTests` 9、`LeaseProblemsTests` 13） | 真实 `budget-exhausted` 续跑与真实 lease 持有 NOT RUN-需模型/设备 |
| 漏面评审 | PARTIAL | `scripts/observation_resume.py:175`（`merge_coverage`）；`scripts/observation_contract.py:742`（verdict 一致性） | `test_observation_resume.py` 63 OK；`test_observation_semantics.py` 41 OK | 覆盖合并与 verdict 一致性是机械规则；真实漏面检出质量 NOT RUN-需模型 |
| stop_reason 其余枚举 / lease / write:deny | stop_reason+lease FIXED（机械）；write:deny NOT RUN | `scripts/observation_contract.py`（STOP_STATE 映射/枚举）；`scripts/observation_resume.py:359/400` | `test_observation_contract.py` 49 OK（`test_stop_state_mapping`/`test_stop_state_invalid_values`）；`test_observation_resume.py` 63 OK；`test_observation_permissions.py` 9 OK（`test_agent_files_do_not_declare_write_permission_keys`） | S13 明确未引入未经宿主验证的 `write: deny` 键；其余枚举值/lease 的实机行为 NOT RUN |
| token 成本 | NOT RUN-需模型 | 同 P2-18 | —（本轮未采集） | 不给出任何数值 |

### 2.3 附录 A harness 缺陷（13 项）

| 项 | 状态 | 实现位置 | 测试证据 | 限制说明 |
|---|---|---|---|---|
| 旧沙箱 driver（类型错、命令路径、编码、进程树、fixture 自缺陷等） | PARTIAL（替代核心已测）；端到端 BLOCKED-需重启 | `validation/observation-calibration/driver_core.py:48/89/150/179/195/239/267/297`（8 个纯函数）；`validation/observation-calibration/README.md` | `test_calibration_driver.py` 39 OK（含 `test_no_default_stop_reason_is_supplied`、`test_missing_trace_is_rejected_not_defaulted`、`test_server_before_setup_raises`） | 旧装置位于仓库外 `po-validation-sandbox/driver/`，未重写也未端到端重跑；新驱动只覆盖控制器机械动作 → 真实运行 NOT RUN |

### 2.4 S05/S07 关联新发现（含 S04/S19 的语义补充）

| 新发现 | 状态 | 实现位置 | 测试证据 | 限制说明 |
|---|---|---|---|---|
| finish-goal 未传 trace | FIXED | `scripts/check.py:2276`（`enforce_product_observation` 读 gate 并重算）；gate record 带 trace 绑定 | `test_observation_gate.py` 33 OK（`GateRecordClosedLoopTests` 9：`test_gate_cli_requires_a_trace`、`test_changed_trace_file_blocks_check_current`、`test_unverified_trace_provenance_blocks_check_current`、`test_stale_goal_definition_hash_blocks_finish`） | CLI 闭环在测试内驱动；真实宿主 trace 文件未生成 → 实机 NOT RUN |
| workspace 二次阻断 | FIXED | `scripts/runtime_state_policy.py:199/223`；`scripts/check.py:2215`（`enforce_workspace_binding` 策略 stale 时 `continue`） | `test_observation_state_binding.py` 26 OK（`EndToEndStatefulTests` 6：`test_without_policy_state_write_fails_workspace_binding`、`test_policy_excludes_state_write_and_binds_evidence`、`test_state_write_after_verification_is_tolerated`） | 策略改变后必须全量重验（无局部重验） |
| review hash 路径不一致 | FIXED | `scripts/product_observation.py:579`（按 sidecar `discover_ref`/`compare_ref` 实算 sha256，ref 缺失才回退固定名） | `test_observation_gate.py` 33 OK（`ReviewHashBindingTests::test_review_hashes_use_sidecar_referenced_files`） | ref 指向目录外时仍会 fail closed 报问题 |
| 证据仅字符串 | FIXED | `scripts/product_observation.py`（`_evidence_ref_problems`：非空/非绝对/无 `..`/存在且 resolve 后仍在 cdir 内） | `test_observation_gate.py` 33 OK（`EvidenceReferenceTests` 5：`test_missing_evidence_file_is_reported`、`test_evidence_ref_escaping_the_candidate_scope_is_reported`、`test_absolute_evidence_ref_is_reported`） | 只保证存在与作用域，不解析内容/类型（S05 已知限制） |
| capability gap 校验不足 | FIXED（机械） | `scripts/observation_contract.py` 规则 + `scripts/product_observation.py:579`（channel+reason 双非空阻断） | `test_observation_gate.py` 33 OK（`ObservationRegressionTests::test_capability_gap_still_blocks`）；`test_observation_contract.py` 49 OK（`test_blocked_needs_notes_or_capability_gaps`） | `observation_media.capture_chain` 的媒体 capability 状态机未冻结进 gate（S17 决定 7） |
| 矛盾 review 通过 | FIXED | `scripts/observation_contract.py:742`（verdict 与开放阻断/判断项一致性） | `test_observation_semantics.py` 41 OK（`ReviewVerdictConsistencyTests` 12：`test_open_blocking_with_sufficient_verdict_is_a_problem`、`test_insufficient_coverage_with_sufficient_verdict_fails_consistency`） | `notes` 多原因要求仍只写在文档，不被解析 |
| owner-decision 阻断 | FIXED | `scripts/observation_contract.py:600`（`BLOCKING_FINDING_STATUSES` 含 `owner-decision`） | `test_observation_semantics.py` 41 OK（`BlockingSemanticsTests::test_owner_decision_high_is_blocking`）；`test_product_observation.py` 31 OK（`test_owner_decision_critical_finding_blocks`） | `owner_decision_ref` 仅非空字符串校验 |
| known-old-issue | FIXED | `scripts/observation_contract.py`（`known-old-issue` 需 `evidence_refs`） | `test_observation_semantics.py` 41 OK（`test_known_old_issue_needs_evidence`） | 旧语料未迁移（设计如此） |
| dismissal_reason | FIXED | `scripts/observation_contract.py`（`dismissed` 必须带 `dismissal_reason`） | `test_observation_contract.py` 49 OK（`test_dismissed_requires_dismissal_reason`）；语义测试 `test_readme_only_dismissal_fails_the_gate` | 解除阻断仍需 owner decision（S04 权威顺序） |

## 3. 语料回放结果（21 份）

`docs/po-repair/corpus/` 共 21 份归档结果（18 report + 3 review；其中 3 份为 t1 手工作品）。各阶段终态：

| 阶段 | 工具/口径 | 结果 | 证据 |
|---|---|---|---|
| S00 基线 | 当时校验器直检 | VALID 3 / INVALID 16 / VALIDATOR-CRASH 2 | `corpus/INDEX.json`（S00 时点，未改） |
| S03 终态 | `tests/test_observation_malformed.py` 逐份判定 | legacy 21 / invalid 0 / valid 0 / crash 0；每份恰好 1 条 legacy 迁移诊断；18 份 report envelope_error_count=3、3 份 review=0 | `baseline/s03-corpus-regression.json` |
| S09 终态 | `tests/test_observation_format_repair.py` 格式纠偏回放 | status 全部 `needs-observation`（cap）；attempts=3、repair_count=2、initial_errors=1；底层 payload 合同错误数 3–93；0 采纳、0 崩溃 | `baseline/s09-corpus-repair.json` |
| S21 回放 | 原样导入 `tools/collect_corpus.py`，输出重定向 | collected=21 / valid=0 / invalid=21 / validator_crash=0 / copy_matches=21/21 / handmade=3 | `baseline/s21/corpus-validity.txt`、`baseline/s21/corpus-replay/INDEX.json` |

口径说明（诚实性）：

- S21 回放的 `invalid=21` 与 S03 的 `legacy=21` 不矛盾：两者都表示"21 份全部被拒绝且 0 崩溃"；
  该收集脚本按 schema 分派校验器（只认 review `/2`），3 份 v1 review 被路由到 report 校验器，
  因此多出 31/32/23 条"未知字段"诊断；18 份 v1 report 各 1 条 legacy 诊断。
  终态判定以 S03/S09 为准，S21 回放的独立价值是**再次确认 0 崩溃、21/21 字节复制一致**。
- 回放只读沙箱源（`E:\MISC\代码项目\po-validation-sandbox`）；`docs/po-repair/corpus/` 未被写入。
- 全部 21 份均为 v1，在 v2 合同下不可能直接合法；真实"重观察"未执行（NOT RUN-需模型）。

## 4. 真实运行计划（全部未运行）

运行手册：`validation/observation-calibration/README.md`（§3 命令、§3.9 归档）；案例与指标定义：
`validation/product-observation/README.md`。本轮 `validation/observation-calibration/runs/` 不存在，
即 **所有案例 0 执行、0 归档、0 指标**。

| 项 | 状态 | 前提 | 命令入口 |
|---|---|---|---|
| 案例 A–G（A 干净对照、B 双模式静默失效、C 旧入口断连、D 入口消失、E 跨功能状态不一致、F 合理变更须 `intended-change`、G 间歇故障须 `intermittent`） | NOT RUN-需模型 | ① 重启 OpenCode 使 `.opencode/plugins/workflow-visibility.js` 生效；② 目标项目 `.opencode` 可解析 `@opencode-ai/plugin`（缺失时 `npm install`）；③ `.opencode/mvp/visibility.json` 选中真实模型；④ S20A 冒烟目录或 `python scripts/install.py <target>` 新装项目 | README §3.1–§3.9：`make_primary_mirror` → `state_reset` → `server_order_plan` → `workflow_packets.py observer --model ... --preflight ...` → `visibility_dispatch`（或 fallback `opencode run --auto --model ... --agent po-observer`）→ `result_source_is_single`/`adopt_result`/`adopt_review` → `runtime_trace.py export` → `check.py product-audit-gate <goal> --trace <trace>` |
| Web 案例 A-web ~ F-web（visual + console） | NOT RUN-需模型/设备 | `agent-browser` 固定到 `product-observer/UPSTREAM.md` 版本且 backend probes 通过；真实模型可用 | packet `channels` 注入 → `observation_backend.preflight_skip_plan` → `choose_backend` → `agent_browser_argv` → `run_step_sequence`，证据入 `evidence_dir` |
| 多模态：图片感知 | NOT RUN-需模型/设备 | 选中模型支持 `image_read`（S01 §4 的 CLI 图片探针仅为历史参考）；真实会话附件链路未验证 | `observation_vision.make_color_probe` 生成纯色 PNG → `dispatch_mode` 判定 → 派发模型回答主色 → `build_perception_record` → `perception_claim_problems` 核 sha256/证据范围 |
| 多模态：音频/视频 | NOT RUN-需模型/设备 | ffmpeg/ffprobe 在 PATH；`MEDIA_MODEL_BASE_URL`/`MEDIA_MODEL_API_KEY`/`MEDIA_MODEL_NAME` 三键齐备（`media_endpoint.available=True`）；控制探针有真实音频 | `observation_media.probe_media`（真实 `process_runner`）→ `extract_frames_argv`/`extract_audio_argv` → `capture_chain_verdict` → `silence_claim_problems` |
| 桌面（desktop） | NOT RUN-需模型/设备 | midscene/UI-TARS 实际安装且探针 `passed`（`adapter_status` 的 `status_hint` 不得升级状态） | `observation_vision.adapter_status`/`host_requirements` → `dispatch_mode`（desktop 需 image_read+visual_grounding+desktop_control）→ 适配器实操 + 截图证据 |
| 修复后重审（新 candidate 完整 discover+compare+review） | NOT RUN-需模型 | 与 A–G 相同 | README §3 全流程 + `update_sidecar` + gate 闭环 |

## 5. 成本指标

- **真实 token / 墙钟未采集**：S21 未执行任何真实派发、浏览器或媒体运行，`runs/` 为空，故观察流程的
  token 数、墙钟、动作数、缺陷召回/误报率均**无数据**；本文不给出任何估计值。
- 可如实记录的只有确定性测试耗时（`baseline/s21/` 原始输出）：

| 运行 | 耗时 |
|---|---|
| 全量 `test_*.py`（1183 tests） | 71.529s |
| `node --test "tests/js/**/*.test.mjs"`（23 tests） | 0.397s |
| 14 个分测试文件 | 0.005s ~ 2.261s（明细见 §1.1） |
| `check.py --selftest` | 原始输出未计时（如实说明） |
| 语料回放 | 原始输出未计时（如实说明） |

- `tests/test_workflow_metrics.py`（13 OK）只证明通用 token/cost 聚合函数正确；观察流程成本统计尚未接入。
- 报告中"25 次有效 run ≈ 3.5h 墙钟、token 未统计"是修复前历史记录（见 COVERAGE-MAP P2-18），非本轮测量。

## 6. 结论边界

### 6.1 机械验证成立（FIXED，均有测试证据）

P1-4（校验/纠偏）、P1-5、P1-6、P1-7、P1-8、P1-9、P2-10（合同/计划）、P2-13、P2-14、P2-15（原语）、
P2-18（仅通用指标函数；观察成本未采集）；关联新发现 6 项全部（finish trace、workspace 二次阻断、
review hash、证据核验、capability gap、矛盾 review）+ owner-decision/known-old-issue/dismissal_reason；
未测项中的续跑/lease 与 stop_reason 其余枚举（机械层）。

### 6.2 BLOCKED-需重启（依赖重启后的 OpenCode 插件/权限）

1. `visibility_dispatch`/`visibility_status` 实机加载与派发；子会话模型 = `visibility.json` 选择的端到端核验。
2. observer/reviewer 权限实机拒绝（edit/写命令/`bash: deny`）。
3. 真实宿主的 `runtime_trace.py export` + `check.py product-audit-gate --trace` 闭环（当前仅测试内驱动 CLI）。
4. 会话内图片附件链路与感知探针的真实派发。

### 6.3 NOT RUN-需模型或设备

1. 案例 A–G、Web A-web~F-web、图片/音频/视频、桌面，全部 0 执行。
2. 真实格式纠偏回合（`run_format_repair` 接真实 `send`）、真实 reviewer 质量与漏面评审。
3. 真实 agent-browser/CLI 进程树清理、编码边界、续跑与 lease 现场行为。
4. token/墙钟等成本指标（未采集，不编造）。
5. 旧 harness 装置端到端重跑（新驱动核心仅机械层）。

### 6.4 附加限制

- `intermittent` 正向值无专门用例（PARTIAL，见 §2.2）。
- `write: deny` 权限键未引入也未验证（S13 决策）。
- `capture_chain` 媒体字段未进入冻结合同（S17 决定 7），媒体 capability 未接 gate。
- `owner_decision_ref` 只到字符串层；`notes` 多原因不参与机械判定。

## 7. 证据索引（`docs/po-repair/baseline/s21/`）

> 2026-09-21 清理：本节原始运行输出（`test_all.txt`、`check_selftest.txt`、
> `node-test-glob.txt`、14 份 `test_*.py.txt`、`env.txt`、`corpus-validity.txt`、
> `evidence-index.txt`）已删除，见 git 历史；`replay_corpus.py`、
> `evidence_index.py` 与 `corpus-replay/` 保留。

- 语料：`corpus-replay/INDEX.json`、`corpus-replay/`（复制件）
- 工具：`replay_corpus.py`（只读重定向运行器）、`evidence_index.py`

## 8. S21 实机校准补录（2026-09-21，真实模型运行）

环境：OpenCode 1.18.25，Node v24.19.0；目标项目 `C:\Users\24083\AppData\Local\Temp\opencode\s20a-target`
（S20A 安装 + `.opencode` 内 `npm install`：`@opencode-ai/plugin` 1.18.25，27 包）；模型
`openai/gpt-5.6-luna`；派发走 primary 镜像 + `opencode run`（插件实机加载仍需重启，未验证）。
运行器：`validation/observation-calibration/run_case.py`（新，实现 README §3 流程 + S09 纠偏回合）；
原始输出与指标：`validation/observation-calibration/runs/<case>/<cid>/`。

### 8.1 真实结果

| 案例 | 阶段（模型耗时） | 检出 | 评审 | gate | 结论 |
|---|---|---|---|---|---|
| A-term **good**（干净对照，cand-calib-2） | discover 81s；compare 67s；0 纠偏 | 0 findings | sufficient | **PASS**（exit 0） | 假阳性对照通过；完整闭环（严格 v2 采纳 + 原生 trace + gate）实测成立 |
| A-term **bad**（B 模式静音种子，cand-bad-1） | discover 62s；compare 80s；compare 触发 **1 次格式纠偏**（`capability_gaps[0] must be an object`） | **MISS**：0 findings；两模式都跑了但把无音效判为成功 | sufficient | FAIL（unresolved capability gap: historical-baseline） | **检出漏报**；同时暴露“无基线被写成 capability gap 导致 gate 误阻断”的语义问题 |
| B-term **bad**（save 静默失效种子，cand-bbad-1） | discover 108s；compare 84s；0 纠偏 | **HIT**：discover F-001 high/confirmed（4 个真实证据文件）；compare `confirmed-defect` | needs-observation（两项 insufficient） | FAIL（unresolved critical/high + review verdict） | **检出命中 + 正确阻断**；证据捕获助手实测可用 |
| 图片感知探针 | `make_color_probe` 随机 green + luna `--file` 回答 | 回答 `green`，sha256 匹配 | `perception_claim_problems == []` | — | **image_read VERIFIED**（CLI 附件链路） |

### 8.2 实机验证到的机制

1. **S13 权限拒绝真实生效**：observer 尝试 `... > evidence\mode-a.txt` 被宿主权限拒绝，原始输出
   （`runs/A-term/cand-calib-1/discover.raw.txt`）含完整规则列表；`edit: deny` 未被模型触发。
2. **盲态成立**：observer 只读 packet 与 candidate manifest，未读 goal 卡或 `.opencode/mvp/**`。
3. **证据捕获助手**：`observation_capture.py` 在 B-term 真实运行中被使用，生成标准输出/错误/
   meta 三类文件；finding 的 `evidence_refs` 全部指向真实文件并通过 gate 核验。
4. **纠偏回合**：A-term bad 的 compare 在 1 次纠偏后通过采纳，证明 S09 状态机接真实 `send` 可用。
5. **gate 阻断**：两个缺陷案例均以不同原因正确 fail（capability gap / unresolved high findings）。

### 8.3 校准中发现并已修复的问题

1. **CLI 证据落盘缺口（新发现）**：observer 被禁止 shell 重定向且无合法落盘工具，首轮只能交空证据。
   修复：新增 `scripts/observation_capture.py`（证据目录内落盘 + meta + sha256）、packet 规则 2b、
   observer agent CLI 证据规则、安装器清单与 `tests/test_observation_capture.py`（7 条）。
2. **`baseline: none` 被写成 capability gap（新发现）**：导致干净 compare 的 gate 误阻断。
   修复（协议层）：`observation-protocol.md` 与 packet 规则明确“无历史基线不是 capability gap”。
3. **运行器缺陷**：review 信封误含 `candidate_id`（合同信封无此字段）、review 阶段误走 observer
   分支；均已修复。

### 8.4 仍待研究 / 未运行

- reviewer 对“证据充分的 confirmed 发现”给出 `findings_validity=insufficient`（B-term），语义待查
  （gate 结论不变，仍阻断）。
- 检出率明显依赖模型：同一 A-term bad 种子，luna **漏报**，而旧沙箱 glm-5.3-flash 曾报出。
- Web A-web~F-web、音频/视频、桌面、intermittent、续跑/lease、`visibility_dispatch` 插件实机加载
  仍未运行；成本 token 仍未采集。
- 结论边界：以上为单模型（luna）+ 两个 CLI 种子的**小样本**结果，不能外推为整体检出率。

### 8.5 复现命令

```bash
python validation/observation-calibration/run_case.py \
  --project <installed-target> --case A-term|B-term --variant good|bad \
  --model openai/gpt-5.6-luna --cid <cand-id> --phases discover,compare,review
# review 单独补跑（保留候选）：
python validation/observation-calibration/run_case.py ... --phases review --no-prepare
# gate：
python <target>/.opencode/workflow/scripts/runtime_trace.py export <target> --out <target>/.opencode/mvp/trace.json
python <target>/.opencode/workflow/scripts/check.py product-audit-gate <target>/.opencode/mvp/g-obs.md --trace <target>/.opencode/mvp/trace.json
```

### 8.6 其余 CLI 种子案例（同一模型，2026-09-21）

| 案例 | 阶段（含纠偏） | 检出 | 评审 | gate | 结论 |
|---|---|---|---|---|---|
| C-term bad（README 五章节，菜单缺 archive）— **修正前** | discover 92s；compare 95s | **MISS**（未读 README） | sufficient | **PASS（缺陷放行）** | 假阴性 + 错误放行 |
| C-term bad — **加入“必读候选公开文档”规则后**（cand-cbad-2） | discover 145s；compare 114s | **HIT**：F-001 medium/confirmed（菜单缺 archive） | needs-observation | FAIL | 同一案例由漏报变检出，规则修正有效 |
| D-term bad（主题保存但不生效 + README “v2 note”称有意） | discover 164s；compare 93s | **HIT**：F-001 high/confirmed + F-002 medium（非法值被接受）；compare 仍判 `confirmed-defect` | findings sufficient / coverage insufficient → needs-observation | FAIL（unresolved high） | 检出命中；**README 洗白未降低判定**（权威顺序生效） |
| E-term redesign（add 不持久化） | discover 360s（1 次纠偏：confidence 枚举）；compare 106s | **HIT**：F-001/F-002 high/confirmed；compare confirmed-defect | needs-observation（coverage insufficient） | FAIL（unresolved high） | 检出命中；纠偏回合再次实战可用 |
| F-term bad（每 3 次 save 静默失败） | discover 190s；compare 163s | **HIT**：discover high/confirmed（复现两次）→ compare high/**intermittent**（“有时成功、后续可恢复”） | **needs-repair**（validity/coverage 均 sufficient） | FAIL（unresolved high/intermittent） | 检出命中；**intermittent 保留规则与 reviewer 决策表实测生效** |

CLI 小结：6 个种子案例中 5 个检出（A-term bad 漏报；C-term 在规则修正后检出），干净对照无假阳性；
所有检出案例 gate 均正确阻断；C 修正前出现过一次缺陷放行。

### 8.7 校准驱动的提示修正（A/B 对照）

**问题**：C-term bad 首轮 0 findings 且 gate 放行——observer 从未读取候选内的 `app/README.md`，
因此不知道“文档承诺 archive 章节”。reviewer 也未识破。

**修正**（协议/提示层，非代码逻辑）：
1. `scripts/workflow_packets.py` 的 `OBSERVER_RULES_TEXT` 增加 4b：候选内公开使用文档是允许输入，
   探索前先读，文档承诺作为 `expected_basis`；文档与实际不一致属可报告缺陷。
2. `.opencode/agents/mvp-product-observer.md` 同步该规则。

**A/B 验证**：同一 C-term bad、同一模型、新候选 `cand-cbad-2`：discover 检出 F-001（medium）
并 compare 判 `confirmed-defect`，gate FAIL（needs-observation）。**漏报 → 检出**。

### 8.8 Web 通道实机案例（B-web bad，agent-browser）

运行器新增最小 Web 支持（先 `python -m http.server` 起服务、后冻结候选；atexit 关闭服务）。
同一模型 `openai/gpt-5.6-luna`，backend=agent-browser，channels=[visual,console]。

| 阶段 | 耗时 | 结果 |
|---|---|---|
| discover | 370s | **F-001 high/confirmed**：“编辑备注并点击 Save 后，reload 恢复为 hello world；未出现文档承诺的 Saved ✓” |
| compare | 154s | F-01 high/confirmed + F-02 medium/confirmed-defect |
| review | — | validity/coverage 均 sufficient → **needs-repair** |
| gate | — | FAIL（unresolved high ×2 + review verdict） |

证据：`evidence/` 下含 agent-browser 截图（`compare-after-save.png` 等）与经
`observation_capture.py` 落盘的 snapshot/console 文本（含 meta/sha256）。

**对 P0-2 的意义**：旧沙箱在 glm-5.3-flash 上 Web 派发全部超时、0 数据点；本轮在同一宿主、
同一 agent-browser 0.38.1 上以 luna 完整跑通 discover+compare+review+gate，且检出并阻断种子缺陷。
Web 通道可行性依赖模型档位（luna 可跑，约 2–6 分钟/阶段），不再需要“headless 批处理”才能开工；
预算分层与批处理（S15）仍是后续优化项而非阻塞项。服务生命周期经 atexit 清理，无残留进程。

### 8.9 校准最终统计（2026-09-21）

- 真实 CLI 种子案例：A(clean)/A(bad)/B(bad)/C(bad)×2/D(bad)/E(redesign)/F(bad) = 8 次全流程运行
  （每次 discover+compare+review+gate，共 24 次模型派发 + 2 次格式纠偏）。
- 检出：种子缺陷 6 例中 **5 例检出**（A-bad 漏报；C 规则修正后检出）；干净对照 0 假阳性；
  所有检出案例 gate 均正确阻断；C 修正前出现过 1 次缺陷放行（已修复并 A/B 验证）。
- Web：B-web bad 检出并阻断（agent-browser + 截图/快照证据）。
- 多模态图片：image_read VERIFIED（随机色探针）。
- 尚未运行：音频/视频、桌面、A-web~F-web 其余案例、续跑/lease、`visibility_dispatch` 插件实机加载
  （需重启）、token 成本采集。
