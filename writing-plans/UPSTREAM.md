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

2026-09-22 对照上游当前 writing-plans/TDD 与 github/spec-kit 的 plan/tasks 方法：
恢复设计先于任务、显式组件接口、关键代码块、依赖顺序和逐步实测反馈；参考
Spec Kit 对研究/数据模型/契约/验证指南的职责分离。此处为本地原创适配，未
安装整套上游编排器，也不声明与某上游版本的行为等价。不能把单元 TDD 当作
真实外部集成验证；运行后端优先复用 Playwright（Web）/Airtest（游戏适用时），
后端能力必须实测，不能凭 skill 名称或安装成功宣称可用。

本轮重构进一步明确：所有步骤完整设计、单一共享接口定义、按当前任务裁剪上下文、
组件/真实边界/集成里程碑分层验证、设计冲突回交规划者。结构验证只负责引用和顺序；
计划质量以设计走查与实际执行评估为准，不能由测试数量推出弱模型产出稳定。
