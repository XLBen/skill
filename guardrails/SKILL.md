---
name: guardrails
description: 为项目建立一条机械检查命令（格式、lint、类型检查），把防御性写法等能机械判断的问题交给检查器，并写进 plan.md 的“## 检查”节，让每个任务 verify 时自动运行。新项目在 T01 使用；已有项目在第一次规划时使用；ship 时可选加 CI。Set up one deterministic check command (format, lint, types) that runs on every task.
---

# Guardrails：让检查器来抓机械问题

能机械判断的错误（裸 except、捕获后什么都不做、类型不匹配、未使用的导入），用检查器抓，比在提示词里多写一条规则可靠。
目标：项目里有**一条**检查命令，写进 plan.md 的 `## 检查` 节，`wf verify` 每次都会运行它。

## 1. 先找已有的
读 `package.json` 的 scripts、`pyproject.toml` / `setup.cfg`、`Makefile`、`.pre-commit-config.yaml`、`.github/workflows/`。
- 已经有 lint / typecheck / check 命令：直接运行一次。能通过就用它；坏了就修好再用。不要另起一套。
- 没有：按下面的默认配置建立。新增开发依赖之前问用户一次（项目要求“只用标准库”时，开发工具是否允许由用户决定）。

## 2. 默认配置

**Python**：本机有 `uv` 时优先用它管理开发工具，命令统一写成 `uv run ...`（不用激活虚拟环境，三个平台写法相同）：
- 开发工具放进依赖组：`uv add --group dev ruff`（类型检查再加 `ty`，或沿用项目已有的 pyright / mypy）。
  不要用 `[project.optional-dependencies]` 放开发工具，不要手改 pyproject 加依赖，不要 `uv pip install`。
- 单文件脚本需要第三方库时，用 PEP 723 在文件头声明依赖，用 `uv run 脚本.py` 运行，不另建 requirements.txt。
- 没有 uv 时用 `python -m pip install ruff`，命令写成 `python -m ruff ...`。

ruff 规则（0.7 以上）。在 `pyproject.toml` 中：
```toml
[tool.ruff.lint]
extend-select = ["E722", "BLE001", "S110", "S112", "TRY203", "F", "B"]
```
- `E722` 裸 except，`BLE001` 捕获所有异常，`S110` / `S112` except 后直接 pass / continue，`TRY203` 捕获后原样重新抛出（无用的 try），`F`/`B` 常见错误。
  不要开 `SIM105`：它建议改用 `contextlib.suppress`，错误还是被吞掉了。
- 检查命令：`uv run ruff check .`、`uv run ruff format --check .`，有类型检查时加 `uv run ty check`
  （没有 uv 时把 `uv run` 换成 `python -m`，类型检查用 pyright 或 mypy）。

**JavaScript / TypeScript**（eslint + tsc）：
- 规则：`no-empty`、`no-useless-catch`、`@typescript-eslint/no-unnecessary-condition`（需要类型信息）、`@typescript-eslint/no-floating-promises`。
- 在 package.json 里加一个 `"check": "eslint . && tsc --noEmit"`，检查命令就是 `npm run check`。

**其他语言**：用该语言的标准工具（`go vet`、`cargo clippy -- -D warnings` 等）。

规则只开能明确说出“它抓什么错误”的那些。不要一次打开整套严格规则：新项目可以从零开始，已有项目一次性报出几百条问题时，
只开和本计划相关的规则，或者只检查本计划改动的文件。

## 3. 自定义规则（lint 管不到的重复问题）
retro 或审查反复发现同一种写法、而现成的 lint 规则抓不到时（例如“捕获异常后返回空列表”），用 semgrep 写一条项目规则：
- 每条规则一个目录：`.semgrep/<规则名>/<规则名>.yaml` 加一个同名测试文件。测试文件里，应该报的行上面写 `# ruleid: <规则名>`，
  不该报的写 `# ok: <规则名>`。**一定要写“不该报”的例子**，误报会让人不再相信这个检查。
- 先写测试，再写规则；`semgrep --test .semgrep/<规则名>/` 全部通过才算完成。
- 模式要具体，指定语言（不要用 `generic`），一个文件只放一条规则。
- 现成的例子：`references/semgrep/except-returns-empty/`（抓“捕获异常后返回空列表/空字典/空字符串/None”，已用
  `semgrep --test` 验证）。Python 项目可以直接复制到 `.semgrep/`。注意：规则报在匹配开始的那一行（这里是 `try:`），
  `# ruleid:` 注释要写在那一行上面。
- 把 `semgrep --config .semgrep --error --exclude .semgrep .` 加进 `## 检查`（`--exclude` 不能省，否则规则自己的测试文件也会被报出来）。semgrep 在 Windows 上用不了时，只在 CI（Linux）里跑这一条。

## 4. 写进计划
在 plan.md 的“约定”后面加：
````markdown
## 检查
```bash
uv run ruff check .
uv run ruff format --check .
```
````
命令要能在 Windows、macOS、Linux 上运行（规则同 plan skill 的验证命令）。改了这一节之后，已经 verify 过的任务要重新 verify。

## 5. CI（可选，ship 时由用户决定）
用户想要时，加一个 GitHub Actions 工作流，在推送和 PR 时运行同一条检查命令和测试命令。需要多平台时用
`strategy.matrix.os: [ubuntu-latest, windows-latest, macos-latest]`。更复杂的流水线加载 `ci-cd-and-automation`（release 档案）。

## 汇报
`检查命令: <命令> | 新增开发依赖: <有/无> | 当前结果: <通过 / N 个问题>`
