# L1 Start: Receipt Totals CLI

## Goal

验证明确、可逆、本地任务是否走最小流程，同时仍保持独立红测、冻结 hash、内容断言
和真实 owner 验收。该档不应被扩张成多阶段项目。

## 0. Preflight

在本目录运行：

```powershell
python .opencode/workflow/scripts/check.py --selftest
```

把输出和 `opencode --version` 记入 `docs/benchmark-run-log.md`。

## 1. Plan With GLM 5.3

```powershell
opencode . -m zhipuai-coding-plan/glm-5.3
```

依次输入：

```text
/review TASK.md
/plan
```

只按 `TASK.md` 回答问题。预期选择 `direct`，Phase 0 记录为有事实依据的
`not-needed`，而不是伪造外部探针。确认 PLAN 后退出，导出会话到
`docs/sessions/01-planning.json`。

## 2. Author Tests In A Fresh Flash Session

```powershell
opencode . -m zhipuai-coding-plan/glm-5.3-flash
```

输入：

```text
/test-author slice-01
```

必须得到真实 red 和冻结 manifest；此会话不得写 `src/`。退出并导出到
`docs/sessions/02-test-author.json`。

## 3. Implement In Another Fresh Flash Session

```powershell
opencode . -m zhipuai-coding-plan/glm-5.3-flash
```

输入：

```text
/build
```

要求使用已有 manifest，不得在 implementation session 重写测试。施工完成后，
owner 在普通终端执行可见场景：

```powershell
python src/receipt_totals.py fixtures/receipts.csv
```

预期标准输出：

```json
{"accepted_count":3,"category_totals_cents":{"books":2500,"food":1500},"grand_total_cents":4000}
```

把该原始输出交给会话，明确作出 accepted/rejected 决定；accepted 后输入
`/finish`。退出并导出到 `docs/sessions/03-implementation.json`。

## 4. Owner-Only Oracle

Finish 后在 OpenCode 外执行：

```powershell
python evaluation/verify.py 2>&1 | Tee-Object -FilePath "docs/evidence/benchmark/oracle.txt"
```

oracle 必须显示 `L1 ORACLE PASS`。若失败，不允许删除工件重跑成一条成功日志。

## 5. Evidence-Based Retro

使用新的 GLM 5.3 会话运行 `/retro`，传入 oracle 输出路径，填写
`docs/benchmark-result.md`。导出为 `docs/sessions/04-retro.json`，再由 owner 运行
`python ../tools/check_run.py .`；结构 PASS 仍不能替代 `ACCEPTANCE.md` 人工门。
