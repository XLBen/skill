# 2D 三消 / 消除类（Match-3）

## Contents
- 系统拆解 · 棋盘数据 · 匹配检测 · 消除-下落-连锁 · 交换合法性 · 特有技巧 · 坑 · API 速查

## 核心系统拆解

网格棋盘（宝石）→ 交换操作 → 匹配检测 → 消除 → 重力下落 → 补充 → 连锁结算

## 棋盘数据结构

```csharp
// 文件: Assets/Scripts/Match3/Match3Board.cs
public class Gem
{
    public int type;                    // 类型 0~5
    public Vector2Int pos;              // 棋盘坐标
    public SpriteRenderer view;         // 池化视图对象
}
private Gem[,] _board;                  // 初始化时避开初始三连(生成时检查左两格/下两格)
```

## 匹配检测（核心算法）

```csharp
public List<Gem> FindMatches()
{
    var matched = new HashSet<Gem>();
    for (int y = 0; y < Height; y++)
        for (int x = 0; x < Width - 2; x++)
            if (_board[x, y].type == _board[x + 1, y].type &&
                _board[x, y].type == _board[x + 2, y].type)
            {
                matched.Add(_board[x, y]); matched.Add(_board[x + 1, y]); matched.Add(_board[x + 2, y]);
            }
    // 纵向同理
    return matched.ToList();
}

// 优化: 交换后只查涉及的两格周边窗口(FindMatchesAround),不扫全盘
```

## 消除 → 下落 → 补充 → 连锁（流程状态机）

```csharp
IEnumerator ResolveRoutine()
{
    while (true)
    {
        var matches = FindMatches();
        if (matches.Count == 0) break;          // 无匹配: 回合结束,查死局
        yield return RemoveGems(matches);       // 消除动画
        yield return ApplyGravity();            // 每列从下往上填空洞
        yield return RefillBoard();             // 顶部补新宝石
    }
}
```

## 交换合法性

```csharp
public bool TrySwap(Vector2Int a, Vector2Int b)
{
    if (!AreAdjacent(a, b)) return false;
    Swap(a, b);
    bool legal = FindMatchesAround(a).Count > 0 || FindMatchesAround(b).Count > 0;
    if (!legal) Swap(a, b);                     // 无效交换: 换回 + 表现动画
    return legal;
}
```

## 特有编程技巧

- **特殊宝石**：4 连 → 条纹宝石（消整行/列）；5 连 → 彩虹宝石（消同色全部）；T/L 形 → 炸弹（检测水平+垂直延伸长度判形状）
- **连击 Combo**：同一 Resolve 循环连锁数计数，倍率递增（×2 ×3...）
- **死局检测**：所有可能交换无匹配 → 重排棋盘直到可解（上限 + 确定性算法）
- **对象池**：宝石频繁创建销毁务必池化；或"视图固定、只换 type/sprite"变体
- **特效队列**：消除粒子/飘字按坐标排队，连锁异步演出不阻塞流程
- **目标关卡**：步数限制/目标分/收集目标独立结算模块

## 坑（现象 → 原因 → 解法）

1. 动画与逻辑不同步 → 并发修改棋盘 → 状态机串行（等消除完再下落）
2. 补新宝石又生三连 → 没循环检测 → while 循环到无匹配为止
3. 交换动画中途再输入 → 无输入锁 → isResolving 标志
4. 死局无限重排 → 无上限 → 重排次数上限 + 重排后校验

**BAD/GOOD 示例（流程控制）：**

```csharp
// BAD: 消除/下落/补充并发执行,棋盘状态错乱
RemoveMatches(); ApplyGravity(); Refill();

// GOOD: 协程串行 + 输入锁
yield return RemoveGems(matches);
yield return ApplyGravity();
yield return RefillBoard();
```

## API 速查

| 类 | 关键成员 |
|---|---|
| 协程 | 流程串行编排 |
| `SpriteRenderer.sprite` | 宝石视图切换 |
| `HashSet<Gem>` | 匹配去重 |
| `System.Random` | 宝石生成（可复现） |

## 相关文件

- 协程：`references/01-scripting-core.md` · 对象池：`references/00-techniques.md` · 手感（连击反馈）：`references/16-game-feel.md`

## 文档速查

- 协程手册：https://docs.unity3d.com/6000.5/Documentation/Manual/coroutines-section.html
- SpriteRenderer：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/SpriteRenderer.html
