#!/usr/bin/env python3
"""Machine-checkable assurance floor for Audited slice packages.

Several Audited requirements were prompt-layer claims: a Phase 0 disposition,
a bound test manifest, author separation recorded in the manifest, and a
resolved dispatch state. This module turns those *mechanical facts* into a
deterministic package check.

Boundary: this checker validates structure, presence, hashes and recorded
identities. It cannot and does not judge whether a threat model is complete or
a phrase like "passed" is semantically earned; that remains the independent
reviewer's job. When it cannot verify a required fact it fails closed.

Enforcement is opt-in per package through `assurance-policy.json`
(`assurance-policy/1`, `"strict": true`), mirroring the existing
`runtime-policy.json` pattern; `check.py finish-plan` runs the check when that
file exists. New Audited runs are required by the workflow docs to write the
policy file.

Python 3.10+, stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

POLICY_SCHEMA = "assurance-policy/1"
REQUIRED_PACKAGE_FILES = ("contract.md", "PLAN.md", "workflow-events.jsonl", "change-orders.md")
_TABLE_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|\s*$")
_NOT_BOUND = {"", "pending", "pending-binding", "<subagent/session id>", "tbd", "none"}


class AssuranceError(Exception):
    pass


def load_policy(package_dir: Path) -> dict[str, Any] | None:
    path = package_dir / "assurance-policy.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssuranceError(f"assurance-policy.json unreadable: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != POLICY_SCHEMA:
        raise AssuranceError(f"assurance-policy.json schema must be {POLICY_SCHEMA}")
    if not isinstance(data.get("strict"), bool):
        raise AssuranceError("assurance-policy.json strict must be a boolean")
    return data


def _manifest_table(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in text.splitlines():
        match = _TABLE_ROW.match(line.strip())
        if not match:
            continue
        field = match.group(1).strip()
        if field and field.lower() not in ("field", "---"):
            rows.setdefault(field, match.group(2).strip())
    return rows


def _phase0_problems(package_dir: Path) -> list[str]:
    candidates = sorted(package_dir.glob("evidence/phase-0-*.md"))
    if not candidates:
        for parent in list(package_dir.parents)[:3]:
            candidates.extend(sorted((parent / "evidence").glob("phase-0-*.md")))
    if not candidates:
        return ["phase 0 record is missing (docs/evidence/phase-0-*.md)"]
    text = " ".join(path.read_text(encoding="utf-8-sig").lower() for path in candidates)
    problems = []
    if "refuted" in text:
        problems.append("phase 0 disposition contains 'refuted'")
    if "blocked" in text:
        problems.append("phase 0 disposition contains 'blocked'")
    if "not-needed" not in text and "not needed" not in text and "passed" not in text:
        problems.append("phase 0 record has no clear disposition (passed or not-needed)")
    return problems


def _norm_author(value: str) -> str:
    return value.split("(")[0].strip().lower()


def _manifest_problems(package_dir: Path, manifest_path: Path | None, project_root: Path | None) -> list[str]:
    if manifest_path is None:
        candidates = sorted((package_dir / "test-manifests").glob("*.md"))
        if not candidates:
            candidates = sorted((package_dir / "test-manifests").glob("**/*.md"))
        if not candidates:
            return ["test manifest is missing (test-manifests/*.md)"]
        manifest_path = candidates[-1]
    try:
        rows = _manifest_table(manifest_path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        return [f"test manifest unreadable: {exc}"]
    problems: list[str] = []
    status = rows.get("Provenance status", "")
    if status != "bound":
        problems.append(f"test manifest provenance status is {status!r}, not 'bound'")
    author = rows.get("Test author ID", "")
    author_key = _norm_author(author)
    if not author_key or author_key in _NOT_BOUND:
        problems.append("test manifest has no bound test author id")
    implementer = rows.get("Implementation author ID", "")
    implementer_key = _norm_author(implementer)
    if implementer_key and implementer_key not in _NOT_BOUND | {"pending"} and implementer_key == author_key:
        problems.append("test manifest records the same test and implementation author")
    if not rows.get("Frozen at", ""):
        problems.append("test manifest has no frozen-at timestamp")
    if not rows.get("Spec hash", ""):
        problems.append("test manifest has no spec hash")
    protected = rows.get("Protected test files", "")
    if not protected or protected.lower() in _NOT_BOUND:
        problems.append("test manifest protects no test files")
    else:
        pairs = [item.strip() for item in protected.split(",") if item.strip()]
        resolved_any = False
        for pair in pairs:
            if "=" not in pair:
                problems.append(f"protected test entry lacks path=hash: {pair!r}")
                continue
            path_part, _, hash_part = pair.rpartition("=")
            path_part = path_part.strip().strip("`")
            hash_part = hash_part.strip()
            if not path_part or not hash_part:
                problems.append(f"protected test entry is incomplete: {pair!r}")
                continue
            candidates = []
            if project_root is not None:
                candidates.append(project_root / path_part)
            candidates.append(package_dir / path_part)
            existing = next((item for item in candidates if item.is_file()), None)
            if existing is None:
                problems.append(f"protected test file is missing: {path_part}")
                continue
            resolved_any = True
            actual = hashlib.sha256(existing.read_bytes()).hexdigest()
            if actual != hash_part:
                problems.append(f"protected test hash mismatch: {path_part}")
        if not resolved_any and pairs:
            problems.append("no protected test file could be resolved and verified")
    return problems


def _dispatch_problems(package_dir: Path, dispatch_path: Path | None) -> list[str]:
    if dispatch_path is None:
        candidates = sorted(
            path for path in package_dir.glob("*.dispatch.json") if path.is_file()
        )
        if not candidates:
            return []
        dispatch_path = candidates[0]
    if not dispatch_path.is_file():
        return [f"dispatch record is missing: {dispatch_path}"]
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import workflow_runtime as _runtime  # local import keeps the module optional
    except ImportError as exc:  # pragma: no cover
        return [f"workflow_runtime is unavailable: {exc}"]
    try:
        record = _runtime.load_dispatch(dispatch_path)
    except _runtime.RuntimeStateError as exc:
        return [f"dispatch record is invalid: {exc}"]
    report = _runtime.next_action(record)
    problems = []
    for blocker in report.get("blocked_by") or []:
        kind = blocker.get("kind")
        if kind == "owner-gate":
            continue  # owner gates are legitimate state, not a defect
        problems.append(f"dispatch state blocks completion: {kind}")
    if report["action"]["kind"] == "circuit-break":
        problems.append("dispatch state is at a circuit break")
    return problems


def _infer_project_root(package_dir: Path) -> Path | None:
    """Infer the project root for protected-test paths.

    The five-command layout is `<root>/docs/audit-slices/<goal>/<slice>`; the
    project root is the parent of `docs/`. Otherwise walk up for a project
    marker. When nothing matches, protected paths cannot be resolved and the
    caller should pass an explicit project root."""

    parts = package_dir.parts
    if "audit-slices" in parts:
        index = parts.index("audit-slices")
        if index >= 1:
            docs_root = Path(*parts[:index])
            if docs_root.is_dir():
                return docs_root.parent
    for parent in package_dir.parents:
        if (parent / ".opencode").is_dir() or (parent / ".git").is_dir():
            return parent
    return None


def package_problems(
    package_dir: Path,
    manifest_path: Path | None = None,
    dispatch_path: Path | None = None,
    project_root: Path | None = None,
    require: tuple[str, ...] = ("phase0", "test-manifest", "dispatch"),
) -> list[str]:
    """Mechanical facts a strict Audited package must satisfy. Fail-closed."""

    package_dir = Path(package_dir).resolve()
    if not package_dir.is_dir():
        return [f"package directory does not exist: {package_dir}"]
    if project_root is None:
        project_root = _infer_project_root(package_dir)
    problems: list[str] = []
    for name in REQUIRED_PACKAGE_FILES:
        if not (package_dir / name).is_file():
            problems.append(f"required package file is missing: {name}")
    if "phase0" in require:
        problems.extend(_phase0_problems(package_dir))
    if "test-manifest" in require:
        problems.extend(_manifest_problems(package_dir, manifest_path, project_root))
    if "dispatch" in require:
        problems.extend(_dispatch_problems(package_dir, dispatch_path))
    return problems


def check_package(package_dir: Path, **kwargs: Any) -> dict[str, Any]:
    problems = package_problems(package_dir, **kwargs)
    return {
        "schema": "assurance-report/1",
        "package": str(package_dir).replace("\\", "/"),
        "verdict": "pass" if not problems else "fail",
        "problems": problems,
        "boundary": (
            "structural checks only; semantic adequacy of the phase 0 probe, tests and "
            "review verdicts remains the independent reviewer's judgement"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="check an Audited package's mechanical facts")
    check.add_argument("package", help="slice package directory")
    check.add_argument("--manifest", help="explicit test manifest path")
    check.add_argument("--dispatch", help="explicit dispatch record path")
    check.add_argument("--project-root", help="project root for protected test paths")
    check.add_argument("--out", help="optional report JSON output path")
    args = parser.parse_args(argv)

    if args.cmd == "check":
        report = check_package(
            Path(args.package),
            manifest_path=Path(args.manifest) if args.manifest else None,
            dispatch_path=Path(args.dispatch) if args.dispatch else None,
            project_root=Path(args.project_root) if args.project_root else None,
        )
        text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
        if report["verdict"] == "pass":
            print(f"assurance check PASS: {args.package}")
            return 0
        print(f"assurance check FAIL ({len(report['problems'])}):")
        for problem in report["problems"]:
            print(f"  - {problem}")
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
