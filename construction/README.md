# construction

这个内部 skill 从确认后的 Audited PLAN 开始，不负责问需求，也不负责重新规划。
首个切片或 SI 必须先由 fresh subagent 加载 test-author 生成并冻结验收测试。

- 公开 `/build` 和 `/resume` 由 mvp-delivery 路由到这里。
- 无命令的缺陷请求在现实和契约不一致时触发内部 Fix Mode 与 CR；计划内增量仍使用 SI。
- finish/reconcile 和可选 retro 都是内部操作，不再是用户命令。

显式 `/build` 遇到 PLAN 缺失或过期时提示 `/plan`；无命令 work 方法可内部规划，不会临时编造。
执行、测试隔离、失败签名和恢复细节见 `references/step-protocol.md`。
