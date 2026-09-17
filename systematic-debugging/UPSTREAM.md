# UPSTREAM

本 skill 适配自 [obra/superpowers](https://github.com/obra/superpowers)
（MIT License）中的 `systematic-debugging` 技能方法论（含其引用的
root-cause-tracing、defense-in-depth 技术）。

- 保留的核心思想：四阶段根因流程（复现/隔离/假设/验证）、区分性探针、
  一次一个变量、修复后边界复查。
- 本仓库的适配：与既有失败签名/熔断规则的衔接、防甩锅条款与本仓库
  handoff 输出格式为本仓库新增；不复制上游文本。
- 上游许可：MIT（见仓库 LICENSE）。本目录不包含上游代码副本。
