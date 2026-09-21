# S00 问题—测试映射清单（COVERAGE-MAP）

- 日期：2026-09-21
- 问题来源：`E:\MISC\代码项目\po-validation-sandbox\PROBLEM-REPORT.md`（P0-1~P2-18）、
  `results/evidence-digest.md`、S00 语料直检（`docs/po-repair/corpus/INDEX.json`）。
- "当前状态"口径：**已覆盖** = 有能真实变红的测试或机械断言；**部分** = 只覆盖声明/构造层，
  不能覆盖报告中的真实失败模式；**无** = 无对应测试（或属宿主/装置问题，仓库内不可单测）。
- 计划步骤映射按 S00 任务书固定，不在此自行调整。

## 1. 主表

| 问题 | 现有测试/文件位置（若存在） | 当前状态 | 计划修复步骤 | 备注 | 状态（S21 核验） | 证据（S21；详见 CALIBRATION.md §1/§2） |
|---|---|---|---|---|---|---|
| P0-1 CLI 派发 subagent 席位静默回落 build | `tests/test_subagent_orchestration.py:82-89`（只断言 agent 文件含 `mode: subagent` / `edit: deny` 文本）；宿主 `opencode run --agent` 行为无测试 | 无（仅声明层） | S01/S12/S20 | 需实机验证；生产正门是会话内 task 派发，本轮未测 | PARTIAL（插件/配置逻辑已测；真实派发 BLOCKED-需重启） | `tests/js` 23/23；`test_visibility_config.py` 59；`test_observation_dispatch.py` 27；`test_subagent_orchestration.py` 9 |
| P0-2 Web 通道（agent-browser）不可行 | `tests/test_product_observation.py:110`、`tests/test_observer_packets.py:94` 仅出现 `backend: agent-browser` 字符串；无浏览器旅程测试 | 无 | S10/S14-S17/S21 | 8 次 Web 派发零产出，属真实模型/预算问题 | BLOCKED-需重启（无浏览器实机） | `test_observation_backend.py` 49（假 runner） |
| P1-3 `edit: deny` 拦不住 Write；compare 覆写 discover 证据 | `tests/test_subagent_orchestration.py:29-34`（声明层）；无运行时写权限测试 | 部分（声明层） | S08/S13 | 需要 agent 定义 + 结果交付走控制器归档 | PARTIAL（声明/命令模式静态回归）；实机权限 BLOCKED-需重启 | `test_observation_permissions.py` 9 |
| P1-4 schema 词表/结构漂移 18/21 | `tests/test_product_observation.py:338-356`（构造样本）；真实语料 `docs/po-repair/corpus/INDEX.json`（21 份，16 INVALID + 2 CRASH） | 部分（构造层；真实语料未纳入断言） | S02/S03/S09 | 需容错归一或纠偏回合；S00 已把真实语料固化为 corpus | FIXED（校验器/纠偏层）；真实重观察 NOT RUN-需模型 | `test_observation_contract.py` 49、`test_observation_malformed.py` 14、`test_observation_format_repair.py` 20；语料回放 0 崩溃 |
| P1-5 有状态应用写自身目录被误判篡改 | 仓库内 `state_glob` 零命中；`tests/test_evidence_binding.py` 是交付物 workspace 绑定，机制不同 | 无 | S06/S07 | F-term `.tries`/`note.txt`、B-term `note.txt` 两例 | FIXED（机械） | `test_observation_state_binding.py` 26（skip=1）、`test_observation_candidate.py` 40（skip=2） |
| P1-6 结果交付通道未定义（stdout JSON vs 写文件） | `tests/test_observer_packets.py` 只覆盖 packet 结构；无交付通道/双通道采纳契约测试 | 无（packet 侧部分） | S08/S09 | 首轮 3 次派发 2 次 NO-JSON | FIXED（机械）；真实纠偏回合 NOT RUN-需模型 | `test_observation_results.py` 94；`test_calibration_driver.py` 39 |
| P1-7 校验器被畸形输入弄崩（TypeError） | 无测试；S00 语料直检首次在本仓库复现 2 份（corpus/INDEX.json 的 `VALIDATOR-CRASH`） | 无 | S03 | `review.findings_validity` 为 dict；同类集合成员测试遍布 report 校验 | FIXED | `test_observation_malformed.py` 14；语料回放 21/21 无崩溃 |
| P1-8 gate 早退掩盖后续问题 | `tests/test_product_observation.py:203-208` 只断言单个 missing 提示；无"全量收集"断言 | 无 | S05 | T3 的 gate 只显示 stale 一行即为例证 | FIXED | `test_observation_gate.py` 33（`FullDiagnosisTests` 5） |
| P1-9 上一轮证据被覆写与采纳歧义 | 无测试 | 无 | S08 | 与 P1-3/P1-6 同源 | FIXED（机械） | `test_observation_results.py` 94（`RunLayoutTests` 8、`AdoptCreateOnlyTests` 3） |
| P2-10 技能仪式无 preflight 豁免 | `tests/test_observer_packets.py` 无 `preflight` 字段/豁免测试 | 无 | S10/S15 | packet 需要 `preflight: controller-verified` | FIXED（合同/计划）；真实探针 NOT RUN-需模型/设备 | `test_observer_packets.py` 23（preflight 5 类）；`test_observation_backend.py` 49 |
| P2-11 reviewer 判断错误 + 表达欲越界 | 无产品观察 review 语义测试（`reviewer/SKILL.md` 已改但无机械断言） | 无 | S04/S05 | T3：有 open high 时 verdict=sufficient；两份 review 用富对象表达 | PARTIAL（verdict 一致性机械 FIXED；评审质量 NOT RUN-需模型） | `test_observation_semantics.py` 41（`ReviewVerdictConsistencyTests` 12） |
| P2-12 goal 与随产品 README 权威冲突 | 无测试 | 无 | S04/S19 | D-term 被 README "v2 note" 洗白为 owner-decision/low | PARTIAL（owner_decision_ref 机械阻断 FIXED；真实权威判定 NOT RUN-需模型） | `test_observation_semantics.py` 41；`test_product_observation.py` 31 |
| P2-13 观察者无法自知 session id | `tests/test_product_observation.py:295-316` 覆盖控制器传入 trace 的 provenance；无自报/补绑文本与契约测试 | 部分 | S08/S12 | 需要"控制器补绑"语义 | FIXED（控制器绑定）；实机 trace 部分 BLOCKED-需重启 | `test_observation_results.py` 94；`test_observation_dispatch.py` 27 |
| P2-14 词表不一致（known-old-issue、dismissal_reason） | `scripts/product_observation.py:32-39`（`FINDING_STATUSES` 无 `known-old-issue`）；语料 A/B/D-term compare 实际写出 `classification: known-old-issue`；无测试 | 无 | S02/S04 | `dismissal_reason` 亦无 schema 字段 | FIXED | `test_observation_contract.py` 49；`test_observation_semantics.py` 41 |
| P2-15 孤儿进程树与目录锁 | 仓库内无（harness 级运维问题） | 无 | S14 | 需 taskkill /F /T + `agent-browser close --all` + 目录退避规程 | FIXED（原语）；实机 NOT RUN-需设备 | `test_observation_process.py` 20 |
| P2-16 Windows 编码三连 | `python scripts/check.py --selftest` 在当前 GBK 控制台 PASS；无字节捕获/`utf-8 decode(replace)` 的显式回归测试 | 部分 | S14/S20 | GBK 控制台 `✓`、mojibake、UnicodeDecodeError | PARTIAL（原语+控制台自检）；宿主链路 NOT RUN-需设备 | `test_observation_process.py` 20；`check.py --selftest` PASS |
| P2-17 opencode / agent-browser CLI 摩擦 | 无（宿主缺陷） | 无 | S01/S14/S20 | `--file` 吞提示词、session list 非 JSON、管道杀进程 | PARTIAL（绕行原语）；宿主行为 NOT RUN-需设备 | `test_observation_process.py` 20；`test_observation_dispatch.py` 27 |
| P2-18 成本 | `tests/test_workflow_metrics.py:116-226` 覆盖通用 token/cost 聚合；无观察流程成本统计 | 部分 | S15/S21 | 本轮 25 次有效 run ≈ 3.5h 墙钟，token 未统计 | PARTIAL（通用聚合已测）；观察成本未采集 NOT RUN | `test_workflow_metrics.py` 13；无 token/墙钟数据（CALIBRATION §5） |
| 未测项（报告 §3 共 7 项） | 均无测试 | 无 | S12/S18/S21 | Web 检出、seats 会话内派发、intermittent 保留、续跑/resume、漏面评审、stop_reason 其余枚举/lease/write:deny、token 成本 | 逐项：Web BLOCKED-需重启；seats BLOCKED-需重启；intermittent PARTIAL（无正向用例）；resume FIXED 机械；漏面 PARTIAL；stop_reason/lease FIXED 机械、write:deny NOT RUN；token NOT RUN | CALIBRATION.md §2.2 |
| 附录 A harness 缺陷（13 项） | 装置在仓库外 `po-validation-sandbox/driver/`；仓库内无 | 无 | S20 | 类型错、命令路径、编码、进程树、fixture 自缺陷等 | PARTIAL（替代核心已测）；端到端 BLOCKED-需重启 | `validation/observation-calibration/driver_core.py` + `test_calibration_driver.py` 39 |
| 关联新发现（6 项，明细见 §2） | 见 §2；均无测试 | 无 | S05/S07/S08/S17 | finish 未传 trace、workspace 二次阻断、review hash 路径不一致、证据仅字符串、capability gap 校验不足、矛盾 review 通过 | FIXED×6（机械）；另 owner-decision/known-old-issue/dismissal_reason 语义项 FIXED（CALIBRATION §2.4）；实机 NOT RUN | `test_observation_gate.py` 33、`test_observation_semantics.py` 41、`test_observation_state_binding.py` 26 |

