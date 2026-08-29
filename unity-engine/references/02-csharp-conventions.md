# 02 C# 编码规范与序列化（Unity 6.5）

## Contents
- 命名规范 · 字段声明 · 序列化规则 · 常用特性 · ScriptableObject · C# 版本 · asmdef · 空引用防御

## 命名规范（遵循 Unity 官方 C# 风格）

| 元素 | 规范 | 示例 |
|---|---|---|
| 类/方法/属性 | PascalCase | `PlayerController`, `Move()` |
| 私有字段 | _camelCase | `private float _moveSpeed;` |
| 局部变量 | camelCase | `int playerCount` |
| 常量 | PascalCase 或全大写 | `const int MaxPlayers = 4;` |
| 接口 | I 前缀 | `IDamageable` |

## 字段声明规范

- Inspector 显示：`[SerializeField] private`（封装 + 可配置）；不推荐 public 字段
- 属性 `{ get; }` 不序列化；组件引用与数值分组，`[Header]`/`[Tooltip]` 分组：

```csharp
[Header("移动")]
[SerializeField] private float _moveSpeed = 5f;
[SerializeField, Range(0f, 100f)] private float _acceleration;
[SerializeField, Tooltip("跳跃高度（米）")] private float _jumpHeight = 2f;
```

## 序列化规则（Inspector 显示 + 场景保存的前提）

**可序列化**：public 字段、`[SerializeField]` 私有字段、`[Serializable]` 自定义类型
**不可序列化**：static、const、readonly、属性、字典、二维数组、委托/事件、object

```csharp
public List<string> tags = new();          // List 可序列化
// public Dictionary<string,int> map;      // 不可!改用 List<KeyValuePair> 或自定义类
```

来源：https://docs.unity3d.com/6000.5/Documentation/Manual/script-serialization.html

## 常用特性（Attribute）

| 特性 | 作用 |
|---|---|
| `[SerializeField]` | 私有字段进 Inspector 并序列化 |
| `[HideInInspector]` | 公有字段隐藏 |
| `[Header("标题")]` / `[Tooltip("说明")]` / `[Space]` | Inspector 排版 |
| `[Range(min,max)]` / `[Min]` / `[Max]` | 数值滑条/边界 |
| `[RequireComponent(typeof(Rigidbody2D))]` | 挂载自动添加组件 |
| `[DisallowMultipleComponent]` | 禁止重复挂载 |
| `[ExecuteAlways]` | 编辑器中也执行 Update |
| `[ContextMenu("方法名")]` | 组件右键菜单调用 |
| `[CreateAssetMenu(menuName = "...")]` | 右键创建 ScriptableObject |
| `[SerializeReference]` | 多态序列化（接口/抽象类引用） |

## ScriptableObject 数据容器

数据与逻辑分离核心工具（武器/敌人/掉落表/任务定义）。好处：资源即数据（热改/复用/版本管理），不同敌人共享同脚本不同资源。**运行时改资源字段会污染项目资产（MUST 避免）**，运行时状态拷贝到实例类。

## C# 版本与语法

Unity 6 支持 C# 9（部分 10）。可用：switch 表达式、模式匹配、目标类型 new、record。IL2CPP 对反射/dynamic 受限，发布前 IL2CPP 构建验证。

## 程序集定义 asmdef

大型项目用 `.asmdef` 拆程序集（核心/UI/工具）：编译快、依赖清晰、防循环引用。创建后文件夹内脚本归入该程序集，跨程序集需添加引用；编辑器专用代码加 Assembly Definition Reference 指向 Editor 平台。

## 空引用与防御

```csharp
// UnityEngine.Object 判空: 用 == null(重载了 operator),被 Destroy 后仍返回 true
if (_target == null) return;
// C# 的 ?. 与 ?? 不识别该重载,对 UnityEngine.Object 链式调用不可靠
```

## 相关文件

- 脚本核心：`references/01-scripting-core.md` · 架构：`references/13-architecture.md` · 编辑器扩展：`references/10-editor-scripting.md`

## 文档速查

- 命名规范（.NET 官方）：https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/naming-guidelines
- ScriptableObject：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/ScriptableObject.html
