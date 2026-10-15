# UPSTREAM

本 skill 的方法论受 [anthropics/skills](https://github.com/anthropics/skills)
仓库（其中技能多为 Apache-2.0）中 `webapp-testing` 技能的启发：用
Playwright 等专用浏览器自动化对 Web 应用做真实操作与断言。

- 保留的核心思想：用已安装的 Playwright 脚本执行真实 Web 操作；动态页面
  先观察渲染结果再选定位器，按需要复用服务生命周期工具，而非猜页面状态。
- 本仓库的适配：脚本/一次性会话/桌面边界的优先级、computer-use 的分工与互斥、可观察就绪状态等待
  均为本地策略。上游当前 main 举例使用 Python Playwright 和
  `with_server.py`，但本项目**没有**捆绑该脚本；也不机械照搬其中
  `networkidle` 等待作为所有页面的就绪信号。未复制上游文本或代码。
- 上游许可：Apache-2.0（详见上游仓库声明）。本目录不包含上游代码副本，
  本文件满足来源标注。

另外参考了 [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)（Apache-2.0）：
把它作为一次性浏览器检查的首选工具，使用方式（安装、`skills get core`、独立会话、snapshot → @ref → 重新 snapshot 的循环、
dogfood 试用流程）用自己的话概括，没有复制原文；最新用法以已安装版本的 `agent-browser skills get core` 输出为准。
