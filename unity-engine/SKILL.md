---
name: unity-engine
description: Use when developing Unity 2D games (Unity 6 / 6000.x): MonoBehaviour scripts, GameObject, Sprite, Tilemap, Rigidbody2D, Collider2D, Animator, URP 2D, Light 2D, UI, Input System, editor tooling (MenuItem), prefabs, scenes, builds, performance, and game-genre patterns (platformer, top-down, card, tower defense, match-3, fighting, idle...). Provides engine rules, curated Chinese references, and prebuilt editor-bridge scripts. Use ONLY for Unity projects; not for 3D, HDRP, VR, or netcode-heavy work.
compatibility: Unity 6.5 (6000.5)
license: MIT
metadata:
  unity-version: "6000.5"
  language: "zh-CN"
---

# Unity 6 2D 游戏开发 Skill

**成果声明**：本 skill 帮助你在 Unity 6（6000.x）项目中写出可直接编译、遵循引擎规则的 2D 游戏代码，并把可视化编辑器操作转成可执行脚本。内容以 6000.5 官方英文文档为基线，按项目实际版本自适应。

## 何时使用 / 何时不用

**使用**：编写/修改/调试 Unity 项目（尤其 2D）的 C# 脚本、场景、Prefab、UI、输入、Tilemap、动画、性能优化，以及需要编辑器自动化（批量资源处理、场景搭建）时。

**不用**：纯 3D / HDRP / VR / 联机为主的项目（本库 UI、架构、技巧类文件仍可参考，引擎 API 部分请改用对应版本文档）；非 Unity 项目；纯美术/策划文档写作。

## 0. 项目检测与版本适配（新任务开始时执行）

1. **确认 Unity 项目**：当前目录存在 `Assets/` 与 `ProjectSettings/ProjectVersion.txt`。没有则先问用户项目路径。
2. **读版本**：`ProjectVersion.txt` 里的 `m_EditorVersion`（如 `6000.5.8f1`）决定文档 URL 用 `https://docs.unity3d.com/<大.小>/...`（如 `6000.5`）。项目版本 ≠ 6000.5 时，动态替换本库所有 URL 中的版本段。
3. **读包版本**：`Packages/manifest.json` 确认已装包及版本（inputsystem、2d.animation 等），建议 API 时以实际版本为准。
4. **工具通道**：若项目配置了 Unity MCP，优先用 MCP 工具操作编辑器；没有则用第 5 节 Editor 桥接脚本。
5. **编译验证**：命令行可用 `Unity.exe -batchmode -quit -projectPath <项目> -executeMethod <静态方法>` 验证编译；否则提示用户在 Editor 中编译。
6. **宣布结果**：明示检测到的版本与即将读取的文件，例："检测到 Unity 6000.5，读取 `references/04-2d-physics.md` 与 `genres/2d-platformer.md`"。

**版本差异须知**：本库按 6000.5 编写；6000.0 LTS 项目个别 API（如 `linearVelocity` 命名已一致）与 2022.3 项目（旧 `velocity`/`drag` 命名、Input System 需手动启用）有差异，涉及时先查对应版本文档再写。

## 1. 工作流（可复制清单）

```
任务清单：
- [ ] 1. 项目检测与版本适配（§0）
- [ ] 2. 按 §6/§7 分发索引读取本地参考文件（宣布读了什么）
- [ ] 3. 细节不足 → webfetch 官方文档（§2；404 则回退对应 landing 页）
- [ ] 4. 写代码（遵循 02 规范与 §9 输出模板；用 Unity 6 新 API 命名）
- [ ] 5. 验证（§0.5 编译验证 / 改场景与 Prefab YAML 前先列修改清单请用户确认）
- [ ] 6. 需要 Editor 操作 → 用 §5 预置脚本或现场生成 Editor 脚本
```

- **同一会话后续请求**：不重读 SKILL.md 本体，直接按需读参考文件；任务切换领域时改读对应文件。
- **验证闭环**：生成代码后必须给出验证方式（编译 / 菜单执行 / 场景检查）；失败则修后重验。

## 2. 官方文档 URL 构造规则

- 手册：`https://docs.unity3d.com/<版本>/Documentation/Manual/<主题>.html`
- 脚本 API 类页：`https://docs.unity3d.com/<版本>/Documentation/ScriptReference/<类名>.html`
- 成员页：`https://docs.unity3d.com/<版本>/Documentation/ScriptReference/<类名>.<成员>.html`
- 命名空间：`https://docs.unity3d.com/<版本>/Documentation/ScriptReference/<命名空间>.html`
- 包文档：`https://docs.unity3d.com/Packages/com.unity.<包名>@<版本或latest>/`
- 完整索引见 `references/99-doc-index.md`；抓取 404 时从其 landing 页找正确链接。

## 3. 铁律（违规直接返工）

