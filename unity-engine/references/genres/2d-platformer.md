# 2D 平台跳跃（Platformer）

## Contents
- 系统拆解 · 角色控制器 · 特有技巧 · 坑 · API 速查

## 核心系统拆解

角色控制（移动/跳跃/攻击）→ 关卡（Tilemap）→ 敌人 AI → 收集品/机关 → 相机跟随

## Unity 实现要点

- 角色：`Rigidbody2D`（Dynamic）+ `CapsuleCollider2D`，冻结 Z 旋转
- 关卡：Tilemap 碰撞层 + `CompositeCollider2D`（见 `references/05-tilemap.md`）
- 相机：LateUpdate 跟随（`references/00-techniques.md`）

## 角色控制器（模板见 assets/templates/PlayerController2D.cs）

```csharp
// 文件: Assets/Scripts/Player/PlayerController.cs
void Update()
{
    float x = Input.GetAxisRaw("Horizontal");   // 旧 Input 简写;Input System 见 references/09
    _rb.linearVelocity = new Vector2(x * _moveSpeed, _rb.linearVelocity.y);   // Unity 6 命名

    _jumpBufferTimer = Input.GetButtonDown("Jump") ? _jumpBuffer : _jumpBufferTimer - Time.deltaTime;
    _coyoteTimer = IsGrounded() ? _coyoteTime : _coyoteTimer - Time.deltaTime;

    if (_jumpBufferTimer > 0 && _coyoteTimer > 0)
    {
        _rb.linearVelocity = new Vector2(_rb.linearVelocity.x, _jumpForce);
        _jumpBufferTimer = 0; _coyoteTimer = 0;
    }
    // 松开跳跃提前截断: velocity.y * 0.5f(低跳/高跳)
}
```

## 特有编程技巧

- **手感三件套**：Coyote time 0.08~0.15s + Jump buffer 0.1~0.2s + 跳高截断（×0.5）
- **移动手感**：地面/空中加速度分开（空中 X 控制更弱）；冲刺（dash）短暂大速度 + 重力缩放
- **二段跳/墙跳**：跳跃计数落地/贴墙重置；墙跳反向推力 + 短暂禁用朝向输入
- **单向平台**：`PlatformEffector2D`（one way），「下+跳」穿过：检测下键 + 短暂 `Physics2D.IgnoreCollision` 或改 collider
- **移动平台**：Kinematic + 代码位移；乘客方案 = 玩家 parent 到平台（简单可靠）
- **机关编排**：开关/门/钉刺状态机 + 触发器，协程/Timeline 编排

## 坑（现象 → 原因 → 解法）

1. 高速下落穿透薄地面 → 离散检测漏帧 → 角色 `CollisionDetectionMode.Continuous`
2. 相机抖动 → 刚体没插值 → `Interpolation.Interpolate`
3. 墙跳后贴墙吸附 → 反向输入未禁用 → 墙跳瞬间短禁朝向输入 + 离墙速度
4. 角色摔倒旋转 → 没冻结旋转 → constraints 冻结 Z

**BAD/GOOD 示例（每帧找对象）：**

```csharp
// BAD: 每帧字符串查找
void Update() { GameObject player = GameObject.Find("Player"); }

// GOOD: 启动时缓存一次
private GameObject _player;
void Start() { _player = GameObject.FindWithTag("Player"); }
```

## API 速查

| 类 | 关键成员 |
|---|---|
| `Rigidbody2D` | `linearVelocity` / `gravityScale` / `interpolation` / `constraints` |
| `Physics2D` | `Raycast`（地面检测）/ `IgnoreCollision`（穿平台） |
| `PlatformEffector2D` | one way 单向平台 |
| `Animator` | `SetBool` / `SetTrigger`（跑跳动画） |

## 相关文件

- 控制器模板：`assets/templates/PlayerController2D.cs` · 手感配方：`references/16-game-feel.md` · 关卡设计：`references/18-level-design.md`

## 文档速查

- Rigidbody2D：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Rigidbody2D.html
- PlatformEffector2D：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/PlatformEffector2D.html
