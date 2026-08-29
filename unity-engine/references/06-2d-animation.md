# 06 2D 动画（Unity 6.5）

## Contents
- 三方案选型 · Animator 基础 · 混合树 · 动画事件 · 代码控制 · 2D Animation 骨骼 · 代码驱动动画 · 坑

## 三种方案选型

| 方案 | 适用 | 包 |
|---|---|---|
| Sprite 帧动画 + Animator | 帧序列精灵（像素风、特效） | 内建 |
| 2D Animation 骨骼 | 多关节角色、换装、IK | com.unity.2d.animation |
| 代码驱动换 sprite | 简单闪烁/程序化特效 | 无 |

## Animator 基础

- Animator 组件 + Animator Controller；参数（Float/Int/Bool/Trigger）驱动状态转移
- `SetBool("isRunning", true)` / `SetTrigger("jump")` / `SetFloat("speed", v)`
- 状态转移：动作游戏取消 Has Exit Time 保响应；攻击动画用 Exit Time 保证播完
- 分层 Layers：移动+射击上下半身分离

```csharp
Animator anim;
void Start() { anim = GetComponent<Animator>(); }
void Update()
{
    anim.SetFloat("speed", Mathf.Abs(rb.linearVelocity.x));   // 混合树驱动
    if (Input.GetButtonDown("Jump")) anim.SetTrigger("jump");
}
```

## 混合树 Blend Tree

2D Freeform Directional：按 moveX/moveY 混合四方向待机/移动。

## 动画事件 Animation Events

```csharp
public void OnAttackHit() { /* 攻击动画中段回调: 生成判定/伤害 */ }
public void OnFootstep() { /* 脚步声 */ }
```

方法必须 public 无重载（IL2CPP 可靠）。

## 代码控制播放

```csharp
anim.Play("Attack");               // 立即播放
anim.CrossFade("Run", 0.1f);       // 平滑过渡
anim.speed = 2f;                   // 变速
anim.GetCurrentAnimatorClipInfo(0)[0].clip.normalizedTime;  // 进度 0~1
```

- 连段：`SetInteger("combo", i)` 或按 normalizedTime 阈值接受下一次输入
- 状态结束回调：StateMachineBehaviour（OnStateExit）挂状态上

## 2D Animation 骨骼（包: com.unity.2d.animation + com.unity.2d.psdimporter）

流程：PSD/多精灵 → Sprite Editor 切分 → Skinning Editor 建骨 → 蒙皮 → Animator 驱动。

- `SpriteSkin` 骨骼蒙皮；`Sprite Library / Sprite Resolver` 换装；`IKManager2D`（CCD/FABRIK）脚踩地面/手瞄准
- 骨骼动画内存小、可插值，但像素风需帧对齐（PSD Importer 的 frame alignment）
- 相机动画方案（Cinemachine 的 2D 跟随/限制）见 `references/00-techniques.md`

## 代码驱动动画（无 Animator）

```csharp
// 简单循环动画: 每 1/fps 秒换一帧
timer += Time.deltaTime;
if (timer >= 1f / fps) { timer = 0; frame = (frame + 1) % frames.Length; sr.sprite = frames[frame]; }
```

适用：宝箱开合、金币旋转等无状态机需求的简单特效。注意每帧换 sprite 影响合批。

## 坑（现象 → 原因 → 解法）

1. Awake 里 SetBool 无效 → 参数在 Animator 初始化前设置被覆盖 → Start/首帧后再设
2. 同帧多次 SetTrigger 只触发一次 → Trigger 被消费 → 用 Bool 或分帧设
3. 动画事件不触发 → 方法私有/重载 → public 且无重载
4. 动作响应迟钝 → Has Exit Time 等播完 → 动作类转移取消退出时间
5. 骨骼角色翻转后 IK 错 → 翻转只翻了精灵 → 翻根节点骨骼

## 相关文件

- 手感演出：`references/16-game-feel.md` · 状态机：`references/00-techniques.md`（代码 FSM 与 Animator 选型）

## 文档速查

- Animator API：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Animator.html
- Animator 手册：https://docs.unity3d.com/6000.5/Documentation/Manual/Animator.html
- 2D Animation 包：https://docs.unity3d.com/Packages/com.unity.2d.animation@latest
