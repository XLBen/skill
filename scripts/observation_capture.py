#!/usr/bin/env python3
"""Controller-provided evidence capture helper for CLI/API products.

The observer's shell cannot use redirection or file-writing commands (the
agent permission rules deny them on purpose). For CLI products the observer
still must persist real command output as evidence, so this helper runs an
approved command and writes the raw bytes plus a metadata record under the
round evidence directory.

Usage:

    python observation_capture.py --evidence-root <evidence_dir> \
        --out <evidence_dir>/mode-a.txt [--cwd DIR] [--timeout 60] \
        -- <command> [args...]

The helper prints the captured stdout so the observer can read it in the same
step. It never writes outside the evidence root and never uses a shell.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import observation_process as op
else:  # pragma: no cover - package import path
    from . import observation_process as op


def _utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def capture(evidence_root: Path, out: Path, argv: list[str], cwd: Path,
            timeout: float) -> tuple[int, str]:
    root = Path(evidence_root)
    if not root.is_dir():
        return 2, f"evidence root does not exist: {root}"
    target = Path(out)
    if not target.is_absolute():
        target = (cwd / target).resolve()
    if not _inside(target, root):
        return 2, f"refusing to write outside the evidence root: {target}"
    if not argv:
        return 2, "no command given after --"

    result = op.run_process(argv, cwd=cwd, timeout=timeout)
    if "error" in result:
        return 2, f"command could not start: {result['error']}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(result["stdout_bytes"])
    stderr_path = target.with_suffix(target.suffix + ".stderr.txt")
    stderr_path.write_bytes(result["stderr_bytes"])
    meta = {
        "schema": "observation-capture/1",
        "argv": argv,
        "cwd": str(Path(cwd).resolve()),
        "exit_code": result["exit_code"],
        "timed_out": result["timed_out"],
        "elapsed_seconds": result["elapsed_seconds"],
        "stdout_path": str(target).replace("\\", "/"),
        "stdout_sha256": hashlib.sha256(result["stdout_bytes"]).hexdigest(),
        "stderr_path": str(stderr_path).replace("\\", "/"),
        "stderr_sha256": hashlib.sha256(result["stderr_bytes"]).hexdigest(),
    }
    meta_path = target.with_suffix(target.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")
    summary = (
        f"captured argv={json.dumps(argv, ensure_ascii=False)} "
        f"exit={result['exit_code']} timed_out={result['timed_out']} "
        f"evidence={target} stderr={stderr_path}"
    )
    return 0, summary + "\n--stdout--\n" + op.text_of(result["stdout_bytes"])


def main(argv: list[str] | None = None) -> int:
    _utf8()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command[:1] == ["--"]:
        command = command[1:]
    code, message = capture(Path(args.evidence_root), Path(args.out), command,
                            Path(args.cwd), args.timeout)
    stream = sys.stdout if code == 0 else sys.stderr
    print(message, file=stream)
    return code


if __name__ == "__main__":
    sys.exit(main())
