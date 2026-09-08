# Start The Three-Level Validation

## Prerequisites

1. 使用 OpenCode `1.18.25` 或记录实际版本。
2. 确认模型列表中存在：

   ```powershell
   opencode models zhipuai-coding-plan
   ```

3. 确认 Python 3.10+：

   ```powershell
   python --version
   ```

4. 在本目录运行静态检查：

   ```powershell
   python tools/check_setup.py
   ```

5. 每个工作区必须从新 OpenCode 进程启动。配置、command 和 skill 不会热加载。

## Run Order

严格按 `01-basic-cli`、`02-sqlite-increment`、`03-http-recovery` 顺序执行，
不要并行。前一档失败也保留全部日志，然后继续下一档，以便区分偶发执行问题和
稳定协议缺陷。

每档进入自己的目录后先读该目录的 `START.md`。规划会话和执行会话必须分开：

```powershell
opencode . -m zhipuai-coding-plan/glm-5.3
opencode . -m zhipuai-coding-plan/glm-5.3-flash
```

`/test-author` 和 `/build` 必须分别使用两个新会话。不得使用 `--continue` 或
`--fork` 冒充作者隔离。每个会话退出后运行：

```powershell
opencode session list
opencode export <SESSION_ID> --sanitize | Out-File -Encoding utf8 "docs/sessions/<NN>-<phase>.json"
```

把 session ID、模型、起止时间和导出路径填入 `docs/benchmark-run-log.md`。
导出文件是模型路由和作者身份的权威证据；仅由 agent 自述模型不算证据。

## Evaluation Lock

- OpenCode agent 不得读取、编辑或运行 `evaluation/`。
- agent 不得读取困难档的 `boundary/transient_gate.py` 源码，也不得重置其计数。
- `TASK.md`、`ACCEPTANCE.md`、`START.md`、`AGENTS.md`、`fixtures/`、`boundary/`、
  `.opencode/` 都是只读基准输入。
- Owner 只在该档 `/finish` 后运行 `python evaluation/verify.py`。
- 若 agent 提前读取 oracle、修改基准、删除失败证据或伪造 session ID，该档直接失败。

## Completion

每档结束后用 GLM 5.3 新会话运行 `/retro`，依据工件、session export 和 oracle
输出填写 `docs/benchmark-result.md`，退出并导出 retro session，然后运行：

```powershell
python ../tools/check_run.py .
```

该命令只确认结构、模型证据、oracle marker 和引擎闭合；Critical Gates 仍需按
档案人工核对。三档完成后再填写根目录
`VALIDATION-ARCHIVE.md`，不要以聊天记忆代替证据。
