# 10 Editor 扩展脚本（Unity 6.5）

## Contents
- 组织与原则 · MenuItem · 自动创建资源/场景 · 自定义 Inspector · PropertyDrawer · SceneView/Gizmos · AssetDatabase 批量 · UI Toolkit 编辑器 UI · 常用 API · 坑

编辑器脚本是实现「代码驱动编辑器」的桥梁。全部放 `Assets/Editor/`（或 Editor 平台 asmdef 文件夹），用 `UnityEditor` 命名空间，**运行时代码禁止引用**（打包报错）。预置成品见 `assets/editor-tools/`。

## MenuItem 菜单

```csharp
using UnityEditor;
using UnityEngine;

public static class GameTools
{
    [MenuItem("Tools/MyGame/一键搭场景")]
    public static void BuildScene() { }

    [MenuItem("Tools/MyGame/生成敌人 %#e")]    // %=Ctrl #=Shift &=Alt → Ctrl+Shift+E
    public static void SpawnEnemy() { }

    [MenuItem("GameObject/MyGame/创建玩家", false, 10)]
    public static void CreatePlayer() { }

    [MenuItem("CONTEXT/Rigidbody2D/重置速度")]
    public static void ResetVelocity(MenuCommand cmd)
    {
        ((Rigidbody2D)cmd.context).linearVelocity = Vector2.zero;
    }
}
```

## 自动创建资源与场景

```csharp
var data = ScriptableObject.CreateInstance<EnemyData>();
AssetDatabase.CreateAsset(data, "Assets/Data/Enemies/Goblin.asset");
AssetDatabase.SaveAssets();

PrefabUtility.SaveAsPrefabAsset(go, "Assets/Prefabs/Enemy.prefab");
EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
```

## 自定义 Inspector

```csharp
[CustomEditor(typeof(PlayerController2D))]
public class PlayerController2DEditor : Editor
{
    public override void OnInspectorGUI()
    {
        serializedObject.Update();
        EditorGUILayout.PropertyField(serializedObject.FindProperty("_moveSpeed"));
        if (GUILayout.Button("调试：跳转出生点"))
        {
            var p = (PlayerController2D)target;
            p.transform.position = p.spawnPoint;
        }
        serializedObject.ApplyModifiedProperties();
    }
}
```

## PropertyDrawer（字段级自定义显示）

```csharp
[CustomPropertyDrawer(typeof(MinMaxRange))]
public class MinMaxRangeDrawer : PropertyDrawer
{
    public override void OnGUI(Rect pos, SerializedProperty prop, GUIContent label)
    {
        // 双滑条显示 min/max
    }
}
```

## SceneView / Gizmos

```csharp
[DrawGizmo(GizmoType.Selected)]
static void DrawGizmo(PlayerController2D p, GizmoType t)
{
    Gizmos.color = Color.yellow;
    Gizmos.DrawWireSphere(p.transform.position, p.attackRange);
}
```

## AssetDatabase 批量操作

```csharp
string[] guids = AssetDatabase.FindAssets("t:Sprite", new[] { "Assets/Art" });
foreach (string guid in guids)
{
    string path = AssetDatabase.GUIDToAssetPath(guid);
    var importer = AssetImporter.GetAtPath(path) as TextureImporter;
    if (importer == null) continue;
    importer.spritePixelsPerUnit = 32;
    importer.SaveAndReimport();
}
```

成品脚本：`assets/editor-tools/BatchSetSpriteImport.cs`。

## UI Toolkit 编辑器 UI（EditorWindow 现代化写法）

```csharp
public class MyToolWindow : EditorWindow
{
    [MenuItem("Tools/MyGame/工具窗口")]
    public static void Open() => GetWindow<MyToolWindow>("工具窗口");

    public void CreateGUI()
    {
        var root = rootVisualElement;
        root.Add(new Label("批量工具"));
        var btn = new Button(() => Debug.Log("执行")) { text = "执行批量操作" };
        root.Add(btn);
        // 复杂界面用 UXML/USS(Assets/Editor/*.uxml),比 IMGUI 易维护
    }
}
```

IMGUI（OnGUI）与 UI Toolkit 二选一；新窗口建议 UI Toolkit。

## 常用 API 速查

| 类 | 用途 |
|---|---|
| `Selection` | 当前选中（`Selection.activeObject`） |
| `EditorUtility.DisplayDialog` | 弹窗 |
| `AssetDatabase` | 资源增删改查/刷新 |
| `PrefabUtility` | 预制体实例/嵌套操作 |
| `EditorSceneManager` | 编辑器内场景加载保存 |
| `EditorGUILayout` | Inspector 绘制 |
| `Handles` | SceneView 手柄绘制 |
| `Undo.RecordObject` | 撤销支持（**改序列化数据必须包 Undo**） |

## 坑（现象 → 原因 → 解法）

1. 撤销无效 → 改序列化字段没包 Undo → `Undo.RecordObject(target, "描述")` 后再改
2. 编辑器里 Instantiate 不生效/泄漏 → 用了运行时语义 → 编辑器资源用 DestroyImmediate 销毁
3. 静态字段隔次失效 → 域重载（Domain Reload）重置 → `SessionState` 持久化或 [InitializeOnLoad] 恢复
4. 打包报 UnityEditor 引用 → 运行时代码引了编辑器类 → 隔离到 Editor 程序集
5. 脚本刚写完菜单不出现 → 编译未完成/文件不在 Editor 目录 → 放 Assets/Editor/ 等编译刷新
6. 批量操作无进度反馈 → 卡死无感 → `EditorUtility.DisplayProgressBar` 显示进度

## 相关文件

- 预置脚本：`assets/editor-tools/`（CreatePlayer/BatchSetSpriteImport/CreateEnemyDataAssets/SetupTilemapScene）
- 规范：`references/02-csharp-conventions.md` · 项目文件操作安全：SKILL.md §4

## 文档速查

- 编辑器脚本手册：https://docs.unity3d.com/6000.5/Documentation/Manual/ExtendingTheEditor.html
- MenuItem API：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/MenuItem.html
- AssetDatabase API：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/AssetDatabase.html
