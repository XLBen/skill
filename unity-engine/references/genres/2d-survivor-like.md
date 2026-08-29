# 2D 类吸血鬼幸存者（Survivor-like / 弹幕割草）

## Contents
- 系统拆解 · 大规模敌人管理 · 无物理碰撞 · 自动武器 · 升级选择 · 特有技巧 · 坑 · API 速查

## 核心系统拆解

自动攻击 → 大规模敌人（数百上千）→ 经验升级 → 技能构筑 → 计时波次/Boss。**性能第一**：全程对象池 + 无 GC 热路径 + 无物理引擎。

## 大规模敌人管理（核心）

```csharp
// 文件: Assets/Scripts/Enemies/EnemyManager.cs — 单一循环驱动全部敌人
private List<Enemy> _enemies = new();        // 活跃
private Queue<Enemy> _pool = new();

void Update()
{
    Vector2 playerPos = Player.Instance.Position;
    for (int i = _enemies.Count - 1; i >= 0; i--)   // 倒序遍历支持 RemoveAtSwapBack
    {
        Enemy e = _enemies[i];
        e.MoveTowards(playerPos, Time.deltaTime);    // 结构体内纯计算(无 Mono Update)
        if (e.isDead) { _pool.Enqueue(e); _enemies.RemoveAtSwapBack(i); }
    }
}
```

进阶：千级敌人上 Job System + Burst（NativeArray 批量位移）+ 空间网格哈希分桶（只查相邻桶）；万级才上 ECS。

## 无物理碰撞检测

```csharp
// 接触伤害: 距离检测(圆形近似),比 Collider 便宜两个数量级
for (int i = _enemies.Count - 1; i >= 0; i--)
{
    var e = _enemies[i];
    float r = e.radius + _playerRadius;
    if ((e.pos - playerPos).sqrMagnitude < r * r)   // sqrMagnitude 免开方
    {
        Player.TakeDamage(e.damage);
        e.pos += (e.pos - playerPos).normalized * knockback;   // 击退(纯位移)
    }
}
```

## 自动武器系统

```csharp
// 文件: Assets/Scripts/Weapons/WeaponManager.cs
void Update()
{
    foreach (var w in _weapons)
    {
        w.timer -= Time.deltaTime;
        if (w.timer <= 0)
        {
            w.timer = w.data.interval * w.cooldownMultiplier;
            Fire(w);                      // 目标选择: 最近敌人/随机方向/扇形
        }
    }
}
// WeaponData ScriptableObject: 间隔/伤害/弹数/射程/瞄准模式;等级是运行时实例状态
```

## 经验掉落与升级三选一

```csharp
// 磁吸: 玩家磁铁范围内宝石飞向玩家(纯位移,无物理)
// 升级: 随机三选一(卡池权重按解锁/稀有度),UI 弹出卡牌
public void ShowLevelUpChoices(UpgradeData[] pool)
{
    var choices = PickWeighted(pool, 3);
    // 武器满级 + 对应被动 → 组合超武(组合表)
}
```

## 特有编程技巧

- **伤害数字**：精灵数字图集（0-9 sprite 池化），不用逐字 Text（GC 灾难）
- **对象池全家桶**：敌人、弹体、经验宝石、伤害数字、特效全部池化
- **屏幕外裁剪**：敌人离开相机范围禁用 sprite（继续模拟或回收）
- **性能目标**：移动端同屏 200+ 敌人 60FPS；Profiler 验证（`references/12-performance-2d.md`）
- **波次压力曲线**：生成频率/血量随时间指数上升，Boss 每 N 分钟

## 坑（现象 → 原因 → 解法）

1. 敌人逐个 MonoBehaviour Update 卡死 → 数百组件更新 → 统一管理器循环
2. 弹体×敌人 O(n×m) 爆炸 → 全量两两检测 → 空间分桶/最近目标查询
3. 物理 Collider 方案直接崩溃 → 物理引擎开销 → 此类型弃用物理碰撞，全数学检测
4. 伤害数字 Text 每帧 new string → 字符串分配 → 精灵数字图集

**BAD/GOOD 示例（敌人驱动）：**

```csharp
// BAD: 500 个敌人 = 500 个 Update 调用
public class Enemy : MonoBehaviour { void Update() { /* 各自移动 */ } }

// GOOD: 管理器单循环 + 纯数据敌人
public class EnemyManager : MonoBehaviour { void Update() { /* 一次循环驱动全部 */ } }
```

## API 速查

| 类 | 关键成员 |
|---|---|
| `List<T>` + `RemoveAtSwapBack` | 活跃列表维护 |
| `Vector2.sqrMagnitude` | 免开方距离 |
| Job System + Burst | 千级批量位移（进阶） |
| 对象池 | 全部实体复用 |

## 相关文件

- 对象池：`references/00-techniques.md` · 性能：`references/12-performance-2d.md` · 手感：`references/16-game-feel.md`

## 文档速查

- Job System：https://docs.unity3d.com/6000.5/Documentation/Manual/job-system.html
- 性能手册：https://docs.unity3d.com/6000.5/Documentation/Manual/adaptive-performance/performance-optimization-strategies.html
