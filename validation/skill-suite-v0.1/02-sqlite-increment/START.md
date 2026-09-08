# L2 Start: SQLite Event Ledger

## Goal

验证 `light` 项目能否先用真实 SQLite 探针关闭事务风险，只交付可用首切片，再把
计划内的验证强化作为 SI-01 增量，而不是预先做完整项目或滥用 CR。

## 0. Preflight

```powershell
python .opencode/workflow/scripts/check.py --selftest
```

记录 OpenCode/Python 版本和原始输出。

## 1. First-Slice Plan With GLM 5.3

```powershell
opencode . -m zhipuai-coding-plan/glm-5.3
```

输入：

```text
/review TASK.md
/plan
```

预期 profile 为 `light`。Phase 0 应在小预算临时数据库中真实验证 Python SQLite
事务与唯一键能力；首 contract 只激活 `TASK.md` 的 First Slice，SI-01 留作明确的
计划增量。确认 PLAN 后退出并导出 `docs/sessions/01-first-plan.json`。

## 2. First-Slice Red And Build

新建 Flash 会话，运行 `/test-author slice-01`，退出并导出
`docs/sessions/02-first-test-author.json`。再新建另一个 Flash 会话运行 `/build`，
导出 `docs/sessions/03-first-build.json`。

Owner 删除旧演示库后执行：

```powershell
Remove-Item -ErrorAction SilentlyContinue "artifacts/demo.db"
python src/event_ledger.py ingest --db artifacts/demo.db fixtures/events.jsonl
python src/event_ledger.py report --db artifacts/demo.db
python src/event_ledger.py ingest --db artifacts/demo.db fixtures/events.jsonl
```

预期依次为：

```text
{"duplicates":0,"inserted":3}
{"account_totals":{"alpha":3,"beta":7},"event_count":3}
{"duplicates":3,"inserted":0}
```

把结果写入 owner acceptance，但此时不要 `/finish`。

## 3. Plan SI-01 With A New GLM Session

启动新的 GLM 5.3 会话并输入：

```text
/review 当前 slice-01 已通过上述真实验收并由 owner 接受。请严格按 TASK.md 的 SI-01 创建计划内 slice increment；不得创建 CR，不得重放未受影响步骤。完成受影响 contract/PLAN revision 的评审并停在 owner 确认点。
/plan
```

确认增量 PLAN，退出并导出 `docs/sessions/04-si-plan.json`。如果 `/review` 无法可靠
路由到 SI，保留失败证据，不要自行手写一个看似正确的 SI。

## 4. SI Red And Build

新建 Flash test-author 会话运行 `/test-author SI-01`，导出
`docs/sessions/05-si-test-author.json`。再新建 Flash implementation 会话运行
`/build` 或 skill 判定的合法 resume 路径，导出 `docs/sessions/06-si-build.json`。

Owner 用已导入的 `artifacts/demo.db` 执行：

```powershell
python src/event_ledger.py ingest --db artifacts/demo.db fixtures/events-invalid.jsonl
python src/event_ledger.py report --db artifacts/demo.db
```

第一条必须 exit 2 且无 stdout，第二条仍必须是 3 个事件、`alpha=3`、`beta=7`。
记录接受决定后，在 Flash 会话运行 `/finish`。

## 5. Owner-Only Oracle And Retro

Finish 后执行：

```powershell
python evaluation/verify.py 2>&1 | Tee-Object -FilePath "docs/evidence/benchmark/oracle.txt"
```

必须显示 `L2 ORACLE PASS`。最后用新 GLM 5.3 会话运行 `/retro`，填写
`docs/benchmark-result.md`，导出 `docs/sessions/07-retro.json`。Owner 再运行
`python ../tools/check_run.py .` 并人工核对 `ACCEPTANCE.md`。
