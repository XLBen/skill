# ADHD-Friendly Workflow Output

这是 [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd) 的本地适配版。
它只负责用户沟通格式，不做医学判断，不裁剪验收事实，也不新增公开命令。

## Integration

工作流在阶段交接时建立完整 `ACCEPTANCE_HANDOFF`：

```text
完整交接包
  -> ADHD acceptance-preview
  -> 现有 reviewer 加载 PUA 检查
  -> 主控制器修复/复验/等待决定
  -> ADHD delivery 或 blocker
```

ADHD 输出是用户视图；reviewer 和 PUA 使用完整交接包。不要用一条短消息替代目标、
范围、产物和证据。

## Scope

- 默认随 `/grill`、`/plan`、`/build`、`/work`、`/fix`、`/resume` 的工作流内部加载。
- 不提供 `/i-have-adhd` 公开命令，不安装 hook，不写全局状态。
- 用户要求详细说明时，完整性优先；用户要求关闭简洁模式时，只关闭展示约束。
- engine gate、owner 决定、reviewer 独立性和 PUA 检查不因简洁输出而改变。

上游版本、适配内容和许可证见 [`UPSTREAM.md`](UPSTREAM.md)。
