## 5. `test-freeze`

**位置**：`test-author/SKILL.md` Invariants/Procedure；`construction/SKILL.md` 的 test-author dispatch。

**输入**：冻结规格、场景、test manifest、pre-change 输出、保护路径和 hash。

**质询与动作**：

- “永远绿的测试也是交付？”确认新行为有真实 behavior-red，回归基线绿有明确分类。
- 检查断言内容/状态/schema/不变量，而不是只看 exit 0、进程存在、日志非空或文件存在。
- 核对每个关键场景真实执行，没有 skip、todo、过滤、空套件、假 fixture 或弱化 wrapper。
- 测试语义或边界变化必须走 CR、独立 test-author 重验、reviewer 和 manifest hash 刷新。

**证据**：逐场景 pre-change 结果、命令/输出 hash、冻结文件 hash、boundary/mock policy。

**出口**：意外绿、基线红、setup blocker 或保护路径变更均不能进入实现，返回具体 blocker。

