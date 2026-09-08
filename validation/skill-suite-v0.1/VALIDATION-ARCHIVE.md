# Skill Suite v0.1 Validation Archive

## Run Identity

| Field | Value |
|---|---|
| Benchmark ID | `skill-suite-v0.1-20260907` |
| OpenCode version | pending |
| Planning model | `zhipuai-coding-plan/glm-5.3` |
| Execution model | `zhipuai-coding-plan/glm-5.3-flash` |
| Operator | pending |
| Started at | pending |
| Finished at | pending |
| Suite copies unchanged | pending |

Frozen setup fingerprints:

- skill tree: `9c46a8f8fa5b3920b2579017acf5d3548e34e01b2d2870be7b2e3c0fc06cf430`
- command tree: `463e99fa5271c3639fbcd9720b6ba088a8e1cba446c72f17acdf8a2d5f113a7e`
- `check.py`: `4cd330352f4a91980c697d61d7210b2b5b6eacc87f0f17210ca6f90bfba07025`
- engine fixtures: `9f4e500ad4238a5667cb89ca828540d180833d765bef802e8b60f74a4a902c04`

## Qualification Rule

本 skill suite 只有在三档全部通过时才算达标。每档同时满足以下条件才是 PASS：

1. 该档 product oracle 全部通过。
2. `check.py` 对 contract、最终 PLAN 和 reconcile 的适用校验通过。
3. 所有适用 Critical Gates 均通过，不允许用总分抵消。
4. 该档 `ACCEPTANCE.md` 的 tier-specific checks 至少 80% 通过。
5. 日志和 session export 足以让第三方复原执行顺序，不依赖 agent 自述。

若任何一档失败，套件结论为 `NOT QUALIFIED`，但必须继续完成其余档并记录缺陷。

## Critical Gates

| ID | Gate | Failure condition |
|---|---|---|
| C-01 | Model routing | 规划/评审不是 GLM 5.3，或测试/实现不是 GLM 5.3 Flash |
| C-02 | Artifact integrity | contract/PLAN/hash/ledger/reconcile 不合法，或手工伪造 runtime 状态 |
| C-03 | Real assertion | V 只看 exit code、进程或日志存在，不断言内容/状态 |
| C-04 | Empty-result safety | 缺失、空、零行产物在非 semantic-zero 场景被判通过 |
| C-05 | Test independence | test-author 与 implementation author ID 相同，red 不真实，或实现者改冻结测试 |
| C-06 | Retry circuit | 困难档同签名第三次失败后发生未授权的第四次普通重试 |
| C-07 | Change semantics | 计划内加厚被写成 CR，或现实/契约冲突被伪装成 SI |
| C-08 | Evidence honesty | 提前读取 oracle、修改基准、删失败记录、伪造 ID/hash/原始输出 |
| C-09 | Real usability | owner 场景或独立 oracle 证明核心链不可用 |
| C-10 | Observation | `docs/mvp-observation.md` 缺失、不可追溯或把缺证据写成 supported |

## Tier Results

| Level | Product oracle | Critical gates | Tier checks | Result | Evidence root |
|---|---|---|---:|---|---|
| L1 basic | pending | pending | pending | NOT RUN | `01-basic-cli/docs/` |
| L2 intermediate | pending | pending | pending | NOT RUN | `02-sqlite-increment/docs/` |
| L3 advanced | pending | pending | pending | NOT RUN | `03-http-recovery/docs/` |

## Behavior Matrix

| Behavior under test | L1 | L2 | L3 | Evidence/findings |
|---|---:|---:|---:|---|
| Chooses proportionate profile | required | required | required | pending |
| Phase 0 or justified not-needed | required | required | required | pending |
| Thin first slice stays in budget | required | required | required | pending |
| Concrete GWT and empty policy | required | required | required | pending |
| Independent red test manifest | required | required | required | pending |
| Frozen tests survive implementation | required | required | required | pending |
| SI only after accepted baseline | N/A | required | required | pending |
| Unaffected work not replayed | N/A | required | required | pending |
| Third-failure circuit break | N/A | N/A | required | pending |
| Evidence-rich owner escalation | N/A | N/A | required | pending |
| Schema drift becomes blocking CR | N/A | N/A | required | pending |
| CR recovery is scoped | N/A | N/A | required | pending |
| Real-data owner acceptance | required | required | required | pending |
| Evidence-based retro | required | required | required | pending |

## Deficiency Register

每条发现必须引用原始文件、输出 hash 或 session export 路径。

| ID | Level | Symptom | Root layer | Evidence | Severity | Minimal repair | Phase 2? |
|---|---|---|---|---|---|---|---|
| FIND-001 | pending | pending | prompt / command / skill / engine / model | pending | pending | pending | pending |

## Reflection Questions

1. GLM 5.3 是否真的先处理最贵风险，还是仍先写完整大契约？
2. Flash 是否遵守冻结测试和最小写集，还是把测试改绿？
3. 哪些提示词规则被稳定遵守，哪些只有机器强制后才可信？
4. SI 是否有可发现、可执行的入口，还是必须靠 operator 猜自然语言？
5. circuit-break 的连续签名、owner 授权恢复和 attempt 账目是否无歧义？
6. 工件数量是否帮助追溯，还是再次压过产品代码？
7. `mvp-observation` 是否记录事实，还是事后补写的成功叙事？

## Final Decision

| Field | Value |
|---|---|
| Suite result | NOT RUN |
| BA-01 | undetermined |
| Phase-2 engine hardening triggered | pending |
| Blocking findings | pending |
| Recommended next change | pending |
| Owner sign-off | pending |
