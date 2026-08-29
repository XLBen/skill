# 2D 俯视角射击 / 双摇杆 / Rogue（Top-down Shooter）

## Contents
- 系统拆解 · 双摇杆输入 · 射击与子弹 · 敌人 AI 模式 · Rogue 随机房间 · 特有技巧 · 坑 · API 速查

## 核心系统拆解

八向移动 + 瞄准射击 → 弹幕/敌人 AI → 拾取/武器 → （Rogue）随机房间与流程

## 双摇杆输入

```csharp
// 文件: Assets/Scripts/Player/TopDownShooter.cs (Input System)
Vector2 move = _move.ReadValue<Vector2>();
Vector2 aim = _aim.ReadValue<Vector2>();

if (aim.sqrMagnitude < 0.1f)   // 手柄模式(键鼠时 aim 从鼠标世界坐标换算)
{
    Vector2 mouseWorld = Camera.main.ScreenToWorldPoint(Mouse.current.position.ReadValue());
    aim = (mouseWorld - (Vector2)transform.position).normalized;
}

_rb.linearVelocity = move * _moveSpeed;
if (aim.sqrMagnitude > 0.01f) transform.up = aim;   // 朝向瞄准方向
```

## 射击与子弹

```csharp
// 文件: Assets/Scripts/Weapons/Gun.cs — 对象池 + 冷却(池模板见 assets/templates/ObjectPool.cs)
_cooldown -= Time.deltaTime;
if (_fire.ReadValue<float>() > 0.5f && _cooldown <= 0)
{
    _cooldown = 1f / fireRate;
    Bullet b = _bulletPool.Get();
    b.Init(transform.position, transform.up, damage);
}
```

子弹：Kinematic 直飞（纯 Transform 移动省物理开销）+ 触发器命中；生命周期（3s 未命中回池）。

## 敌人 AI 常用模式

- **直线冲撞**：朝玩家方向速度
- **绕圈盘旋**：切向 + 径向速度合成
- **射击型**：保持距离 + 冷却开火；预测提前量 `aimPoint = playerPos + playerVel * t`
- **波次生成**：WaveData ScriptableObject + 生成点 + 对象池

## Rogue 随机房间

- 房间模板预制体/程序生成，图结构随机连通（最小生成树 + 10-20% 回环 + BFS 校验可达）
- 种子：`System.Random(seed)` 全流程可复现（`references/17-procedural-gen.md`）
- 生成顺序：Boss/商店/宝箱房 → 随机房间 + 走廊 → 可达性校验

## 特有编程技巧

- **子弹时间**：`Time.timeScale` 慢动作 + 玩家特效
- **后坐力与扩散**：`spread = baseSpread + recoil; dir = Rotate(dir, Random.Range(-spread, spread))`
- **弹幕模式**：扇形（n 发均分角度）、环形、螺旋（角度偏移随时间推进）；弹幕表数据驱动
- **无敌帧**：受击后 bool 控制 + 闪烁（sprite alpha 交替）；近战：OverlapCircle + 判定窗口

## 坑（现象 → 原因 → 解法）

1. 大量子弹挂 Rigidbody 卡死 → 物理开销 → 子弹 Kinematic/纯 Transform + 触发器
2. 枪口随翻转反向 → 枪口放朝向 forward → 翻转只翻精灵不翻子物体层级
3. 鼠标瞄准错位 → 没转世界坐标 → ScreenToWorldPoint（保证正交相机）
4. 随机房间死路不通 → 没校验连通性 → 生成后 BFS 校验

**BAD/GOOD 示例（子弹命中判定）：**

```csharp
// BAD: 每颗子弹一个 Rigidbody2D + OnTriggerEnter2D,数百子弹物理爆炸
public class Bullet : MonoBehaviour { public Rigidbody2D rb; }

// GOOD: Kinematic 移动 + 命中检测(触发器或射线),物理引擎不参与
public class Bullet : MonoBehaviour
{
    void Update() { transform.Translate(_velocity * Time.deltaTime); }
    void OnTriggerEnter2D(Collider2D other) { /* 伤害 + 回池 */ }
}
```

## API 速查

| 类 | 关键成员 |
|---|---|
| `Camera.main.ScreenToWorldPoint` | 鼠标 → 世界坐标 |
| `Physics2D.OverlapCircleAll` | 索敌/近战判定（Unity 6 内部池化，无 GC 分配） |
| `System.Random(seed)` | 可复现随机房间 |
| `Time.timeScale` | 子弹时间 |

## 相关文件

- 程序化生成：`references/17-procedural-gen.md` · 对象池：`references/00-techniques.md` · 手感（震屏/顿帧）：`references/16-game-feel.md`

## 文档速查

- Physics2D：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Physics2D.html
