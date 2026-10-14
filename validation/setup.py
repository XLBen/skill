#!/usr/bin/env python3
"""为一次评测创建干净的工作区。

    python validation/setup.py 01-basic-cli <工作区目录> [--skills-repo <仓库路径>]

复制 tasks/<名称>（不含 ROUND*.md，后续轮次由操作者粘贴），git init 并提交基线，
然后用 --skills-repo 指向的仓库（默认本仓库）的 scripts/install.py 安装工作流。
对比 v1 时，把 --skills-repo 指向 v1 的检出目录即可。
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task", choices=sorted(p.name for p in (HERE / "tasks").iterdir() if p.is_dir()))
    parser.add_argument("workspace")
    parser.add_argument("--skills-repo", default=str(HERE.parent))
    args = parser.parse_args()

    dest = Path(args.workspace).resolve()
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"工作区不是空目录: {dest}")
    shutil.copytree(HERE / "tasks" / args.task, dest, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("ROUND*.md", "__pycache__"))
    run = lambda *cmd: subprocess.run(cmd, cwd=dest, check=True)
    run("git", "init", "-q")
    run(sys.executable, str(Path(args.skills_repo) / "scripts" / "install.py"), str(dest))
    run("git", "add", "-A")
    run("git", "-c", "user.name=bench", "-c", "user.email=bench@localhost", "commit", "-qm", "baseline")
    rounds = sorted((HERE / "tasks" / args.task).glob("ROUND*.md"))
    print(f"\n工作区: {dest}")
    if rounds:
        print("后续轮次（按顺序粘贴给 agent）: " + ", ".join(str(r) for r in rounds))
    print("评测完成后运行: python validation/metrics.py " + str(dest))


if __name__ == "__main__":
    main()
