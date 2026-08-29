# 04 2D 物理（Unity 6.5）

## Contents
- Rigidbody2D · 移动方式 · Collider2D · 碰撞 vs 触发 · 地面检测 · 射线与查询 · Effector · Joint · 设置与坑

2D 物理基于 Box2D 的独立实现，与 3D 物理不通用：2D 组件都带 `2D` 后缀。**命名注意**：Unity 6 中 `Rigidbody2D.velocity` 已改名 `linearVelocity`（旧名仍可用但标记过时），`drag` → `linearDamping`。

## Rigidbody2D 关键属性

| 属性 | 说明 |
|---|---|
| `bodyType` | Dynamic（受力）/ Kinematic（只受代码控制）/ Static（不动，性能最好） |
| `gravityScale` | 重力缩放（平台游戏调手感；0 = 无重力） |
| `mass` | 质量（影响碰撞冲量，不影响下落速度） |
| `linearDamping` / `angularDamping` | 线性/角阻尼 |
| `linearVelocity` / `angularVelocity` | 直接设速度（移动首选） |
| `constraints` | 冻结轴/旋转（横版角色冻结 Z 防摔倒） |
| `interpolation` | 插值（相机跟随抖动时设 Interpolate） |
| `collisionDetectionMode` | 高速物体防穿透设 Continuous（仅快物体开，Discrete 足够多数场景） |

来源：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Rigidbody2D.html

## 移动方式（四选一，明确默认）

**默认：直接设 linearVelocity（平台游戏）**

```csharp
void FixedUpdate()
{
    rb.linearVelocity = new Vector2(inputX * speed, rb.linearVelocity.y);
}
```

| 方式 | 场景 |
|---|---|
| `linearVelocity` 赋值 | 平台跳跃（默认） |
| `AddForce(…, ForceMode2D.Impulse)` | 俯视角推动/爆炸冲量 |
| `MovePosition` | Kinematic 移动（移动平台） |
| `rb.Cast` + 手动修正 | 精确碰撞控制（进阶） |

力放 FixedUpdate 调用，速度是瞬时量（每帧覆盖）。

## Collider2D 类型与选择

| 类型 | 场景 |
|---|---|
| BoxCollider2D | 矩形，最常用 |
| CircleCollider2D | 圆形，性能优 |
| CapsuleCollider2D | 角色，无勾角卡墙 |
| PolygonCollider2D | 精确外形（Sprite Editor 自动生成） |
| EdgeCollider2D | 地形边缘/斜坡 |
| CompositeCollider2D | 合并多碰撞体（Tilemap 必配，配合 Rigidbody2D `Used By Composite`） |

属性：`isTrigger`（触发器穿透检测）、`sharedMaterial`（PhysicsMaterial2D：friction/bounciness）。

## 碰撞 vs 触发

- **碰撞**：`OnCollisionEnter2D/Stay2D/Exit2D(Collision2D)`，参数含接触点与相对速度
- **触发**（isTrigger）：`OnTriggerEnter2D/Stay2D/Exit2D(Collider2D)`
- 条件：双方至少一个 Rigidbody2D；接收方组件在被撞方对象上

```csharp
void OnCollisionEnter2D(Collision2D c)
{
    if (c.gameObject.CompareTag("Ground")) _isGrounded = true;
}
void OnTriggerEnter2D(Collider2D other)
{
    if (other.CompareTag("Player")) Collect();
}
```

## 地面检测（平台核心）

```csharp
bool IsGrounded()
{
    // Raycast 从底部向下;或用 BoxCast 覆盖角色宽度防漏检
    Vector2 origin = (Vector2)transform.position - new Vector2(0f, _halfHeight);
    RaycastHit2D hit = Physics2D.Raycast(origin, Vector2.down, 0.15f, _groundLayer);
    return hit.collider != null;
}
```

## 射线与区域查询

```csharp
Physics2D.Raycast(origin, dir, dist, layerMask);
Physics2D.RaycastAll(...);                    // 穿透全部
Physics2D.CircleCast / BoxCast / CapsuleCast;
Physics2D.OverlapCircle(point, r, layerMask); // 范围内敌人
Physics2D.OverlapCircleAll / OverlapBoxAll;
Physics2D.IgnoreCollision(a, b, true);
Physics2D.queriesHitTriggers = true;
```

**Unity 6 查询分配说明**：6.x 已移除 `*NonAlloc` 系列，`OverlapCircleAll`/`RaycastAll` 等内部使用池化缓冲，重复调用不再产生 GC 分配。高频索敌仍建议降频（0.2s 一次）以省 CPU。

## Effector2D（力场/特殊区域）

`PlatformEffector2D`（单向平台）、`AreaEffector2D`（区域风/推力）、`BuoyancyEffector2D`（浮力）、`PointEffector2D`（点吸斥力）、`SurfaceEffector2D`（传送带）。

## Joint2D（关节）

`SpringJoint2D`（弹簧绳）、`DistanceJoint2D`（定长绳）、`HingeJoint2D`（铰链/门/链条）、`SliderJoint2D`（滑轨）、`WheelJoint2D`（车轮）、`RelativeJoint2D`（拖拽跟随）、`FixedJoint2D`/`FrictionJoint2D`。

## 设置与坑（现象 → 原因 → 解法）

1. 高速下落穿透薄地面 → 离散检测漏帧 → 快物体设 Continuous（不建议全开，性能）
2. 斜坡滑行抖动 → 物理材质 friction 低 → friction 设 1
3. 刚体相互叠加抖动 → 求解迭代不足/Update 改 Transform → 提高 solver iterations、物理移动只走 Rigidbody API
4. 每帧 OverlapCircleAll 卡顿 → 查询过频 → Unity 6 已内部池化（无 GC 分配），降频查询（0.2s）省 CPU
5. 角色摔倒旋转 → 未冻结旋转 → constraints 冻结 Z 旋转
6. 物理行为随帧率抖动 → 逻辑写 Update → FixedUpdate 统一物理逻辑

**注**：2D 无 CharacterController2D，平台角色用 Rigidbody2D 手写（见 `references/genres/2d-platformer.md`）。

## 相关文件

- 物理调参（时间步/CCD）：参考 `references/12-performance-2d.md` 物理优化节
- 平台手感：`references/genres/2d-platformer.md` · 无物理碰撞方案：`references/genres/2d-survivor-like.md`

## 文档速查

- Physics2D：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Physics2D.html
- Collider2D：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Collider2D.html
- 物理设置（Physics 2D）：https://docs.unity3d.com/6000.5/Documentation/Manual/PhysicsSection.html
