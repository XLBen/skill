## 1. `brief-final`

**位置**：`grill/SKILL.md` 的 Brief final；`/grill` 命令结束处。

**输入**：当前 brief、JSON item、frontier、用户确认内容。

**质询与动作**：

- “这份 summary 是用户说的，还是你替用户补的？”逐项对照事实、决定、假设、成功信号和非目标。
- 未回答的问题必须仍是 open/deferred，不能为了 final 填 owner decision。
- 向用户展示 `this is what I heard`，取得明确确认后才执行 brief validator、hash 和冻结。
- 核对本轮没有因为追求闭环而偷偷缩小目标或把可选愿望改成必需 BS。
- 由 reviewer 席位执行本卡时，只核对已记录的 owner 确认与 brief 证据；与用户的
  确认交互本身仍由执行席位/主控完成，reviewer 不代答也不因未参与交互而阻塞。

**证据**：brief 校验输出、最终 hash、用户确认记录、frontier 清空状态。

**出口**：未确认是 `待 owner 决定`；结构/语义缺口是 `需修复`；不能交给 contract-review。

