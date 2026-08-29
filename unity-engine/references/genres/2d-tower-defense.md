# 2D 塔防（Tower Defense）

## Contents
- 系统拆解 · 敌人寻路 · 塔索敌与攻击 · 波次系统 · 特有技巧 · 坑 · API 速查

## 核心系统拆解

路径（敌人寻路）→ 塔位摆放 → 塔索敌攻击 → 敌人波次 → 经济 → 升级与胜负

## 敌人寻路（Waypoint 方案）

```csharp
// 文件: Assets/Scripts/Enemy/Enemy.cs — 路径点由 PathManager 共享(所有敌人读同一份)
void Update()
{
    if (_wpIndex >= _waypoints.Length) { ReachEnd(); return; }
    Vector3 target = _waypoints[_wpIndex].position;
    transform.position = Vector3.MoveTowards(transform.position, target, _speed * Time.deltaTime);
    if ((transform.position - target).sqrMagnitude < 0.05f * 0.05f) _wpIndex++;   // sqr 比较省开方
}
```

- 路径可变（迷宫塔防）：自写 A*（网格图 + 开放/关闭列表）；塔位变化后增量/低频重算
- 官方 AI Navigation 包支持 2D（NavMeshSurface 旋转模式），复杂寻路可评估

## 塔索敌与攻击

```csharp
// 文件: Assets/Scripts/Towers/Tower.cs
// Unity 6: OverlapCircleAll 内部池化,无 GC 分配(NonAlloc 系列已移除)
void Update()
{
    _cooldown -= Time.deltaTime;
    if (_cooldown > 0) return;
    Collider2D[] hits = Physics2D.OverlapCircleAll(transform.position, _range, _enemyLayer);
    if (hits.Length == 0) return;
    _cooldown = 1f / _fireRate;
    Fire(PickByStrategy(hits, _aimStrategy));   // First/Last/Strongest/Nearest
}
```

- 索敌检测频率可降到 0.2s 一次（省 CPU）；追踪弹每帧转向，目标死亡重选或自毁
- 弹体对象池（`assets/templates/ObjectPool.cs`）

## 波次系统

```csharp
[CreateAssetMenu(menuName = "Game/WaveData")]
public class WaveData : ScriptableObject
{
    public SpawnGroup[] groups;      // 每组: 敌人类型/数量/间隔/延迟
}

IEnumerator SpawnWave(WaveData wave)
{
    foreach (var g in wave.groups)
    {
        yield return new WaitForSeconds(g.startDelay);
        for (int i = 0; i < g.count; i++)
        {
            SpawnEnemy(g.enemy);
            yield return new WaitForSeconds(g.interval);
        }
    }
}
// 波次完成检测: 场上无敌人 + 生成完毕 → 下一波;难度: 血量/速度随波次指数上升
```

## 特有编程技巧

- **经济**：金钱 = 初始 + 击杀/波次奖励 - 建塔/升级花费；UI 更新用事件（`references/13-architecture.md`）
- **升级**：塔数值按等级索引表；升级换 sprite
- **放置校验**：塔位占坑 + **通路校验**（放置后 A* 重算，防堵死路线）
- **减速/状态塔**：目标挂减速 buff（速度 ×0.5 持续 2s）；叠加规则取最大或叠加
- **AOE 塔**：落点爆炸 OverlapCircle + 范围伤害衰减；**出售**：回收 70% 金钱 + 池回收

## 坑（现象 → 原因 → 解法）

1. 每帧 OverlapCircleAll 卡顿 → 查询过频 → Unity 6 已内部池化（无 GC），降频 0.2s 一次即可
2. 追踪弹目标死亡空引用 → 未重选目标 → 每帧判空重选
3. 塔位堵死敌人路径 → 没做通路校验 → 放置时 A* 验证
4. 波次表手配易错 → Inspector 手填 → Editor 工具批量生成波次表（`references/10-editor-scripting.md`）

**BAD/GOOD 示例（索敌查询）：**

```csharp
// BAD: 每塔每帧全量查询 + 不设层过滤
Collider2D[] hits = Physics2D.OverlapCircleAll(transform.position, _range);

// GOOD: 层过滤 + 降频(0.2s);Unity 6 的 All 系列内部池化,无 GC 分配
Collider2D[] hits = Physics2D.OverlapCircleAll(transform.position, _range, _enemyLayer);
```

## API 速查

| 类 | 关键成员 |
|---|---|
| `Physics2D.OverlapCircleAll` | 索敌（内部池化） |
| `Vector3.MoveTowards` | 敌人行进 |
| `A*`（自实现） | 可变路径寻路 |
| ScriptableObject | WaveData/塔配置 |

## 相关文件

- 对象池：`references/00-techniques.md` · Editor 工具：`references/10-editor-scripting.md` · 性能：`references/12-performance-2d.md`

## 文档速查

- Physics2D API：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Physics2D.html
- AI Navigation 包：https://docs.unity3d.com/Packages/com.unity.ai.navigation@latest
