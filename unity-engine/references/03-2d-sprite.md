# 03 2D 精灵与渲染排序（Unity 6.5）

## Contents
- Sprite 导入 · SpriteRenderer · 排序规则 · 像素风 · 图集 · 像素美术管线约定 · 性能 · 坑

## Sprite 导入设置（TextureImporter）

- **Texture Type: Sprite (2D and UI)**；**Sprite Mode**：Single / Multiple（图集切分）/ Polygon（多边形，配 PolygonCollider2D）
- **Pixels Per Unit (PPU)**：世界单位换算基准，默认 100；图集内所有精灵 PPU 必须一致（不同 PPU 混用 → 缩放错乱）
- **Filter Mode**：像素风 Point，其余 Bilinear/Trilinear；**Compression**：像素风 None 防模糊
- **Generate Mip Maps**：2D 精灵一般不勾；**Max Size**：图集 2048/4096 按需

批量设置用 `assets/editor-tools/BatchSetSpriteImport.cs`（菜单 Tools/UnitySkill/批量设置精灵导入）。

## SpriteRenderer

```csharp
spriteRenderer.sprite = newSprite;
spriteRenderer.color = Color.white;      // 颜色调制(受伤闪白/闪红)
spriteRenderer.flipX = true;             // 朝向翻转
spriteRenderer.sortingOrder = 10;        // 排序层内顺序
spriteRenderer.sortingLayerName = "Foreground";
spriteRenderer.drawMode;                 // Simple/Sliced(9宫格)/Tiled
```

- `drawMode = Sliced`：九宫格拉伸（UI 面板/血条边框不变形，需 Sprite Editor 设 Border）
- `drawMode = Tiled`：平铺填充背景
- 来源：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/SpriteRenderer.html

## 排序规则（2D 核心）

渲染顺序 = **Sorting Layer** → **Order in Layer** → **相机距离**（仅 Transparent）。Y-Sort 遮挡：`sortingOrder = -(int)(transform.position.y * 100)`；缓存 `SortingLayer.NameToID` 避免每帧字符串查找。

## 像素风要点

- Filter Point + Compression None + PixelPerfectCamera（包 com.unity.2d.pixel-perfect）
- 手动方案：正交 Size = 屏幕高 / (2 × PPU)；移动像素对齐（取整到 1/PPU 网格）
- URP 下用 2D Renderer 保证光照正确（见 `references/07-render-2d.md`）

## 图集 Sprite Atlas

- 创建：Assets > Create > 2D > Sprite Atlas；Objects for Packing 填文件夹或标签绑定
- UI 精灵关 `Allow Rotation`（旋转破坏 UI 布局）；不需要脚本读纹理就别开 Read/Write（内存翻倍）
- 运行时 `atlas.GetSprite("icon_coin")`；Addressables 场景用 `SpriteAtlasManager.atlasRequested` 延迟绑定

## 像素美术管线约定（多人协作必读）

1. **统一 PPU**：全项目一个值（如 32），写进项目文档；新图入库跑批量设置脚本
2. **图集规划**：按"功能域"打图集（UI/角色/环境），同图集同材质才合批
3. **命名规范**：`type_name_variant`（如 `icon_coin_gold`），图集内名字唯一
4. **锚点约定**：角色 pivot 在脚底、UI 在中心，写进命名后缀或文档
5. **Tight Packing + Padding 4**：默认组合，边缘漏色调大 padding 或 Alpha Dilation

## 性能相关

- 同图集 + 同材质 + 连续排序 = 合批；每帧换 sprite 打破合批（见 `references/12-performance-2d.md`）
- 透明重叠 Overdraw 是 2D 头号杀手，移动端大尺寸半透明精灵谨慎

## 坑（现象 → 原因 → 解法）

1. 相同尺寸精灵实际大小不一 → 各图 PPU 不同 → 统一 PPU 后重新导入
2. 图集里精灵显示错位 → 名字冲突 → 图集内精灵名全局唯一
3. 像素风变模糊 → Filter 设了 Bilinear → Point + Compression None
4. 排序时对时错 → 同层魔法数混乱 → 定义 Sorting Layer（Background/Actors/Foreground/UI）+ 层内微调

## 相关文件

- 渲染光照：`references/07-render-2d.md` · 性能：`references/12-performance-2d.md` · 批量导入脚本：`assets/editor-tools/BatchSetSpriteImport.cs`

## 文档速查

- Sprite 落地页：https://docs.unity3d.com/6000.5/Documentation/Manual/sprite/sprite-landing.html
- 排序：https://docs.unity3d.com/6000.5/Documentation/Manual/sprite/sort-sprites/sort-sprites-landing.html
- Sprite Atlas：https://docs.unity3d.com/6000.5/Documentation/Manual/class-SpriteAtlas.html
