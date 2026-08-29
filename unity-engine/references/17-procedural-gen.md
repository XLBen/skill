# 17 程序化生成（Unity 6.5 / 2D）

## Contents
- 噪声（Perlin/Simplex）与用途
- 地牢生成三法（BSP/房间走廊/元胞自动机）
- 种子与可复现
- 与 Tilemap 结合
- 校验与重试

## 噪声

`Mathf.PerlinNoise(x, y)` 返回 0~1 平滑噪声，2D 用途：

```csharp
// 地形高度: 采样一维噪声
float height = Mathf.PerlinNoise(x * frequency, seed) * amplitude;

// 地图填充: 二维采样 + 阈值(草地/水/森林)
float n = Mathf.PerlinNoise(x * scale + seed, y * scale + seed);
int tileType = n < 0.3f ? WATER : n < 0.6f ? GRASS : FOREST;
```

- 分形叠加（octaves）：多层不同频率/振幅噪声相加，地形更自然
- **Perlin 的坑**：输入整数点返回整数点相同的值（网格感），采样坐标加小数偏移；Perlin 有方向性偏斜，地形类可换 Simplex（FastNoiseLite 等库或自实现）

## 地牢生成三法

### 1. BSP 二叉树分割（房间多且规整）

```csharp
void Split(Node n, int depth)
{
    if (depth == 0) { CreateRoom(n.bounds); return; }
    // 随机方向切两半,递归
    Split(n.left, depth - 1);
    Split(n.right, depth - 1);
}
// 之后: 兄弟节点间连走廊(取各自房间中心折线连接)
```

### 2. 随机房间 + 走廊（Rogue 常用）

1. 随机撒 N 个不重叠房间矩形
2. 房间两两按最近距离连边 → 最小生成树（保连通）
3. 加 10-20% 额外边形成回环（探索趣味）
4. 走廊用 L 形折线

### 3. 元胞自动机（洞穴）

```csharp
// 初始 45% 墙随机,迭代 4 次: 邻居墙>=5 则生墙,<5 则空地
for (int iter = 0; iter < 4; iter++)
    for (int x = 1; x < w - 1; x++)
        for (int y = 1; y < h - 1; y++)
        {
            int walls = CountWallNeighbors(x, y);
            next[x, y] = walls >= 5 ? WALL : EMPTY;
        }
```

迭代次数越多洞穴越圆滑。生成后 flood-fill 取最大连通区（丢弃孤岛）。

## 种子与可复现

```csharp
var rng = new System.Random(seed);        // 全流程用同一个 rng 实例
```

肉鸽存档只存种子，重开同种子同地图（回放/分享）。`UnityEngine.Random.InitState(seed)` 供 Unity API 随机时用。**别混用**两个随机源导致不可复现。

## 与 Tilemap 结合

生成结果（int[,] 地图）→ `tilemap.SetTiles` 批量写入（比逐格 SetTile 快），完成后 `CompressBounds()`（见 `references/05-tilemap.md`）。装饰（草/石）用加权随机 + 噪声密度。碰撞层单独一张 Tilemap 或复用带碰撞的 Tile。

## 校验与重试

- 生成后必须**可达性校验**：从起点 flood-fill/BFS，终点/所有房间可达才通过；失败换种子重试（上限 10 次）
- 参数约束：走廊不穿房间、出生点与出口距离 > 阈值
- 编辑器预览：生成逻辑写成纯 C# + `[ContextMenu]` 或 Editor 窗口即时预览，调参效率翻倍

## 坑（现象 → 原因 → 解法）

1. 每次进入关卡地图不同 → 存档没存种子/生成随机源不一致 → 生成参数全部入存档
2. 玩家卡死墙里 → 出生点随机在墙上 → 校验出生点可达空地
3. 生成的 Tilemap 碰撞不可见/失效 → 批量写入后没刷碰撞 → `CompressBounds()` + 碰撞 Tilemap 刷新
4. Perlin 网格状 → 整数采样 → 坐标加小数偏移/非整数缩放

## 相关文件

- Tilemap：`references/05-tilemap.md`
- RNG：`references/00-techniques.md`
- Rogue 房间：`references/genres/2d-topdown-shooter.md`

## 文档速查

- Mathf.PerlinNoise：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Mathf.PerlinNoise.html
- Tilemap.SetTiles：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Tilemaps.Tilemap.SetTiles.html
