# contract-review & construction skills

这套 workflow 解决一件事：别让 agent 听着一句模糊需求就开始写代码。

它会先把需求问清，再做契约和计划，最后按计划施工。上一环的产物没通过
机器校验，下一环不会启动。

## 我现在该用哪个命令？

只记住这条主线：

```text
想法还模糊？ /grill（可选）
        ↓ docs/brief.md
/review
        ↓ docs/contract.md (passed)
/plan
        ↓ docs/PLAN.md (confirmed)
/build
        ↓ 代码 + 验收证据
/finish
```

拿不准要不要 `/grill`，直接用 `/review`。如果目标、用户、约束或成功标准
还不够清楚，它会先调用 grill，不会硬猜。

### 五个主命令

- `/grill <idea>`：想法还很模糊，或者事情昂贵、不可逆、涉及隐私时用。
  它只负责把需求问清，产出 `docs/brief.md`。
- `/review <requirements>`：需求已经能说清楚时用。它产出经过独立评审的
  `docs/contract.md`。
- `/plan`：契约通过后用。它把契约编译成不能手改的 `docs/PLAN.md`。
- `/build`：PLAN 确认后用。它逐步实现，每一步都跑验收命令并留证据。
- `/finish`：所有步骤完成后用。它做最终对账，确认代码确实满足契约。

### 遇到情况再用

- `/resume`：施工中断后继续。
- `/change <fact>`：发现契约和现实不符，例如“这个接口其实不存在”。
- `/challenge <idea>`：只想找一个已说清想法的漏洞，不启动完整流程。
- `/assess <idea>`：只想判断值不值得做。
- `/debate <design>`：已经有设计，想看取舍是否站得住。
- `/retro`：竣工后复盘，可选。

自然语言也能触发，例如“帮我把需求问清楚”“评审这个方案”“继续施工”。
英文命令是确定入口，自然语言是方便入口。

## 安装

在本仓库根目录运行，把 `<target-project>` 换成目标项目：

```powershell
python scripts/install.py "E:/path/to/target-project"
```

安装器会做三件事：把真实 command wrapper 复制到目标项目的
`.opencode/commands/`，把校验引擎安装到 `.opencode/workflow/`，并在
`opencode.json` 注册本仓库的 skills path。
如果目标用 `opencode.jsonc`，安装器会保留注释、不自动改配置，并告诉你要
手动添加哪一行。

需要 Python 3.10+，没有第三方依赖。安装后重启 OpenCode。
安装器只会自动升级它上次安装且未被本地修改的文件；遇到同名自定义 command
会拒绝覆盖。确认要替换时显式加 `--force`。

## 一个完整例子：做 TODO List

需求还很粗时，从 `/grill` 开始：

```text
你：/grill 我想做一个团队待办工具，但细节还没想好
agent：谁会用它？最近一次团队因为任务管理出问题是什么情况？
你：五个人的小团队。上周有人漏了上线前的检查项。
……
agent：需求简报已确认，docs/brief.md 校验通过。下一步用 /review docs/brief.md。

你：/review docs/brief.md
agent：简报中的需求都已进入契约或说明了暂不处理的理由。
       独立评审通过，docs/contract.md 状态为 passed。

你：/plan
agent：PLAN 已编译：数据层、界面、联调。请确认。
你：确认。

你：/build
agent：开始数据层……验收通过，证据已保存。开始界面……

你：/finish
agent：最终对账 clean，独立审计无硬伤。PLAN 已置 done。
```

如果需求一开始就很明确，跳过第一段，直接 `/review <requirements>`。

## 接力为什么不会丢需求？

`brief.md`、`contract.md` 和 `PLAN.md` 都有机器可读的 JSON 核心和独立 hash。
契约会记录它消费的是哪一版 brief，并要求 brief 里的每一项都有明确去处：
进入了哪些契约节点、推迟到以后，或者为什么拒绝。漏掉任何一项，契约不能
通过。

contract hash 又进入 PLAN hash；施工和恢复前会重新检查整条链。brief 被契约
消费后就冻结，后续变化必须走 `/change`，不能回头偷偷改。

## 这五个 skill 各管什么

- `grill`：需求澄清。问问题、查事实、产出 brief，不写契约和代码。
- `contract-review`：评审 + 规划。把 brief/明确需求变成 contract，再编译 PLAN。
- `construction`：纯施工。只按确认后的 PLAN 执行。
- `reviewer`：只读独立评审，由主 skill 调用；`/challenge` 也会直接用它。
- `step-executor`：隔离执行一个施工步骤，由 construction 调用。

## 流程开关

`direct` 适合明确、可逆的小改动，可以跳过 grill；`light` 是默认；`full` 用于
跨模块、不可逆、涉及隐私或花钱的工作。

交互上，`autonomous` 尽量少打扰，`checkpoints` 在关键节点问你，`stepwise`
每步都问。涉及花钱、隐私、不可逆操作或增删需求时，无论选什么模式都会停
下来确认。

## 手动检查

平时这些命令由 agent 调用。排查问题时可以自己运行：

```powershell
python .opencode/workflow/scripts/check.py brief docs/brief.md
python .opencode/workflow/scripts/check.py contract docs/contract.md
python .opencode/workflow/scripts/check.py compile docs/contract.md docs/PLAN.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py confirm-plan docs/PLAN.md selection.json --contract docs/contract.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py plan-event docs/PLAN.md event.json --contract docs/contract.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py finish-plan docs/PLAN.md finish-event.json --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py reconcile docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python .opencode/workflow/scripts/check.py --selftest
```

完整合法示例在 `tests/fixtures/`；引擎规则以
`contract-review/references/contract-schema.md` 为准。

## License

MIT.
