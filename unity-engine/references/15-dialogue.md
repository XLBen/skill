# 15 对话系统（Unity 6.5）

## Contents
- 数据模型与来源（ScriptableObject/JSON/Ink）
- 对话运行时（逐字显示/选项分支）
- 分支与条件（变量/好感度）
- 与任务/事件系统联动

## 数据模型

对话数据核心是节点图：`节点 = 文本 + 选项列表 + 后续节点`。

```csharp
[CreateAssetMenu(menuName = "Game/DialogueData")]
public class DialogueData : ScriptableObject
{
    public List<DialogueNode> nodes = new();
}

[System.Serializable]
public class DialogueNode
{
    public string id;                  // 节点唯一 ID（存档/跳转用）
    public string speakerName;
    [TextArea(3, 6)] public string text;
    public List<DialogueOption> options = new();
    public string nextNodeId;          // 无选项时的直连
    public List<DialogueEffect> effects = new();   // 好感+1、给物品...
}

[System.Serializable]
public class DialogueOption
{
    public string label;
    public string nextNodeId;
    public string condition;           // 显示条件表达式（如 "affection>=5"）
}
```

大规模剧本用 JSON/CSV 经 Editor 脚本导入生成上述资源（数据管道见 `references/13-architecture.md`）。分支复杂 + 变量丰富的叙事项目可评估 **Ink**（ink 引擎，com.inkle.ink-unity-integration）或 **Yarn Spinner**（com.yarnspinner.unity），两者都适合视觉小说。

## 运行时（逐字显示 + 选项）

```csharp
public class DialogueRunner : MonoBehaviour
{
    [SerializeField] private DialogueData _data;
    [SerializeField] private TextMeshProUGUI _textUI;
    private int _nodeIndex;
    private Coroutine _typing;

    public void StartDialogue()
    {
        _nodeIndex = 0;
        ShowNode(_data.nodes[0]);
    }

    void ShowNode(DialogueNode node)
    {
        _typing = StartCoroutine(TypeText(node.text));
        // 清空选项 UI,生成选项按钮(onClick → ShowNodeById(option.nextNodeId))
    }

    IEnumerator TypeText(string full)
    {
        _textUI.text = "";
        foreach (char c in full)
        {
            _textUI.text += c;                       // 逐字;量大时用 StringBuilder + 间隔写入
            yield return new WaitForSeconds(0.03f);
        }
    }

    // 点击文本: 未打完 → 立即显示全文;打完 → 走 nextNodeId
    public void OnTextClicked()
    {
        if (_typing != null) { StopCoroutine(_typing); _textUI.text = /* 全文 */; _typing = null; }
        else Advance();
    }
}
```

## 条件与变量

- 全局变量存 `DialogueState`（好感度、已触发旗标），选项显示条件用表达式解析（简单场景 switch/字典硬编码，复杂场景引入表达式解析器）
- 节点效果（effects）在进入节点时执行：`DialogueState.affection += 1`、`Inventory.Add(itemId)`、触发事件
- 节点重复对话：`HasSeen(nodeId)` 判断，NPC 重复对话用随机普通句

## 与任务/事件联动

```csharp
[System.Serializable]
public class DialogueEffect
{
    public EffectType type;            // AddAffection / GiveItem / SetFlag / RaiseEvent
    public string key;
    public int value;
}

// 执行
case EffectType.RaiseEvent: EventBus.RaiseDialogueEvent(key); break;
```

任务系统监听对话事件推进任务状态（见 `references/13-architecture.md` 事件解耦）。

## 坑（现象 → 原因 → 解法）

1. 存档后读档对话重头开始 → 只存了节点 id 没存变量状态 → 存档含 DialogueState 全量变量
2. 快速点击逐字动画串字 → 打字协程未停就开下一个 → 切换节点前 StopCoroutine
3. 中文逐字用 `foreach(char)` 每帧拼字符串有 GC → 用 StringBuilder + 间隔写入
4. 对话中玩家还能移动 → 没锁输入 → 对话开始时禁用玩家输入/开对话 UI 遮罩
5. 选项按钮监听重复注册 → 每次显示选项前 RemoveAllListeners

## 相关文件

- UI：`references/08-ui.md`（TextMeshPro）
- 事件解耦：`references/13-architecture.md`
- 视觉小说类型：`references/genres/2d-visualnovel.md`

## 文档速查

- Ink 引擎：https://www.inklestudios.com/ink/
- Yarn Spinner：https://docs.yarnspinner.dev/
- TextMeshPro：https://docs.unity3d.com/Packages/com.unity.textmeshpro@latest
