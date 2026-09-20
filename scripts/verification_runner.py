#!/usr/bin/env python3
"""Bounded verification runner with explicit isolation modes.

Audited verification commands currently execute with ambient host authority.
This runner makes the isolation level an explicit, recorded property:

  - `host` mode: runs in the caller's environment and honestly reports
    `isolated: false`. It never claims sandboxing.
  - `container` mode: runs inside a container engine (docker/podman) with the
    workspace mounted at /workspace, network disabled unless `--allow-network`,
    and the image named on the command line. It fails closed when the engine or
    image is unavailable instead of silently degrading.

`--require-isolation` refuses host execution outright. The runner writes a
`verification-run/1` report (command, mode, exit, timeout, bounded output,
duration) that callers can attach as evidence. It does not itself approve any
result, and it is not wired into the engine gates in this version.

Python 3.10+, stdlib only.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

RUN_SCHEMA = "verification-run/1"
OUTPUT_CAP_BYTES = 200_000
_CONTAINER_WORKDIR = "/workspace"


class RunnerError(Exception):
    pass


def _decode(data: bytes) -> tuple[str, bool]:
    truncated = len(data) > OUTPUT_CAP_BYTES
    if truncated:
        data = data[-OUTPUT_CAP_BYTES:]
    return data.decode("utf-8", errors="replace"), truncated


def _run_process(argv: str | list[str], timeout: int, cwd: str | None,
                 shell: bool) -> tuple[int | None, bool, str, bool, str, bool, float]:
    started = time.perf_counter()
    process = subprocess.Popen(
        argv,
        shell=shell,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
           else {"start_new_session": True}),
    )
    timed_out = False
    try:
        stdout_raw, stderr_raw = process.communicate(timeout=timeout)
        exit_code = process.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout_raw, stderr_raw = exc.stdout or b"", exc.stderr or b""
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
                )
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            process.kill()
            stdout_raw, stderr_raw = process.communicate(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            pass
    stdout, stdout_truncated = _decode(stdout_raw)
    stderr, stderr_truncated = _decode(stderr_raw)
    duration = time.perf_counter() - started
    return (
        exit_code,
        timed_out,
        stdout,
        stdout_truncated,
        stderr,
        stderr_truncated,
        duration,
    )


def run_verification(
    command: str,
    mode: str,
    cwd: Path,
    timeout: int,
    container_image: str | None = None,
    container_engine: str = "docker",
    allow_network: bool = False,
    require_isolation: bool = False,
) -> dict[str, Any]:
    cwd = Path(cwd).resolve()
    if not cwd.is_dir():
        raise RunnerError(f"working directory does not exist: {cwd}")
    if not 1 <= timeout <= 3600:
        raise RunnerError("timeout must be between 1 and 3600 seconds")
    if mode == "host" and require_isolation:
        raise RunnerError(
            "--require-isolation was set but mode is host; refusing to run without isolation"
        )
    report: dict[str, Any] = {
        "schema": RUN_SCHEMA,
        "mode": mode,
        "isolated": False,
        "command": command,
        "cwd": str(cwd),
        "engine": None,
        "image": None,
        "network": None,
        "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "exit_code": None,
        "timed_out": False,
        "duration_seconds": None,
        "stdout": "",
        "stdout_truncated": False,
        "stderr": "",
        "stderr_truncated": False,
        "note": "",
    }
    if mode == "host":
        (
            exit_code,
            timed_out,
            stdout,
            stdout_truncated,
            stderr,
            stderr_truncated,
            duration,
        ) = _run_process(command, timeout, str(cwd), shell=True)
        report.update(
            {
                "exit_code": exit_code,
                "timed_out": timed_out,
                "duration_seconds": round(duration, 6),
                "stdout": stdout,
                "stdout_truncated": stdout_truncated,
                "stderr": stderr,
                "stderr_truncated": stderr_truncated,
                "note": (
                    "host mode inherits the caller's environment and credentials; it is not a "
                    "sandbox and cannot contain network, filesystem or credential side effects"
                ),
            }
        )
        return report

    if mode != "container":
        raise RunnerError(f"unknown mode {mode!r}; expected host or container")
    engine_path = shutil.which(container_engine)
    if engine_path is None:
        raise RunnerError(
            f"container engine {container_engine!r} is not available; isolation cannot be "
            "guaranteed. Install the engine or run with an explicit host-mode decision."
        )
    if not container_image:
        raise RunnerError("container mode requires --container-image")
    network = "bridge" if allow_network else "none"
    argv = [
        engine_path,
        "run",
        "--rm",
        "--network",
        network,
        "-v",
        f"{cwd}:{_CONTAINER_WORKDIR}",
        "-w",
        _CONTAINER_WORKDIR,
        container_image,
        "sh",
        "-c",
        command,
    ]
    (
        exit_code,
        timed_out,
        stdout,
        stdout_truncated,
        stderr,
        stderr_truncated,
        duration,
    ) = _run_process(argv, timeout, None, shell=False)
    report.update(
        {
            "isolated": True,
            "engine": Path(engine_path).name,
            "image": container_image,
            "network": network,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "duration_seconds": round(duration, 6),
            "stdout": stdout,
            "stdout_truncated": stdout_truncated,
            "stderr": stderr,
            "stderr_truncated": stderr_truncated,
            "note": (
                "container mode mounts the workspace read-write at /workspace and disables "
                "network by default; the image and engine are recorded. Mounted-workspace "
                "writes are intentional and part of the verification."
            ),
        }
    )
    return report


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run a verification command")
    run.add_argument("--command", required=True)
    run.add_argument("--mode", choices=("host", "container"), default="host")
    run.add_argument("--cwd", default=".")
    run.add_argument("--timeout", type=int, default=300)
    run.add_argument("--container-image")
    run.add_argument("--container-engine", default="docker")
    run.add_argument("--allow-network", action="store_true")
    run.add_argument("--require-isolation", action="store_true")
    run.add_argument("--out", help="optional report JSON path")
    args = parser.parse_args(argv)

    try:
        report = run_verification(
            args.command,
            args.mode,
            Path(args.cwd),
            args.timeout,
            container_image=args.container_image,
            container_engine=args.container_engine,
            allow_network=args.allow_network,
            require_isolation=args.require_isolation,
        )
    except RunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"verification report written: {args.out} "
            f"(mode={report['mode']}, exit={report['exit_code']}, timed_out={report['timed_out']})"
        )
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report["timed_out"]:
        return 1
    return 0 if report["exit_code"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
