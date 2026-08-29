# 2D 银河城（Metroidvania）

## Contents
- 系统拆解 · 房间间过渡 · 能力门控 · 地图系统 · 房间状态持久化 · 特有技巧 · 坑 · API 速查

## 核心系统拆解

平台动作（复用 platformer 控制器）→ 大世界（房间制）→ 能力门控 → 地图系统 → 存档点 → 收集/强化

## Unity 实现要点

- 房间 = 单场景（SceneManager.LoadSceneAsync 切房间）或单场景分段（相机 Confiner 限区域）
- 相机：房间内跟随 + 边界限制（Cinemachine Confiner 2D，见 `references/00-techniques.md`）
- 房间状态持久化：跨房间回访保留已破坏墙/已开宝箱

## 房间间过渡

```csharp
// 文件: Assets/Scripts/World/RoomTransition.cs
void OnTriggerEnter2D(Collider2D other)
{
    if (!other.CompareTag("Player")) return;
    TransitionManager.Instance.GoToRoom(roomToLoad, spawnPointId);
    // 黑幕淡出 → 异步加载 → 淡入;每个房间多个 spawnPoint 按入口 ID 选择
}
```

## 能力门控（Ability Gating）

能力 = 状态（位掩码 flags），不是道具清单：

```csharp
[System.Flags]
public enum Abilities { None = 0, DoubleJump = 1, Dash = 2, WallJump = 4, Grapple = 8 }

public bool HasAbility(Abilities a) => (_abilities & a) == a;

// 门 = 触发器检查能力
if (PlayerAbilities.HasAbility(required)) OpenGate();
```

- 能力点放死路末端，形成「看到拿不到 → 拿了回来拿」回溯循环
- 能力影响控制器分支：`if (HasAbility(DoubleJump))` 允许第二跳

## 地图系统

- 房间注册表 ScriptableObject：sceneName + 地图坐标（Vector2Int）+ 小地图 icon
- 解锁规则：进过的房间可见，未进隐藏；「地图能力」解锁完整地图
- 小地图 UI：RawImage + 程序生成 Texture2D，或每房间小图拼

## 房间状态持久化（核心难点）

```csharp
// 存档驱动重建: 房间加载后按存档恢复(数据驱动最可控)
[System.Serializable]
public class RoomState
{
    public string roomId;
    public List<string> openedGates = new();    // 已开机关
    public List<string> collectedItems = new(); // 已取收集品
}
// 会话内: RoomStateManager 字典缓存;存档时序列化(含 schemaVersion,见 references/13)
```

方案对比：①每房间静态化场景 ②存档驱动重建（推荐）③全局单例存状态。

## 特有编程技巧

- **存档点**：保存位置 + 房间状态 + 角色状态；死亡回最近存档点并恢复房间状态
- **敌人重生**：离房 N 秒重置（记录击杀状态）；Boss 房不重置
- **快速移动**：存档点间传送（地铁系统）
- **隐藏房间**：假墙（可破坏 Tile + 视觉提示）、密道（触发后 Tilemap 区域卸载）
- **回溯完成度**：收集物全局计数（收集单例 + 事件）

## 坑（现象 → 原因 → 解法）

1. 切房间后敌人全重置 → 击杀状态没持久化 → 击杀记录入 RoomState
2. 切房间相机状态残留 → Cinemachine 相机没重置 → 切房间重置虚拟相机优先级
3. 门控被冲刺穿过 → 碰撞时序 → 门只在开启时启用 collider
4. 房间状态字典无限膨胀 → 无变化房间也缓存 → 存档时清理无变化房间

**BAD/GOOD 示例（门控判定）：**

```csharp
// BAD: 用碰撞体开关门,冲刺帧穿透时顺序错乱
void OnTriggerEnter2D(Collider2D other) { if (other.CompareTag("Player")) OpenGate(); }

// GOOD: 门控逻辑独立于物理,开启时先验能力再切 collider
void TryOpen() { if (!PlayerAbilities.HasAbility(_required)) return; _collider.enabled = false; }
```

## API 速查

| 类 | 关键成员 |
|---|---|
| `SceneManager` | `LoadSceneAsync` / `UnloadSceneAsync` |
| `CinemachineConfiner2D` | 相机房间边界限制 |
| `Tilemap` | `SetTile(cell, null)` 破坏性墙 |
| ScriptableObject | RoomData 房间注册表 |

## 相关文件

- 场景切换：`references/11-scene-prefab-package.md` · 存档：`references/13-architecture.md` · 平台手感：`references/genres/2d-platformer.md`

## 文档速查

- SceneManager：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/SceneManagement.SceneManager.html
- Cinemachine：https://docs.unity3d.com/Packages/com.unity.cinemachine@latest
