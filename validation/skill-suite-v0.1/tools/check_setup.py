#!/usr/bin/env python3
"""Validate the immutable three-workspace benchmark setup."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKSPACES = (
    ROOT / "01-basic-cli",
    ROOT / "02-sqlite-increment",
    ROOT / "03-http-recovery",
)
SKILLS = (
    "grill",
    "contract-review",
    "construction",
    "reviewer",
    "step-executor",
    "test-author",
)
COMMON_FILES = (
    "opencode.json",
    "AGENTS.md",
    "START.md",
    "TASK.md",
    "ACCEPTANCE.md",
    "evaluation/verify.py",
    "docs/benchmark-run-log.md",
    "docs/benchmark-result.md",
    "docs/sessions/README.md",
    "docs/evidence/benchmark/README.md",
)
PLANNING_COMMANDS = {
    "assess.md",
    "challenge.md",
    "change.md",
    "debate.md",
    "grill.md",
    "plan.md",
    "retro.md",
    "review.md",
}
EXECUTION_COMMANDS = {"build.md", "finish.md", "resume.md", "test-author.md"}
PLANNING_MODEL = "zhipuai-coding-plan/glm-5.3"
EXECUTION_MODEL = "zhipuai-coding-plan/glm-5.3-flash"
EXPECTED_SKILL_DIGEST = "9c46a8f8fa5b3920b2579017acf5d3548e34e01b2d2870be7b2e3c0fc06cf430"
EXPECTED_COMMAND_DIGEST = "463e99fa5271c3639fbcd9720b6ba088a8e1cba446c72f17acdf8a2d5f113a7e"
EXPECTED_ENGINE_DIGEST = "4cd330352f4a91980c697d61d7210b2b5b6eacc87f0f17210ca6f90bfba07025"
EXPECTED_FIXTURE_DIGEST = "9f4e500ad4238a5667cb89ca828540d180833d765bef802e8b60f74a4a902c04"


def tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def command_model(path: Path) -> str | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return None
    for line in lines[1:]:
        if line == "---":
            break
        if line.startswith("model:"):
            return line.split(":", 1)[1].strip()
    return None


def main() -> int:
    errors: list[str] = []
    skill_digests: list[str] = []
    command_digests: list[str] = []
    engine_digests: list[str] = []
    fixture_digests: list[str] = []

    for workspace in WORKSPACES:
        if not workspace.is_dir():
            errors.append(f"missing workspace: {workspace.name}")
            continue
        for relative in COMMON_FILES:
            if not (workspace / relative).is_file():
                errors.append(f"{workspace.name}: missing {relative}")
        if workspace.name == "03-http-recovery":
            for relative in (
                "boundary/API.md",
                "boundary/scenario.txt",
                "boundary/server.py",
                "boundary/control.py",
                "boundary/transient_gate.py",
            ):
                if not (workspace / relative).is_file():
                    errors.append(f"{workspace.name}: missing {relative}")
        config_path = workspace / "opencode.json"
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{workspace.name}: invalid opencode.json: {exc}")
            continue
        if config.get("model") != PLANNING_MODEL:
            errors.append(f"{workspace.name}: default planning model is not pinned")
        if config.get("small_model") != EXECUTION_MODEL:
            errors.append(f"{workspace.name}: small/execution model is not pinned")

        skills_root = workspace / ".opencode" / "skills"
        for skill in SKILLS:
            if not (skills_root / skill / "SKILL.md").is_file():
                errors.append(f"{workspace.name}: missing skill {skill}")
        if skills_root.is_dir():
            skill_digests.append(tree_digest(skills_root))

        commands_root = workspace / ".opencode" / "commands"
        for filename in PLANNING_COMMANDS:
            path = commands_root / filename
            if not path.is_file() or command_model(path) != PLANNING_MODEL:
                errors.append(f"{workspace.name}: wrong planning model in {filename}")
        for filename in EXECUTION_COMMANDS:
            path = commands_root / filename
            if not path.is_file() or command_model(path) != EXECUTION_MODEL:
                errors.append(f"{workspace.name}: wrong execution model in {filename}")
        if commands_root.is_dir():
            command_digests.append(tree_digest(commands_root))

        engine = workspace / ".opencode" / "workflow" / "scripts" / "check.py"
        if not engine.is_file():
            errors.append(f"{workspace.name}: missing workflow engine")
        else:
            engine_digests.append(hashlib.sha256(engine.read_bytes()).hexdigest())
        fixtures = workspace / ".opencode" / "workflow" / "tests" / "fixtures"
        if not fixtures.is_dir():
            errors.append(f"{workspace.name}: missing workflow fixtures")
        else:
            fixture_digests.append(tree_digest(fixtures))

    if len(set(skill_digests)) > 1:
        errors.append("the three copied skill trees are not byte-identical")
    if len(set(command_digests)) > 1:
        errors.append("the three copied command trees are not byte-identical")
    if len(set(engine_digests)) > 1:
        errors.append("the three copied check.py files are not byte-identical")
    if len(set(fixture_digests)) > 1:
        errors.append("the three copied fixture trees are not byte-identical")
    if skill_digests and any(value != EXPECTED_SKILL_DIGEST for value in skill_digests):
        errors.append("a copied skill tree differs from the frozen benchmark baseline")
    if command_digests and any(value != EXPECTED_COMMAND_DIGEST for value in command_digests):
        errors.append("a copied command tree differs from the frozen benchmark baseline")
    if engine_digests and any(value != EXPECTED_ENGINE_DIGEST for value in engine_digests):
        errors.append("a copied check.py differs from the frozen benchmark baseline")
    if fixture_digests and any(value != EXPECTED_FIXTURE_DIGEST for value in fixture_digests):
        errors.append("a copied fixture tree differs from the frozen benchmark baseline")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: {len(WORKSPACES)} standalone workspaces")
    print(f"skill-tree-sha256: {skill_digests[0]}")
    print(f"command-tree-sha256: {command_digests[0]}")
    print(f"check.py-sha256: {engine_digests[0]}")
    print(f"fixture-tree-sha256: {fixture_digests[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
