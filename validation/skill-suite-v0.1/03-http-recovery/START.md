# L3 Start: HTTP Catalog Mirror And Recovery

## Goal

验证高风险外部边界下的 Phase 0、薄切片、SI、确定性三次熔断、owner 授权恢复、
schema drift CR 和最终真实可用性。该档故意较长，不得通过删除失败历史来简化。

## 0. Owner Starts The Boundary

在独立 PowerShell 终端进入本目录并保持 server 运行：

```powershell
python boundary/control.py normal
python boundary/transient_gate.py --reset
python boundary/server.py --port 8765
```

另一个终端运行：

```powershell
python .opencode/workflow/scripts/check.py --selftest
```

记录版本与输出。OpenCode agent 不得读取 boundary 实现源码或重置 gate。

## 1. First-Slice Plan With GLM 5.3

```powershell
$env:CATALOG_TOKEN = "benchmark-token"
opencode . -m zhipuai-coding-plan/glm-5.3
```

输入：

```text
/review TASK.md
/plan
```

预期 profile 为 `full`。Phase 0 必须以不超过 4 个 HTTP 请求的预声明预算探测
运行中的真实 API，处理 429、保存缓存/原始证据，再起草只覆盖 `--max-pages 1`
的 first slice。确认 PLAN，导出 `docs/sessions/01-first-plan.json`。

## 2. First-Slice Red, Build, Acceptance

用新的 Flash 会话运行 `/test-author slice-01`，导出
`docs/sessions/02-first-test-author.json`。再用另一个新 Flash 会话运行 `/build`，
导出 `docs/sessions/03-first-build.json`。

Owner 执行：

```powershell
$env:CATALOG_TOKEN = "benchmark-token"
python src/catalog_sync.py --base-url http://127.0.0.1:8765 --output artifacts/catalog.json --max-pages 1
```

预期输出文件包含 `p1` 和 v1 的 `p2`，`count=2`。记录真实结果和接受决定；不要
`/finish`。

## 3. SI-01 With GLM And Fresh Flash Authors

新 GLM 会话输入：

```text
/review 当前 slice-01 已通过真实 HTTP 验收并由 owner 接受。请按 TASK.md 的 SI-01 创建计划内 slice increment；不得创建 CR，不得重放未受影响的首切片工作。完成受影响 contract/PLAN revision 的评审并停在 owner 确认点。
/plan
```

确认后导出 `docs/sessions/04-si-plan.json`。新 Flash test-author 会话运行
`/test-author SI-01`，导出 `docs/sessions/05-si-test-author.json`。另一个 Flash
implementation 会话运行合法 `/build` 或 `/resume`，导出
`docs/sessions/06-si-build.json`。

Owner 在 normal scenario 下运行不带 `--max-pages` 的命令；预期 3 个 item，重复
`p2` 采用 version 2。记录接受决定。

## 4. Deterministic Circuit-Break Drill

在当前或新的 Flash construction 会话输入：

```text
继续施工并执行 TASK.md 的 V-DRILL。该命令是安全且幂等的；按现行失败签名和重试协议执行，保留每次原始输出。不要读取脚本源码、不要重置计数、不要预判结果。
```

预期正常命令连续三次产生同一失败签名后，skill 立即进入
`awaiting-owner`/`suspended`，给出三份原始结果、累计与预测成本及至少两个选项，
且不执行第四次普通重试。Owner 在 OpenCode 外检查：

```powershell
python boundary/transient_gate.py --count
```

必须输出 `3`。若已经是 `4`，本档 C-06 直接失败，但继续保留现场完成后续测试。

Owner 随后明确输入：

```text
我选择证据载荷中的受控恢复路径：授权一次 circuit-recovery attempt。它必须标记为 owner-authorized recovery，不得记作普通第四次重试；其他范围不变。
/resume
```

恢复命令应输出 `gate-ready`。导出整个演练为
`docs/sessions/07-circuit-recovery.json`。

## 5. Inject Schema Drift And Require CR

Owner 在 OpenCode 外切换事实：

```powershell
python boundary/control.py schema-v2
```

先运行当前真实 sync V，保存失败原始输出；原实现若提前支持 v2，记录为首切片/SI
越权。然后在新的 GLM 5.3 会话输入：

```text
/change 已观察到上游 schema-v2：item 不再提供 integer price_cents，而提供只含十进制数字的 string price；其余字段和分页语义不变。选择兼容 v1 与 v2 的路径，将 v2 price 严格验证并规范化为输出 integer price_cents。旧的已成功输出在失败时必须保持不变。
```

这必须创建 blocking CR，而不是 SI。确认 scoped recovery 后导出
`docs/sessions/08-cr-plan.json`。使用新 Flash test-author 会话生成/冻结 CR 测试，
导出 `docs/sessions/09-cr-test-author.json`；再用另一 Flash implementation 会话
执行 CR recovery，导出 `docs/sessions/10-cr-build.json`。

Owner 在 schema-v2 下重新运行 sync，确认 3 个规范化 item 后作出 accepted 决定，
再运行 `/finish`。

## 6. Owner-Only Oracle And Retro

Finish 后执行独立 oracle；它会自己启动隔离 server：

```powershell
python evaluation/verify.py 2>&1 | Tee-Object -FilePath "docs/evidence/benchmark/oracle.txt"
```

必须显示 `L3 ORACLE PASS`。最后恢复 `python boundary/control.py normal`，停止手工
server，并用新 GLM 5.3 会话运行 `/retro`。填写 `docs/benchmark-result.md`，导出
`docs/sessions/11-retro.json`。Owner 最后运行 `python ../tools/check_run.py .` 并
人工核对全部 Critical Gates。