1. MUST：不在构造函数里访问 Unity 对象/组件。初始化放 Awake/Start/OnEnable。
2. MUST：UnityEngine.Object 判空用 `== null` 或 `if (obj)`；`?.`/`??` 不识别其假 null 重载。
3. MUST：引用优先 Inspector 序列化字段（`[SerializeField] private`）；`Find*` 系列仅初始化时用一次。
4. MUST：不手写 `.meta` 的 GUID；移动/重命名文件用 Unity 或 `AssetDatabase.MoveAsset`。
5. MUST：改 `.unity`/`.prefab` YAML 前先备份并列出修改清单；能用 Editor 脚本的不用手改。
6. MUST：运行时只修改实例数据，不写 prefab/ScriptableObject 资源字段（污染项目资产）。
7. SHOULD：连续运动用 `Time.deltaTime`；物理移动放 FixedUpdate；销毁用 `Destroy`（帧末），`DestroyImmediate` 仅编辑器脚本。
8. SHOULD：高频生成用对象池；热路径避免字符串拼接、LINQ、每帧 Find/`Camera.main`。
9. 生命周期顺序：Awake（同对象组件可靠）→ OnEnable → Start → FixedUpdate → Update → LateUpdate（跟随相机）。
10. `Time.timeScale` 影响 Update 的 deltaTime 与 WaitForSeconds，不影响 fixedDeltaTime 与 realtimeSinceStartup；不受暂停影响的等待用 `WaitForSecondsRealtime`。

**高频坑 TOP10 速查**（细节见各文件"坑"节）：① 每帧 Find* ② 直接改 prefab 资源 ③ 忘取消事件订阅 ④ 协程里死循环无 yield ⑤ 物理移动写 Update ⑥ UI 同 Canvas 混动静元素 ⑦ 忘设 CompositeCollider2D 8 脚本里字符串拼 Text 每帧 new ⑨ `== null` 假 null 误判 ⑩ 包版本号凭记忆乱写。

## 4. 项目文件操作与安全（plan-validate-execute）

- 批量/破坏性操作（批量改导入设置、批量建资源、改场景）先产出**修改清单**（文件路径 + 变更）→ 用户确认 → 再执行（脚本或 Editor 脚本）。
- `.meta` / `Packages/packages-lock.json` 不手动编辑；`manifest.json` 可编辑加依赖（版本号以 Package Manager 实际可用为准，不确定就写 `@latest` 说明）。
- 图片/音频等二进制资源不可直接编辑，改导入设置用 `AssetImporter` API（预置脚本见 `assets/editor-tools/BatchSetSpriteImport.cs`）。
- opencode 在 Unity 项目根目录启动，项目级 skill 放 `<项目>/.opencode/skills/unity-engine/`。

## 5. Editor 桥接与预置工具

agent 无法点击 Unity Editor UI。预置工具放 `assets/editor-tools/`（**执行方式**：把对应 .cs 复制到项目的 `Assets/Editor/` 下，Unity 编译后从菜单运行，**不要**逐字重写进上下文）：

| 文件 | 菜单 | 用途 |
|---|---|---|
| `CreatePlayer.cs` | Tools/UnitySkill/创建玩家 | 一键建玩家（SpriteRenderer+Rigidbody2D+脚本槽位） |
| `BatchSetSpriteImport.cs` | Tools/UnitySkill/批量设置精灵导入 | 批量改 PPU/FilterMode/压缩 |
| `CreateEnemyDataAssets.cs` | Tools/UnitySkill/批量创建敌人数据 | 按清单批量生成 ScriptableObject 资源 |
| `SetupTilemapScene.cs` | Tools/UnitySkill/搭建 Tilemap 场景 | 建 Grid+3 层 Tilemap+碰撞合并 |

其他可视化操作现场生成 Editor 脚本（规范见 `references/10-editor-scripting.md`）。

## 6. 主题分发索引（触发短语 → 读什么 → 何时读）

| 主题 | 触发短语 | 读 | 何时读 |
|---|---|---|---|
| 生命周期/组件/协程 | "Awake/Start/Update 顺序""协程怎么写" | `references/01-scripting-core.md` | 写脚本前 |
| 命名/序列化 | "SerializeField""怎么序列化" | `references/02-csharp-conventions.md` | 定义字段时 |
| 精灵/排序/图集 | "Sprite 排序""图集""像素风" | `references/03-2d-sprite.md` | 涉及渲染顺序时 |
| 2D 物理 | "碰撞""触发器""Rigidbody2D" | `references/04-2d-physics.md` | 物理交互时 |
| Tilemap | "Tilemap""瓦片""Rule Tile" | `references/05-tilemap.md` | 关卡搭建时 |
| 动画 | "Animator""帧动画""骨骼" | `references/06-2d-animation.md` | 做动画时 |
| 渲染/光照 | "2D 光照""URP""后处理" | `references/07-render-2d.md` | 渲染相关时 |
| UI | "UI""血条""屏幕适配" | `references/08-ui.md` | 做界面时 |
| 输入/音频 | "Input System""手柄""音效" | `references/09-input-audio.md` | 接入输入/音频时 |
| 编辑器扩展 | "MenuItem""批量处理资源" | `references/10-editor-scripting.md` | Editor 自动化时 |
| 场景/预制体/包 | "LoadScene""Prefab""装包" | `references/11-scene-prefab-package.md` | 场景切换/装包时 |
| 性能 | "卡顿""Profiler""合批" | `references/12-performance-2d.md` | 优化时 |
| 架构/存档 | "GameManager""事件解耦""存档" | `references/13-architecture.md` | 搭框架时 |
| 异步 | "async/await""加载不卡 UI" | `references/14-async-patterns.md` | 异步需求时 |
| 对话 | "对话系统""剧情分支" | `references/15-dialogue.md` | 做剧情时 |
| 手感 | "打击感""震屏""顿帧" | `references/16-game-feel.md` | 调手感时 |
| 程序化生成 | "随机地图""地牢生成""噪声" | `references/17-procedural-gen.md` | 生成内容时 |
| 关卡设计 | "关卡节奏""白盒" | `references/18-level-design.md` | 设计关卡时 |
| 通用技巧（对象池/状态机/相机/RNG） | "对象池""状态机""相机跟随" | `references/00-techniques.md` | 任何主题的基础 |
| 官方文档 URL | "查文档""这个 API 的参数" | `references/99-doc-index.md` | 需要官方细节时 |

