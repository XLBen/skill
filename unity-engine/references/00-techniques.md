# 00 游戏通用编程技巧（Unity 6.5）

## Contents
- 对象池 · 状态机 · 相机系统 · 时间控制 · 伤害/Buff · 存档 · RNG · 输入缓冲/手感 · 场景管理 · 其他

跨类型通用的游戏编程技巧。所有代码面向 Unity 6.5（新 API 命名），2D 优先。

## 对象池 Object Pool

`Instantiate`/`Destroy` 频繁调用会产生 GC 和卡顿。弹幕、敌人、粒子、UI 飘字必须用对象池。现成模板见 `assets/templates/ObjectPool.cs`（含 `IPoolable` 接口约定 `OnSpawn/OnDespawn`）。

```csharp
// 用法示例（模板实现见 assets/templates/ObjectPool.cs）
var pool = new ObjectPool<Bullet>(bulletPrefab, prewarmCount: 32, parent: transform);
Bullet b = pool.Get();       // 自动 OnSpawn
pool.Return(b);              // 自动 OnDespawn(重置状态) 后隐藏
```

要点：预热（prewarm）避免首帧卡顿；回收时重置状态（速度、颜色、计时器）。

## 状态机 FSM

玩家（待机/跑/跳/攻击）、敌人（巡逻/追击/攻击/死亡）都适合状态机。三种实现：

1. **Animator 状态机**：动画驱动场景，逻辑放 StateMachineBehaviour，纯逻辑用 2/3
2. **枚举 + switch**：状态 <6 时最简单
3. **类状态机**（推荐，可扩展）：模板见 `assets/templates/StateMachine.cs`

```csharp
// 使用: 每状态一个类,跨状态共享参数放上下文
stateMachine.SwitchTo(_attackState);
stateMachine.Update();      // 驱动当前状态
```

## 相机系统（2D）

- 跟随：相机逻辑放 `LateUpdate`，`Vector3.Lerp`/`SmoothDamp` 平滑；移动方向预留视距（look-ahead）
- 死区：目标偏离屏幕中心超阈值才移动；生产项目直接上 Cinemachine（Follow + 死区/软边界，Confiner 限房间，见 `references/99-doc-index.md`）
- 震屏：Cinemachine Impulse（推荐）或手写（见 `references/16-game-feel.md`）
- 2D 相机用正交投影；像素风设 PixelPerfectCamera；分辨率适配见 `references/08-ui.md`

## 时间控制

- 暂停：`Time.timeScale = 0`；恢复 `= 1`。注意 Update 的 deltaTime 变 0，FixedUpdate 不受影响
- 慢动作：`Time.timeScale = 0.3f`
- 被暂停也要运行的逻辑：`Time.unscaledDeltaTime` / `Time.realtimeSinceStartup` / `WaitForSecondsRealtime`
- 帧率无关：速度 `* Time.deltaTime`；瞬时事件（跳跃）只需 Update 检测一次
- 物理帧：默认 `Time.fixedDeltaTime = 0.02`（50Hz），可在 Project Settings > Time 调 60Hz

## 伤害 / Buff 系统（数据驱动）

ScriptableObject 存数据、MonoBehaviour 做逻辑（结构见 `references/13-architecture.md`）。结算规则：先算 Add 类再算 Multiply 类；同名 Buff 刷新时长（不可叠加）或加层数（可叠加），规则必须明确定义。

## 存档系统（含版本迁移）

- `PlayerPrefs`：仅极小数据（设置、最高分），存注册表不适合大存档
- `JsonUtility`：内建、无依赖；不支持字典/多态
- 路径：`Application.persistentDataPath` 跨平台
- **Schema 版本迁移**：存档结构变更时 `schemaVersion` +1，读档时按版本逐级迁移（旧字段补默认值），示例见 `assets/templates/SaveService.cs`
- 退出时（`OnApplicationPause`/`OnApplicationQuit`）与关键节点双保险存档；重要数值加校验和

## RNG 随机

- `UnityEngine.Random`：静态简单场景；`System.Random`：可传种子可复现（地图生成/肉鸽）
- 洗牌 Fisher-Yates；加权随机（掉落表）累加权重查找，数据放 ScriptableObject
- 可复现流程全用同一个 rng 实例（见 `references/17-procedural-gen.md`）

## 输入缓冲 / 手感技巧

- 输入缓冲：按下后 N 秒内仍生效（0.1~0.2s）
- 土狼时间 Coyote time：离开平台后 N 秒内仍可跳（0.08~0.15s）
- 跳高截断：松开跳跃键提前终止上升速度（×0.5）
- 完整手感配方见 `references/16-game-feel.md` 与 `references/genres/2d-platformer.md`

## 场景管理与过场

- 异步加载 + `allowSceneActivation` 控制激活时机；加载界面用真实进度（0~0.9 加载，0.9~1 激活）
- 跨场景常驻：`DontDestroyOnLoad`（挂 GameManager 单例，防重复见 `assets/templates/GameManager.cs`）
- async 版本见 `references/14-async-patterns.md`

## 其他常用

- **延迟调用**：协程 `WaitForSeconds` 优先（`Invoke` 字符串方法名，性能差不建议）
- **安全区域**：移动端刘海屏 `Screen.safeArea`
- **离线收益**：`DateTime.UtcNow` 时间戳差值结算（见 `references/genres/2d-idle.md`）
- **对象查找**：唯一实例用单例；解耦用事件（`assets/templates/EventBus.cs` / `references/13-architecture.md`）

## 相关文件

- 异步：`references/14-async-patterns.md` · 手感：`references/16-game-feel.md` · 生成：`references/17-procedural-gen.md` · 关卡：`references/18-level-design.md`
- 模板：`assets/templates/`（ObjectPool/StateMachine/GameManager/EventBus/SaveService/PlayerController2D）
