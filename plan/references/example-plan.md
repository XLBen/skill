# wordfreq 计划

来源: 用户目标“统计文本文件里出现最多的词，输出 JSON”（已确认，无 brief 文件）

## 背景
命令行工具：`python -m wordfreq <文件> [--top N]`，读取 UTF-8 文本，忽略大小写统计英文单词，
stdout 输出出现次数最多的 N 个词（默认 10）的 JSON。给开发者在终端里用，只有这一个入口。

## 架构
| 文件 | 职责 | 对外接口 |
|---|---|---|
| wordfreq/__main__.py | 参数解析、读文件、打印、退出码 | main(argv) -> int |
| wordfreq/count.py | 纯计算：分词与计数 | count_words(text), top_words(counts, n) |
| tests/test_count.py | count.py 单元测试 | — |
| tests/test_cli.py | 通过子进程调用 CLI 的端到端测试 | — |

## 约定
- Python 3.10+，仅标准库；测试用 unittest
- 运行：`python -m wordfreq <文件>`；测试：`python -m unittest discover -s tests -v`
- 代码组织：严格按上表放文件，不新增模块
- JSON 输出：`json.dumps(obj, ensure_ascii=False)`，单行

## 共享接口
```python
# wordfreq/count.py
def count_words(text: str) -> collections.Counter[str]:
    """小写化后按正则 [a-z']+ 取词计数。"""

def top_words(counts: collections.Counter[str], n: int) -> list[list]:
    """返回 [[词, 次数], ...]：次数降序，次数相同按词升序，最多 n 项。"""
```
CLI 输出格式：`{"top": [["the", 3], ["a", 2]], "total": 5}`，total 为总词数。

## 错误策略
只处理下面列出的失败；其他异常直接抛出，不捕获、不兜底、不重试。
| 失败 | 在哪一层处理 | 表现 |
|---|---|---|
| 文件不存在 | __main__ 捕获 FileNotFoundError | stderr `error: file not found: <路径>`，退出码 2 |
| --top 不是正整数 | argparse 的 type 函数 | argparse 标准错误，退出码 2 |

## 风险与探针
无（只用标准库，本地文件）。

## 任务

### T01 端到端骨架：CLI 读取文件并输出总词数
- [ ] 完成
依赖: 无
文件: wordfreq/__init__.py(新增，空), wordfreq/__main__.py(新增), wordfreq/count.py(新增), tests/test_cli.py(新增)
接口: 提供 count_words、main(argv)
要点:
- count_words：`Counter(re.findall(r"[a-z']+", text.lower()))`
- main：argparse 接收位置参数 path；`Path(path).read_text(encoding="utf-8")` → count_words → 打印 `{"top": [], "total": sum(counts.values())}`；返回 0
- `if __name__ == "__main__": sys.exit(main(sys.argv[1:]))`
- test_cli：在临时目录写入 "The cat. the dog"，子进程运行 `python -m wordfreq <file>`，断言 stdout 解析后 total == 4
验证:
```bash
python -m unittest tests.test_cli -v
```
完成标准: 对样例文件输出 `{"top": [], "total": 4}`

### T02 实现 top_words 与单元测试
- [ ] 完成
依赖: T01
文件: wordfreq/count.py(修改), tests/test_count.py(新增)
接口: 提供 top_words（签名见共享接口）
要点:
- `sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]`，每项转成 list
- 测试：并列次数按词升序；n 大于词数时返回全部；"Don't don't" 计为 ["don't", 2]
验证:
```bash
python -m unittest tests.test_count -v
```
完成标准: 三个单元测试通过

### T03 CLI 接入 --top，输出完整 JSON（里程碑）
- [ ] 完成
依赖: T02
文件: wordfreq/__main__.py(修改), tests/test_cli.py(修改)
接口: 使用 count_words、top_words
要点:
- argparse 加 `--top`，type 为正整数函数：`int(v)`，`<= 0` 时抛 `argparse.ArgumentTypeError`；默认 10
- 输出 `{"top": top_words(counts, args.top), "total": ...}`
- test_cli 增加：`--top 1` 只返回 `[["the", 2]]`；`--top 0` 退出码为 2
验证:
```bash
python -m unittest discover -s tests -v
```
完成标准: `python -m wordfreq 样例 --top 1` 输出 `{"top": [["the", 2]], "total": 4}`

### T04 文件不存在时报错退出
- [ ] 完成
依赖: T03
文件: wordfreq/__main__.py(修改), tests/test_cli.py(修改)
接口: 无变化
要点:
- 只在 read_text 外捕获 FileNotFoundError：打印 `error: file not found: <path>` 到 stderr，return 2
- test_cli 增加：不存在的路径 → 退出码 2，stdout 为空，stderr 含 "file not found"
验证:
```bash
python -m unittest discover -s tests -v
```
完成标准: 不存在的文件得到退出码 2 和一行错误