## 7. 游戏类型分发（用户提到类型时读取）

| 类型 | 文件 |
|---|---|
| 平台跳跃/横版动作 | `references/genres/2d-platformer.md` |
| 银河城 | `references/genres/2d-metroidvania.md` |
| 俯视角射击/双摇杆/Rogue | `references/genres/2d-topdown-shooter.md` |
| 回合制 RPG/JRPG | `references/genres/2d-rpg-turnbased.md` |
| 卡牌/肉鸽卡牌 | `references/genres/2d-card.md` |
| 棋牌/回合制对战 | `references/genres/2d-board-chess.md` |
| 三消 | `references/genres/2d-match3.md` |
| 塔防 | `references/genres/2d-tower-defense.md` |
| 类吸血鬼幸存者 | `references/genres/2d-survivor-like.md` |
| 格斗 | `references/genres/2d-fighting.md` |
| 跑酷 | `references/genres/2d-runner.md` |
| 放置/挂机 | `references/genres/2d-idle.md` |
| 视觉小说/文字冒险 | `references/genres/2d-visualnovel.md` |
| 生存建造（泰拉瑞亚类） | `references/genres/2d-survival-craft.md` |

## 8. 组合规则（多文件任务）

- 加载顺序：引擎文件（API 归属）→ 学科文件（通用概念/算法）→ 类型文件（结构编排）→ 技巧文件（跨类型实现细节）。
- 所有权：引擎文件负责 API 与语法；学科文件（14-18）负责概念与算法；genre 文件负责系统拆解与编排，链接而不重讲基础。
- 冲突时以官方文档为准（§2 现场抓取验证）。

## 9. 输出格式模板（交付代码时）

```markdown
文件：Assets/Scripts/Player/PlayerController.cs
依赖包：无 / com.unity.inputsystem（已装？）
说明：一句话用途

[代码块：完整可编译的类，关键行中文注释，无伪代码]

验证：Editor 菜单 Tools/xxx 执行 / 挂到 Player 对象按 Play 测试
```

## 10. 术语表（全文统一使用）

| 统一术语 | 不再使用 |
|---|---|
| Prefab（预制体） | 预设 |
| ScriptableObject | SO 数据、脚本化对象 |
| 协程 Coroutine | 协同程序 |
| 触发器 Trigger | 扳机（仅指输入扳机时除外） |
| Sorting Layer（排序层） | 层渲染顺序 |
| `linearVelocity`（Unity 6） | `velocity`（标注为旧版） |
| 图集 Sprite Atlas | 图集纹理、atlas |

## 11. 示例对照（worked examples）

| 用户请求 | 读取 | 输出 |
|---|---|---|
| "写个玩家移动脚本" | 01 + genres/2d-platformer | PlayerController2D（模板参考 `assets/templates/`） |
| "帮我搭一个 Tilemap 关卡" | 05 | Tilemap 设置步骤 + `assets/editor-tools/SetupTilemapScene.cs` |
| "敌人怎么索敌攻击" | 04 + 00（状态机） | Enemy AI 状态机 + OverlapCircle 索敌 |
| "游戏卡顿怎么查" | 12 | Profiler 排查流程 + 合批检查清单 |
| "做一套卡牌抽牌系统" | genres/2d-card | 牌堆/抽牌/弃牌系统代码 |
| "怎么批量把 100 张图设成精灵" | 10 + assets/editor-tools | BatchSetSpriteImport.cs 使用说明 |

## 12. 回复原则

- 代码用 Unity 6 API（新命名），注释与说明中文，标识符英文。
- 提供代码时注明文件路径、依赖包与验证方式（§9）。
- 修改场景 YAML 或删除资源前先列清单请用户确认。
- 不确定的 API 行为不猜，按 §2 抓官方文档确认。
