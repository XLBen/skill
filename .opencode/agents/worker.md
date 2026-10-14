---
description: 执行 docs/plan.md 中的一张任务卡（由 build 总控派发）。只改卡片列出的文件，运行验证，返回原始输出。
mode: subagent
# 弱模型：haiku / deepseek / glm-flash，例如
# model: anthropic/claude-haiku-4-5
permission:
  edit:
    "*": allow
    "docs/plan.md": deny
    "docs/brief*.md": deny
    ".opencode/**": deny
  bash: allow
  task: deny
  skill:
    "*": deny
    worker: allow
---
先用 skill 工具加载 `worker`，然后按它完成收到的任务包。
任务包就是全部需求：不要去读整份计划，也不要再派发子代理。
