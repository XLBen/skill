# 2D 棋牌游戏（Board / Chess / 回合制对战）

## Contents
- 系统拆解 · 坐标工具 · 规则引擎 · 回合流转 · AI（Minimax） · 特有技巧 · 坑 · API 速查

## 核心系统拆解

棋盘网格（坐标系统）→ 棋子 → 规则引擎（合法性校验）→ 回合流转 → （可选）AI → 胜负判定

## Unity 实现要点

- 棋盘：Tilemap 静态棋盘或代码生成；逻辑坐标用 `Vector2Int` 整数网格
- 坐标换算统一工具：

```csharp
// 文件: Assets/Scripts/Board/BoardUtil.cs
public static Vector2Int ToBoard(Vector3 worldPos, float cellSize)
    => new(Mathf.RoundToInt(worldPos.x / cellSize), Mathf.RoundToInt(worldPos.y / cellSize));
public static Vector3 ToWorld(Vector2Int pos, float cellSize)
    => new(pos.x * cellSize, pos.y * cellSize, 0);
```

## 规则引擎（纯 C#，可单测可复用 AI）

```csharp
// 文件: Assets/Scripts/Board/ChessEngine.cs — 不引用 UnityEngine(可单测)
public class ChessEngine
{
    public PieceData[,] board = new PieceData[8, 8];
    public int currentPlayer;

    public List<Vector2Int> GetLegalMoves(Vector2Int from)
    {
        var moves = GeneratePseudoMoves(from);
        moves.RemoveAll(m => !IsLegalAfterMove(from, m));   // 过滤走完被将军的着法
        return moves;
    }

    public bool TryMove(Vector2Int from, Vector2Int to)
    {
        if (!GetLegalMoves(from).Contains(to)) return false;
        ApplyMove(from, to);            // 改棋盘 + 特殊规则(易位/吃过路兵/升变)
        CheckGameOver();
        currentPlayer = 1 - currentPlayer;
        return true;
    }
}
```

## 回合流转与状态

```csharp
public enum GameState { Waiting, PlayerTurn, OpponentTurn, Animating, Checkmate, Draw }
// 动画期间锁输入(Animating),动画回调进下一回合;计时: 每方走棋时钟,超时判负
```

## AI 对手（Minimax + Alpha-Beta 剪枝）

```csharp
// 深度 3~4 对休闲玩家足够;评估函数 = 子力值 + 位置表
// 实现要点: 复制棋盘或走+撤销支持模拟;计算放协程/Task 后台,不卡 UI(见 references/14)
(int score, Move move) AlphaBeta(ChessEngine e, int depth, int alpha, int beta, bool max)
{
    if (depth == 0 || e.IsGameOver()) return (Evaluate(e), null);
    // 递归 + 剪枝,标准实现
}
```

## 特有编程技巧

- **棋类通用框架**：棋盘状态（二维数组）+ 移动生成器 + 规则校验器 + 状态判定器，四模块解耦可复用于象棋/围棋/五子棋/跳棋
- **五子棋胜负**：落子后四方向连子扫描
- **悔棋**：移动历史栈（Undo 按序回滚）；**复盘**：move 序列回放
- **联机回合**（可选）：Netcode for GameObjects 或服务器中继走子消息
- **提示系统**：AI 引擎算一步提示

## 坑（现象 → 原因 → 解法）

1. 规则引擎引 Unity 类无法单测 → 耦合 UnityEngine → 纯 C# + Vector2Int
2. AI 深搜卡 UI → 主线程搜索 → 协程分帧/Task 后台
3. 动画期间重复落子 → 无输入锁 → Animating 状态锁
4. 悔棋后特殊状态错 → 只回滚棋盘 → 移动历史存完整状态快照

**BAD/GOOD 示例（规则与表现分离）：**

```csharp
// BAD: 规则混在 MonoBehaviour 里,AI 无法模拟、无法单测
public class ChessPiece : MonoBehaviour { void OnMouseDown() { /* 校验+移动 */ } }

// GOOD: 规则引擎纯 C#,表现层只做动画与输入转发
if (engine.TryMove(from, to)) StartCoroutine(AnimateMove(from, to));
```

## API 速查

| 类 | 关键成员 |
|---|---|
| `Vector2Int` | 棋盘坐标 |
| `Grid.CellToWorld` | 坐标换算（Tilemap 棋盘） |
| `Task`/协程 | AI 后台计算 |
| Netcode 包 | 联机走子（可选） |

## 相关文件

- 异步（AI 不卡 UI）：`references/14-async-patterns.md` · 回合制同类：`references/genres/2d-rpg-turnbased.md`

## 文档速查

- Vector2Int：https://docs.unity3d.com/6000.5/Documentation/ScriptReference/Vector2Int.html
- Netcode 包：https://docs.unity3d.com/Packages/com.unity.netcode.gameobjects@latest
