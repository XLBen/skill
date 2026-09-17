# UPSTREAM

本 skill 的方法论受 [anthropics/skills](https://github.com/anthropics/skills)
仓库（其中技能多为 Apache-2.0）中 `webapp-testing` 技能的启发：用
Playwright 等专用浏览器自动化对 Web 应用做真实操作与断言。

- 保留的核心思想：Web UI 测试优先用确定性脚本；分层（脚本 > 一次性
  会话 > 桌面控制）；场景自建自清；证据可独立核查。
- 本仓库的适配：与 `ui-acceptance/1` sidecar、`check.py ui-gate`、
  computer-use 的分工与互斥规则为本仓库新增；未复制上游文本或代码。
- 上游许可：Apache-2.0（详见上游仓库声明）。本目录不包含上游代码副本，
  本文件满足来源标注。
