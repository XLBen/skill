# 评估场景（Evals）

验收本 skill 是否解决真实问题的 3 个场景。自测方式：在加载本 skill 的 opencode 会话中分别执行以下任务，对照"期望行为"逐条检查，未达标项回改对应文件。

## 场景 1：平台跳跃控制器（触发生命周期+物理+手感）

**任务**："写一个 2D 平台跳跃玩家控制器，要有土狼时间和跳跃缓冲"

**期望行为**：
- [ ] 触发了 skill（回复出现"检测到 Unity …"与读取文件声明）
- [ ] 读取了 `references/genres/2d-platformer.md`（而非重讲 01 全部内容）
- [ ] 代码用 `Rigidbody2D` + `linearVelocity`（不是旧 `velocity`）
- [ ] 含 Coyote time 与 Jump buffer 参数且数值有注释依据（0.08~0.15s / 0.1~0.2s）
- [ ] 物理移动在 FixedUpdate、输入在 Update
- [ ] 给出了验证方式（挂载 Play 测试）

## 场景 2：Tilemap 关卡 + 批量资源（触发 Editor 桥接）

**任务**："帮我搭一个带碰撞的 Tilemap 关卡，并把 Art 文件夹里 50 张图批量设成 PPU=32 的精灵"

**期望行为**：
- [ ] 读取了 `references/05-tilemap.md`
- [ ] 碰撞方案含 `TilemapCollider2D` + `CompositeCollider2D`（不是逐瓦片碰撞）
- [ ] 批量操作先列修改清单请用户确认，或直接引用 `assets/editor-tools/BatchSetSpriteImport.cs`
- [ ] 未建议手改 `.meta`/GUID

## 场景 3：卡牌抽牌系统（触发 genre 文件）

**任务**："做一套卡牌游戏的抽牌/弃牌系统，抽牌堆空了要把弃牌堆洗回去"

**期望行为**：
- [ ] 读取了 `references/genres/2d-card.md`
- [ ] 牌堆数据与卡牌数据分离（CardData ScriptableObject + 运行时实例，不污染资源）
- [ ] 洗牌用 Fisher-Yates，空堆判空防死循环
- [ ] 提供了验证方式
