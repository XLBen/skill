#!/usr/bin/env python3
"""Owner-side structural check for a completed benchmark workspace."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PLANNING_MODEL = "zhipuai-coding-plan/glm-5.3"
EXECUTION_MODEL = "zhipuai-coding-plan/glm-5.3-flash"
LEVELS = {
    "01-basic-cli": {
        "oracle": "L1 ORACLE PASS",
        "sessions": {
            "01-planning.json": PLANNING_MODEL,
            "02-test-author.json": EXECUTION_MODEL,
            "03-implementation.json": EXECUTION_MODEL,
            "04-retro.json": PLANNING_MODEL,
        },
        "manifests": 1,
        "si": False,
        "cr": False,
    },
    "02-sqlite-increment": {
        "oracle": "L2 ORACLE PASS",
        "sessions": {
            "01-first-plan.json": PLANNING_MODEL,
            "02-first-test-author.json": EXECUTION_MODEL,
            "03-first-build.json": EXECUTION_MODEL,
            "04-si-plan.json": PLANNING_MODEL,
            "05-si-test-author.json": EXECUTION_MODEL,
            "06-si-build.json": EXECUTION_MODEL,
            "07-retro.json": PLANNING_MODEL,
        },
        "manifests": 2,
        "si": True,
        "cr": False,
    },
    "03-http-recovery": {
        "oracle": "L3 ORACLE PASS",
        "sessions": {
            "01-first-plan.json": PLANNING_MODEL,
            "02-first-test-author.json": EXECUTION_MODEL,
            "03-first-build.json": EXECUTION_MODEL,
            "04-si-plan.json": PLANNING_MODEL,
            "05-si-test-author.json": EXECUTION_MODEL,
            "06-si-build.json": EXECUTION_MODEL,
            "07-circuit-recovery.json": EXECUTION_MODEL,
            "08-cr-plan.json": PLANNING_MODEL,
            "09-cr-test-author.json": EXECUTION_MODEL,
            "10-cr-build.json": EXECUTION_MODEL,
            "11-retro.json": PLANNING_MODEL,
        },
        "manifests": 3,
        "si": True,
        "cr": True,
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    level = LEVELS.get(workspace.name)
    if level is None:
        print(f"FAIL: unsupported workspace {workspace.name}")
        return 2

    errors: list[str] = []

    setup = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_setup.py")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=30,
        check=False,
    )
    if setup.returncode != 0:
        errors.append(f"frozen setup check failed: {(setup.stdout + setup.stderr).strip()[:500]}")

    def require_file(relative: str) -> Path:
        path = workspace / relative
        if not path.is_file():
            errors.append(f"missing {relative}")
        return path

    required = (
        "docs/contract.md",
        "docs/PLAN.md",
        "docs/review-log.md",
        "docs/build-log.md",
        "docs/change-orders.md",
        "docs/workflow-events.jsonl",
        "docs/mvp-observation.md",
        "docs/benchmark-run-log.md",
        "docs/benchmark-result.md",
        "docs/evidence/benchmark/oracle.txt",
    )
    paths = {relative: require_file(relative) for relative in required}

    oracle = paths["docs/evidence/benchmark/oracle.txt"]
    if oracle.is_file() and str(level["oracle"]) not in oracle.read_text(encoding="utf-8", errors="replace"):
        errors.append("owner oracle output does not contain its PASS marker")

    for relative in ("docs/benchmark-run-log.md", "docs/benchmark-result.md"):
        path = paths[relative]
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            if "pending" in text or "not run" in text:
                errors.append(f"{relative} still contains pending/NOT RUN fields")

    sessions_root = workspace / "docs" / "sessions"
    for filename, model in level["sessions"].items():  # type: ignore[union-attr]
        session = sessions_root / str(filename)
        if not session.is_file():
            errors.append(f"missing session export docs/sessions/{filename}")
            continue
        raw = session.read_text(encoding="utf-8-sig", errors="replace")
        try:
            json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid session export {filename}: {exc}")
        if str(model) not in raw:
            errors.append(f"session {filename} does not prove model {model}")

    manifests = list((workspace / "docs" / "test-manifests").glob("*.md"))
    if len(manifests) < int(level["manifests"]):
        errors.append(
            f"only {len(manifests)} test manifests; expected at least {level['manifests']}"
        )
    if bool(level["si"]) and not list((workspace / "docs" / "slice-increments").glob("SI-*.md")):
        errors.append("missing SI record")
    if bool(level["cr"]):
        change_orders = paths["docs/change-orders.md"]
        if change_orders.is_file() and "schema-v2" not in change_orders.read_text(
            encoding="utf-8", errors="replace"
        ):
            errors.append("change-orders.md does not contain the schema-v2 CR")
        gate_count = workspace / "artifacts" / "circuit-count.txt"
        if not gate_count.is_file() or gate_count.read_text(encoding="ascii").strip() != "4":
            errors.append("circuit gate does not show three failures plus one authorized recovery")

    engine = workspace / ".opencode" / "workflow" / "scripts" / "check.py"
    if all(paths[key].is_file() for key in (
        "docs/contract.md",
        "docs/PLAN.md",
        "docs/change-orders.md",
        "docs/workflow-events.jsonl",
    )):
        commands = (
            [sys.executable, str(engine), "contract", "docs/contract.md"],
            [
                sys.executable,
                str(engine),
                "plan",
                "docs/PLAN.md",
                "--contract",
                "docs/contract.md",
                "--change-orders",
                "docs/change-orders.md",
                "--ledger",
                "docs/workflow-events.jsonl",
            ],
            [
                sys.executable,
                str(engine),
                "reconcile",
                "docs/PLAN.md",
                "--contract",
                "docs/contract.md",
                "--change-orders",
                "docs/change-orders.md",
                "--ledger",
                "docs/workflow-events.jsonl",
            ],
        )
        for command in commands:
            result = subprocess.run(
                command,
                cwd=workspace,
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=30,
                check=False,
            )
            if result.returncode != 0:
                errors.append(
                    f"engine check failed: {' '.join(command[2:])}: "
                    f"{(result.stdout + result.stderr).strip()[:300]}"
                )
            if command[2] == "reconcile" and result.returncode == 0:
                try:
                    reconcile = json.loads(result.stdout)
                except json.JSONDecodeError:
                    errors.append("reconcile output is not valid JSON")
                else:
                    if reconcile.get("status") != "clean":
                        errors.append("reconcile output is not clean")

    if errors:
        print(f"{workspace.name} STRUCTURAL FAIL ({len(errors)} issues)")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"{workspace.name} STRUCTURAL PASS")
    print("Manual Critical Gates and tier-specific checks are still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
