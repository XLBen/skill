# step-executor

隔离执行器，从 construction 分离出来的子 skill。由 construction 通过 skill
工具调用，一次只执行一个编译后的步骤。

调用方传入：步骤 ID、unit/variant/segment、动作、接口、声明的副作用、幂等
与回滚说明、绑定该步的精确 V 命令、当前 contract/PLAN/step hash。

执行者只做三件事：按 minimal-diff 实现、原样跑 V、回报原始输出。状态、
账本、事件记录归控制器所有；发现契约事实问题即停并上报（那是 CR 决策）。
