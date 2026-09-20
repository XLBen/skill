#!/usr/bin/env python3
"""Package sealing for completed Audited slice packages.

A completed package is immutable by protocol; this tool makes that property
checkable. `seal` writes a canonical manifest (every file with path, size and
sha256, plus a root hash) outside the mutable package state, and `verify`
recomputes it to report added, removed or changed files.

Boundary: a local seal detects changes relative to the sealed baseline; it is
not tamper-proof, because a writer with filesystem access can re-seal the
package. Projects that need adversarial tamper evidence must anchor the root
hash in an external, write-protected store (VCS tag, CI attestation); this
tool never auto-commits or configures an external service.

Usage:

  package_seal.py seal <package-dir> [--out <seal.json>] [--parent <seal.json>]
  package_seal.py verify <seal.json>
  package_seal.py verify-package <package-dir>   # seal path defaults to <pkg>/package-seal.json

Python 3.10+, stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SEAL_SCHEMA = "package-seal/1"
DEFAULT_SEAL_NAME = "package-seal.json"


class SealError(Exception):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_files(package_dir: Path, seal_path: Path) -> list[Path]:
    files = []
    for path in sorted(package_dir.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.name.endswith(".pyc"):
            continue
        if path.resolve() == seal_path.resolve():
            continue
        files.append(path)
    return files


def _root_hash(entries: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item["path"]):
        digest.update(entry["path"].encode("utf-8") + b"\0")
        digest.update(entry["sha256"].encode("ascii") + b"\0")
        digest.update(str(entry["bytes"]).encode("ascii") + b"\0")
    return digest.hexdigest()


def seal_package(
    package_dir: Path,
    out_path: Path | None = None,
    parent_seal: Path | None = None,
) -> dict[str, Any]:
    package_dir = Path(package_dir).resolve()
    if not package_dir.is_dir():
        raise SealError(f"package directory does not exist: {package_dir}")
    out_path = (Path(out_path) if out_path else package_dir / DEFAULT_SEAL_NAME).resolve()
    entries: list[dict[str, Any]] = []
    for path in _package_files(package_dir, out_path):
        entries.append(
            {
                "path": path.relative_to(package_dir).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    if not entries:
        raise SealError(f"package has no files to seal: {package_dir}")
    seal: dict[str, Any] = {
        "schema": SEAL_SCHEMA,
        "package": package_dir.name,
        "files": entries,
        "file_count": len(entries),
        "root_hash": _root_hash(entries),
        "note": (
            "local seal detects changes relative to this baseline; it is not tamper-proof. "
            "Anchor root_hash externally when adversarial tampering matters."
        ),
    }
    if parent_seal is not None:
        try:
            parent = json.loads(Path(parent_seal).read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SealError(f"parent seal unreadable: {exc}") from exc
        if not isinstance(parent, dict) or parent.get("schema") != SEAL_SCHEMA:
            raise SealError("parent seal has an invalid schema")
        seal["parent"] = {
            "package": parent.get("package"),
            "root_hash": parent.get("root_hash"),
        }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(seal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return seal


def verify_seal(seal_path: Path) -> dict[str, Any]:
    seal_path = Path(seal_path).resolve()
    try:
        seal = json.loads(seal_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SealError(f"seal unreadable: {exc}") from exc
    if not isinstance(seal, dict) or seal.get("schema") != SEAL_SCHEMA:
        raise SealError(f"seal schema must be {SEAL_SCHEMA}")
    package_dir = seal_path.parent
    recorded = {
        entry["path"]: entry
        for entry in seal.get("files") or []
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    }
    current: dict[str, dict[str, Any]] = {}
    for path in _package_files(package_dir, seal_path):
        relative = path.relative_to(package_dir).as_posix()
        current[relative] = {
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    added = sorted(set(current) - set(recorded))
    removed = sorted(set(recorded) - set(current))
    changed = sorted(
        path
        for path in set(recorded) & set(current)
        if recorded[path].get("sha256") != current[path]["sha256"]
    )
    problems: list[str] = []
    if added:
        problems.append("files added after sealing: " + ", ".join(added))
    if removed:
        problems.append("files removed after sealing: " + ", ".join(removed))
    if changed:
        problems.append("files changed after sealing: " + ", ".join(changed))
    if not problems:
        recomputed = _root_hash(list(current.values()))
        if recomputed != seal.get("root_hash"):
            problems.append("root hash mismatch")
    return {
        "schema": "package-seal-report/1",
        "seal": str(seal_path).replace("\\", "/"),
        "package": seal.get("package"),
        "root_hash": seal.get("root_hash"),
        "verdict": "pass" if not problems else "fail",
        "added": added,
        "removed": removed,
        "changed": changed,
        "problems": problems,
        "note": (
            "detects changes relative to the sealed baseline only; re-sealing by a writer "
            "is visible as a different root_hash only when an external anchor exists"
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
    seal = sub.add_parser("seal", help="seal a package directory")
    seal.add_argument("package")
    seal.add_argument("--out", help=f"seal output path (default <pkg>/{DEFAULT_SEAL_NAME})")
    seal.add_argument("--parent", help="parent package seal for SI/FIX lineage")
    verify = sub.add_parser("verify", help="verify a seal against the package")
    verify.add_argument("seal")
    verify_package = sub.add_parser("verify-package", help="verify <pkg>/package-seal.json")
    verify_package.add_argument("package")
    args = parser.parse_args(argv)

    try:
        if args.cmd == "seal":
            result = seal_package(
                Path(args.package),
                out_path=Path(args.out) if args.out else None,
                parent_seal=Path(args.parent) if args.parent else None,
            )
            print(
                f"package sealed: {args.package} "
                f"(files={result['file_count']}, root={result['root_hash']})"
            )
            return 0
        if args.cmd == "verify":
            report = verify_seal(Path(args.seal))
            return _report(report)
        if args.cmd == "verify-package":
            report = verify_seal(Path(args.package) / DEFAULT_SEAL_NAME)
            return _report(report)
    except SealError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


def _report(report: dict[str, Any]) -> int:
    if report["verdict"] == "pass":
        print(f"seal verified: {report['seal']} (root={report['root_hash']})")
        return 0
    print(f"seal FAIL ({len(report['problems'])}):")
    for problem in report["problems"]:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
