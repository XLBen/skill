# Delivery Recovery Details

> When to read: `/resume`, after an Audited slice finishes, when a completed
> package needs a defect repair, or when scope/deferred questions arise.
> Seat: controller. Inputs: goal card, dispatch record, audit packages,
> original request/brief.

## Resume

从持久目标卡和适用的严格状态恢复，不从聊天猜进度。恢复候选按固定次序发现：

1. `.opencode/mvp/` 下的 unfinished goal（含 blocked）；
2. 无卡时，可识别的未完成严格包（legacy 根级 `docs/PLAN.md` 或
   `docs/audit-slices/` 下非 done 的 PLAN），沿用 `/build` 的建卡规则，
   恢复施工前先建立并校验当前 goal 卡；
3. 无目标且无严格包、而有 draft brief 时加载 `grill` 从持久 frontier 继续
   访谈，不创建目标卡或开始施工。

多个互不相关的候选（多个 active 卡、严格包与无关 draft 并存且关系不明）时
询问用户，不按 mtime 或新旧猜测。从第一个 pending/blocked 结果继续；目标或
基线不明确时先问。

恢复时先读 `subagent-orchestration.md` 的最小恢复读取集，再按缺口展开；
不得默认读取全部 dispatch archive 或全部历史 findings。重新派发前先核对
dispatch record 与实际产物，规则见该文件。

## Next Slice After An Audited Finish

Audited 的 `construction` finish 只关闭当前切片；随后更新目标卡并由主控重判
下一片风险：

- Normal/Guarded 下一片继续轻量执行（无 contract/PLAN）；
- 只有 Audited 下一片才用 `contract-review` 的 SI 协议在新包中准备并确认
  delta，然后回到 construction。

不要对已完成的 PLAN 编译累计契约（当前引擎会把未受影响步骤重置为
pending）。新包只包含受影响工作，并通过目标卡引用先前的 reconcile 证据。
这个接力不需要新命令，但每次 SI 需要 owner 对已观察基础切片的实际验收和
delta 决定，然后确认新生成的 PLAN；goal 批准不是对未来 PLAN 的预授权。
这些 gate 前暂停，批准后内部继续。

### PUA Acceptance: `slice-acceptance`

For an Audited slice, before requesting the SI decision, load `../pua/SKILL.md`
and execute the `slice-acceptance` card. Ask “clean 了当前 slice，整件事也交付了
吗？” Show the owner the real input, output, environment, limitations and
evidence for the observed slice. Keep goal-level pending outcomes visible. A
missing owner decision is `待 owner 决定`, not a retry or a pass.

## Fixing Completed Audited Packages

Fixing a defect in an already completed Audited package is not an SI, cannot use
the engine's same-PLAN CR recovery, and never mutates that package. Create a
sibling `docs/audit-slices/<goal-slug>/FIX-<nn>-<slug>/` replacement package.
Its `repair.md` names the base package/hash and observed mismatch. Release its
standalone affected-only contract as a normal new Audited slice, compile a new
PLAN without `--previous-contract`, and verify the correction plus regression
behavior. After clean reconcile, the goal card marks which prior
outcome/evidence it supersedes while retaining the old package as history. Use
engine CR recovery only while the mismatching package is still active.

## Scope And Deferred Discipline

实现中发现的新想法默认不扩张目标。原始目标内被首片延后的内容必须继续处理，
不能静默丢弃。必需成功结果不能藏入 `deferred`，也不能把真实设备/API 目标改成
样例目录或 mock。分别记录缺实现与缺验证；原始边界所需 outcome 保持
pending/blocked，阻止 complete。可选愿望不应假装成 BS 后静默删除；范围改变
必须重新明确确认，冻结 brief/契约仍按 CR 或新包规则处理。MVP 是排序机制，
不是永久的 scope cut。

需求已明确时不提问，直接宣布首片并开始；不明确时只问使最终成功变得可观察
所必需的问题，一次一个；一旦可以选择并验证首片就执行，不继续做完整需求
访谈。若用户明确要求深度澄清，再加载 `grill`。
