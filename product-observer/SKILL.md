---
name: product-observer
description: Whole-product black-box observation seat for the delivery workflow. Use when a stable candidate build exists after implementation and engine verification - the observer uses the complete delivered product as a first-time user (discover phase), then checks it against the original goal, historical product maps and prior-version behavior (compare phase), reporting obvious severe non-crashing problems with reproduction evidence. Adapted from agent-browser's dogfood skill; see UPSTREAM.md for provenance and the exact adaptations.
license: Apache-2.0
metadata:
  language: "zh-CN"
  called-by: "mvp-delivery, construction"
  public-command: "none"
---

# Product Observer

在目标卡要求全产品观察时，把"完整产品在真实使用下仍然正常"变成交付前的必经检查，而不是实现者
的自我声明。本 skill 是工作流的**产品观察能力**：观察者以第一次接触
产品的用户身份实际使用当前候选版本的全部重要表面，发现明显、严重、
不崩溃的问题；发现结果进入修复循环与完成 gate。

方法论改编自 agent-browser 的 dogfood skill：保留按产品表面探索、
发现即记录与严重度分类；证据后端、可用性预算和阻断条件按本地协议
调整（见 `UPSTREAM.md`，不得冒充上游功能）。

## Role

- **盲态独立性**：`discover` 阶段只收到产品用途、目标用户、公开使用
  说明、候选版本入口、测试数据引用、预算与后端。**不读** diff、测试、
  实现说明、验收场景或已知缺陷位置。上游规则"Never read the target
  app's source code"同样适用。
- **排他 UI lease**：观察阶段 observer 持有被观察产物的 UI 会话独占
  权；其他 runner 按 controller 既有规则暂停。见
  `references/observation-protocol.md`。
- **只观察，不修复**：observer 永不修改产品代码、测试、goal 卡、
  dispatch record 或 gate 文件；发现按结构化格式返回给 controller。
- **禁止递归派发**：不 dispatch 子代理；需要 controller 执行的动作按
  既有 `CONTROLLER_ACTION` 模板返回。

## Execution

每次派发只执行一个 phase，读取 controller 生成的 v2 phase packet：

```text
workflow_packets.py observer <goal> --phase discover|compare --model <provider/model> --out <packet>
```

1. **读包即开工**：先加载本 skill，读取 packet（`workflow-observer-packet/2`）
   后**尽快操作产品**；不要为观察预设固定探测路线，也不要重跑 packet 声称
   已完成的工作。
2. **Preflight 语义**：packet 的 `preflight` 覆盖 host / model / candidate /
   session；仅当覆盖项 `status: passed` 且其记录的**全部身份字段**与本次
   派发上下文一致时才跳过对应探测——身份缺失、不一致或出现
   "controller-verified" 字样都不构成豁免。后端 `unavailable` 时返回
   `blocked` 并点名缺失前提——绝不转成 `not-applicable`，绝不用降级手段
   冒充通过。
3. **discover（独立探索）**：从真实入口建立产品地图（功能 × 模式 ×
    入口 × 连接关系），对每个重要表面执行代表性短旅程批次；发现问题立即
    按复现纪律记录，交互问题先核能否复现；不能稳定复现但有实际证据时
    标为 `intermittent`，绝不因未复现而删除。再继续其余区域的广度巡检。返回
   `product-observation/2`（phase=discover），不宣布整体结论。
4. **compare（目标/历史查漏）**：在 discover 结果已采纳并绑定候选版本
   后，对照 packet.original 的原始目标、历史产品地图与上一稳定版本行为
   证据，专门寻找消失、退化、断开的能力；每个 finding 必须给出
   `difference_classification`（与 `status` 相互独立，枚举见
   `references/finding-rules.md`）。
5. **格式纠偏协作**：首次回复必须是**恰好一个 ```json 围栏块**。controller
   按 `references/format-repair.md` 要求纠偏时，只修格式——不操作产品、
   不新增事实、不猜 controller 字段；信息不足时回 `needs-observation`
   marker，最多两次纠偏后不合法则本轮按 `needs-observation` 停止。
6. **Stop conditions**：`coverage-completed`（重要表面覆盖完成且证据可审，
   **允许同时存在阻断 finding**，在 notes 说明未修复项）→ completed；
   `budget-exhausted` 必须给出 `continuation` → incomplete；`blocked` /
   `no-backend` / `lease-lost` → blocked，零接触轮用 `notes` 或
   `capability_gaps` 说明原因。同签名三次无新证据 → 沿用既有无进展熔断。

## Output

结构化 `product-observation/2` payload（字段表、所有权与派生状态见
`references/result-contract.md`，不在此重复；发现格式与严重度见
`references/finding-rules.md`）：产品地图、旅程、发现、未观察区域、
能力缺口、续跑游标、停止原因、证据引用。**只输出一个 ```json 围栏块**；
不写结果文件，也不写任何工作流文件。`goal_id`、`candidate_id`、
`observer_session_id`、`model`、`packet_hash`、`received_at`、`attempt`
由 controller 采纳时补充，observer 不得猜测或填写。证据文件真实写入
packet 的 `evidence_dir`，引用使用候选目录内的相对路径。

观察证据（截图、录屏、trace、日志）供验收评审；它们不是
`verify-goal` 的引擎事件，不是 owner 验收，也不能替代任何既有 gate。
controller 不得改写 observer 的结论后冒充观察结果。
