# S00 基线（BASELINE）

> **2026-09-21 清理说明**：本目录的历史测试运行输出快照已删除
> （各阶段 `s03`–`s22` 的 `test_all.txt`/`check_selftest.txt` 等原始输出、
> 根目录 `*.txt` 快照、`s21` 的测试输出与 `evidence-index.txt`）。保留：
> `s01/`（主机兼容证据，`test_visibility_config.py` 的目录快照出处）、
> `s03-corpus-regression.json` 与 `s09-corpus-repair.json`（测试回写终态）、
> `s21/replay_corpus.py`、`s21/evidence_index.py`、`s21/corpus-replay/`
> （校准重放工具与证据）、`../corpus/`（21 份语料输入）。历史原始输出
> 可在本仓库 git 历史中查阅。PROGRESS.md / FINAL-REPORT.md 中指向已删
> 快照的路径同样以 git 历史为准。

- 步骤：S00 — 基线建立与失败语料索引
- 日期：2026-09-21
- 仓库：`E:\MISC\代码项目\skill`（分支 `main`，HEAD `f62c2f0c93658b11bfc392e1d59ae67e508af82b`）
- 沙箱（只读，本次未写入）：`E:\MISC\代码项目\po-validation-sandbox`
- 解释器：`python` → `D:\python\python.exe`，**Python 3.10.7**（本步骤四个命令全部使用该解释器）；
  `py -3` 也可用（Python 3.12.10），本次未使用。
- 修复前原执行模型（语料来源）：`zhipuai-coding-plan/glm-5.3-flash`
  （依据：`PROBLEM-REPORT.md` 头部、`results/driver.log`、原始 raw 输出中的 `> po-observer · glm-5.3-flash`）。
- 只读状态确认：`scripts\product_observation.py` 在 `skill-copy` 与当前仓库的 SHA256 相同
  （`FCE217FF…196B`），说明本次直检所用校验器与生成 evidence-digest 的校验器一致；
  沙箱下无任何文件被本次修改。

## 1. 仓库状态（修复前）

- 已跟踪文件修改 **25 个**：`scripts/check.py`、`scripts/install.py`、`scripts/runtime_trace.py`、
  `scripts/workflow_packets.py`、`scripts/workflow_protocol.py`、`scripts/workflow_runtime.py`、
  `tests/test_install.py`、`tests/test_runtime_doctor.py`、`tests/test_subagent_orchestration.py`
  及 README / SKILL / references 若干；合计 **493 insertions(+), 20 deletions(-)**。
- 未跟踪（修复前已存在）：`.opencode/agents/mvp-product-observer.md`、`product-observer/`、
  `scripts/product_observation.py`、`tests/test_observer_packets.py`、`tests/test_product_observation.py`、
  `validation/product-observation/`。
- 完整输出：`docs/po-repair/baseline/git-status.txt`、`docs/po-repair/baseline/git-diff-stat.txt`。
- 注：`git-status.txt` 中的 `?? docs/po-repair/` 是 S00 自己创建的目录（捕捉时目录已建、文件未写）；
  `docs/po-repair/**` 下其余全部文件均为 S00 产物。
- 结论：工作树非干净且不是错误状态，是既有工作。后续所有修复必须在此之上**增量修改**；
  禁止 `reset / clean / stash / checkout -- .`；不得覆盖或删除上述未跟踪文件。

## 2. 测试基线（修复前）

| # | 命令 | 解释器 | 退出码 | 耗时 | 结果 | 完整输出 |
|---|---|---|---|---|---|---|
| 1 | `python -m unittest discover -s tests -p "test_product_observation.py" -v` | Python 3.10.7 | 0 | 0.613s | Ran 20 tests, **OK** | `baseline/test_product_observation.txt` |
| 2 | `python -m unittest discover -s tests -p "test_observer_packets.py" -v` | Python 3.10.7 | 0 | 0.102s | Ran 10 tests, **OK** | `baseline/test_observer_packets.txt` |
| 3 | `python -m unittest discover -s tests -p "test_*.py"`（全量） | Python 3.10.7 | 0 | 37.269s | Ran 408 tests, **OK** | `baseline/test_all.txt` |
| 4 | `python scripts/check.py --selftest` | Python 3.10.7 | 0 | 10.7s | **selftest PASS**（365 行） | `baseline/check_selftest.txt` |

- **失败测试清单：无**。四个命令 0 failures、0 errors；unittest 汇总无 skipped 计数
  （`test_all.txt:389` 的 `"schema_check": "skipped (offline)"` 是某测试打印的 JSON 载荷，不是 unittest skip）。
- 关键含义（后续步骤必须正视）：
  1. 现有测试套件**全绿**，但真实模型语料 **18/21** 不通过 schema 直检（见 §3）。
     P1-4（schema 漂移）、P1-7（校验器崩溃）、P1-8（gate 早退）在现有测试中**毫无失败信号**，
     只在真实输出语料上暴露；因此 S01 起每一项修复都必须先补能变红的回归测试，
     不能把"现有测试全绿"当作修复完成的证据。
  2. P1-7 的 `TypeError` 路径当前未被任何测试触发，本次由语料直检首次在本仓库复现。

## 3. 失败语料基线（21 份归档结果，逐份直检）

- 收集与直检脚本：`docs/po-repair/tools/collect_corpus.py`（只读沙箱、只写 `docs/po-repair/`）。
- 直检函数：当前 `scripts/product_observation.py` 的 `validate_observation_report` /
  `validate_observation_review`；异常归类 `VALIDATOR-CRASH`，不中断收集。
- 复制校验：21/21 份复制到 `docs/po-repair/corpus/<case>/<candidate>/<file>` 后 SHA256 与源一致
  （另用 PowerShell `Get-FileHash` 独立抽查 3 份，全部 MATCH）；21 份均为合法 UTF-8 可解码。
