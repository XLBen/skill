---
name: webapp-testing
description: Use for web-only UI acceptance journeys in /build, /fix and /resume - loading a delivered page, operating it as a user, and asserting observable results through dedicated browser automation (Playwright or an equivalent installed driver). Deterministic scripts preferred over agentic screenshot loops; native desktop apps, OS dialogs and file pickers stay with computer-use. Adapts the webapp-testing methodology from anthropics/skills for this workflow's evidence and gate rules.
license: MIT
metadata:
  language: "zh-CN"
  called-by: "mvp-delivery, construction"
  public-command: "none"
---

# Webapp Testing (Web UI 验收)

Web 旅程的验收优先用专用浏览器自动化，不用桌面截图循环。本 skill 受
[anthropics/skills](https://github.com/anthropics/skills) 中 webapp-testing
技能的方法论启发，在本仓库中作为 computer-use 的 Web 侧对应能力（见
`UPSTREAM.md`）：产出同一 `ui-acceptance/1` sidecar 证据，走同一
`check.py ui-gate`。

## When To Use

- 受影响 outcomes 包含 Web 页面旅程（表单、导航、结果渲染）时，
  `/build`/`/fix`/`/resume` 的 UI 验收优先使用本 skill；
- 原生桌面应用、OS 对话框、文件选择器仍然走 `../computer-use/SKILL.md`；
- 纯 API/CLI 改动不适用（无界面声明时无需 sidecar）。

## 方法层级（优先级从高到低）

先确认交付的 URL、后端和当前 build：已有服务先核身份，不把未知端口的
旧进程当本轮目标；需启动服务时由本轮持有进程、限定就绪期限并保证清理。
静态页面可读已有 HTML 定位入口；动态页面先打开、等待可观察的就绪
信号，再从**实际渲染的** DOM/可访问名称发现定位器，不猜元素 ID。
不要把 `networkidle` 当成所有应用的固定就绪条件（持续轮询页面可能永不空闲）；
等具体目标状态并用断言确认。工具脚本先看 `--help`，缺脚本时不臆造命令。

1. **断言式脚本**：用仓库中已安装的 Playwright（或等价 driver）写
   deterministic 场景脚本——打开入口、执行动作、断言可见内容与状态。
   脚本可重复运行、可入回归，是最高等级的自动化证据。
2. **一次性的浏览器会话验证**：没有可留存的脚本价值时（一次性 smoke），
   通过浏览器自动化工具交互式执行同一旅程，记录观察与结果文件。
3. **桌面控制**：只有浏览器自动化实际覆盖不了的边界（原生对话框、
   系统级交互）才交给 computer-use。

禁止用 API 调用结果冒充“页面可用”的证据；API 与 UI 是不同验收面。

## 场景执行规则

- 复用 `ui-acceptance/1` sidecar 的既有场景结构（precondition/input/
  actions/expected）与状态机（pending/passed/failed/blocked/
  not-applicable）；本 skill 不新增 schema。
- 每个场景一次有界执行：明确的步骤序列、每步断言、总时限。断言失败
  即 `failed`，交回控制器修复循环——不在浏览器里原地反复尝试。
- 值得重复执行的场景脚本放 `tests/`（或仓库既有测试目录）；一次性 smoke
  可只留浏览器运行回执，不为它生成无用测试文件。证据文件
  （runner 日志、观察记录、结果 JSON）按 sidecar 的 refs 规则引用，
  路径相对项目根。
- 隔离与清理：使用独立测试账号/测试数据；场景自建自清（产生的数据、
  本轮启动的进程）；任何结果未知的提交先回读页面/后端状态再重试，
  登录凭据不写入日志。
- 与交互式桌面会话互斥：浏览器 runner 与 computer-use 会话串行，不同时
  操作同一应用。产品观察阶段（product-observer 持排他 UI lease）同样
  串行：观察窗口内暂停本 skill 的场景执行，观察结束后恢复；本 skill 的
  场景证据不得标注为观察证据。

## 证据与 Gate

- `passed` 场景需要：runner 证据文件 + 观察/结果 refs + 目标 build/URL
  身份；`ui_tools` policy 存在时，native call 引用需匹配其 glob。
- 走既有 `check.py ui-gate`（含 `--bind` 产物绑定与失效重跑规则）；
  本 skill 不修改任何 gate 语义。
- 截图仅在布局/视觉断言需要时保留，并遵守 computer-use 的隐私红线
  （敏感页面、凭据输入时不截屏）。

## 前置缺失

仓库无浏览器自动化能力（未安装 driver/无 MCP）时，Web 旅程按既有规则
置 `blocked` 并点名缺失前提；不降级为截图循环冒充通过，也不擅自安装
全局依赖。
