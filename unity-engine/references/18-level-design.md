# 18 2D 关卡设计（Level Design）

## Contents
- 白盒搭建流程
- 节奏与关卡流
- 引导技巧（教学/提示）
- 难度曲线
- 关卡数据驱动

## 白盒搭建流程

1. **核心玩法先行**：玩家控制器手感完成前不铺关卡（手感决定关卡尺寸：跳高决定墙高、移速决定间距）
2. **白盒**：用纯色方块/基础 Tile 搭布局，只验证空间关系与节奏，不碰美术
3. **指标自检**：每个跳跃间距 = 最大跳距的 60~80%；可行通道宽 ≥ 玩家宽 + 0.5 格
4. **美术替换**：白盒通过后换真素材，保持碰撞轮廓一致

## 节奏与关卡流

- **节奏单元**：紧张段（战斗/追逐）与呼吸段（探索/奖励）交替，约 30~60s 一周期
- **地标**：每屏一个可辨识地标防迷路（2D 尤其重要）
- **奖励节奏**：新机制→练习段→测试段→奖励（经典 4 步，任天堂式关卡设计）
- **检查点密度**：死亡重跑 > 20s 就该加检查点

## 引导技巧

| 技巧 | 说明 |
|---|---|
| 先奖励后危险 | 收集品路径自然引导玩家走安全路线 |
| 危险预告 | 尖刺前放一个静止/闪烁版本 |
| 新机制教学 | 安全环境中强制使用一次（不跳过就过不去） |
| 灯光引导 | URP 2D 光照突出主路径（见 `references/07-render-2d.md`） |
| 敌人站位 | 敌人面向玩家出现，避免背后偷袭教学段 |

## 难度曲线

```csharp
// 跑酷/幸存者类: 速度/密度随时间递增(连续而非阶梯)
speed = baseSpeed + distance * 0.02f;     // 连续递增防断层
```

- 平台类：难度由"输入精度要求 + 判定窗口 + 惩罚"三要素组合，同一关内难度单调上升
- 用数据驱动关卡参数（距离/波次表），策划调数不改代码（见 `references/13-architecture.md`）

## 关卡数据驱动

```csharp
[CreateAssetMenu(menuName = "Game/LevelData")]
public class LevelData : ScriptableObject
{
    public string sceneName;
    public string theme;                 // 主题(森林/火山...)
    public List<string> enemyPool = new();
    public int targetScore;
    public LevelData nextLevel;          // 关卡链
}
```

关卡通配：关卡名/音乐/敌人池/难度参数全部 LevelData 化，新增关卡 = 新建一个资源。

## 坑（现象 → 原因 → 解法）

1. 测试总卡同一跳跃 → 间距 > 最大跳距 → 间距设为最大跳距 60-80%（含起跳平台高度差）
2. 玩家迷路 → 关卡无方向感 → 每屏地标 + 主线视觉引导
3. 教学段玩家跳过导致后面卡死 → 新机制无强制段 → "不掌握过不去"的安全强制教学
4. 后期关卡靠堆怪加难度 → 单调疲劳 → 引入机制组合而非数量

## 相关文件

- 玩家手感：`references/genres/2d-platformer.md`
- 生成式关卡：`references/17-procedural-gen.md`
- 相机视角：`references/00-techniques.md`

## 文档速查

- Tilemap 关卡搭建：https://docs.unity3d.com/6000.5/Documentation/Manual/tilemaps/tilemaps-landing.html
