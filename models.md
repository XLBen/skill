# 模型分工与已知倾向

分工：**强模型做 grill / plan / build 总控 / review，弱模型只做 worker。**
在 `.opencode/agents/*.md` 的 `model:` 字段里填写，或者在 opencode.json 里覆盖。

| 角色 | 建议 | 原因 |
|---|---|---|
| 主会话（grill、plan、build 总控） | GPT / Gemini / muse 中最强的一个 | 需要做跨模块的决定 |
| worker 子代理 | haiku / ds / glm-flash | 任务卡已经消除了设计决定，只需要按卡片施工 |
| worker-strong 子代理 | 强模型（可以和总控相同） | worker 同一任务失败两次后，总控升级派给它 |
| reviewer 子代理 | 强模型，最好和 worker 不是同一家族 | 同一家族的盲点往往相同 |
| test-author 子代理 | 强模型，最好和施工的 worker 不是同一个 | 它写的接口骨架和契约测试就是别人的验收标准；出题和答题分开 |
| backend-worker / frontend-worker 子代理 | 弱模型（可以和 worker 相同） | 有接口契约时按施工线分工；各自只能看到对应领域的 skill |

## 已知倾向与对策

以下是使用中观察到的倾向，**还没有经过基准测试验证**。跑完 `validation/` 后，请根据实际数据修改这张表。

| 模型 | 倾向 | 本套 skill 的对策 |
|---|---|---|
| GPT 系 | 防御性编程：到处 try/except、类型检查、默认值回退 | 计划只有一节错误策略；worker 有明确的禁止清单；`wf diffcheck` 把每处防御代码列出来，由总控对照错误策略审查 |
| Gemini 系 | 喜欢重写整个文件、顺手重排代码 | worker 规则：不改卡片以外的文件，不重排已有代码；diffcheck 检查越界改动 |
| DeepSeek / GLM | 容易提前宣布“已完成”，或总结测试结果而不贴原文 | 汇报必须包含原始输出；总控亲自运行 `wf verify`，`wf done` 只认验证记录 |
| Haiku | 上下文短，长文档容易漏读 | 任务包只包含背景、约定、共享接口、错误策略和当前卡片；`wf lint` 会提醒超过 80 行的卡片 |
| 所有模型做 grill | 追问无关的维度、被反问带偏，或者把自己的想法塞给用户 | 先只问开放问题、不给推荐，再逐行复述（区分原话和推断），决策时先问用户的标准；用户答不上来时改用文字描述的结果场景让他挑；用户指定的技术先问目的、用后果说明是否合适；禁止主动引入用户没提的要求；岔开的话题放进“停车场” |

## 升级规则（build 里执行）
同一任务：第 1 次失败 → 带错误输出重派 worker；第 2 次前 → 总控先诊断，再带结论重派；
第 3 次 → 改派 worker-strong；还失败 → 不再重派，判断是计划错了还是环境/产品问题。
`needs_context` 不算失败。并行施工时所有 worker 用同一个模型，方便比较。

## 换模型时
- worker 太弱、反复失败：先看卡片是不是还需要它自己做设计决定（这是计划的问题），再考虑换模型。
- 总控太弱：症状是计划的任务卡含糊、共享接口缺失。这时 plan 应该换强模型，而不是给 worker 加规则。

## MCP 和插件
MCP 工具的说明会占用每个看得到它的会话的上下文（Playwright MCP 一个就有 25 个工具），所以由 `skills.py` 按档案开关：
档案里列出的 MCP 在项目里打开，其余能找到的（项目、全局配置）全部关闭；worker 类子代理一律看不到 MCP 工具，
`worker-strong` 保留 context7，reviewer 保留 playwright 和 computer-use。全局配置里的某个服务器要在项目里用，加 `--mcp <名字>`。

| 工具 | 建议 |
|---|---|
| context7（MCP） | backend / frontend / automation / ai 档案自动打开；plan 用它查库的官方文档，减少编造 API |
| playwright（MCP） | frontend / automation 档案；一次性检查优先用 agent-browser 命令行，它不占工具说明 |
| computer-use（MCP） | automation 档案；Electron 程序优先走 agent-browser |
| serena（MCP，可选） | 只在大型已有仓库里按项目手动配置，用 LSP 找符号和引用；小项目不需要 |
| GitHub MCP | 不建议，工具太多；用 `gh` 命令行 |
| 代码执行类 MCP（如 code-runner） | 和 bash 重复，不需要 |
| 插件 opencode-dcp | 适合长时间的 build 会话，可以保留 |
| 插件 orchestrator / subtask2 / goal 一类 | 会自己派子代理或自动继续，和 build、wf 的流程重叠；在用本工作流的项目里建议关掉 |
| 插件 sandbox / devcontainers | 无人值守长跑时建议打开，再配合 `--auto` |

