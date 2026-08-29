# 05 Tilemap 瓦片地图（Unity 6.5）

## Contents
- 组件结构 · 布局类型 · Tile 类型 · 脚本操作 · 碰撞与运行时修改 · 性能 · 坑

## 组件结构

```
Grid（定义 Cell Size 与布局）
├── Tilemap（地面）+ TilemapRenderer
├── Tilemap（装饰）+ TilemapRenderer（Sorting Order 递增）
└── Tilemap（碰撞）+ TilemapRenderer + TilemapCollider2D
    + Rigidbody2D(Static, 勾 Used By Composite) + CompositeCollider2D（必须）
```

创建：Hierarchy 右键 > 2D Object > Tilemap。一键搭建脚本见 `assets/editor-tools/SetupTilemapScene.cs`。刷图：Window > 2D > Tile Palette。

## 布局类型

`Rectangle`（矩形）/ `Hexagonal`（六角）/ `Isometric`（等距）/ `Isometric Z as Y`。坐标换算统一走 Grid：

```csharp
Vector3Int cell = grid.WorldToCell(worldPos);
Vector3 world = grid.CellToWorld(cell);
```

## Tile 类型

| 类型 | 说明 |
|---|---|
| `Tile` | 基础瓦片（精灵+颜色+碰撞 Sprite/Grid/None） |
| AnimatedTile | 帧动画瓦片（流水/岩浆） |
| Rule Tile（com.unity.2d.tilemap.extras） | 按相邻瓦片自动选图（自动边框/转角） |
| Random / Weighted Random Tile | 随机变体 |
| Terrain Tile | 地形混合 |
| GameObject / Prefab Brush | 刷 GameObject/预制体 |
| 自定义 Tile | 继承 `TileBase` 重写 `GetTileData`/`StartUp` |

## 脚本操作

```csharp
tilemap.SetTile(cellPos, tile);
tilemap.GetTile(cellPos);
tilemap.SetTile(cellPos, null);        // 删除
tilemap.SetTiles(positions, tiles);    // 批量(比逐格 SetTile 快)
tilemap.BoxFill(start, end, tile);
tilemap.FloodFill(cellPos, tile);
tilemap.ClearAllTiles();
tilemap.CompressBounds();              // 程序化生成后必调
tilemap.GetCellCenterWorld(cellPos);   // 瓦片中心(矩形偏移 0.5,0.5)
```

程序化关卡：字符串地图数组循环 `SetTile`（`references/17-procedural-gen.md`）。

## 碰撞与运行时修改

- 改瓦片后物理网格自动刷新；大量改动后调 `tilemap.RefreshAllTiles()` / `CompositeCollider2D.GenerateGeometry()`
- 破坏性地形：删 Tile + 刷新碰撞；频繁变动场景改用射线打 tilemap 自写碰撞查询
- 来源：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Tilemaps.Tilemap.html

## 性能

- Tilemap 天然合批：同图集同材质整层一次 Draw Call；层间设 Sorting Order
- 大关卡 `CompressBounds()` 清空边界；超大世界 Chunk 分块（见 `references/genres/2d-survival-craft.md`）
- 碰撞网格合并（CompositeCollider2D）远快于每瓦片独立碰撞

## 坑（现象 → 原因 → 解法）

1. 刷的瓦片不显示 → Palette 里瓦片没赋 Sprite → 图片切 Sprite 后拖进 Palette 并赋图
2. 改 Cell Size 后关卡错位 → 网格尺寸变化 → 先定 Cell Size 再刷图
3. 运行时改 Tile 影响全部同引用位置 → Tile 实例共享 → 需要变体时复制 Tile 实例
4. 程序生成后 cellBounds 虚大 → 没 CompressBounds → 生成完必调
5. Rule Tile 不匹配处透明 → 规则不完整 → 补默认 Sprite 或规则表

## 相关文件

- 程序化生成：`references/17-procedural-gen.md` · 搭建脚本：`assets/editor-tools/SetupTilemapScene.cs` · 关卡设计：`references/18-level-design.md`

## 文档速查

- Tilemap 首页：https://docs.unity3d.com/6000.5/Documentation/Manual/tilemaps/tilemaps-landing.html
- Tilemap Extras 包：https://docs.unity3d.com/Packages/com.unity.2d.tilemap.extras@latest
- 六角 Tilemap：https://docs.unity3d.com/6000.5/Documentation/Manual/tilemaps/work-with-tilemaps/hexagonal-tilemaps/hexagonal-tilemap-landing.html
