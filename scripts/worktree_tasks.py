#!/usr/bin/env python3
"""Isolated worktree helpers for bounded concurrent implementation packages.

The controller stays the single writer of the integration workspace. A
Normal/Guarded work package that is independent and cleanly separable may run in
its own detached Git worktree; this tool creates it, collects what actually
changed, checks it against the declared write scope, preflights and applies the
patch in the integration workspace, and refuses to discard un-integrated work.

Subcommands (all print one JSON object on stdout; failures exit non-zero):

  admission --repo <git-root>
  create   --repo <git-root> --task <T-NN> [--base <ref>] --work-root <dir> [--allow-dirty]
  collect  --worktree <dir> [--out <patch>]
  scope    --worktree <dir> --scope <glob> [--scope <glob> ...]
  apply    --repo <git-root> --patch <file> [--check-only]
  cleanup  --worktree <dir> [--repo <git-root>] [--discard]
  status   --worktree <dir>

Python 3.10+, stdlib only. Git is required only when these helpers are used.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class WorktreeError(Exception):
    pass


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    process = subprocess.run(
        ["git", "-C", str(cwd), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace",
    )
    if check and process.returncode != 0:
        raise WorktreeError(
            f"git {' '.join(args)} failed in {cwd}: {process.stderr.strip() or process.stdout.strip()}"
        )
    return process


def _require_repo(repo: Path) -> Path:
    repo = repo.resolve()
    if not (repo / ".git").exists():
        raise WorktreeError(f"not a Git workspace: {repo}")
    return repo


def admission_problems(repo: Path) -> list[str]:
    """Pre-conditions for opening writer isolation; anything here means serial."""

    problems: list[str] = []
    try:
        repo = _require_repo(repo)
    except WorktreeError as exc:
        return [str(exc)]
    head = _git(repo, "rev-parse", "--verify", "HEAD", check=False)
    if head.returncode != 0:
        problems.append("repository has no HEAD commit to base isolation on")
    dirty = _git(repo, "status", "--porcelain", check=False).stdout.strip()
    if dirty:
        problems.append("integration workspace is not clean; commit or stash controlled changes first")
    return problems


def _porcelain_entries(worktree: Path) -> list[dict[str, str]]:
    raw = _git(worktree, "status", "--porcelain", "-z").stdout
    entries = []
    parts = raw.split("\0")
    index = 0
    while index < len(parts):
        part = parts[index]
        if not part:
            index += 1
            continue
        status = part[:2]
        path = part[3:]
        if "R" in status or "C" in status:
            index += 1
            original = parts[index] if index < len(parts) else ""
            entries.append({"status": status.strip(), "path": path, "original": original})
        else:
            entries.append({"status": status.strip(), "path": path})
        index += 1
    return entries


def create_task(repo: Path, task_id: str, work_root: Path, base: str | None = None,
                allow_dirty: bool = False) -> dict[str, Any]:
    if not task_id or any(character in task_id for character in "\\/:*?\"<>|"):
        raise WorktreeError(f"invalid task id for a directory name: {task_id!r}")
    repo = _require_repo(repo)
    if not allow_dirty:
        problems = admission_problems(repo)
        if problems:
            raise WorktreeError("admission failed: " + "; ".join(problems))
    work_root = work_root.resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    worktree = work_root / task_id
    if worktree.exists():
        raise WorktreeError(f"task worktree already exists: {worktree}")
    base_ref = base or "HEAD"
    base_commit = _git(repo, "rev-parse", base_ref).stdout.strip()
    _git(repo, "worktree", "add", "--detach", str(worktree), base_ref)
    return {"task_id": task_id, "worktree": str(worktree), "base_ref": base_ref,
            "base_commit": base_commit}


def changed_entries(worktree: Path) -> list[dict[str, str]]:
    """Actual changes in the task worktree, including untracked files."""

    worktree = worktree.resolve()
    return _porcelain_entries(worktree)


def collect_patch(worktree: Path, out_path: Path | None = None) -> dict[str, Any]:
    worktree = worktree.resolve()
    # Intent-to-add makes new files appear in `git diff`; deleted, renamed and
    # binary files are covered by --binary and the status entries.
    _git(worktree, "add", "--all", "--intent-to-add")
    entries = changed_entries(worktree)
    diff = _git(worktree, "diff", "--binary", "--no-color", "HEAD").stdout
    result: dict[str, Any] = {
        "worktree": str(worktree),
        "changed": entries,
        "patch_bytes": len(diff.encode("utf-8")),
    }
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(diff, encoding="utf-8", newline="\n")
        result["patch"] = str(out_path)
    else:
        result["patch"] = diff
    return result


def scope_problems(entries: list[dict[str, str]], scope: list[str]) -> list[str]:
    """Report changes whose every real path is not inside the declared scope.

    A rename counts as in scope only when both sides match; a cross-boundary
    move would otherwise let a task touch an out-of-scope destination."""

    if not scope:
        return ["no write scope declared"]
    problems = []
    for entry in entries:
        path = entry["path"]
        original = entry.get("original") or ""
        in_scope = any(fnmatch.fnmatch(path, pattern) for pattern in scope)
        if original:
            in_scope = in_scope and any(
                fnmatch.fnmatch(original, pattern) for pattern in scope
            )
        if not in_scope:
            problems.append(f"{entry['status']} {path} is outside the declared write scope")
    return problems


def apply_patch(repo: Path, patch: Path, check_only: bool = False) -> dict[str, Any]:
    """Apply one collected patch to the integration workspace.

    Workspace cleanliness is an admission condition for *opening new task
    worktrees*, not for integrating a batch: the controller applies patches
    serially, so the workspace is expected to be dirty between them. Safety
    comes from `git apply --check`: a patch that conflicts with existing local
    content is rejected rather than overwriting unrelated work."""

    repo = _require_repo(repo)
    patch = Path(patch).resolve()
    if not patch.is_file():
        raise WorktreeError(f"patch not found: {patch}")
    _git(repo, "apply", "--check", "--binary", str(patch))
    payload: dict[str, Any] = {"repo": str(repo), "patch": str(patch), "applied": False}
    if not check_only:
        _git(repo, "apply", "--binary", str(patch))
        payload["applied"] = True
    return payload


def cleanup(worktree: Path, repo: Path | None = None, discard: bool = False,
            integrated: bool = False) -> dict[str, Any]:
    """Remove a task worktree.

    Un-integrated changes are never silently dropped: pass `--integrated` to
    confirm the collected patch was applied to the integration workspace, or
    `--discard` to explicitly throw the work away."""

    worktree = worktree.resolve()
    if not worktree.is_dir():
        raise WorktreeError(f"task worktree does not exist: {worktree}")
    entries = changed_entries(worktree)
    if entries and not (discard or integrated):
        raise WorktreeError(
            "refusing to remove a worktree with un-integrated changes; apply the collected "
            "patch and pass --integrated, or pass --discard to drop "
            f"{len(entries)} changed file(s)"
        )
    payload: dict[str, Any] = {
        "worktree": str(worktree),
        "discarded_changes": entries if discard else [],
        "confirmed_integrated": bool(integrated) and bool(entries),
    }
    if repo is not None:
        repo = _require_repo(repo)
        _git(repo, "worktree", "remove", "--force", str(worktree))
    else:
        try:
            _git(worktree, "rev-parse", "--git-dir")
        except WorktreeError:
            shutil.rmtree(worktree, ignore_errors=True)
        else:
            shutil.rmtree(worktree, ignore_errors=True)
    return payload


def task_status(worktree: Path) -> dict[str, Any]:
    worktree = worktree.resolve()
    if not worktree.is_dir():
        return {"worktree": str(worktree), "exists": False}
    entries = changed_entries(worktree)
    return {"worktree": str(worktree), "exists": True, "changed": entries}


def _load_plan_steps(plan_path: Path) -> tuple[dict[str, dict[str, Any]], list[tuple[str, str]]]:
    """Read step definitions from a compiled PLAN (markdown fence or raw JSON)."""

    try:
        text = plan_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise WorktreeError(f"PLAN unreadable: {exc}") from exc
    if plan_path.suffix.lower() == ".json":
        try:
            plan = json.loads(text)
        except json.JSONDecodeError as exc:
            raise WorktreeError(f"PLAN JSON is invalid: {exc}") from exc
    else:
        marker = "```json plan"
        if marker not in text:
            raise WorktreeError(f"PLAN has no json plan fence: {plan_path}")
        try:
            plan = json.loads(text.split(marker, 1)[1].split("```", 1)[0])
        except json.JSONDecodeError as exc:
            raise WorktreeError(f"PLAN fence JSON is invalid: {exc}") from exc
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list):
        raise WorktreeError("PLAN has no steps list")
    steps: dict[str, dict[str, Any]] = {}
    for step in plan["steps"]:
        if isinstance(step, dict) and isinstance(step.get("id"), str):
            steps[step["id"]] = step
    unit_edges = [
        (edge[0], edge[1])
        for edge in (plan.get("unit_dag") or [])
        if isinstance(edge, (list, tuple)) and len(edge) == 2
    ]
    return steps, unit_edges


def _scope_overlap(left: str, right: str) -> bool:
    """Conservative overlap test for write-scope globs.

    Anything uncertain counts as overlapping (dependencies, shared prefixes,
    wildcards), so an unsafe batch falls back to serial instead of guessing."""

    def literal_prefix(pattern: str) -> str:
        cut = len(pattern)
        for index, character in enumerate(pattern):
            if character in "*?[":
                cut = index
                break
        prefix = pattern[:cut].replace("\\", "/").rstrip("/")
        return prefix

    left_norm = left.replace("\\", "/")
    right_norm = right.replace("\\", "/")
    if left_norm == right_norm:
        return True
    left_prefix = literal_prefix(left_norm)
    right_prefix = literal_prefix(right_norm)
    if left_prefix and right_prefix:
        if left_prefix == right_prefix:
            return True
        if left_prefix.startswith(right_prefix + "/") or right_prefix.startswith(left_prefix + "/"):
            return True
    # A wildcard in the middle of either pattern makes the comparison uncertain.
    if ("*" in left_norm or "?" in left_norm or "[" in left_norm) and (
        right_prefix.startswith(left_prefix) or left_prefix.startswith(right_prefix)
    ):
        return True
    if ("*" in right_norm or "?" in right_norm or "[" in right_norm) and (
        left_prefix.startswith(right_prefix) or right_prefix.startswith(left_prefix)
    ):
        return True
    return False


def _reaches(start: str, target: str, adjacency: dict[str, set[str]]) -> bool:
    seen = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        if node == target:
            return True
        for nxt in adjacency.get(node, set()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return False


def parallel_plan_problems(
    plan_path: Path,
    tasks: list[dict[str, Any]],
    protected: list[str] | None = None,
    max_writers: int = 2,
) -> list[str]:
    """Admission check for running strict PLAN steps in isolated worktrees.

    The batch is admissible only when every referenced step exists, no two
    tasks share or depend on each other's steps/units, declared write scopes
    are provably disjoint, no protected acceptance path is inside a scope, and
    the writer count stays within the declared limit. Any uncertainty means
    serial fallback, never a guess."""

    problems: list[str] = []
    if not 1 <= max_writers <= 3:
        raise WorktreeError("max_writers must be between 1 and 3")
    steps, unit_edges = _load_plan_steps(Path(plan_path))
    if not isinstance(tasks, list) or not tasks:
        return ["tasks must be a nonempty list"]
    if len(tasks) > max_writers:
        problems.append(
            f"{len(tasks)} tasks exceed the writer limit of {max_writers}; run in serial waves"
        )
    assigned: dict[str, str] = {}
    for task in tasks:
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            problems.append("every task needs a nonempty task_id")
            continue
        step_ids = task.get("step_ids")
        if not isinstance(step_ids, list) or not step_ids:
            problems.append(f"task {task_id}: step_ids must be a nonempty list")
            continue
        for step_id in step_ids:
            if step_id not in steps:
                problems.append(f"task {task_id}: unknown PLAN step {step_id!r}")
            if step_id in assigned:
                problems.append(
                    f"step {step_id} is assigned to both {assigned[step_id]} and {task_id}"
                )
            assigned[step_id] = task_id
        scope = task.get("write_scope")
        if not isinstance(scope, list) or not scope or any(
            not isinstance(item, str) or not item for item in scope
        ):
            problems.append(f"task {task_id}: write_scope must be a nonempty string list")
    if problems:
        return problems

    unit_of = {step_id: steps[step_id].get("unit") for step_id in assigned}
    step_adjacency: dict[str, set[str]] = {}
    for step_id, step in steps.items():
        step_adjacency[step_id] = {
            dep for dep in (step.get("depends_on_segments") or []) if isinstance(dep, str)
        }
    unit_adjacency: dict[str, set[str]] = {}
    for source, target in unit_edges:
        unit_adjacency.setdefault(source, set()).add(target)

    for index, left in enumerate(tasks):
        left_steps = left["step_ids"]
        for right in tasks[index + 1:]:
            right_steps = right["step_ids"]
            dependency_found = False
            for left_step in left_steps:
                for right_step in right_steps:
                    if _reaches(left_step, right_step, step_adjacency) or _reaches(
                        right_step, left_step, step_adjacency
                    ):
                        dependency_found = True
                    left_unit, right_unit = unit_of[left_step], unit_of[right_step]
                    if left_unit and right_unit and (
                        _reaches(left_unit, right_unit, unit_adjacency)
                        or _reaches(right_unit, left_unit, unit_adjacency)
                    ):
                        dependency_found = True
            if dependency_found:
                problems.append(
                    f"tasks {left['task_id']} and {right['task_id']} have a step/unit dependency; "
                    "run the dependent task in a later wave"
                )
            for left_scope in left["write_scope"]:
                for right_scope in right["write_scope"]:
                    if _scope_overlap(left_scope, right_scope):
                        problems.append(
                            f"tasks {left['task_id']} and {right['task_id']} have overlapping "
                            f"write scopes ({left_scope!r}, {right_scope!r}); serial fallback"
                        )
    for task in tasks:
        for scope in task["write_scope"]:
            for pattern in protected or []:
                if _scope_overlap(scope, pattern):
                    problems.append(
                        f"task {task['task_id']}: write scope {scope!r} touches protected "
                        f"acceptance path {pattern!r}"
                    )
    return problems


def parallel_plan(
    plan_path: Path,
    tasks: list[dict[str, Any]],
    protected: list[str] | None = None,
    max_writers: int = 2,
) -> dict[str, Any]:
    problems = parallel_plan_problems(plan_path, tasks, protected, max_writers)
    return {
        "schema": "workflow-parallel-plan/1",
        "plan": str(Path(plan_path).resolve()).replace("\\", "/"),
        "max_writers": max_writers,
        "admissible": not problems,
        "problems": problems,
        "tasks": [
            {
                "task_id": task.get("task_id"),
                "step_ids": task.get("step_ids"),
                "write_scope": task.get("write_scope"),
                "work_root": task.get("work_root"),
            }
            for task in tasks
        ],
        "rules": {
            "integration": "controller applies collected patches serially",
            "formal_v": "after integration, on the canonical version, controller-owned",
            "review": "fresh reviewer sees the integrated version only",
            "protected_tests": "write scopes must not touch frozen acceptance paths",
            "fallback": "any failed condition means serial execution",
        },
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("admission")
    p.add_argument("--repo", required=True)
    p = sub.add_parser("create")
    p.add_argument("--repo", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--base")
    p.add_argument("--work-root", required=True)
    p.add_argument("--allow-dirty", action="store_true")
    p = sub.add_parser("collect")
    p.add_argument("--worktree", required=True)
    p.add_argument("--out")
    p = sub.add_parser("scope")
    p.add_argument("--worktree", required=True)
    p.add_argument("--scope", action="append", default=[])
    p = sub.add_parser("apply")
    p.add_argument("--repo", required=True)
    p.add_argument("--patch", required=True)
    p.add_argument("--check-only", action="store_true")
    p = sub.add_parser("cleanup")
    p.add_argument("--worktree", required=True)
    p.add_argument("--repo")
    p.add_argument("--integrated", action="store_true",
                   help="confirm the collected patch was applied to the integration workspace")
    p.add_argument("--discard", action="store_true",
                   help="explicitly drop un-integrated work")
    p = sub.add_parser("status")
    p.add_argument("--worktree", required=True)
    p = sub.add_parser("parallel-plan",
                       help="admission check for a strict parallel implementation batch")
    p.add_argument("--plan", required=True, help="compiled PLAN markdown or JSON")
    p.add_argument("--tasks", required=True, help="task batch JSON file")
    p.add_argument("--protected", action="append", default=[],
                   help="protected acceptance path glob (repeatable)")
    p.add_argument("--max-writers", type=int, default=2)
    args = parser.parse_args(argv)

    try:
        if args.cmd == "admission":
            problems = admission_problems(Path(args.repo))
            print(json.dumps({"admissible": not problems, "problems": problems},
                             ensure_ascii=False, indent=2))
            return 0 if not problems else 1
        if args.cmd == "create":
            print(json.dumps(create_task(Path(args.repo), args.task, Path(args.work_root),
                                         args.base, args.allow_dirty),
                             ensure_ascii=False, indent=2))
            return 0
        if args.cmd == "collect":
            result = collect_patch(Path(args.worktree), Path(args.out) if args.out else None)
            if args.out is None:
                result = {k: v for k, v in result.items() if k != "patch"}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.cmd == "scope":
            entries = changed_entries(Path(args.worktree))
            problems = scope_problems(entries, args.scope)
            print(json.dumps({"in_scope": not problems, "problems": problems,
                              "changed": entries}, ensure_ascii=False, indent=2))
            return 0 if not problems else 1
        if args.cmd == "apply":
            print(json.dumps(apply_patch(Path(args.repo), Path(args.patch), args.check_only),
                             ensure_ascii=False, indent=2))
            return 0
        if args.cmd == "cleanup":
            print(json.dumps(cleanup(Path(args.worktree), Path(args.repo) if args.repo else None,
                                     args.discard, args.integrated),
                             ensure_ascii=False, indent=2))
            return 0
        if args.cmd == "status":
            print(json.dumps(task_status(Path(args.worktree)), ensure_ascii=False, indent=2))
            return 0
        if args.cmd == "parallel-plan":
            try:
                batch = json.loads(Path(args.tasks).read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                raise WorktreeError(f"task batch unreadable: {exc}") from exc
            tasks = batch.get("tasks") if isinstance(batch, dict) else None
            if not isinstance(tasks, list):
                raise WorktreeError("task batch must be an object with a tasks list")
            report = parallel_plan(
                Path(args.plan), tasks, protected=args.protected, max_writers=args.max_writers
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["admissible"] else 1
    except WorktreeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(_main())
