# 11 场景、预制体、包管理与 Addressables（Unity 6.5）

## Contents
- 场景管理 · Prefab · 包管理 · Addressables · 坑

## 场景管理

```csharp
using UnityEngine.SceneManagement;

SceneManager.LoadScene("Level2");                        // 同步(卡顿)
SceneManager.LoadScene("Level2", LoadSceneMode.Additive);  // 叠加
SceneManager.LoadSceneAsync("Level2");                   // 异步

var op = SceneManager.LoadSceneAsync("Level2");
op.allowSceneActivation = false;                         // 加载完不激活
// op.progress: 0~0.9 加载, 0.9~1 等待激活(到 0.9 停住是正常的)

Scene active = SceneManager.GetActiveScene();
SceneManager.sceneLoaded += OnSceneLoaded;
SceneManager.UnloadSceneAsync("Level2");
```

- 场景必须加入 Build Settings（EditorBuildSettings.scenes）
- 2D 常见结构：Boot 场景（初始化管理器）→ 主菜单 → 关卡 → 过场
- 来源：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/SceneManagement.SceneManager.html

## Prefab 预制体

- 结构：父物体（逻辑）+ 子物体（视觉/碰撞）；变体 Prefab Variant 只覆盖差异（Boss 变体）
- 编辑器修改：实例改动回写资源 `PrefabUtility.ApplyPrefabInstance`；解绑 `PrefabUtility.UnpackPrefabInstance`
- **MUST**：运行时只改实例数据，改 prefab/ScriptableObject 资源字段会污染项目资产（经典事故）

## 包管理 Package Manager

- UI：Window > Package Manager（Unity Registry 装官方包）
- 文件：`Packages/manifest.json` 直接加依赖（**版本号以 Package Manager 实际可用为准，不确定写 `@latest` 后让用户确认**）：

```json
{
  "dependencies": {
    "com.unity.2d.tilemap.extras": "2.4.2",
    "com.unity.inputsystem": "1.11.2"
  }
}
```

- 常用 2D 官方包：2d.animation（骨骼）、2d.psdimporter（PSD）、2d.tilemap.extras（Rule Tile 等）、2d.pixel-perfect、textmeshpro、inputsystem、ai.navigation、cinemachine

## Addressables（异步加载/热更）

- 包 com.unity.addressables；Addressables Groups 窗口标记资源地址
- 适用：大量图集/关卡按需加载（切关加载下一关）、DLC/热更、内存引用计数释放

```csharp
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.AsyncOperations;

public AssetReferenceGameObject enemyPrefab;   // Inspector 拖引用(类型安全)
enemyPrefab.InstantiateAsync(parent);

Addressables.LoadAssetAsync<Sprite>("Sprites/hero").Completed += op =>
{
    if (op.Status == AsyncOperationStatus.Succeeded) _renderer.sprite = op.Result;
};
Addressables.Release(sprite);                  // 引用计数释放,加载必须配对 Release
```

- 场景用 `Addressables.LoadSceneAsync`；不需要热更/超大资源就用传统场景引用（Resources 夹慎用：全载内存、启动扫描慢）

## 坑（现象 → 原因 → 解法）

1. 构建后 LoadScene 黑屏 → 场景没进 Build Settings → 构建列表添加场景
2. 重复加载 Boot 场景出现双 GameManager → 单例未防重 → `assets/templates/GameManager.cs` 的 Awake 判空销毁模式
3. 运行时改 prefab 资源 → 数值永久污染 → 只改实例；需要持久修改用 PrefabUtility（编辑器）
4. Addressables 内存只涨不降 → Release 没配对 → 加载计数与释放一一对应
5. 装包后代码报错找不到类型 → 没编译等待/包版本不兼容 → 等 Unity 解析完成，版本按 manifest 实际可用选

## 相关文件

- 异步加载：`references/14-async-patterns.md` · 单例/事件：`references/13-architecture.md`

## 文档速查

- 场景管理手册：https://docs.unity3d.com/6000.5/Documentation/Manual/CreatingScenes.html
- Prefab 手册：https://docs.unity3d.com/6000.5/Documentation/Manual/Prefabs.html
- Addressables 包：https://docs.unity3d.com/Packages/com.unity.addressables@latest
