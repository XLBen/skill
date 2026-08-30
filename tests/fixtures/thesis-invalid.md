---
project: demo-invalid
version: 1
status: broken
phase: questioning
date: 2026-08-30
---

# demo-invalid 立项论文 v1

## §1 问题与目标

- P-01 自动生成日报

## §2 方案总览

抓取 Git 提交记录生成日报。

## §3 关键决策与被否替代方案

- D-01 用 cron 而非常驻进程

## §4 假设清单

- A-01 提交信息足以还原工作内容

## §5 风险与失败模式

- R-01 私有仓库 token 失效

## §6 验证计划

- V-01 生成结果人工抽查一遍就行

## §7 边界与非目标

- B-01 不做周报
