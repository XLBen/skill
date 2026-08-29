# 2D 回合制 RPG（Turn-based RPG / JRPG）

## Contents
- 系统拆解 · 数据模型 · 战斗状态机 · 回合顺序 · 伤害公式 · 状态效果 · 特有技巧 · 坑 · API 速查

## 核心系统拆解

探索（Tilemap 地图 + 玩家移动）→ 遇敌 → 回合战斗 → 角色养成 → 剧情对话 → 存档

## 数据模型（ScriptableObject）

```csharp
// 文件: Assets/Data/SkillData.cs
[CreateAssetMenu(menuName = "Game/SkillData")]
public class SkillData : ScriptableObject
{
    public string skillName;
    public int power;                    // 威力
    public float mpCost;
    public TargetType targetType;        // 单体/全体
    public Element element;              // 属性(相克表)
    public StatusEffectData[] effects;
}
```

角色/技能/敌人/物品全 SO 化；**运行时状态拷贝到普通类，不改资源**（MUST）。

## 战斗状态机

```csharp
// 文件: Assets/Scripts/Battle/BattleManager.cs
public enum BattleState { Intro, Selecting, Acting, EnemyTurn, Victory, Defeat }
// 状态切换用类状态机(assets/templates/StateMachine.cs),演出用协程序列
```

## 回合顺序（速度制）

```csharp
// 行动条制(CTB): 速度决定行动频率
foreach (var fighter in _fighters)
{
    fighter.turnGauge += fighter.speed * Time.deltaTime * scale;  // 每帧累积
    if (fighter.turnGauge >= 100) QueueAction(fighter);           // 满 100 排队
}
// 整队回合制: 按速度降序排行动顺序 List.Sort
```

## 伤害公式与结算

```csharp
// 文件: Assets/Scripts/Battle/DamageFormula.cs — 数值集中一处,平衡改这里
public static int Physical(int attack, int defense, float skillPower)
{
    float raw = attack * skillPower - defense * 0.5f;
    return Mathf.Max(1, Mathf.RoundToInt(raw));     // 保底 1 点
}
// 暴击: Random.value < critRate → ×1.5;浮动 ±10%
```

## 状态效果（Buff/Debuff）

```csharp
// 回合末结算: 中毒扣血、回合递减、到期移除
void OnTurnEnd()
{
    foreach (var e in _statusEffects) e.ApplyTick(this);
    _statusEffects.RemoveAll(e => e.turnsRemaining-- <= 0);
}
```

- 麻痹跳过行动、沉默禁技能——AI 选行动前检查
- 同名状态：不可叠加型刷新回合，可叠加型加层数

## 特有编程技巧

- **战斗演出编排**：协程序列（镜头推近 → 施法 → 特效 → 飘字 → 血条动画 → 死亡演出）
- **遇敌**：随机遭遇（步数/时间概率）+ 明雷（可见敌人接触触发）
- **经验曲线**：`expNeeded = baseExp * level^1.5`；升级回血策略策划定
- **掉落表**：加权随机，稀有度分层（`references/00-techniques.md`）
- **对话**：`references/15-dialogue.md`；**队伍**：`List<CharacterData>` + 编队 UI

## 坑（现象 → 原因 → 解法）

1. 战斗状态机堆 Update 难扩展 → 状态杂糅 → 类状态机拆状态
2. SO 资源字段被运行时改 → 直接写资源 → 运行时拷贝实例类，配置只读
3. 存档后 SO 引用丢失 → 存对象引用 → 存 ID 读档查表恢复
4. 演出期间 AI 决策错乱 → 实时读玩家状态 → 行动时快照

**BAD/GOOD 示例（运行时改配置）：**

```csharp
// BAD: 直接改资源,项目被污染(存档后永久生效)
skillData.power += 10;

// GOOD: 运行时实例隔离
var runtimeSkill = new RuntimeSkill(skillData);   // 拷贝数值
runtimeSkill.power += 10;
```

## API 速查

| 类 | 关键成员 |
|---|---|
| ScriptableObject | 技能/敌人/物品配置 |
| `JsonUtility` | 存档序列化（ID 引用） |
| 协程 | 战斗演出时序 |
| `List.Sort` | 速度排序 |

## 相关文件

- 对话：`references/15-dialogue.md` · 存档版本迁移：`references/13-architecture.md` · 状态机模板：`assets/templates/StateMachine.cs`

## 文档速查

- ScriptableObject：https://docs.unity3d.com/6000.5/Documentation/Manual/class-ScriptableObject.html
- JsonUtility：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/JsonUtility.html
