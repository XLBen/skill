#!/usr/bin/env python3
"""wf.py — docs/plan.md 的最小执行工具（仅标准库）。

状态就是 plan.md 里每个任务的复选框；验证记录放在 .wf/。

  python wf.py status            任务列表与下一个可做任务
  python wf.py next              下一个依赖已完成的任务 ID
  python wf.py task T03          打印交给 worker 的任务包
  python wf.py verify T03        运行任务的验证命令并记录结果
  python wf.py done T03          最近一次 verify 通过才勾选
  python wf.py diffcheck T03     对照卡片检查改动范围与防御性代码
  python wf.py lint              检查计划格式与拆分规则
  python wf.py regress           重跑所有已完成任务的验证（回归）
  python wf.py reopen T03        把任务改回未完成
  python wf.py impact parse_row  哪些任务提到了这个名称
  python wf.py next --all        可以并行的一组任务
  python wf.py wt-add T03        为任务建 git worktree（并行施工）
  python wf.py wt-merge T03      提交 worktree 并合并回当前分支；冲突则中止
  python wf.py wt-drop T03       丢弃任务的 worktree
  python wf.py contracts         逐条运行 '## 接口契约' 的契约测试
  python wf.py lanes             按执行者分组列出任务，给出关键路径

plan.md 的 '## 检查' 节（```bash 代码块）会在每个任务 verify 时和 regress 末尾自动运行。
verify/diffcheck/regress 支持 --cwd（在 worktree 中运行）。验证命令以 python/python3/py
开头时，自动换成运行 wf.py 的解释器，方便同一份计划在 Windows/macOS/Linux 上运行。

全局参数：--plan PATH（默认 docs/plan.md），命令从项目根目录运行。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TASK_HEADING = re.compile(r"^###\s+(T\d+)\s+(.*)$")
CONTRACT_HEADING = re.compile(r"^###\s+(I\d+)\s+(.*)$")
CHECKBOX = re.compile(r"^- \[( |x|X)\]")
FIELD = re.compile(r"^(依赖|文件|接口|阅读|完成标准|执行者|提供|使用|契约测试)\s*[:：]\s*(.*)$")
SPLIT = re.compile(r"[,，、;；]")
PACKAGE_SECTIONS = ("背景", "约定", "共享接口", "错误策略", "检查")
MAX_FILES = 4
STATE_DIR = Path(".wf")
GENERATED = re.compile(r"(^|/)(\.wf|__pycache__|node_modules|\.pytest_cache|\.mypy_cache|dist|build)/|\.pyc$")

# 防御性代码的常见信号：只作为审查提示，不是门禁。
DEFENSIVE_PATTERNS = {
    "try/except": re.compile(r"^\s*(try\s*:|except\b|try\s*\{|\}\s*catch\b|catch\s*\()"),
    "类型守卫": re.compile(r"\b(isinstance|hasattr)\(|\btypeof\s+\w+\s*[!=]=="),
    "空值守卫": re.compile(r"\bis\s+(not\s+)?None\b|[!=]==?\s*(null|undefined)\b|\?\?|\?\."),
    "静默回退": re.compile(r"\bfallback\b|\bor\s+(\{\}|\[\]|\"\"|''|None)|\.get\([^()]*,\s*(\{\}|\[\]|\"\"|''|None)\s*\)", re.IGNORECASE),
    "重试": re.compile(r"\bretr(y|ies)\b|\bbackoff\b", re.IGNORECASE),
}


@dataclass
class Task:
    id: str
    title: str
    start: int  # heading 行号（0 起）
    end: int  # 下一节开始的行号
    done: bool = False
    has_checkbox: bool = False
    deps: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    verify: list[str] = field(default_factory=list)
    milestone: bool = False
    executor: str = "worker"


@dataclass
class Contract:
    """'## 接口契约' 里的一条：### I01 签名。提供方、使用方和契约测试命令。"""
    id: str
    title: str
    start: int
    end: int
    provider: str = ""
    users: list[str] = field(default_factory=list)
    test: str = ""


