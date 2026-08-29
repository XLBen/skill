# 2D 格斗游戏（Fighting）

## Contents
- 系统拆解 · 帧数据 · 攻击判定 · 输入缓冲与指令 · 连段 · 特有技巧 · 坑 · API 速查

## 核心系统拆解

帧数据驱动动作 → 判定框（Hitbox/Hurtbox）→ 输入缓冲与搓招 → 连段 → 防御/硬直 → 角色状态机

## Unity 实现要点

- 角色状态机（类状态机，`assets/templates/StateMachine.cs`）；Animator 或纯代码帧驱动（格斗对时机精度要求高，推荐代码驱动帧计时）
- 判定框：矩形数学相交（快且精确），不用物理引擎

## 帧数据（核心概念）

最小时间单位是帧（60FPS）。招式由帧数据定义：

```csharp
[CreateAssetMenu(menuName = "Game/MoveData")]
public class MoveData : ScriptableObject
{
    public string moveName;
    public int startupFrames;       // 启动帧(出招到判定生效)
    public int activeFrames;        // 判定持续帧
    public int recoveryFrames;      // 收招硬直
    public int damage;
    public Vector2 knockback;
    public int hitstunFrames;       // 命中硬直(受击方)
    public int cancelWindow;        // 可取消窗口(连段)
    public Rect[] hitboxRects;      // 判定框(带帧窗口)
}
```

## 攻击判定流程

```csharp
// 文件: Assets/Scripts/Fighter/AttackState.cs — 招式帧推进
public override void Update()
{
    _frame++;
    if (_frame == _move.startupFrames) CheckHit();                 // 判定生效帧
    if (_frame == _move.startupFrames + _move.activeFrames) _hasHit = false;
    if (_frame >= _move.startupFrames + _move.activeFrames + _move.recoveryFrames)
        Ctx.SwitchState(Ctx.IdleState);                            // 收招结束
}

void CheckHit()
{
    foreach (var hb in _move.hitboxRects)
        if (RectOverlaps(hb, Opponent.CurrentHurtbox())) { ResolveHit(_move); _hasHit = true; break; }
}
```

## 输入缓冲与指令识别（搓招）

```csharp
// 文件: Assets/Scripts/Fighter/InputBuffer.cs — 存最近 N 帧输入历史
public class InputBuffer
{
    private readonly Queue<(int frame, InputCmd cmd)> _history = new();
    // 波动拳 236P: 窗口内按序匹配 ↓ ↘ → + P(8~12 帧窗口 + 方向宽松匹配)
    public bool Matches(CommandPattern pattern, int windowFrames = 10) { /* ... */ }
}
public enum InputCmd { None, Down, DownForward, Forward, Back, Punch, Kick, /* ... */ }
```

- 指令表：波动拳 236P、升龙 623P 等存 `CommandPattern`（方向序列 + 按键 + 宽松度）
- 优先级：升龙 > 波动拳（先判复杂指令）

## 连段系统

```csharp
public bool TryCancelInto(MoveData next)
{
    if (_frame <= _move.cancelWindow && _hasHit)   // 命中 + 取消窗口内
    {
        Ctx.StartMove(next);
        _comboCount++;
        return true;
    }
    return false;
}
// 连段规则: 普通技取消特殊技取消超必杀(取消链表);连段伤害修正 damageScale = 1 - combo*0.1
```

## 特有编程技巧

- **Hitbox 可视化**：Gizmos 绘制判定框，帧窗口调参（`references/10-editor-scripting.md`）
- **打击感**：顿帧（hitstop 2-8 帧）+ 震屏 + 击退 + 火花粒子（`references/16-game-feel.md`）
- **浮空与受身**：受击 velocity 向上 + 击退，落地受身（起身无敌帧）
- **防御**：站防/蹲防/空中不能防下段；防御减伤 + 削槽
- **霸体/无敌帧**：招式带 armor/invincible 属性，命中检测前检查
- **回滚联网**（进阶）：Rollback Netcode，2D 格斗联机标准

## 坑（现象 → 原因 → 解法）

1. Animator 驱动帧时机不可控 → 状态机延迟 → 代码驱动帧计时
2. 物理引擎判定漏检/开销 → 碰撞体方案 → 纯矩形相交
3. 搓不出招 → 输入窗口过窄 → 8~12 帧窗口 + 方向宽松
4. 连段中位置漂移 → 击退累积 → 命中后微调双方位置（真空吸附）
5. 顿帧冻住全局 → timeScale 全局停 → 短顿帧用 unscaledTime 或只停双方表现

**BAD/GOOD 示例（帧驱动）：**

```csharp
// BAD: 等 Animator 动画事件驱动判定,帧时机不受控
void OnAttackHitEvent() { CheckHit(); }

// GOOD: 招式帧计数器驱动,判定帧精确
void Update() { _frame++; if (_frame == _move.startupFrames) CheckHit(); }
```

## API 速查

| 类 | 关键成员 |
|---|---|
| 自实现帧计数器 | 招式时序 |
| `Gizmos` | 判定框可视化 |
| `Time.timeScale` | 顿帧（配合 unscaled） |
| ScriptableObject | MoveData 帧数据 |

## 相关文件

- 状态机模板：`assets/templates/StateMachine.cs` · 输入缓冲：`references/09-input-audio.md` · 打击感：`references/16-game-feel.md`

## 文档速查

- Gizmos：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Gizmos.html
- Time.timeScale：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Time-timeScale.html
