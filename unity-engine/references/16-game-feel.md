# 16 游戏手感（Game Feel / Juice）

## Contents
- 打击感四件套（hitstop/震屏/击退/粒子）
- 位移与挤压拉伸
- 相机抖动配方
- 音效与节奏
- 手感调参数值参考

## 打击感四件套

命中反馈按强度分层组合：**顿帧 > 震屏 > 击退 > 粒子/音效**。

### 1. 顿帧 Hitstop（打击停顿）

```csharp
// 全局短暂停: 命中瞬间 Time.timeScale = 0,几十毫秒后恢复
public void HitStop(float duration)
{
    if (_hitStopRoutine != null) StopCoroutine(_hitStopRoutine);
    _hitStopRoutine = StartCoroutine(DoHitStop(duration));
}

IEnumerator DoHitStop(float duration)
{
    Time.timeScale = 0f;
    yield return new WaitForSecondsRealtime(duration);   // Realtime: 不受 timeScale 影响
    Time.timeScale = 1f;
    _hitStopRoutine = null;
}
```

参考值：轻攻击 0.03~0.06s，重击/必杀 0.1~0.25s。**顿帧只冻表现**：期间 UI 计时器等用 `unscaledDeltaTime`。

### 2. 震屏 Camera Shake（见 `references/00-techniques.md` 相机系统，或 Cinemachine Impulse）

Cinemachine 方案（生产推荐）：`CinemachineImpulseSource.GenerateImpulse(velocity)`，噪声配置文件控制衰减，比手写更可控。

### 3. 击退 Knockback

```csharp
// 命中方向推速度 + 短控锁(受击硬直)
rb.linearVelocity = hitDir * knockbackForce;
_controlLockTimer = hitstunDuration;   // 期间禁输入,见 genres/2d-fighting.md 帧数据
```

### 4. 粒子与音效

- 命中火花：对象池粒子，命中点生成，随受击对象颜色变化
- 音效随机化：同音效 3-4 个变体随机 pitch（±0.1）防重复感（见 `references/09-input-audio.md`）

## 挤压拉伸 Squash & Stretch

经典动画原则，2D 精灵用 scale 实现（骨骼动画缩放根节点）：

```csharp
// 落地压缩: 水平拉宽 1.2, 竖直压扁 0.8, 0.1s 内恢复
IEnumerator LandSquash()
{
    transform.localScale = new Vector3(1.25f, 0.75f, 1f);
    float t = 0f;
    while (t < 1f)
    {
        t += Time.deltaTime / 0.12f;
        transform.localScale = Vector3.Lerp(new Vector3(1.25f, 0.75f, 1f), Vector3.one, t);
        yield return null;
    }
}
```

要点：只在表现层改 scale，碰撞体不变形；频率控制（每 0.1s 最多一次）。

## 反馈配方（按事件）

| 事件 | 组合 |
|---|---|
| 玩家受伤 | 闪红（sprite color）+ 震屏 0.15s + 音效 + 无敌帧闪烁 |
| 暴击 | 大字飘字 + 强顿帧 + 强震屏 + 白闪一帧 |
| 拾取金币 | 飘字 + 金币飞向 UI（贝塞尔）+ 递增音效 pitch |
| 升级 | 光柱 + 全屏闪 + 音效渐强 |
| 死亡 | 慢动作（timeScale 0.3）+ 灰度后处理 + 延迟重开 |

## 通用要点

- **节奏**：高频事件（走路）微反馈，低频事件（升级）强反馈，全屏震动滥用会疲劳
- **优先级**：一次只让一个强反馈占据屏幕，冲突时按 伤害>暴击>拾取 优先级覆盖
- **手柄振动**：`Gamepad.current.SetMotorSpeeds(low, high)`（Input System），移动端跳过
- **UI 过渡**：面板弹出用缩放+缓动（0.15s ease-out-back），不用瞬显

## 坑（现象 → 原因 → 解法）

1. 顿帧把 UI 也冻住 → 全局 timeScale 影响一切 → 计时/血条用 unscaledDeltaTime
2. 挤压拉伸后精灵位置漂移 → 缩放绕中心但 pivot 不在底 → 落地压缩用 pivot 在脚底的精灵或偏移修正
3. 震屏时 UI 跟着抖 → UI 挂在相机下 → UI Canvas 用 Screen Space Overlay 独立于相机
4. 连击时顿帧叠加导致卡顿感 → 多个 hitstop 并发 → 单例管理 hitstop，新请求覆盖旧

## 相关文件

- 相机：`references/00-techniques.md`；Cinemachine：`references/99-doc-index.md`
- 帧数据格斗：`references/genres/2d-fighting.md`

## 文档速查

- Cinemachine 包：https://docs.unity3d.com/Packages/com.unity.cinemachine@latest
- Time.timeScale：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Time-timeScale.html