def split_commands(lines: list[str]) -> list[str]:
    """代码块按行拆成命令；行尾 \\ 续行，# 开头为注释。"""
    result, pending = [], ""
    for line in lines:
        stripped = line.strip()
        if not stripped or (stripped.startswith("#") and not pending):
            continue
        if stripped.endswith("\\"):
            pending += stripped[:-1] + " "
            continue
        result.append(pending + stripped)
        pending = ""
    if pending:
        result.append(pending.strip())
    return result


class Plan:
    def __init__(self, path: Path):
        self.path = path
        self.lines = path.read_text(encoding="utf-8").splitlines()
        self.tasks: dict[str, Task] = {}
        self.contracts: dict[str, Contract] = {}
        self.sections: dict[str, str] = {}
        self._parse()

    def _parse(self) -> None:
        headings, in_fence = [], False
        for i, line in enumerate(self.lines):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
            elif not in_fence and line.startswith(("## ", "### ")):
                headings.append(i)
        for n, i in enumerate(headings):
            end = headings[n + 1] if n + 1 < len(headings) else len(self.lines)
            line = self.lines[i]
            if line.startswith("## "):
                # 二级节的正文到下一个二级标题为止
                end = next((j for j in headings[n + 1:] if self.lines[j].startswith("## ")), len(self.lines))
                title = line[3:].strip()
                for name in PACKAGE_SECTIONS:
                    if title.startswith(name):
                        self.sections[name] = "\n".join(self.lines[i:end]).rstrip()
                continue
            match = CONTRACT_HEADING.match(line)
            if match:
                contract = Contract(match.group(1), match.group(2).strip(), i, end)
                self._parse_contract(contract)
                if contract.id in self.contracts:
                    raise SystemExit(f"计划中接口契约 ID 重复: {contract.id}")
                self.contracts[contract.id] = contract
                continue
            match = TASK_HEADING.match(line)
            if match:
                task = Task(match.group(1), match.group(2).strip(), i, end)
                task.milestone = "里程碑" in task.title
                self._parse_task(task)
                if task.id in self.tasks:
                    raise SystemExit(f"计划中任务 ID 重复: {task.id}")
                self.tasks[task.id] = task

    def _parse_task(self, task: Task) -> None:
        body = self.lines[task.start + 1:task.end]
        in_verify = in_fence = False
        for line in body:
            stripped = line.strip()
            if in_fence:
                if stripped.startswith("```"):
                    in_fence = in_verify = False
                elif in_verify:
                    task.verify.append(line)
                continue
            if stripped.startswith("```"):
                in_fence = True
                continue
            if not task.has_checkbox and CHECKBOX.match(stripped):
                task.has_checkbox = True
                task.done = stripped[3] in "xX"
                continue
            if re.match(r"^验证\s*[:：]", stripped):
                in_verify = True
                continue
            match = FIELD.match(stripped)
            if not match:
                continue
            key, value = match.groups()
            if key == "依赖":
                task.deps = re.findall(r"T\d+", value)
            elif key == "执行者":
                task.executor = value.strip().strip("`") or "worker"
            elif key == "文件":
                value = re.sub(r"[（(][^)）]*[)）]", "", value)  # 去掉 (新增) 之类的注释
                task.files = [f.strip().strip("`") for f in SPLIT.split(value) if f.strip()]

    def _parse_contract(self, contract: Contract) -> None:
        for line in self.lines[contract.start + 1:contract.end]:
            match = FIELD.match(line.strip())
            if not match:
                continue
            key, value = match.groups()
            if key == "提供":
                contract.provider = next(iter(re.findall(r"T\d+", value)), "")
            elif key == "使用":
                contract.users = re.findall(r"T\d+", value)
            elif key == "契约测试":
                contract.test = value.strip().strip("`")

    def provided(self, task: Task) -> list[Contract]:
        return [c for c in self.contracts.values() if c.provider == task.id]

    def related(self, task: Task) -> list[Contract]:
        return [c for c in self.contracts.values() if c.provider == task.id or task.id in c.users]

    def commands(self, task: Task) -> list[str]:
        return split_commands(task.verify)

    def check_commands(self) -> list[str]:
        """'## 检查' 节代码块里的命令：每个任务 verify 时都会运行。"""
        lines, in_fence = [], False
        for line in self.sections.get("检查", "").splitlines():
            if line.strip().startswith("```"):
                in_fence = not in_fence
            elif in_fence:
                lines.append(line)
        return split_commands(lines)

    def verify_commands(self, task: Task) -> list[str]:
        """任务自己的验证 + 它提供的接口的契约测试 + '## 检查'。"""
        contract_tests = [c.test for c in self.provided(task) if c.test]
        return self.commands(task) + contract_tests + self.check_commands()

    def ready(self) -> list[Task]:
        return [t for t in self.tasks.values() if not t.done and all(self.tasks.get(d) and self.tasks[d].done for d in t.deps)]

    def get(self, task_id: str) -> Task:
        task = self.tasks.get(task_id.upper())
        if not task:
            raise SystemExit(f"计划中没有任务 {task_id}；现有: {', '.join(self.tasks) or '无'}")
        return task

    def set_done(self, task: Task, done: bool) -> None:
        for i in range(task.start + 1, task.end):
            if CHECKBOX.match(self.lines[i].strip()):
                self.lines[i] = re.sub(r"\[( |x|X)\]", "[x]" if done else "[ ]", self.lines[i], count=1)
                self.path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
                return
        raise SystemExit(f"{task.id} 没有 '- [ ]' 状态行")

    def parallel_batch(self, limit: int) -> list[Task]:
        """依赖已完成、且“文件”两两不重叠的就绪任务。"""
        batch, taken = [], set()
        for task in self.ready():
            files = set(task.files)
            if files & taken:
                continue
            batch.append(task)
            taken |= files
            if len(batch) == limit:
                break
        return batch


