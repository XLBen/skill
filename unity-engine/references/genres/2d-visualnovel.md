# 2D 视觉小说 / 文字冒险（Visual Novel）

## Contents
- 核心系统拆解
- 剧本与演出层
- 存档与快进
- 特有技巧
- 坑与速查

## 核心系统拆解

剧本（对话+分支）→ 演出（立绘/背景/转场）→ 变量系统（好感度/旗标）→ 存档/快进/回看

## Unity 实现要点

- 对话引擎：`references/15-dialogue.md` 的节点图 + 条件变量；复杂叙事用 Ink/Yarn Spinner
- 立绘：SpriteRenderer 或 UI Image 分层（背景层 < 立绘层 < 前景特效层 < UI 层），切换用淡入淡出协程
- 演出：立绘移动/缩放/表情切换、背景横移、转场（黑幕/白闪/溶解 Shader）

## 演出层（表现与逻辑分离）

```csharp
// 演出指令队列: 剧本节点里带演出标记,由演出器执行
public class StageDirector : MonoBehaviour
{
    [SerializeField] private SpriteRenderer _bg;
    [SerializeField] private List<SpriteRenderer> _characters;   // 立绘槽位

    public IEnumerator PlayStageCommand(StageCommand cmd)
    {
        switch (cmd.type)
        {
            case StageType.FadeBg:      // 背景淡换
                yield return FadeSwap(_bg, cmd.sprite, cmd.duration);
                break;
            case StageType.MoveChar:    // 立绘平移(进场/退场)
                yield return MoveTo(_characters[cmd.slot], cmd.pos, cmd.duration);
                break;
            case StageType.Transition:  // 转场黑幕
                yield return FadeTransition(cmd.duration);
                break;
        }
    }
}
```

演出指令放剧本数据里（节点带 `List<StageCommand>`），作家在数据层编排，不改代码。

## 变量与分支（影响结局）

```csharp
public class VNState
{
    public Dictionary<string, int> flags = new();   // 旗标
    public int[] affection = new int[4];            // 各角色好感度
    public int route;                               // 当前路线
}
```

- 选项显示条件：`affection[0] >= 5` 类表达式（解析器或 switch）
- 结局判定：终章按变量走不同结局节点
- 好感度变化用事件通知 UI（小爱心飘出等演出）

## 存档 / 快进 / 回看

- **存档**：当前节点 id + VNState 全量 + 已读历史索引。SL 是 VN 刚需，存档点设计成"任意对话行可存"
- **快进**：只显示已读文本（`_readHistory.Contains(nodeId)` 判断），未读段正常速度——标准 VN 体验
- **回看 Backlog**：历史列表（文本+说话人），点击跳回（只回看不可改分支，或允许重选分支）

## 特有技巧

- **自动模式**：定时推进（读取速度/文本长度计时），点击/按键退出自动
- **语音同步**：按字符推进音（嘟嘟声）或整段语音（AudioSource，行末停止）
- **表情切换**：立绘 sprite 图集按表情换（Sprite Library 换装系统也可复用，见 `references/06-2d-animation.md`）
- **文本效果**：富文本颜色/渐隐、震动、描边（TMP 富文本标签）
- **CG 收集**：CG 图鉴 + 解锁存档（collection 数据）

## 坑（现象 → 原因 → 解法）

1. 快进时演出动画错乱 → 演出协程与文本推进竞速 → 快进时跳过演出指令（只跳文本，演出快进模式用短时长）
2. 读档后分支没生效 → 只存了节点 id → 存档必须含 VNState 全量变量
3. 立绘叠放顺序乱 → 直接用 sprite sortingOrder 魔法数 → 分层槽位约定（槽位即层）
4. 自动模式读太快/太慢 → 固定间隔 → 按文本长度算时长（每字 0.05-0.08s）

## API 速查

| 类 | 用途 |
|---|---|
| `TextMeshProUGUI` | 对话文本（富文本/自动换行） |
| `SpriteRenderer` | 立绘/背景（排序层控制遮挡） |
| `Image`（uGUI） | UI 层元素（对话框/选项按钮） |
| `AudioSource.PlayOneShot` | 语音/音效 |
| 协程 | 演出/转场时序 |

## 相关文件

- 对话系统：`references/15-dialogue.md`
- UI：`references/08-ui.md`
- 存档：`references/00-techniques.md`

## 文档速查

- Ink：https://www.inklestudios.com/ink/
- Yarn Spinner：https://docs.yarnspinner.dev/
