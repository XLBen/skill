# 12 2D 性能优化（Unity 6.5）

## Contents
- 四大瓶颈 · 合批 · Overdraw · GC · 物理优化 · Profiler · 帧预算表 · 移动端专项 · 内存 · 坑

## 2D 性能四大瓶颈

1. **Draw Call/合批** 2. **Overdraw**（透明像素重复填充） 3. **GC 分配** 4. **物理开销**

## 合批 Batching

- **同图集 + 同材质 + 连续排序层** → 自动合批；Tilemap 天然合批；UI 用 UI Atlas
- 避免：每帧换 sprite、同层混用多图集、动态改 material
- 检查：Game 视图 Stats 面板（Batches、SetPass calls、Saved by batching）

## Overdraw 控制

- 大尺寸半透明精灵（全屏烟雾/光晕）最耗填充率
- 缩小透明区域：Tight Packing、裁剪空白；像素游戏用不透明渲染路径
- 粒子减少大尺寸低透明度粒子

## GC 与热路径

- 高频生成销毁用对象池（`assets/templates/ObjectPool.cs`）
- 避免每帧字符串拼接（Text 用 StringBuilder/TMP 缓存）；避免热路径 LINQ
- 射线/区域查询：Unity 6 已移除 NonAlloc 系列，All 系列内部池化无 GC 分配；高频索敌降频即可（`references/04-2d-physics.md`）
- 缓存 `Camera.main`/`SortingLayer.NameToID` 等隐式查找

## 物理优化

- 静态环境全部 Static + CompositeCollider2D 合并
- 减少 Dynamic 刚体（敌人死亡后禁用 simulated）；合理设置碰撞层矩阵（Layer Collision Matrix）
- 静止物体自动休眠，不要每帧改 Static 物体 transform
- 弹幕类用数学检测替代 Collider（见 `references/genres/2d-survivor-like.md`）

## Profiler 使用

- Window > Analysis > Profiler：CPU Usage（脚本/渲染/物理）、Rendering、Memory；2D 专用模块 Window > Analysis > 2D Profiler（图集/光效）
- Deep Profiling 精确但开销大，仅分析时开
- 代码打点：`Profiler.BeginSample("Name") ... Profiler.EndSample()`

## 帧预算表（目标 16.6ms @60FPS）

| 模块 | 移动端预算 |
|---|---|
| 脚本 Update | ≤ 4ms |
| 渲染（Draw Call） | ≤ 200 次（低端机 ≤ 100） |
| 物理 | ≤ 2ms |
| 灯光 | ≤ 10 盏非投影 |

## 移动端专项

- 渲染分辨率：低端机降 URP Render Scale；像素风低分辨率正交相机 + Point 采样
- 光照限量（见上表）；阴影尽量不用；音频用 Vorbis 压缩
- `Application.targetFrameRate = 60`（移动端默认 30 需手动设）
- 发热：限制 Bloom 等后处理、减少全屏透明叠加

## 内存

- 图集 Max Size 按需（2048 足够多数 2D）；纹理压缩移动端 ASTC/ETC2
- 关卡资源 Addressables 按需加载（`references/11-scene-prefab-package.md`），卸载后 `Resources.UnloadUnusedAssets()`
- 深查：Memory Profiler 包（com.unity.memoryprofiler）

## 坑（现象 → 原因 → 解法）

1. 合批数远低于预期 → 同层精灵排序被打断/多图集 → 图集与排序层统一规划
2. 首帧卡顿 → Instantiate 集中爆发 → 对象池预热
3. 整屏 UI 重建频繁 → 动静元素同 Canvas → 拆 Canvas
4. 移动端发热掉帧 → 后处理+灯光超量 → 按预算表裁剪
5. 每帧 GC 尖峰 → 字符串拼接/LINQ/数组分配 → 热路径审计（Profiler GC Alloc 列）

## 相关文件

- 精灵/图集：`references/03-2d-sprite.md` · 幸存者类极限优化：`references/genres/2d-survivor-like.md`

## 文档速查

- 2D Profiler：https://docs.unity3d.com/6000.5/Documentation/Manual/sprite/profiler-2d.html
- 性能与优化：https://docs.unity3d.com/6000.5/Documentation/Manual/adaptive-performance/performance-optimization-strategies.html
- Profiler 手册：https://docs.unity3d.com/6000.5/Documentation/Manual/Profiler.html
