# UPSTREAM

本 skill 适配自 [obra/superpowers](https://github.com/obra/superpowers)
（MIT License）中的 `systematic-debugging` 技能方法论（含其引用的
root-cause-tracing、defense-in-depth 技术）。

- 保留的核心思想：先读错误与最近变更，比较正常/失败路径、跨边界定位和
  沿调用链追根因，再作单变量的区分性实验，修复后验证原复现与回归。
- 本仓库的适配：四阶段压缩表达、间歇性发现保留、与既有失败签名/熔断
  规则及 handoff 衔接为本地规则。上游强调单个具体假设，不要求第一轮
  强制列两个；本地也只在确有竞争解释或 PUA L1 时列可区分候选。
  不复制上游文本，也不将上游的自动 TDD/提交要求挪作每次小修的门禁。
- 上游许可：MIT（见仓库 LICENSE）。本目录不包含上游代码副本。
