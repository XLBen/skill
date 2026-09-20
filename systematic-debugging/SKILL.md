---
name: systematic-debugging
description: Use when a failure needs root-cause diagnosis before repair - /fix work, repeated test failures, flaky behavior, production symptoms, or any "it doesn't work" report where the cause is not yet proven. Enforces a four-phase evidence-driven process: reproduce, isolate, hypothesize, verify the fix - no shotgun edits, no unverified attribution to environment or permissions.
license: MIT
metadata:
  language: "zh-CN"
  called-by: "mvp-delivery (fix mode), construction, task-worker"
  public-command: "none"
---

# Systematic Debugging (系统化根因排查)

修复从复现开始，不从猜测开始。本 skill 适配自
[obra/superpowers](https://github.com/obra/superpowers) 的
systematic-debugging 方法（见 `UPSTREAM.md`），服务于 `/fix` 与一切
“行为错误但原因未证实”的场景。它不替代既有失败计数与熔断规则，只规定
每次尝试之间的方法。

## When To Use

- `/fix <problem>`：复现、定位、最小修复、回归验证的主流程；
- 同一失败签名第二次出现、准备“再试一次”之前；
- 任何准备说“可能是环境/权限/网络问题”之前。

**生产影响优先分流**：正在发生的线上故障、数据损坏/泄露、安全事件或需要立即
止损的告警，先加载 `../incident-response/SKILL.md` 完成定级、控制影响与恢复，
再回到本流程做根因修复。先复现可能扩大损失。

## 四阶段

### 1. Reproduce（复现）

- 找到或构造最小可复现命令/输入；记录精确环境（cwd、版本、配置）。
- 不能稳定复现时，先收敛复现条件（数据、时序、并发、状态），不要带病继续。
- 复现本身就是第一个证据：记下确切错误文本与退出码。

### 2. Isolate（隔离）

- 用二分法缩小范围：注释/桩化/缩短输入/切换入口，直到最小差异集。
- 读真实代码与真实日志，不凭记忆推断调用链；用工具验证每一跳。
- 断言当前认知：“失败发生在 X 与 Y 之间，因为 Z 已被排除（证据：…）”。

### 3. Hypothesize（假设）

- 至少列出两个互相可区分的假设；每个假设给出一个能证伪的最小探针。
- 修复前先让探针运行：证实一个假设、排除其余，再动手改代码。
- 禁止同时改多处后“看看好了没”——一次只验证一个变量。

### 4. Verify（验证修复）

- 修复后：原始复现命令转绿 + 受影响范围回归 + 边界条件抽查
  （空输入、重复执行、失败中途恢复）。
- 回归测试固化该根因，防止复发（并入 `/fix` 既有要求）。
- 检查同一根因的同类调用点（冰山法则），处理完再收工。

## 防偏航规则

- **禁止甩锅**：说“环境/权限/依赖版本”之前，必须有探针证据。
- **禁止暴力重试**：同一签名第三次出现走既有熔断（construction 三连败 /
  mvp no-progress），本 skill 的 L1 要求是“换本质不同的方法”。
- **禁止 shotgun 修复**：改了 N 处但无法说明哪一处生效 = 未完成隔离。
- **失败中途状态**：修复可能已产生副作用，先查 postcondition 再重跑。

## 输出

诊断结论一行：`根因=<一句事实> | 证据=<探针/日志引用> | 修复=<最小变更> |
回归=<命令与结果>`。交给既有 handoff 格式，不新增工件。
