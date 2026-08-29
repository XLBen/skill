# 13 游戏架构（Unity 6.5 / 2D 项目）

## Contents
- 分层结构 · GameManager 单例 · 事件解耦 · SO 事件通道 · 数据驱动 · 数据管道（导入） · 存档版本迁移 · 状态管理 · 初始化顺序 · 坑

## 分层结构与目录

```
启动层（Boot 场景: GameManager/音频/对象池/存档）
├── 核心层（游戏规则）
├── 数据层（ScriptableObject 配置）
├── 表现层（动画/特效/UI）
└── 工具层（Editor 扩展）
```

```
Assets/Scripts/{Core,Player,Enemy,UI,Utils}  Assets/Data  Assets/Prefabs
Assets/Scenes  Assets/Art  Assets/Audio  Assets/Editor
```

## GameManager 单例

模板见 `assets/templates/GameManager.cs`（防重复实例 + DontDestroyOnLoad + 全局状态机）。管理器常驻 Boot 场景，子管理器初始化顺序在 GameManager.Start 里显式编排，避免依赖 Script Execution Order（难维护）。

## 事件解耦

```csharp
// 静态事件总线(模板: assets/templates/EventBus.cs)
public static class EventBus
{
    public static event System.Action<int> OnScoreChanged;
    public static void RaiseScoreChanged(int score) => OnScoreChanged?.Invoke(score);
}
// 订阅: OnEnable 订阅, OnDisable 取消(防幽灵引用)
```

UnityEvent 适合 Inspector 可视化绑定（UI 与逻辑）；C# event 适合代码内解耦。

## ScriptableObject 事件通道

```csharp
[CreateAssetMenu(menuName = "Events/IntEvent")]
public class IntEventSO : ScriptableObject
{
    private event System.Action<int> _action;
    public void Raise(int value) => _action?.Invoke(value);
    public void AddListener(System.Action<int> l) => _action += l;
    public void RemoveListener(System.Action<int> l) => _action -= l;
}
```

Inspector 拖拽连线（谁广播/谁监听可视化）。**注意**：SO 静态事件在域重载后残留订阅，OnDisable 记得取消。

## 数据驱动

- 数值全部 ScriptableObject 化（策划调资源不改代码）
- 数值公式集中静态类（伤害 = 攻击 × 倍率 × 暴击...），平衡一处改

## 数据管道（CSV/JSON → ScriptableObject）

```csharp
// Editor 脚本导入管道: CSV 行 → EnemyData 资源
[MenuItem("Tools/MyGame/从 CSV 导入敌人")]
public static void ImportFromCsv()
{
    string[] lines = File.ReadAllLines("Assets/Data/enemies.csv");
    foreach (var line in lines.Skip(1))   // 跳过表头
    {
        var cols = line.Split(',');
        var data = ScriptableObject.CreateInstance<EnemyData>();
        data.maxHealth = int.Parse(cols[1]);
        // ...
        AssetDatabase.CreateAsset(data, $"Assets/Data/Enemies/{cols[0]}.asset");
    }
    AssetDatabase.SaveAssets();
}
```

好处：策划用表格工具批量维护数值，导入脚本保证资源与表格同步；CSV 可进版本管理。

## 存档版本迁移

存档类带 `schemaVersion`；结构变更时 +1，读档按版本逐级迁移（旧字段补默认值）：

```csharp
var data = JsonUtility.FromJson<SaveData>(json);
if (data.schemaVersion == 1) { data.newField = default; data.schemaVersion = 2; }  // 1→2 迁移
```

完整示例（含校验和）见 `assets/templates/SaveService.cs`。时间戳类存档用 UTC（`references/genres/2d-idle.md`）。

## 坑（现象 → 原因 → 解法）

1. 双 GameManager 乱套 → 重复加载 Boot → 单例 Awake 判空销毁（模板已含）
2. 对象销毁后仍被事件调用 → 订阅未取消 → OnEnable/OnDisable 成对订阅取消
3. 切场景引用断链 → 跨场景直接引用 → DontDestroyOnLoad 管理器中转
4. 循环依赖（A↔B） → 编译不过/初始化时序乱 → 事件/接口解耦
5. 存档更新后旧档崩溃 → 无版本迁移 → schemaVersion 逐级迁移

## 相关文件

- 模板：`assets/templates/`（GameManager/EventBus/SaveService/StateMachine/ObjectPool）
- 存档与通用技巧：`references/00-techniques.md` · 对话/任务联动：`references/15-dialogue.md`

## 文档速查

- ScriptableObject 手册：https://docs.unity3d.com/6000.5/Documentation/Manual/class-ScriptableObject.html
- UnityEvent API：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Events.UnityEvent.html
