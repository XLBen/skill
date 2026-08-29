# 2D 卡牌游戏（Card / 肉鸽卡牌）

## Contents
- 系统拆解 · 牌堆系统 · 卡牌数据 · 出牌结算 · 特有技巧 · 坑 · API 速查

## 核心系统拆解

牌库构建 → 抽牌堆/手牌/弃牌堆 → 出牌结算（费用/目标/效果）→ 回合制 → （肉鸽）局外收集

## 牌堆与抽牌（核心代码）

```csharp
// 文件: Assets/Scripts/Card/DeckSystem.cs
private List<CardInstance> _drawPile = new();
private List<CardInstance> _hand = new();
private List<CardInstance> _discardPile = new();
private System.Random _rng;                  // Awake: _rng = new System.Random();

public void ShuffleDeck()
{
    // Fisher-Yates 洗牌
    for (int i = _drawPile.Count - 1; i > 0; i--)
    {
        int j = _rng.Next(i + 1);
        (_drawPile[i], _drawPile[j]) = (_drawPile[j], _drawPile[i]);
    }
}

public CardInstance Draw()
{
    if (_drawPile.Count == 0)               // 抽牌堆空: 弃牌堆洗回
    {
        _drawPile.AddRange(_discardPile);
        _discardPile.Clear();
        ShuffleDeck();
        if (_drawPile.Count == 0) return null;   // 两堆皆空(防死循环)
    }
    var card = _drawPile[0];
    _drawPile.RemoveAt(0);
    _hand.Add(card);
    return card;
}

public void EndTurn()
{
    _discardPile.AddRange(_hand);           // 回合结束手牌全弃
    _hand.Clear();
}
```

## 卡牌实例与数据（数据/实例隔离）

```csharp
[CreateAssetMenu(menuName = "Game/CardData")]
public class CardData : ScriptableObject
{
    public string cardName;
    public int cost;
    public CardType type;            // 攻击/技能/能力
    public EffectData[] effects;     // 数据驱动效果
}

public class CardInstance            // 运行时实例(强化次数等),不污染 ScriptableObject
{
    public CardData data;
    public int upgraded;
}
```

## 出牌结算（效果器模式）

```csharp
public bool TryPlayCard(CardInstance card, ITarget target)
{
    if (_energy < card.data.cost) return false;
    _energy -= card.data.cost;
    foreach (var e in card.data.effects) e.Execute(this, target);   // 效果指令列表
    Discard(card);
    return true;
}
```

效果抽象为可执行指令（伤害 X/抽牌 X/加甲 X...），新卡只改数据不改代码——卡牌可扩展性的关键。

## 特有编程技巧

- **Combo 判定**：连续出同类卡计数，出他类清零；连击加成结算时查询计数
- **目标解析器**：指向/全体/随机 N/最弱——策略模式
- **卡牌强化**：局内升级改实例数值（cost-1 / +50%）
- **肉鸽局外**：解锁卡池 ID 存档 → 开局随机组池 → 通关奖励新卡
- **UI 动画**：抽牌插入、弃牌飞回、出牌飞目标；**逻辑先行结算，动画纯表现**
- **悬浮预览**：悬停放大卡牌（独立 UI 层）

## 坑（现象 → 原因 → 解法）

1. 快速操作状态错乱 → 动画与逻辑耦合 → 结算立即执行，动画只播放
2. 卡牌数据被污染 → 直接改资源 → 严格 Instance 隔离
3. 抽牌死循环 → 两堆皆空没判 → Draw 判空返回 null
4. 拖拽误触点击 → 没区分阈值 → 移动距离 > X 像素才算拖拽

**BAD/GOOD 示例（动画与逻辑）：**

```csharp
// BAD: 逻辑等动画播完才结算,连点卡乱
IEnumerator PlayCard() { yield return FlyToTarget(); ApplyDamage(); }

// GOOD: 立即结算,动画并行播放
void PlayCard() { ApplyDamage(); StartCoroutine(FlyToTarget()); }
```

## API 速查

| 类 | 关键成员 |
|---|---|
| `System.Random` | 洗牌随机源 |
| `IDragHandler` | 手牌拖拽 |
| ScriptableObject | CardData/EffectData |
| `LayoutGroup` | 手牌排列（或计算式定位+缓动） |

## 相关文件

- UI：`references/08-ui.md` · 存档（解锁卡池）：`references/13-architecture.md` · 洗牌/RNG：`references/00-techniques.md`

## 文档速查

- IDragHandler（uGUI 包 API）：https://docs.unity3d.com/Packages/com.unity.ugui@2.0/api/UnityEngine.EventSystems.IDragHandler.html
- ScriptableObject：https://docs.unity3d.com/6000.5/Documentation/Manual/class-ScriptableObject.html