- 汇总：**VALID 3 / INVALID 16 / VALIDATOR-CRASH 2**；其中 handmade（t1）3 份。
- 明细：`docs/po-repair/corpus/INDEX.json`（含 case/candidate/phase/source_path/sha256/size/handmade/
  original_errors/crash/crash_field 等）、`docs/po-repair/baseline/corpus-validity.txt`、
  `docs/po-repair/baseline/corpus-collect.txt`。

| 判定 | 文件 | 错误数 | 备注 |
|---|---|---|---|
| VALID | A-term/cand-good/discover | 0 | 真实模型输出 |
| VALID | t1/cand-x/compare | 0 | **hand-made** |
| VALID | t1/cand-x/review | 0 | **hand-made** |
| INVALID | A-term/cand-bad/compare | 2 | |
| INVALID | A-term/cand-bad/discover | 19 | |
| INVALID | B-term/cand-bad/compare | 8 | |
| INVALID | B-term/cand-bad/discover | 28 | |
| INVALID | B-term/cand-fix/compare | 17 | 报告声称其合法，直检不合法（见 §3.1） |
| INVALID | B-term/cand-fix/discover | 16 | |
| CRASH | B-term/cand-fix/review | 1 | `TypeError: unhashable type: 'dict'`，字段 `review.findings_validity` |
| INVALID | C-term/cand-bad/compare | 6 | |
| INVALID | C-term/cand-bad/discover | 16 | |
| INVALID | D-term/cand-bad/compare | 8 | |
| INVALID | D-term/cand-bad/discover | 18 | |
| INVALID | E-term/cand-good/discover | 17 | |
| INVALID | E-term/cand-redesign/compare | 2 | |
| INVALID | E-term/cand-redesign/discover | 18 | |
| CRASH | E-term/cand-redesign/review | 1 | `TypeError: unhashable type: 'dict'`，字段 `review.findings_validity` |
| INVALID | F-term/cand-bad/compare | 23 | |
| INVALID | F-term/cand-bad/discover | 35 | |
| INVALID | t1/cand-x/discover | 1 | **hand-made**；status 非法值 |

两份崩溃的 `findings_validity` 都是富对象：B-term 为 `{'result','detail'}`，
E-term 为 `{'judgment','detail'}`；崩溃字段由确定性探针给出（按校验器集合成员测试顺序），
异常类型与字段均来自真实调用后的捕获。

### 3.1 与 PROBLEM-REPORT / evidence-digest 的差异（以直检为准）

1. **计数与 evidence-digest 一致**：digest §1 的 21 份中 18 份非 VALID（本次直检 16 INVALID + 2 CRASH），
   3 份 VALID；逐份错误条数与 digest 完全对应，无出入。
2. **PROBLEM-REPORT P1-4 的"3 份合法"名单与直检不一致**：
   - 报告写：`A-term 二轮 cand-good discover`、`B-term T3 cand-fix compare`、`T3 review`。
   - 直检：合法的是 `A-term/cand-good/discover`、`t1/cand-x/compare`、`t1/cand-x/review`。
   - `B-term/cand-fix/compare` 直检 **17 条** schema 问题（不合法）；
     `B-term/cand-fix/review` 属 `VALIDATOR-CRASH`（不合法）。报告名单中只有第一项吻合，
     另外两项与直检冲突，**以本次直检为准**。
3. **PROBLEM-REPORT §0 的语料口径自相矛盾**：报告写"归档观察结果文件 21 份（18 报告 + 3 评审），
   另 T1 手工构造 2 份"。实际本项目录下的 21 份**已经包含** t1 的 3 份（2 报告 + 1 评审）；
   不存在"另 2 份"的第 22、23 份。按任务口径固定为：21 份 = 18 报告 + 3 评审，其中 t1 3 份标注 handmade。
4. **未测项与结论不受影响**：证据摘要 §1 的逐字段错误清单与本次直检可复现，且校验器字节级一致。

## 4. 基线产物清单（S00 创建）

| 路径 | 内容 |
|---|---|
| `docs/po-repair/BASELINE.md` | 本文件 |
| `docs/po-repair/baseline/git-status.txt` | `git status --short` 完整输出（含 `?? docs/po-repair/`） |
| `docs/po-repair/baseline/git-diff-stat.txt` | `git diff --stat` 完整输出（含 LF/CRLF 警告） |
| `docs/po-repair/baseline/test_product_observation.txt` | 命令 1 完整输出（-v，逐用例） |
| `docs/po-repair/baseline/test_observer_packets.txt` | 命令 2 完整输出（-v，逐用例） |
| `docs/po-repair/baseline/test_all.txt` | 命令 3 完整输出（-v，全量 408 用例） |
| `docs/po-repair/baseline/check_selftest.txt` | 命令 4 完整输出 |
| `docs/po-repair/baseline/corpus-validity.txt` | 21 份语料逐份判定摘要 |
| `docs/po-repair/baseline/corpus-collect.txt` | 收集脚本控制台输出 |
| `docs/po-repair/tools/collect_corpus.py` | 语料复制 + 直检 + INDEX.json 生成器（可重跑） |
| `docs/po-repair/corpus/INDEX.json` | 21 份语料索引（含 sha256/错误列表/崩溃字段） |
| `docs/po-repair/corpus/<case>/<candidate>/*.result.json` | 21 份原样复制件 |
| `docs/po-repair/COVERAGE-MAP.md` | 问题—测试映射清单 |
| `docs/po-repair/PROGRESS.md` | S00 进度记录 |
| `docs/po-repair/CONTRACT.md` | S02 占位（未填写） |