def load_state() -> dict:
    path = STATE_DIR / "state.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    (STATE_DIR / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def commands_hash(commands: list[str]) -> str:
    return hashlib.sha256("\n".join(commands).encode("utf-8")).hexdigest()[:12]


def cmd_status(plan: Plan, _args) -> int:
    if not plan.tasks:
        print("计划里没有 '### Txx 标题' 形式的任务")
        return 1
    ready = {t.id for t in plan.ready()}
    state = load_state()
    for task in plan.tasks.values():
        mark = "x" if task.done else (">" if task.id in ready else " ")
        last = state.get(task.id, {}).get("result", "")
        who = f"  @{task.executor}" if task.executor != "worker" else ""
        print(f"[{mark}] {task.id} {task.title}{who}" + (f"   (最近验证: {last})" if last and not task.done else ""))
    done = sum(t.done for t in plan.tasks.values())
    print(f"\n完成 {done}/{len(plan.tasks)}")
    return cmd_next(plan, _args)


def cmd_next(plan: Plan, args) -> int:
    if getattr(args, "all", False):
        batch = plan.parallel_batch(args.max)
        if batch:
            print("可以并行（依赖已完成，文件不重叠）:")
            for task in batch:
                print(f"  {task.id} {task.title}   文件: {', '.join(task.files)}")
            return 0
    ready = plan.ready()
    if ready:
        task = ready[0]
        print(f"下一个: {task.id} {task.title}")
        return 0
    if all(t.done for t in plan.tasks.values()):
        print("全部任务已完成 → 跑验收样例并做最终审查（review 模式 B）")
        return 0
    blocked = [t.id for t in plan.tasks.values() if not t.done]
    print(f"没有依赖就绪的任务；未完成: {', '.join(blocked)}。检查依赖是否写错。")
    return 1


