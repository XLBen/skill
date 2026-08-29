# 2D 跑酷 / 无尽跑（Runner）

## Contents
- 系统拆解 · Chunk 跑道生成 · 三车道切换 · 跳跃滑铲 · 特有技巧 · 坑 · API 速查

## 核心系统拆解

自动前进（或手动加速）→ 跑道生成 → 障碍模式 → 跳跃/滑铲/变道 → 距离计分 → 难度曲线 → 死亡重置

## Unity 实现要点

- 世界移动：玩家 X 固定，世界左移（障碍物/地面滚动），或相机持续右移
- 地面/障碍对象池 + Chunk 块拼接（模式化生成）
- 单按钮操作（跳跃/滑铲），触屏友好

## Chunk 跑道生成

```csharp
// 文件: Assets/Scripts/Runner/ChunkSpawner.cs
[CreateAssetMenu(menuName = "Game/ChunkData")]
public class ChunkData : ScriptableObject
{
    public GameObject chunkPrefab;      // 一段跑道(含障碍摆放)
    public float length;
    public int difficulty;
}

void Update()
{
    float camX = Camera.main.transform.position.x;
    // 前方缺块就补: 难度越高选难块概率越大(距离阈值切换池)
    while (_nextSpawnX < camX + screenBuffer) { SpawnChunk(_nextSpawnX); _nextSpawnX += chunkLength; }
    // 屏幕左外回收(对象池)
}
// 规则约束: 难块不连续(最多 2 连),保证可通行
```

## 三车道切换（横版跑酷）

```csharp
// 文件: Assets/Scripts/Runner/LaneSwitcher.cs
[SerializeField] private float[] _lanes = { -2f, 0f, 2f };   // 车道 X 位置(按项目美术定)
private int _currentLane = 1;

public void SwipeLeft() => ChangeLane(-1);
public void SwipeRight() => ChangeLane(1);

void ChangeLane(int dir)
{
    _currentLane = Mathf.Clamp(_currentLane + dir, 0, _lanes.Length - 1);
}

void Update()
{
    float targetX = _lanes[_currentLane];
    float x = Mathf.MoveTowards(transform.position.x, targetX, _switchSpeed * Time.deltaTime);
    transform.position = new Vector3(x, transform.position.y, 0);
}
```

## 跳跃与滑铲

```csharp
if (Input.GetButtonDown("Jump") && IsGrounded()) Jump();   // 重力加重(gravityScale 更高,下落快)
if (Input.GetButtonDown("Slide")) Slide();                 // 缩小碰撞体 + 滑铲动画
if (Input.GetButtonUp("Slide")) EndSlide();
// Fast-fall: 下落中按下立即加速下坠
```

## 特有编程技巧

- **分数 = 距离 + 金币**：`distance += speed * dt`；最高分 PlayerPrefs
- **难度曲线**：`speed = baseSpeed + distance * factor` 连续递增（阶梯突变会卡手感）；障碍密度随之上升
- **障碍模式组合**：高低交替（跳+铲节奏）、连续三跳、窄缝
- **复活系统**：广告/金币复活，复活点稍提前 + 短暂无敌
- **局外系统**：金币解锁皮肤、每日任务（存档，`references/13-architecture.md`）
- **节奏同步**（音游跑酷）：障碍生成对齐 BPM
- **背景视差**：多层背景按速度比例滚动（far×0.2, mid×0.5, near×0.8）

## 坑（现象 → 原因 → 解法）

1. Chunk 拼接有缝 → 长度非整数单位 → 长度整数对齐 + 边缘重叠 0.01
2. 障碍与相机不同步 → 各自 Update 滚动 → 障碍统一挂世界滚动控制器
3. 高速穿透拾取物 → 离散碰撞漏检 → 距离检测替代碰撞
4. 生成卡顿 → Instantiate 集中 → Chunk 对象池预热
5. 难度断层 → 阶梯提速 → 连续递增公式

**BAD/GOOD 示例（世界滚动）：**

```csharp
// BAD: 每个障碍各自移动,速度不同步出现缝隙
public class Obstacle : MonoBehaviour { void Update() { transform.position += Vector3.left * speed * Time.deltaTime; } }

// GOOD: 单一滚动控制器统一移动世界层,障碍只挂载体
worldRoot.position += Vector3.left * worldSpeed * Time.deltaTime;
```

## API 速查

| 类 | 关键成员 |
|---|---|
| `Mathf.MoveTowards` | 车道平滑 |
| `PlayerPrefs` | 最高分/皮肤 |
| 对象池 | Chunk 复用 |
| ScriptableObject | ChunkData |

## 相关文件

- 对象池：`references/00-techniques.md` · 存档：`references/00-techniques.md`（PlayerPrefs 节）

## 文档速查

- PlayerPrefs：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/PlayerPrefs.html