## 2. 关联新发现明细（本清单行"关联新发现"的展开）

| 新发现 | 代码位置 | 现象 | 当前状态 | 计划步骤 | 状态（S21 核验） | 证据（S21） |
|---|---|---|---|---|---|---|
| finish-goal 未传 trace | `scripts/check.py:2241`（`enforce_product_observation(goal_path, goal)` 无 trace）对比 `scripts/check.py:5157-5163`（CLI `product-audit-gate --trace`） | `finish-goal` 路径跳过 provenance 校验（session/skill 绑定） | 无测试 | S05/S07/S08/S17 | FIXED（测试内 CLI 闭环；实机 trace NOT RUN-需重启） | `scripts/check.py:2276`；`test_observation_gate.py` `GateRecordClosedLoopTests` 9（含 `test_gate_cli_requires_a_trace`、`test_changed_trace_file_blocks_check_current`） |
| workspace 二次阻断 | `scripts/check.py:2239-2242`（门顺序）+ `enforce_workspace_binding`（`scripts/check.py:2160-2199`） | 观察门之后再做 workspace 绑定，状态性产品再次被"workspace changed"阻断（P1-5 下游） | 无测试 | 同上 | FIXED（机械） | `scripts/runtime_state_policy.py:199/223`；`scripts/check.py:2215`；`test_observation_state_binding.py` 26（`test_policy_excludes_state_write_and_binds_evidence`、`test_state_write_after_verification_is_tolerated`） |
| review hash 路径不一致 | `scripts/product_observation.py:459-490`（按 sidecar ref 加载报告）vs `:533-540`（按 `cdir/<phase>.result.json` 固定名比对 hash） | ref 指向别处时，校验的报告与做 hash 的文件可能不是同一份 | 无测试 | 同上 | FIXED（按 sidecar ref 实算） | `test_observation_gate.py` `ReviewHashBindingTests::test_review_hashes_use_sidecar_referenced_files` |
| 证据仅字符串 | `scripts/product_observation.py:227-229、261-263、300-302` | `evidence_refs` 只校验"非空字符串数组"，不校验文件存在/内容；gate 无从判断证据是否支撑 finding | 无测试 | 同上 | FIXED（存在/作用域；不解内容） | `test_observation_gate.py` `EvidenceReferenceTests` 5（缺失/越界/绝对路径/合法） |
| capability gap 校验不足 | `scripts/product_observation.py:292-294`（仅要求 list）、`:509-518`（gate 只看 `item.get("channel")` 真值） | 其余字段/状态无校验，无法机械化阻塞 | 无测试 | 同上 | FIXED（机械；媒体 capture_chain 未接 gate） | `test_observation_gate.py` `ObservationRegressionTests::test_capability_gap_still_blocks`；`test_observation_contract.py` `test_blocked_needs_notes_or_capability_gaps` |
| 矛盾 review 通过 | `scripts/product_observation.py:306-326`（仅枚举校验） | review 的 verdict 与报告 findings 无一致性交叉校验；`notes` 从不参与判定 | 无测试 | 同上 | FIXED（机械） | `scripts/observation_contract.py:742`；`test_observation_semantics.py` `ReviewVerdictConsistencyTests` 12 |

## 3. 说明

- 本表"当前状态"只描述 S00 时点；后续步骤修一项、补一项回归，应同步更新本表（建议在对应步骤的 PROGRESS 记录中注明差异）。
- 所有"真实语料"证据固定在 `docs/po-repair/corpus/`，供 S01 起的回归测试引用；
  测试只读 corpus，不得修改原始文件（corpus 是复制件，重跑脚本可整体重建）。
- P0-1 / P0-2 / P2-15 / P2-17 属宿主或测试装置边界，仓库内单测无法覆盖的，需在对应步骤做
  **实机验证**并在 PROGRESS 中如实标注"未实机验证/BLOCKED"，不得用 mock 通过替代。
- **S21 追加列说明（2026-09-21）**：上表新增"状态（S21 核验）""证据（S21）"两列，既有列内容未改。
  S21 只做机械核验与文档归档：所有 FIXED 均指有测试覆盖的确定性结论；BLOCKED-需重启 与
  NOT RUN-需模型或设备 的完整清单、限制与原始输出索引见 `docs/po-repair/CALIBRATION.md`。
  本轮全量 1183 tests + Node 23 tests 全绿，语料回放 21/21 无崩溃（`baseline/s21/`）。
