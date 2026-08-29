# unity-engine — Unity 6.5 2D 游戏开发 Skill（opencode）

面向 Unity 6（6000.x）2D 项目的中文 skill 库：引擎规则 + 精编参考文件 + 游戏类型玩法模式 + 预置 Editor 脚本与 C# 模板。

## 目录结构

```
unity-engine/
├── SKILL.md                  # 主入口（自动触发、铁律、工作流、分发索引）
├── README.md                 # 本文件
├── LICENSE                   # MIT
├── agents/openai.yaml        # Codex 兼容元数据
├── evals/                    # 3 个验收评估场景
├── scripts/                  # 自测脚本（校验 + 链接检查）
├── assets/
│   ├── unity.gitignore       # Unity 项目 .gitignore 模板
│   ├── editor-tools/         # 预置 Editor 菜单脚本（复制到 Assets/Editor/）
│   └── templates/            # C# 代码模板（玩家控制器/对象池/单例/状态机/事件/存档）
└── references/               # 18 个引擎/学科文件 + 99 文档索引 + 14 个游戏类型文件
```

## 安装（项目级）

```powershell
# 方式一：复制到 Unity 项目
Copy-Item -Recurse "本目录\unity-engine" "<Unity项目>\.opencode\skills\"

# 方式二：目录链接（库更新时项目同步生效）
New-Item -ItemType Junction -Path "<Unity项目>\.opencode\skills\unity-engine" -Target "本目录\unity-engine"
```

然后在 **Unity 项目根目录**启动 opencode 并重启。

## 部署后自检

1. 重启 opencode，在 Unity 项目目录提问："写一个 2D 玩家移动脚本"
2. 观察 skill 是否自动触发（回复开头应出现"检测到 Unity <版本>"）
3. 观察是否按需读取了 `references/genres/2d-platformer.md` 而非一次加载全部
4. 若未触发：检查 skill 目录路径是否在 opencode 的扫描范围内；或改全局注册（opencode.json `skills.paths` 指向本库）

## 自测

```powershell
powershell -File scripts/validate-skills.ps1     # 结构/frontmatter/引用一致性/旧API检查
powershell -File scripts/check-doc-links.ps1     # 99-doc-index.md 等文件的 URL 可达性
```

## 版本适配

skill 内容按 6000.5 编写；打开旧版本项目时 SKILL.md §0 会指示按 `ProjectVersion.txt` 动态切换文档 URL。已知差异：2022.3 使用旧 API 命名（`velocity`/`drag`）、Input System 需手动启用。

## License

MIT
