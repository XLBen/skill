# 09 输入与音频（Unity 6.5）

## Contents
- 输入方案 · Input System · 移动端触控 · 键鼠手柄 · 输入重绑定 · 音频基础 · Audio Mixer · 自适应音乐 · 坑

## 输入方案

Unity 6 推荐 **Input System 包**（com.unity.inputsystem），旧 Input Manager（`Input` 类）已标记 Legacy。项目设置：Player Settings > Active Input Handling 选 Input System Package (New) 或 Both。来源：https://docs.unity3d.com/6000.5/Documentation/Manual/Input.html

## Input System（新）

- **Input Action Asset**（.inputactions 定义 Move/Jump/Attack + 键盘/手柄/触屏绑定）+ **Player Input** 组件（自动驱动）
- **代码直读**：

```csharp
using UnityEngine.InputSystem;

[SerializeField] private InputActionAsset _actions;
private InputAction _move, _jump;

void Awake()
{
    _move = _actions.FindAction("Move");
    _jump = _actions.FindAction("Jump");
}
void OnEnable() { _actions.Enable(); }
void OnDisable() { _actions.Disable(); }

void Update()
{
    Vector2 move = _move.ReadValue<Vector2>();
    if (_jump.WasPressedThisFrame()) { }   // 按下瞬间
    if (_jump.IsPressed()) { }             // 按住
    if (_jump.WasReleasedThisFrame()) { }  // 松开
}
```

- 事件回调：`_jump.performed += ctx => OnJump();`（started/performed/canceled）
- 设备直读：`Keyboard.current` / `Gamepad.current` / `Touchscreen.current` / `Mouse.current`
- 键盘跳跃与手柄 A 绑同一 Action 自动通吃

## 移动端触控

- On-Screen Button / On-Screen Stick 组件（UI 元素映射动作）；或直读 `Touchscreen.current.primaryTouch`
- 虚拟摇杆：On-Screen Stick 输出 Vector2 绑 Move 动作；多指 `Touchscreen.current.touches[i]`

## 输入重绑定（Rebinding，设置界面的"改键"）

```csharp
using UnityEngine.InputSystem;

public async void StartRebind(InputAction action)
{
    var rebind = action.PerformInteractiveRebinding()
        .WithTargetBinding(0)
        .OnComplete(op =>
        {
            op.Dispose();
            SaveBindingOverride(action);   // 存 PlayerPrefs/文件,下次启动加载
        });
    rebind.Start();
}

// 加载存档的覆盖键位
string json = PlayerPrefs.GetString("rebind_" + action.name);
if (!string.IsNullOrEmpty(json))
    action.LoadBindingOverridesFromJson(json);
```

要点：改键 UI 显示当前绑定用 `action.GetBindingDisplayString()`；多人本地分屏用 PlayerInputManager 自动分配。

## 音频

```csharp
_source.PlayOneShot(clip);         // 叠加播放(不可被 Stop 打断)
_source.clip = clip; _source.Play();
_source.loop = true;               // BGM
_source.volume / pitch / spatialBlend;
```

分类：BGM 循环、SFX 一次性（PlayOneShot）、UI 音。随机变体：同音效 3-4 clip 随机挑 + pitch ±0.1 防重复感。

## Audio Mixer

Window > Audio > Audio Mixer：分组（BGM/SFX/UI）控音量与效果（Echo/Lowpass）；音量存档：

```csharp
mixer.SetFloat("BGMVolume", LinearToDb(volume01));   // 线性 0~1 → 分贝
PlayerPrefs.SetFloat("BGMVolume", volume01);
```

## 自适应音乐（Adaptive Music）

- **Snapshot 切换**：战斗/探索/菜单三套 Snapshot，`mixer.TransitionToSnapshots` 平滑过渡（紧张感关键）
- **垂直分层（stems）**：BGM 拆鼓/贝斯/旋律轨，战斗强度提升时鼓轨音量 +12dB
- **水平分段**：Intro→Loop→Outro 三段拼接，无缝循环用 `AudioSource.PlayScheduled` 精确排程
- 触发器：`mixer.TransitionToSnapshots(new[] { snapshot }, new[] { 1f }, 0.5f);`

## 坑（现象 → 原因 → 解法）

1. PlayOneShot 后无法停止 → 独立通道不受 Stop 控制 → 需可打断音效改 `clip + Play()`
2. 双相机报错 → 场景两个 AudioListener → 仅 Main Camera 保留一个
3. 枪声连发削波 → 同 clip 叠加相位重叠 → pitch 随机化
4. 手柄改键后重启失效 → 只改了内存 → `SaveBindingOverridesAsJson` 持久化并启动加载
5. 移动端短音效延迟 → 压缩格式解码慢 → 短音效 Decompress On Load、长 BGM Streaming

## 相关文件

- 脚本核心（旧 Input 示例说明）：`references/01-scripting-core.md` · UI 焦点导航：`references/08-ui.md` · 手感音效：`references/16-game-feel.md`

## 文档速查

- Input System 包：https://docs.unity3d.com/Packages/com.unity.inputsystem@latest
- Audio Mixer：https://docs.unity3d.com/6000.5/Documentation/Manual/AudioMixer.html
- AudioSource API：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/AudioSource.html
