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
    except WorktreeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(_main())
