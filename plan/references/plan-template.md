# 计划模板（docs/plan.md）

`wf.py` 解析这个格式：`## 背景/约定/共享接口/错误策略/检查` 五节会进入每个任务包；
任务用 `### Txx 标题`。其余小节（架构、风险）只给人和规划者看。

````markdown
# <项目名> 计划

来源: docs/brief.md（或一句话目标）

## 背景
两三句话：做什么、给谁用、入口是什么。worker 只靠这段理解全局。

## 架构
| 文件 | 职责 | 对外接口 |
|---|---|---|
| src/app/cli.py | 解析参数、调用 core、打印结果 | main(argv) -> int |
| src/app/core.py | 纯计算 | summarize(rows) -> Summary |

```mermaid
flowchart LR
  cli --> core --> cli
```
（图可选；文件表必需。）

## 约定
- 语言/版本/依赖：Python 3.11，仅标准库
- 运行方式：`python -m app.cli <args>`；测试：`python -m unittest`
- 代码组织：按上表放文件；不建 utils/helpers；单文件超过约 300 行就停下来报告
- 风格：沿用仓库现有风格；不重排无关代码

## 检查
每个任务 verify 时都会自动运行（由 guardrails 建立；没有就省略这一节）。
```bash
uv run ruff check .
```

## 共享接口
跨任务使用的类型与签名只在这里定义一次。任务按名称引用，不得修改。

术语（来自简报）：
- 收据（Row）：CSV 中的一行，不包括表头
```python
@dataclass(frozen=True)
class Row:
    name: str
    amount: int

def parse_rows(text: str) -> list[Row]: ...
def summarize(rows: list[Row]) -> dict[str, int]: ...
```

## 错误策略
只处理下面列出的失败；其他异常直接抛出，不捕获、不兜底、不重试。
| 失败 | 在哪一层处理 | 表现 |
|---|---|---|
| 输入行格式错误 | parse_rows 抛 ValueError(行号)；cli 捕获 | stderr 一行错误、退出码 2 |

## 风险与探针
（没有就写“无”。）未验证且一旦不成立就会让路线作废的假设 → 由哪个 probe 任务先验证。
关键的第三方 API 写上出处：官方文档链接 + 版本，或“本机实测”。

## 任务

（文件末尾可以有“变更记录”和“裁定记录”两节，由 change 和 build 追加。）

### T01 端到端骨架：<最小可运行的完整链路>
- [ ] 完成
依赖: 无
文件: src/app/cli.py(新增), tests/test_cli.py(新增)
接口: 提供 main(argv)
阅读: （可选）施工前要先读的现有文件，例如 src/app/core.py
要点:
- 3-6 条，写清算法、关键调用和数据流向；需要时给出关键代码片段
验证:
```bash
python -m unittest tests.test_cli -v
```
完成标准: 一句可观察的结果，例如“对样例输入打印 {...}”

### T02 ...
````

## 规则速查

- **验证命令**必须断言内容（单元测试、`python -c "assert ..."`），不能只看退出码或文件存在。
  每行一条命令，按顺序运行，遇到失败就停。以 `python` 开头的命令由 wf 换成当前解释器；不用 grep/sed 等
  bash 工具，`python -c` 用双引号，这样同一份计划在 Windows、macOS、Linux 上都能跑。
- 没有依赖关系的任务不要写依赖，“文件”尽量不重叠，build 可以并行施工。
- **文件**字段列出本任务会创建或修改的全部文件（含测试），最多 4 个。
- **阅读**字段（可选）列出要先读、但不修改的现有文件。worker 只读这些文件和“文件”里的文件。
- 标题含“里程碑”的任务完成后，总控会用 brief 的验收样例跑一次端到端检查。
- 不写 TBD/TODO/待定/“适当处理”/“依此类推”；`wf.py lint` 会把这些当作错误。
