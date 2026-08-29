# 14 异步模式（Unity 6.5）

## Contents
- async/await 基础与陷阱
- 取消令牌 CancellationToken
- 与协程的选型
- UniTask 简介
- 异步场景/资源加载组合

## async/await 基础

Unity 2021+ 支持 C# async/await（Task）。适合：加载资源、网络请求、长计算（配合 Task.Run）。

```csharp
public async void Start()
{
    // 注意: async void 无法被调用方等待,异常会抛到 Unity 主循环
    await LoadConfigAsync();
}
```

**陷阱**：

1. **不要 async void**：除事件处理器外一律用 `async Task`，否则异常无法捕获（现象：偶发崩溃无堆栈 → 原因：async void 异常直接上抛 → 解法：改 Task 并 await）。
2. **continuation 线程**：`await Task.Run(...)` 后默认回到 Unity 主线程（Unity SynchronizationContext），可以安全访问组件；但第三方库可能破坏该上下文，防御写法：

```csharp
private async Task ComputeAsync()
{
    int result = await Task.Run(() => HeavyPureCompute());   // 后台线程
    label.text = result.ToString();                          // 回到主线程
}
```

3. **等待帧**：Task 世界里没有 yield return null 的等价物，用 `await Task.Yield()` 或 `await UniTask.Yield()`（UniTask 包）。
4. **对象销毁后继续执行**：await 返回时组件可能已 Destroy，访问前判空（`if (this == null) return;`）。

## 取消令牌（CancellationToken）

加载耗时操作必须可取消（切场景/关闭 UI）：

```csharp
using System.Threading;

CancellationTokenSource _cts = new();

async void Start()
{
    _cts.Cancel();                 // 取消上一次
    _cts = new CancellationTokenSource();
    try
    {
        await LoadAsync(_cts.Token);
    }
    catch (OperationCanceledException)
    {
        Debug.Log("加载已取消");
    }
}

private Task LoadAsync(CancellationToken token)
{
    return Task.Run(async () =>
    {
        for (int i = 0; i < 100; i++)
        {
            token.ThrowIfCancellationRequested();
            await Task.Delay(20, token);
        }
    }, token);
}
```

`OnDestroy`/`OnDisable` 中 `_cts.Cancel()` 防泄漏。协程无内建取消机制，这也是异步场景推荐 Task 的原因之一。

## 与协程的选型

| 场景 | 用 |
|---|---|
| 逐帧动画/时序编排（攻击演出） | 协程（yield 控制帧级节奏） |
| 加载/网络/长计算 + 取消 | async/await + CancellationToken |
| 混合需要 | UniTask（API 与协程相似、可 await、无 GC、自带取消与超时） |

## UniTask 简介（包: com.cysharp.unitask）

```csharp
await UniTask.Delay(1000);                     // 等价 WaitForSeconds 且无 GC
await UniTask.Delay(1000, cancellationToken: token);
await UniTask.Yield();                         // 等待一帧
await UniTask.WaitUntil(() => hp <= 0);        // 条件等待(协程 WaitUntil 的 Task 版)
await UniTask.Delay(TimeSpan.FromSeconds(2), ignoreTimeScale: true);  // 不受暂停影响
```

需要"协程的帧控制 + Task 的取消/异常"时引入；小项目用内建协程+Task 即可。

## 异步场景/资源加载组合

```csharp
// 异步加载场景 + 进度(详见 references/11-scene-prefab-package.md)
var op = SceneManager.LoadSceneAsync("Level2");
op.allowSceneActivation = false;
while (op.progress < 0.9f) { await UniTask.Yield(); }
await FadeOutAsync();
op.allowSceneActivation = true;
```

## 坑（现象 → 原因 → 解法）

1. 场景切换后 UI 被改 → await 续体在旧对象上执行 → 续体前判 `this == null` 或随对象销毁取消令牌
2. 偶发卡顿 → 把 CPU 密集计算直接 await 在主线程 → `Task.Run` 包后台纯计算（注意别在后台线程碰 UnityEngine API）
3. 内存泄漏 → 等待中的 Task 持引用不释放 → 所有长 Task 挂 CancellationToken 并随生命周期取消

## 相关文件

- 协程基础：`references/01-scripting-core.md`
- 场景加载：`references/11-scene-prefab-package.md`

## 文档速查

- 协程手册：https://docs.unity3d.com/6000.5/Documentation/Manual/coroutines-section.html
- UniTask 包（GitHub）：https://github.com/Cysharp/UniTask
