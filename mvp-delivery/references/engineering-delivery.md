# Plan → Build：任务包与分层反馈

**面向新项目的主路径**。规划者完成全部设计；执行者拿一个小任务包；工具处理
绑定、步骤选择和原始回执。不要让执行模型维护第二份任务表或重新设计系统。

## 规划产物与发布

按 `writing-plans` 产出独立工程设计，默认 `docs/plan.md` 或用户指定的项目内路径。
其中 `engineering-plan/2` 索引含统一合同、所有详细任务和分层验证。格式与例子见
`../../writing-plans/references/design-template.md`、`engineering-plan-example.md`。

规划者建立包含原始来源/outcomes 的 goal（定义见 goal-definition.md），运行：

```text
python .opencode/workflow/scripts/check.py prepare-plan <goal> <design-path>
python .opencode/workflow/scripts/check.py engineering-plan <goal>
python .opencode/workflow/scripts/check.py next-step <goal>
```

prepare-plan 自动算 hash、从 browser/desktop 旅程推导 UI 义务、绑定 schema-3 goal，
变更定义时清除旧运行引用。原始证据不删除。路径可任意项目内文件，不是质量标准。
结构检查覆盖全部任务细节、接口 producer/consumer 依赖、外部边界先于集成。
工程合理性仍须规划者执行正常/失败路径走查；不以“JSON 完整”代替设计质量。
prepare-plan 另生成同目录 `<design-stem>.readable.md` 完整可读计划：正文、图、
所有步骤的代码块/检查都由同一索引展开。该视图不手工修改；未标记为工具生成的
既有同名文件不会被覆盖。交付给用户这个可读版本，build 仍读自动裁剪的任务包。

## 执行者只需掌握这个循环

```text
python .opencode/workflow/scripts/check.py next-step <goal>
python .opencode/workflow/scripts/check.py begin-cycle <goal>
# 按任务包 implementation/change 做当前步骤；不改共享接口，不提前做下一步。
python .opencode/workflow/scripts/check.py verify-cycle <goal>
# 检查 observed 的真实输出、返回值和错误；截断时读原始回执路径。
python .opencode/workflow/scripts/check.py observe-cycle <goal> --decision advance --interpretation "实际结果与预期一致的具体依据"
# 再调用 next-step，工具选择下一个依赖就绪任务。
```

命令从项目根运行。底层 shell 是系统 shell（Windows cmd.exe）；需要 PowerShell
时在命令中显式调用。工具运行的外部操作也必须符合既有用户授权范围。

next-step 是只读的：返回当前任务、必要全局约定、consumes/produces 对应的合同、
read_files 和检查。未来任务/不相关合同/全部历史默认不进入执行上下文。
不自动 dispatch 或切模型。begin-cycle 可显式指定步骤（返修），默认按包选择。

verify-cycle 自动捕获命令、stdout/stderr、退出码、超时、版本；observe-cycle 自动
带入当前尝试的实际输出。执行者只写有依据的解释、选决定，不再手填 actual JSON。
不要只看 passed 布尔值。机械记账由工具完成，观察和诊断仍是模型职责。

## 验证的四个层次

| 层 | 计划位置 | 运行与结论 |
|---|---|---|
| 组件 | step.checks level=component | 运行本步组件/状态检查；局部替身不能充当外部能力证据 |
| 实际边界 | step.checks level=boundary | 经交付适配器触及真实目标并读回结果；需要时配本步 preflight |
| 集成里程碑 | step.journey_ids | 在组件接通之后经交付公开入口运行完整用户路径 |
| 最终交付 | outcomes + UI/产品观察 | 最终候选版本的全部承诺，执行现有最终门禁 |

每步只运行计划分配的检查。组件可在尚无完整 app 时通过；外部旅程必须依赖先前
对应的 boundary 检查。高风险边界安排靠前，不允许“全部写完再接真实游戏”。
preflight_boundary_ids 只指定本步需要的就绪条件，避免所有步骤重复探测全部环境。

负向对照按需用于关键失败模式；可在普通测试中断言失败行为并退出 0，也可用
negative_control 明确指定失败退出码及输出。不能硬性要求每个组件/纯函数产生
一个非零进程。固定样例的负对照只排除特定假成功：它不能普遍证明实现没有伪造。
重要输入还需变体/状态变化，目标变化后确实回读，避免仅比对硬编码标记。

## 反馈分支

- `advance`：本次检查全部通过，版本未变；推进。
- `retry`：本步实现问题；按 failure_routes.implementation 修复本步后新尝试。
- `blocked`：环境/权限/外部目标缺失；记录具体证据和解除条件，不换成假环境通过。
  解除后用 `begin-cycle <goal> <step-id>` 显式重试该步（不靠自动循环反复撞阻塞）。
- `replan`：技术能力、共享接口、状态归属等设计假设不成立；停止执行，返还计划。

```text
python .opencode/workflow/scripts/check.py observe-cycle <goal> --decision replan --interpretation "实际返回异步任务句柄，计划却要求同步结果；附本次命令证据"
```

replan 后 next-step 返回受影响任务、共享接口、实际反馈和 failure_routes.design；
begin-cycle 拒绝继续旧设计。规划者更新所有受影响任务/验证/图后 prepare-plan 重新
发布。无需重做 grill，除非改变用户目标；不擅自变更验收断言让错误设计通过。
重新发布使证据失效，不要求重写已满足新计划的代码；读当前实现、复验并保留它。

同一失败签名的无进展预算仍按 delivery-execution.md；不能靠新尝试清零。
中断是未知状态，先检查残留进程/外部状态，再 retry/blocked；不能補记成功。
旧 attempts 只增不改。未观察的尝试挡住下一轮；重跑上游使依赖它的下游失效。

## 收尾与信任范围

next-step 返回 final-acceptance 后，执行 cycle-gate、最终 verify-goal、适用 UI
场景与 required 独立产品观察，再 finish-goal。这些在完整候选做，不每个组件
重跑 discover/compare。具体见 delivery-finish.md。check-current 仍检查新鲜度。

本工具不是编辑沙箱，不阻止模型在命令外提前写很多代码，也不能用文本字段证明
真实游戏被操作过。reviewer 必须核实际入口、驱动、断言语义和操作时序；原生 UI
trace/观察门禁保留。单元、边界、旅程、未验证项分别报告，不用总测试数代替结论。

内部旧 engineering-plan/1 记录仍可读取，但新计划不照旧格式生成。无需为新项目
迁移历史工程；未完成旧项目是否迁移由目标选择决定，不改完成历史。
