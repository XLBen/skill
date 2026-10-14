#!/usr/bin/env python3
"""对一个已完成评测的工作区计算指标。

    python validation/metrics.py <工作区> [--plan docs/plan.md] [--no-oracle]

输出一行 Markdown 表格（贴进 RESULTS.md）和 JSON 明细。
产品代码 = 工作区里除 tests/、evaluation/、boundary/、.opencode/ 以外的 .py 文件。
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import wf  # noqa: E402

EXCLUDED = {"tests", "test", "evaluation", "boundary", ".opencode", ".wf", ".git", "__pycache__"}


def product_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py")
                  if not EXCLUDED.intersection(p.relative_to(root).parts) and not wf.is_test_path(p.name))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("workspace")
    parser.add_argument("--plan", default="docs/plan.md")
    parser.add_argument("--no-oracle", action="store_true")
    args = parser.parse_args()
    root = Path(args.workspace).resolve()
    result: dict = {"workspace": root.name}

    if not args.no_oracle:
        proc = subprocess.run([sys.executable, "evaluation/verify.py"], cwd=root, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=600)
        lines = (proc.stdout + proc.stderr).strip().splitlines()
        result["oracle"] = "PASS" if proc.returncode == 0 else "FAIL"
        result["oracle_tail"] = lines[-5:]

    plan_path = root / args.plan
    if plan_path.is_file():
        plan = wf.Plan(plan_path)
        tasks = list(plan.tasks.values())
        errors, warnings = wf.lint(plan)
        result["tasks"] = len(tasks)
        result["tasks_done"] = sum(t.done for t in tasks)
        result["avg_files_per_task"] = round(sum(len(t.files) for t in tasks) / len(tasks), 1) if tasks else 0
        result["plan_lint"] = f"{len(errors)} 错误 / {len(warnings)} 提醒"
    state_path = root / ".wf" / "state.json"
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        result["verify_runs"] = sum(r["attempt"] for r in state.values())
        result["extra_attempts"] = sum(r["attempt"] - 1 for r in state.values())

    files = product_files(root)
    sized = {str(p.relative_to(root)): p.read_text(encoding="utf-8", errors="replace").splitlines() for p in files}
    code = [(path, line) for path, lines in sized.items() for line in lines
            if line.strip() and not line.strip().startswith("#")]
    hits = wf.scan_defensive(code)
    result["product_files"] = len(files)
    result["product_loc"] = len(code)
    result["largest_file_loc"] = max((len(v) for v in sized.values()), default=0)
    result["junk_drawer_files"] = [p for p in sized if re.search(r"(utils|helpers|common)\.py$", p)]
    result["defensive_signals"] = {k: len(v) for k, v in hits.items()}
    total = sum(result["defensive_signals"].values())
    result["defensive_per_100_loc"] = round(100 * total / len(code), 1) if code else 0

    cols = [result["workspace"], result.get("oracle", "-"), result.get("tasks", "-"), result.get("extra_attempts", "-"),
            result["product_loc"], result["largest_file_loc"], total, result["defensive_per_100_loc"]]
    print("| 工作区 | oracle | 任务数 | 额外验证次数 | 产品代码行 | 最大文件行 | 防御信号 | 每百行 |")
    print("|---|---|---|---|---|---|---|---|")
    print("| " + " | ".join(str(c) for c in cols) + " |")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
