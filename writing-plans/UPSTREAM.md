# UPSTREAM

本 skill 适配自 [obra/superpowers](https://github.com/obra/superpowers)
（MIT License）中的 `writing-plans` 技能方法论。

- 保留的核心思想：计划是写给“没有判断力、没有项目上下文的执行者”的
  prompt；每个任务带精确文件路径、完整实现说明和验证步骤；任务粒度
  以可独立验证为准。
- 本仓库的适配：字段格式（Context/Files/Change/Bounds/Verify/Rollback）、
  边界条件清单、与 Audited PLAN/目标卡/派发模板的嵌入关系、与最薄切片
  原则的对齐为本仓库新增；不复制上游文本。
- 上游许可：MIT（见仓库 LICENSE）。本目录不包含上游代码副本。