def cmd_task(plan: Plan, args) -> int:
    task = plan.get(args.id)
    missing = [d for d in task.deps if not plan.tasks.get(d) or not plan.tasks[d].done]
    if missing:
        print(f"注意: 依赖未完成 {', '.join(missing)}\n")
    print(f"执行者: {task.executor}")
    print(f"项目根目录: {Path.cwd().resolve()}")
    print("所有读写都在这个目录里；路径一律写成相对于它的路径，或用它拼出绝对路径。不要拼接 skill 所在的目录。\n")
    for name in PACKAGE_SECTIONS:
        if name in plan.sections:
            print(plan.sections[name] + "\n")
    related = plan.related(task)
    if related:
        print("## 相关接口契约\n")
        for contract in related:
            role = "你提供（verify 时会运行它的契约测试）" if contract.provider == task.id else "你使用"
            print(f"<!-- {role} -->")
            print("\n".join(plan.lines[contract.start:contract.end]).rstrip() + "\n")
    print("## 当前任务\n")
    print("\n".join(plan.lines[task.start:task.end]).rstrip())
    print("\n只做这个任务。完成后贴出验证命令的原始输出。")
    return 0


PYTHON_PREFIX = re.compile(r"^(python3?|py)(?=\s|$)")


def portable(command: str) -> str:
    """计划里写 python，就用运行 wf.py 的解释器；Windows/macOS/Linux 的命令名不同。"""
    return PYTHON_PREFIX.sub(lambda _: f'"{sys.executable}"', command, count=1)


