# 条件性计划、设计审查与中途用户决定

新计划 `engineering-plan/3` 沿用任务包/分层验证，只增加实际需要的前提，不是
再造审批系统。goal 仍是 schema 3；旧 engineering-plan/1、/2 保持可读。

## 1. 发布完整路线，但只执行条件成立的任务

最小条件示例（写在计划索引，完整字段见 design-template.md）：

```json
{
  "conditions": [
    {"id":"Q-01","kind":"check","claim":"实际目标接受当前驱动的操作",
     "criterion":"S-01/T-01 经实际适配器操作并回读成功，不是工具列表或文件存在",
     "affects":["S-02"],"evidence_required":true,"resolver":{"step":"S-01","check":"T-01"}},
    {"id":"Q-02","kind":"owner","claim":"用户接受演示中的交互方式与等待成本",
     "criterion":"展示准备步骤、设备占用、延迟与失败损失后明确确认，原始禁令不变",
     "affects":["S-02"],"evidence_required":true}
  ]
}
```

技术条件由 resolver 步骤真实运行且观察通过解除，不接受一个手填 passed，也不由
用户批准替代技术检查。resolver 必须是 affected 步骤的严格前置；自依赖会拒绝。
条件影响 affects 及其后继。next-step 可先选择其他不受阻塞的依赖就绪任务，但
显式 begin-cycle 也不能跳过条件。verify/advance/final gate 重新检查相关条件。
关键主张注明 evidence_level 与 scope/invalidated_by，关键未实测主张须关联条件。
来源字符串不证明主张为真，语义由规划走查/独立评审核验。

## 2. 前置工具的自举检查

```json
{"probe":{"command":"python tools/probe.py",
 "assertion":{"type":"stdout-contains","literal":"TARGET_READY"},
 "requires_files":[{"path":"tools/probe.py","provided_by":"S-01"}]}}
```

使用该 preflight 的步骤必须严格依赖 S-01，不能就是 S-01；producer 的 files
需声明路径。已有文件用 provided_by=existing。运行前缺文件明确 blocked，尚未
创建 cycle、不启动命令；无文件依赖用 []。不靠 shell 字符串解析器猜全部导入。
规划者仍需完整声明依赖，reviewer 核真实性。

## 3. 独立设计审查是执行条件

`design_review.mode=self|independent` + reason。Guarded/Audited 必须 independent，
指向一个 kind=review 的 Q 条件，覆盖所有 implementation 任务。明确的最小 probe
可先运行产生审查材料；不能把整工程伪装为 probe。Normal 自查也做反例走查。
发布结构完整的条件性设计，不代表独立审查通过。未通过时 only probe 可执行，
能力不可用报告 blocked。审查范围见 engineering-challenges.md；需要具体反例/
修正要求，不能靠重复转述作者的正常路径签字。

## 4. 中途异议：先持久暂停，再记录真实决定

用户提出路线异议时先停止新的有副作用操作；正在运行的工具按其取消/超时机制
结束，本协议不能异步撤销已发送动作。然后主控运行：

```text
python .opencode/workflow/scripts/check.py request-decision <goal> <request.json>
```

request.json：
```json
{"id":"D-01","question":"看过实际交互后，继续原路线、暂停还是修改方案？","basis":"用户在当前任务提出可接受性异议","affects":["S-07"],"evidence_required":true}
```

它保存问题/影响范围，冻结新的 begin/verify/observe/finish，也阻止换计划 hash
绕过未回答问题；不伪造技术失败、不把当前 attempt 标完成。next-step 返回
owner-decision 及原尝试引用，不需要先把未完成任务强行测绿。

获得真实 question/用户消息后，从本地 OpenCode 会话库显式导出该项目的会话文本：

```text
python .opencode/workflow/scripts/runtime_trace.py export <project-root> --include-conversation-text --out .opencode/mvp/decisions/<goal>/D-01.trace.json
python .opencode/workflow/scripts/check.py resolve-decision <goal> D-01 <decision.json>
# 计划内 owner/review 条件也用同一命令，将 D-01 换成 Q-02 等。
```

decision.json：
```json
{"decision":"accept","actor":"owner","reason":"用户明确选择继续当前路线且原始限制不变",
 "source":{"trace_path":".opencode/mvp/decisions/G-X/D-01.trace.json","trace_sha256":"<trace 文件的实际 sha256>",
   "native_message":{"session_id":"<trace 内 session id>","message_id":"<user message id>","part_id":"<text part id>","quote":"用户原消息中的原文"}},
 "evidence_refs":[".opencode/mvp/decision-sources/demo-results.md"]}
```

`--include-conversation-text` 是显式隐私开关：默认 runtime trace 不导出聊天正文；
导出文件应留在本地 `.opencode/mvp/`、加入 `.gitignore`，不可发布或纳入交付物。
resolve-decision 重新核 trace 文件 hash、SQLite 原生来源、项目目录、message/part
身份、role、正文和 quote；决定 message 必须晚于 request。需演示/审查证据的 accept
还须引用非空 evidence 文件，且重新核 hash。review 条件 actor=reviewer，引用的
assistant message 必须属于真实 `mvp-reviewer` 子 session，其 parent 是 author session；
trace 还须包含同一 author session 发起、完成的 mvp-reviewer task dispatch。审查
seat 的正式 independent/runtime gate 仍会复核原生 trace。

trace/message ID 可以被复制、文件和本地数据库也能被有权进程改写；这是本机来源
一致性检查，不是密码学身份认证或不可抵赖签名。skill/控制器不能仅凭记录文件
宣称 owner 已授权；若宿主不提供可验证的真实 question/user message，应保持 blocked，
使用宿主交互等待实际回答，不得伪造一个“审计证明”。

- accept：只解除决定阻塞；原 attempt 未测就恢复 implement/verify，绝不直接通过。
- reject：保持 blocked，不替用户推导另一个选择。
- revise：当前定义返回 replan；更新受影响设计/必要时修订 brief，再发布。
- 用户明确改变决定：用新的原话来源再次 resolve，同一问题追加不可变版本，
  前一记录保留，不改写旧回复。含糊“算了”先问一个具体问题，不自动 accept。

## 信任与适用边界

记录标记为 **locally-attributed-reference-not-authenticated**：证明引用存在且
未改动，不证明引用真是用户/独立 reviewer 发的。必须来自真实宿主对话/派发，
最终审计仍核原生 provenance；不能编造会话 ID 或把模型文件冒充人类授权。
程序不理解答复的全部语义，也不阻止有文件权限者篡改状态。
Q 决定随定义/策略失效；D 请求跨重新发布保存，未回答/拒绝不能靠改 hash 消失。
已有技术 replan 沿用 observe-cycle，不必每次拉用户审批。产品范围/禁令变更
必须进入 brief，不能用一条 accept 绕过原始承诺。
