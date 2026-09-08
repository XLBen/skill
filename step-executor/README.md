# step-executor

隔离执行器，从 construction 分离出来的子 skill。由 construction 调度 fresh
subagent 后加载，一次只执行一个编译后的步骤。

调用方传入：步骤 ID、unit/variant/segment、动作、接口、声明的副作用、幂等
与回滚说明、绑定该步的精确 V 命令、当前 contract/PLAN/step hash；v0.1
还传入 test-author manifest 和冻结测试 hash。

执行者只写产品实现，不得编辑冻结测试；按 minimal-diff 实现、原样跑 V、
回报原始输出。第三次同签名失败后停止普通重试并上报。状态、账本、事件
记录归控制器所有；发现契约事实问题即停并上报（那是 CR 决策）。