def run_command(command: str, timeout: int, cwd: str | None = None) -> tuple[int | None, str]:
    try:
        proc = subprocess.run(portable(command), shell=True, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        return None, out + f"\n[超时 {timeout}s]"
    return proc.returncode, proc.stdout + proc.stderr


def run_commands(commands: list[str], args) -> tuple[bool, str]:
    log = []
    for command in commands:
        code, output = run_command(command, args.timeout, args.cwd)
        ok = code == 0
        print(f"{'PASS' if ok else 'FAIL'} (exit {code}) $ {command}")
        if not ok or args.verbose:
            tail = output.strip().splitlines()[-args.tail:]
            print("\n".join("    " + line for line in tail))
        log.append(f"$ {command}\n[exit {code}]\n{output}")
        if not ok:
            return False, "\n".join(log)  # 后面的命令通常依赖前面的结果
    return True, "\n".join(log)


def cmd_regress(plan: Plan, args) -> int:
    done = [t for t in plan.tasks.values() if t.done]
    failed = []
    for task in done:
        print(f"== {task.id} {task.title}")
        ok, _ = run_commands(plan.commands(task), args)
        if not ok:
            failed.append(task.id)
    if plan.check_commands():
        print("== 检查")
        ok, _ = run_commands(plan.check_commands(), args)
        if not ok:
            failed.append("检查")
    print(f"\n回归: {len(done) - len(failed)}/{len(done)} 通过" + (f"；失败: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


def cmd_reopen(plan: Plan, args) -> int:
    task = plan.get(args.id)
    plan.set_done(task, False)
    state = load_state()
    state.pop(task.id, None)
    save_state(state)
    print(f"{task.id} 已重新打开（验证记录已清除）")
    return 0


def cmd_impact(plan: Plan, args) -> int:
    hits = [t for t in plan.tasks.values() if args.name in "\n".join(plan.lines[t.start:t.end])]
    contract = plan.contracts.get(args.name.upper())
    if contract:  # 接口契约：提供方和所有使用方都受影响
        ids = [contract.provider, *contract.users]
        hits = [plan.tasks[i] for i in plan.tasks if i in ids or plan.tasks[i] in hits]
    if not hits:
        print(f"没有任务提到 {args.name}")
        return 0
    for task in hits:
        print(f"[{'x' if task.done else ' '}] {task.id} {task.title}")
    print("已完成的任务如果受变更影响：wf reopen <ID>，或追加一个修改任务")
    return 0


def cmd_contracts(plan: Plan, args) -> int:
    """逐条运行接口契约测试。基础任务完成后应当全部失败（只有骨架），全部任务完成后应当全部通过。"""
    if not plan.contracts:
        print("计划里没有 '## 接口契约'")
        return 0
    passed = 0
    for contract in plan.contracts.values():
        if not contract.test:
            print(f"----  {contract.id} {contract.title}（没有契约测试命令）")
            continue
        code, output = run_command(contract.test, args.timeout)
        ok = code == 0
        passed += ok
        provider = plan.tasks.get(contract.provider)
        state = "已完成" if provider and provider.done else "未完成"
        print(f"{'PASS' if ok else 'FAIL'}  {contract.id} {contract.title}   提供: {contract.provider}（{state}）")
        if not ok and args.verbose:
            print("\n".join("    " + l for l in output.strip().splitlines()[-args.tail:]))
    print(f"\n契约测试: {passed}/{len(plan.contracts)} 通过")
    return 0 if passed == len(plan.contracts) else 1


def cmd_lanes(plan: Plan, _args) -> int:
    """按执行者分组列出未完成任务，并给出关键路径（最长的依赖链）。"""
    lanes: dict[str, list[Task]] = {}
    for task in plan.tasks.values():
        if not task.done:
            lanes.setdefault(task.executor, []).append(task)
    for executor, tasks in lanes.items():
        print(f"{executor}: " + ", ".join(t.id for t in tasks))
    longest: dict[str, list[str]] = {}
    for task in plan.tasks.values():  # 依赖只指向前面的任务（lint 保证），按顺序算即可
        best = max((longest[d] for d in task.deps if d in longest), key=len, default=[])
        longest[task.id] = best + [task.id]
    path = max(longest.values(), key=len, default=[])
    print(f"\n关键路径（{len(path)} 个任务）: {' → '.join(path)}")
    return 0


def cmd_verify(plan: Plan, args) -> int:
    task = plan.get(args.id)
    commands = plan.verify_commands(task)
    if not plan.commands(task):
        print(f"{task.id} 没有验证命令（'验证:' 后的代码块）")
        return 1
    runs = STATE_DIR / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    attempt = len(list(runs.glob(f"{task.id}-*.log"))) + 1
    log_path = runs / f"{task.id}-{attempt}.log"
    if args.cwd:
        print(f"在 {args.cwd} 中运行")
    passed, log = run_commands(commands, args)
    log_path.write_text(log, encoding="utf-8")
    state = load_state()
    state[task.id] = {"result": "pass" if passed else "fail", "attempt": attempt, "log": str(log_path),
                      "commands": commands_hash(commands), "time": time.strftime("%Y-%m-%d %H:%M:%S")}
    save_state(state)
    print(f"\n{task.id}: {'通过' if passed else '失败'}（第 {attempt} 次，日志 {log_path}）")
    return 0 if passed else 1


def cmd_done(plan: Plan, args) -> int:
    task = plan.get(args.id)
    if task.done:
        print(f"{task.id} 已经是完成状态")
        return 0
    record = load_state().get(task.id)
    if not record or record["result"] != "pass":
        print(f"{task.id} 最近一次 verify 未通过或未运行，不能勾选。先运行: wf.py verify {task.id}")
        return 1
    if record["commands"] != commands_hash(plan.verify_commands(task)):
        print(f"{task.id} 的验证命令或 '## 检查' 在 verify 之后被改过，请重新 verify")
        return 1
    plan.set_done(task, True)
    print(f"{task.id} 已完成")
    return cmd_next(Plan(plan.path), args)


def git(*args: str, cwd: str | None = None) -> str | None:
    proc = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    return proc.stdout if proc.returncode == 0 else None


def git_run(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)


def dirty_files(cwd: str | None = None) -> list[str] | None:
    status = git("status", "--porcelain", "--untracked-files=all", cwd=cwd)
    if status is None:
        return None
    files = {line[3:].split(" -> ")[-1].strip('"') for line in status.splitlines() if line.strip()}
    return sorted(f for f in files if not GENERATED.search(f))


def cmd_diffcheck(plan: Plan, args) -> int:
    task = plan.get(args.id)
    cwd = args.cwd
    status = git("status", "--porcelain", "--untracked-files=all", cwd=cwd)
    if status is None:
        print("不是 git 仓库：无法自动检查范围，请人工对照卡片的“文件”字段")
        return 0
    changed = sorted({line[3:].split(" -> ")[-1].strip('"') for line in status.splitlines() if line.strip()})
    changed = [c for c in changed if c != plan.path.as_posix() and not GENERATED.search(c)]
    declared = {f.replace("\\", "/") for f in task.files}
    extra = [c for c in changed if c not in declared]
    print(f"改动文件: {', '.join(changed) or '无'}")
    print(f"卡片声明: {', '.join(sorted(declared)) or '无'}")
    if extra:
        print(f"未声明的改动: {', '.join(extra)}  ← 越界还是卡片漏写？")

    added: list[tuple[str, str]] = []
    diff = git("diff", "--no-color", "-U0", "HEAD", cwd=cwd) or git("diff", "--no-color", "-U0", cwd=cwd) or ""
    current = ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("+") and current:
            added.append((current, line[1:]))
    base = Path(cwd or ".")
    for path in changed:  # 新文件不在 git diff 里
        if path not in {p for p, _ in added} and (base / path).is_file() and not (git("ls-files", path, cwd=cwd) or "").strip():
            try:
                added += [(path, l) for l in (base / path).read_text(encoding="utf-8").splitlines()]
            except UnicodeDecodeError:
                pass
    hits = scan_defensive(added)
    total = sum(len(v) for v in hits.values())
    code_lines = sum(1 for _, l in added if l.strip())
    print(f"\n新增代码 {code_lines} 行；防御性信号 {total} 处" + ("（逐条确认是否为错误策略要求）:" if total else ""))
    for kind, items in hits.items():
        for path, line in items[: args.tail]:
            print(f"  [{kind}] {path}: {line.strip()[:100]}")
    return 0


WORKTREES = STATE_DIR / "worktrees"


def commit_identity() -> list[str]:
    """仓库没配置提交身份时用一个本地身份，避免提交失败。"""
    return [] if git("config", "user.email") else ["-c", "user.name=wf", "-c", "user.email=wf@localhost"]


def cmd_wt_add(plan: Plan, args) -> int:
    task = plan.get(args.id)
    dirty = dirty_files()
    if dirty is None:
        raise SystemExit("并行施工需要 git 仓库")
    if dirty:
        print(f"主工作区有未提交的改动，先提交再建 worktree: {', '.join(dirty)}")
        return 1
    path = WORKTREES / task.id
    result = git_run("worktree", "add", "-b", f"wf/{task.id}", str(path), "HEAD")
    if result.returncode != 0:
        print(result.stderr.strip())
        return 1
    print(f"{task.id} 的 worktree: {path.resolve()}")
    print(f"把这个绝对路径交给 worker，要求所有读写都在其中进行；之后运行 verify/diffcheck {task.id} --cwd {path}")
    return 0


def cmd_wt_merge(plan: Plan, args) -> int:
    task = plan.get(args.id)
    path = WORKTREES / task.id
    if not path.is_dir():
        print(f"没有 {path}；先运行 wt-add {task.id}")
        return 1
    if dirty_files():
        print("主工作区有未提交的改动，先提交再合并")
        return 1
    if dirty_files(str(path)):
        git_run("add", "-A", cwd=str(path))
        git_run(*commit_identity(), "commit", "-qm", f"{task.id} {task.title}", cwd=str(path))
    result = git_run(*commit_identity(), "merge", "--no-ff", "--no-edit", "-m", f"合并 {task.id} {task.title}", f"wf/{task.id}")
    if result.returncode != 0:
        conflicts = (git("diff", "--name-only", "--diff-filter=U") or "").split()
        git_run("merge", "--abort")
        print(f"合并 {task.id} 冲突，已中止合并，主分支未改变。冲突文件: {', '.join(conflicts) or result.stdout.strip()}")
        print(f"处理方法: wt-drop {task.id}，等其他任务合并后串行重做")
        return 1
    drop_worktree(task.id)
    print(f"{task.id} 已合并。在主工作区再运行 verify {task.id}，通过后 done {task.id}")
    return 0


def drop_worktree(task_id: str) -> None:
    git_run("worktree", "remove", "--force", str(WORKTREES / task_id))
    git_run("branch", "-D", f"wf/{task_id}")


def cmd_wt_drop(plan: Plan, args) -> int:
    task = plan.get(args.id)
    drop_worktree(task.id)
    print(f"已删除 {task.id} 的 worktree 和分支 wf/{task.id}")
    return 0


def scan_defensive(lines: list[tuple[str, str]]) -> dict[str, list[tuple[str, str]]]:
    hits: dict[str, list[tuple[str, str]]] = {}
    for path, line in lines:
        if is_test_path(path):
            continue
        for kind, pattern in DEFENSIVE_PATTERNS.items():
            if pattern.search(line):
                hits.setdefault(kind, []).append((path, line))
    return hits


def is_test_path(path: str) -> bool:
    name = path.replace("\\", "/")
    return bool(re.search(r"(^|/)(tests?|__tests__)/|(^|/)test_[^/]*$|_test\.\w+$|\.(test|spec)\.\w+$", name))


NON_PORTABLE = re.compile(r"(^|[|;&]\s*)(grep|sed|awk|head|tail|cat|ls|rm|export|test)\b|\$\(|\s-c\s+'")


def lint(plan: Plan) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    for name in ("共享接口", "错误策略"):
        if name not in plan.sections:
            errors.append(f"缺少 '## {name}' 节")
    if not plan.tasks:
        errors.append("没有 '### T01 标题' 形式的任务")
    if not plan.check_commands():
        warnings.append("没有 '## 检查' 节：建议加载 guardrails，建立格式/lint/类型检查命令")
    for contract in plan.contracts.values():
        where = f"{contract.id}"
        if contract.provider not in plan.tasks:
            errors.append(f"{where}: '提供:' 要写成一个存在的任务 ID")
        for user in contract.users:
            if user not in plan.tasks:
                errors.append(f"{where}: 使用方 {user} 不存在")
        if not contract.test:
            errors.append(f"{where}: 缺少 '契约测试:' 命令")
    agents = Path(".opencode/agents")
    if agents.is_dir():
        for task in plan.tasks.values():
            if not (agents / f"{task.executor}.md").is_file():
                warnings.append(f"{task.id}: 执行者 {task.executor} 在 .opencode/agents/ 里没有对应的定义")
    ids = list(plan.tasks)
    for index, task in enumerate(plan.tasks.values()):
        where = f"{task.id}"
        if not task.has_checkbox:
            errors.append(f"{where}: 缺少 '- [ ]' 状态行")
        for dep in task.deps:
            if dep not in plan.tasks:
                errors.append(f"{where}: 依赖 {dep} 不存在")
            elif ids.index(dep) >= index:
                errors.append(f"{where}: 依赖 {dep} 排在它后面")
        if not task.files:
            errors.append(f"{where}: 缺少 '文件:' 字段")
        elif len(task.files) > MAX_FILES:
            warnings.append(f"{where}: 改动 {len(task.files)} 个文件（>{MAX_FILES}），考虑拆分")
        commands = plan.commands(task)
        if not commands:
            errors.append(f"{where}: 缺少验证命令（'验证:' 后跟 ```bash 代码块）")
        elif all(re.match(r"^(echo|true|ls|cat|test -[ef])\b", c) for c in commands):
            errors.append(f"{where}: 验证命令没有断言行为（只有 echo/ls/cat 之类）")
        body = "\n".join(plan.lines[task.start:task.end])
        if not re.search(r"完成标准\s*[:：]", body):
            warnings.append(f"{where}: 缺少 '完成标准:'")
        if re.search(r"TBD|TODO|待定|适当处理|依此类推|按需补齐", body):
            errors.append(f"{where}: 含占位措辞（TBD/TODO/待定/适当处理/依此类推）")
        for command in commands:
            if NON_PORTABLE.search(command):
                warnings.append(f"{where}: 验证命令 `{command[:60]}` 依赖 bash 专有工具或单引号，Windows 上可能无法运行；改用 python -c \"...\" 或测试")
                break
        if len(plan.lines[task.start:task.end]) > 80:
            warnings.append(f"{where}: 任务卡超过 80 行，弱模型可能读不全，考虑拆分或把代码移到共享接口")
    return errors, warnings


def cmd_lint(plan: Plan, _args) -> int:
    errors, warnings = lint(plan)
    for message in errors:
        print(f"错误: {message}")
    for message in warnings:
        print(f"提醒: {message}")
    if not errors:
        print(f"计划格式通过：{len(plan.tasks)} 个任务" + (f"，{len(warnings)} 条提醒" if warnings else ""))
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", default="docs/plan.md")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    nxt = sub.add_parser("next")
    nxt.add_argument("--all", action="store_true", help="列出可以并行的一组任务")
    nxt.add_argument("--max", type=int, default=3)
    sub.add_parser("lint")
    sub.add_parser("lanes")
    contracts = sub.add_parser("contracts")
    contracts.add_argument("--timeout", type=int, default=300)
    contracts.add_argument("--tail", type=int, default=15)
    contracts.add_argument("-v", "--verbose", action="store_true", help="显示失败输出")
    for name in ("task", "done", "reopen", "wt-add", "wt-merge", "wt-drop"):
        sub.add_parser(name).add_argument("id")
    sub.add_parser("impact").add_argument("name")
    for name in ("verify", "regress"):
        runner = sub.add_parser(name)
        if name == "verify":
            runner.add_argument("id")
        runner.add_argument("--cwd", help="在这个目录（例如 worktree）里运行命令")
        runner.add_argument("--timeout", type=int, default=300)
        runner.add_argument("--tail", type=int, default=30, help="失败时显示的输出行数")
        runner.add_argument("-v", "--verbose", action="store_true", help="通过时也显示输出")
    diffcheck = sub.add_parser("diffcheck")
    diffcheck.add_argument("id")
    diffcheck.add_argument("--cwd", help="检查这个目录（例如 worktree）")
    diffcheck.add_argument("--tail", type=int, default=10, help="每类最多显示几条")
    args = parser.parse_args(argv)

    path = Path(args.plan)
    if not path.is_file():
        raise SystemExit(f"找不到计划文件 {path}（用 --plan 指定）")
    handlers = {"status": cmd_status, "next": cmd_next, "task": cmd_task, "verify": cmd_verify,
                "done": cmd_done, "diffcheck": cmd_diffcheck, "lint": cmd_lint, "regress": cmd_regress,
                "reopen": cmd_reopen, "impact": cmd_impact, "wt-add": cmd_wt_add, "wt-merge": cmd_wt_merge,
                "wt-drop": cmd_wt_drop, "contracts": cmd_contracts, "lanes": cmd_lanes}
    return handlers[args.command](Plan(path), args)


if __name__ == "__main__":
    sys.exit(main())
