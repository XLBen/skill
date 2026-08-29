# 2D 生存建造（Survival / Crafting，泰拉瑞亚类）

## Contents
- 核心系统拆解
- 体素世界与区块
- 挖掘/放置/光照
- 合成与背包
- 存档与多人（可选）
- 坑与速查

## 核心系统拆解

可破坏体素世界 → 挖掘/放置 → 资源采集 → 合成/建造 → 昼夜/事件 → 探索推进（Boss 门控）

## Unity 实现要点

- **世界数据与渲染分离**：世界 = 字典 `Vector2Int → TileType`（区块分块存），渲染 = 按区块生成的网格/Tilemap；数据是真理，渲染是视图
- **区块 Chunk**：世界按 32×32 分块，进视野生成/出视野卸载（`References/17-procedural-gen.md` 生成地形）
- 大世界用**自建网格**（Mesh + 图集材质，一次 Draw Call 一片区块）比 Tilemap 灵活（每格可存墙/物/光照值）

## 体素数据结构

```csharp
public class Chunk
{
    public const int Size = 32;
    public Vector2Int coord;
    public TileType[] tiles = new TileType[Size * Size];   // 基础块
    public byte[] walls = new byte[Size * Size];           // 背景墙层
    public byte[] light = new byte[Size * Size];           // 光照缓存
}

// 全局访问: 坐标 → 区块 → 格内索引
public class World
{
    public Dictionary<Vector2Int, Chunk> chunks = new();

    public TileType GetTile(Vector2Int pos)
    {
        Vector2Int chunkCoord = new(Mathf.FloorToInt(pos.x / (float)Chunk.Size),
                                    Mathf.FloorToInt(pos.y / (float)Chunk.Size));
        if (!chunks.TryGetValue(chunkCoord, out var c)) return TileType.Air;
        Vector2Int local = PosMod(pos, Chunk.Size);
        return c.tiles[local.y * Chunk.Size + local.x];
    }
}
```

## 挖掘与放置

```csharp
// 射线/格点拾取: 鼠标世界坐标 → 目标格
Vector2Int cell = new(Mathf.FloorToInt(worldPos.x), Mathf.FloorToInt(worldPos.y));

public void Dig(Vector2Int pos, int power)
{
    var tile = world.GetTile(pos);
    if (tile == TileType.Air) return;
    int hardness = TileRegistry.Hardness(tile);
    if (power >= hardness) { world.SetTile(pos, TileType.Air); RefreshChunk(pos); }
    // 挖掘进度条: power < hardness 时累积进度(泰拉瑞亚式)
}
```

- **TileRegistry**：方块数据表（硬度/掉落/是否发光）ScriptableObject 或静态表
- 修改后重建该区块网格 + 更新相邻格光照

## 光照（生存游戏氛围核心）

- **全局光照近似**：URP 2D 光数量有限，大世界用**格光照缓存**（亮源 flood-fill 到格，渲染时按格亮度调顶点色/精灵色）
- 天空光随时间变化：Time 驱动 ambient 色（见 `references/07-render-2d.md` 的 DayNightCycle 示例）
- 光照重算增量：只在挖放改变处重算

## 合成与背包

```csharp
[CreateAssetMenu(menuName = "Game/RecipeData")]
public class RecipeData : ScriptableObject
{
    public string recipeName;
    public ItemStack[] inputs;      // 材料
    public ItemStack output;
    public string requiredStation;  // 需要的工作台
}

// 合成检查: 背包材料扣减 + 产出
public bool TryCraft(RecipeData recipe, Inventory inv)
{
    if (!inv.Has(recipe.inputs)) return false;
    inv.Remove(recipe.inputs);
    inv.Add(recipe.output);
    return true;
}
```

- 背包：`List<ItemStack>`，格子 UI 复用对象池（见 `references/08-ui.md`）
- 掉落物：挖掘掉实体掉落物（磁吸拾取，对象池）

## 存档

世界分块存档：只存**已修改区块**（地形生成用种子重建），存档 = 种子 + 脏区块 diff + 玩家数据。见 `references/13-architecture.md` 与 `assets/templates/SaveService.cs`（校验和防篡改）。

## 多人（可选，超出本库主范围）

多人用 Netcode for GameObjects（com.unity.netcode.gameobjects）：区块数据服务器权威、客户端按视野同步。本库不展开，参考包文档。

## 坑（现象 → 原因 → 解法）

1. 大世界卡死 → 整张地图放场景里 → 区块分块生成/卸载 + 网格合批
2. 挖放后光不更新 → 光照重算只做了一次 → 增量重算（影响域 flood-fill）
3. 存档爆炸 → 全地图存文件 → 只存脏区块 diff + 种子
4. 每格一个 GameObject → 渲染/物理崩溃 → 数据表 + 自建网格，物理用自写碰撞（体素 AABB 查询）
5. 挖掘射线穿透背景墙 → 没分层判定 → 墙壁/前景层分别射线查询

## API 速查

| 类 | 用途 |
|---|---|
| `Mesh` / `MeshFilter` | 区块网格渲染 |
| `Mathf.FloorToInt` | 世界坐标 → 格坐标 |
| `Texture2D.SetPixels` | 程序图集/光照贴图 |
| ScriptableObject | 方块表/配方表 |
| `System.Random(seed)` | 世界生成种子 |

## 相关文件

- 程序化生成：`references/17-procedural-gen.md`
- 背包/UI：`references/08-ui.md`
- 存档：`references/13-architecture.md`、`assets/templates/SaveService.cs`
- 光照：`references/07-render-2d.md`

## 文档速查

- Netcode 包：https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@latest
- Mesh API：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Mesh.html
