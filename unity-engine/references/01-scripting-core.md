# 01 脚本核心（Unity 6.5）

## Contents
- 生命周期 · 关键类速查（GameObject/Transform/Time/协程/创建销毁） · 查找与引用 · 2D 常用数学 · 坑

## MonoBehaviour 生命周期（调用顺序）

1. `Awake`：实例化时调用一次；同 GameObject 组件可靠获取时机
2. `OnEnable`：组件启用/对象激活时调用（每次激活都调用）
3. `Start`：首帧 Update 前调用一次
4. `FixedUpdate`：物理步进，默认 0.02s；物理逻辑放这里
5. `Update`：每帧；输入检测、普通逻辑
6. `LateUpdate`：Update 之后；跟随相机放这里
7. `OnDisable` / `OnDestroy`

来源：https://docs.unity3d.com/6000.5/Documentation/Manual/execution-order.html

## 关键类速查

### GameObject / Component / Transform

```csharp
GetComponent<T>()                    // 同 GameObject
GetComponentInChildren<T>()          // 含自身与子对象
TryGetComponent<T>(out var c)        // 无组件返回 false 不报错
GetComponentsInChildren<T>()         // 全部

transform.position / localPosition / rotation / localScale
transform.SetParent(parent, worldPositionStays: false)
gameObject.SetActive(bool)           // 激活/禁用整个对象
gameObject.CompareTag("Player")      // 无 GC 分配,优于 == "Player"
transform.Find("子路径")             // 字符串查找慢,仅初始化用
```

### Time

| 成员 | 说明 |
|---|---|
| `Time.deltaTime` | 上一帧耗时（受 timeScale 影响） |
| `Time.fixedDeltaTime` | 固定物理步长 |
| `Time.timeScale` | 时间缩放（0 = 暂停） |
| `Time.unscaledDeltaTime` | 不受缩放的真实帧耗时 |
| `Time.time` | 缩放后的游戏时间 |
| `Time.realtimeSinceStartup` | 真实时间（暂停也走） |

### 协程 Coroutine

```csharp
yield return null;                        // 下一帧
yield return new WaitForSeconds(1f);      // 缩放后的 1 秒
yield return new WaitForSecondsRealtime(1f);   // 真实 1 秒
yield return new WaitForFixedUpdate();
yield return new WaitUntil(() => hp > 0);
yield return StartCoroutine(Other());     // 等子协程
StartCoroutine(MyRoutine());
StopCoroutine(routine);                   // 传 IEnumerator 引用
StopAllCoroutines();
```

要点：协程附着 MonoBehaviour，组件禁用/对象销毁自动停止；`yield break` 提前结束；异步任务选型见 `references/14-async-patterns.md`。

### 对象创建与销毁

```csharp
Instantiate(prefab, position, rotation, parent);
Destroy(gameObject);                // 帧末销毁
Destroy(gameObject, delaySeconds);
DontDestroyOnLoad(gameObject);
Object.DestroyImmediate(obj);       // 仅编辑器脚本
```

## 查找与引用

- **优先序列化引用**：`[SerializeField] private PlayerStats stats;` Inspector 拖拽
- `GameObject.Find` / `FindObjectOfType` / `FindAnyObjectByType`：仅 Awake/Start 或场景加载时一次；**每帧调用是性能杀手**（MUST）
- 动态生成对象的引用：工厂/事件/单例传递，不用 Find

## 2D 常用数学与移动

```csharp
Vector2.MoveTowards / Lerp / SmoothDamp
Mathf.Clamp / Clamp01 / Lerp / Abs / Sign
Mathf.SmoothDamp(current, target, ref velocity, smoothTime)
Vector2.Angle / Vector3.Cross（判断朝向左右）
```

俯视角移动（物理方式；Input System 版本见 `references/09-input-audio.md`）：

```csharp
void Update()
{
    // 旧 Input 示例简写;新项目用 Input System(见 09)
    Vector2 input = new(Input.GetAxisRaw("Horizontal"), Input.GetAxisRaw("Vertical"));
    input = input.normalized * moveSpeed;     // 归一化防斜向加速
    rb.linearVelocity = input;                // Unity 6 命名(旧版为 velocity)
}
```

## 坑（现象 → 原因 → 解法）

1. 脚本挂在对象上 Awake 里拿不到别的脚本字段 → Awake 只保证同对象组件 → 跨对象依赖放 Start/OnEnable
2. 偶发 MissingReferenceException → Destroy 后到帧末对象仍存在，旧引用未置空 → 销毁同时置 null 或用 `== null` 判断
3. 协程卡死游戏 → while(true) 里没 yield → 循环体必须含 yield
4. 距离判断卡顿 → 每帧 Vector3.Distance 开方 → 比较用 sqrMagnitude
5. 停止协程失败 → 用字符串方法名 StopCoroutine("X") → 传 IEnumerator 引用停止

## 相关文件

- 规范与序列化：`references/02-csharp-conventions.md` · 输入：`references/09-input-audio.md` · 异步：`references/14-async-patterns.md`

## 文档速查

- MonoBehaviour：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/MonoBehaviour.html
- Time：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Time.html
