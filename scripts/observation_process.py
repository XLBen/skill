#!/usr/bin/env python3
"""Process and encoding boundary for product-observation runs (S14).

Everything that spawns an observation CLI -- product entry points,
agent-browser style tools, session cleanup -- must go through this module so the
runtime keeps four guarantees:

- ``argv`` is executed directly with ``shell=False``. There is never a
  PowerShell command string, so output pipes (``|``, ``2>&1``) cannot truncate
  output or leak half-killed process trees. CLIs such as ``agent-browser`` must
  be invoked as argv arrays, never through a shell output pipeline.
- ``stdout``/``stderr`` leave the process as raw bytes; ``stdout_bytes`` and
  ``stderr_bytes`` are the evidence. Decoding is display/diagnostics only
  (``text_of``) and always uses ``errors="replace"``, so non-UTF-8 output can
  never raise.
- Timeouts kill the whole process tree (``taskkill /PID <pid> /T /F`` on
  Windows, ``os.killpg`` on POSIX) and report ``timed_out`` with no exit code
  instead of hanging or leaking orphan children.
- Session cleanup is scoped: the target session's ``close`` runs first, and the
  global ``close-all`` fallback only when the caller explicitly allows it, so
  other user sessions are never closed implicitly.

This module deliberately does not depend on ``opencode session list --format
json`` or any other host JSON output; it only knows the argv boundary.

Public API::

    run_process(argv, cwd, timeout, env=None) -> dict
    text_of(raw: bytes) -> str
    run_process_capture(argv, cwd, timeout, stdout_path, stderr_path, env=None) -> dict
    kill_process_tree(pid: int) -> bool
    session_cleanup(base_argv, session_id, *, allow_global_cleanup=False, timeout=30) -> dict
    cleanup_directory(path) -> dict
"""

import hashlib
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

_KILL_COMMAND_TIMEOUT = 10
_FINAL_COMMUNICATE_TIMEOUT = 5


def _argv_list(argv: Sequence[Any]) -> list:
    """Copy argv verbatim (no shell string, no joining)."""
    return [os.fsdecode(os.fspath(part)) for part in argv]


def _blank_record(argv: Sequence[Any], cwd: Any) -> dict:
    return {
        "argv": list(argv),
        "cwd": None if cwd is None else str(cwd),
        "exit_code": None,
        "timed_out": False,
        "elapsed_seconds": 0.0,
        "stdout_bytes": b"",
        "stderr_bytes": b"",
        "cleanup": {"kill_attempted": False, "kill_ok": False},
    }


def _normalize_bytes(data: Any) -> bytes:
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    return b""


def _close_pipes(process: subprocess.Popen) -> None:
    for stream in (process.stdout, process.stderr):
        if stream is None:
            continue
        try:
            stream.close()
        except OSError:
            pass


def kill_process_tree(pid: int) -> bool:
    """Kill ``pid`` and its children. Returns True only on a reported success.

    Windows: ``taskkill /PID <pid> /T /F`` as an argv array. POSIX: kill the
    child's process group (children are started with ``start_new_session=True``,
    so the child is the group leader). Any OSError or timeout returns False and
    is never raised.
    """
    if os.name == "nt":
        try:
            completed = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=_KILL_COMMAND_TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return completed.returncode == 0
    try:
        os.killpg(pid, signal.SIGKILL)
        return True
    except OSError:
        return False


def run_process(argv: Sequence[Any], cwd: Any, timeout: float,
                env: Optional[Mapping[str, str]] = None) -> dict:
    """Run ``argv`` directly and capture raw stdout/stderr bytes.

    The returned dict always has the shape::

        {"argv": [...], "cwd": str | None, "exit_code": int | None,
         "timed_out": bool, "elapsed_seconds": float,
         "stdout_bytes": bytes, "stderr_bytes": bytes,
         "cleanup": {"kill_attempted": bool, "kill_ok": bool}}

    ``argv`` is recorded verbatim; redaction is the caller's job. On timeout the
    process tree is killed, one final ``communicate(timeout=5)`` drains the
    pipes, and if that still times out the pipes are abandoned (on Windows the
    streams are deliberately not closed because reader threads may deadlock).

    This function never raises: a missing executable or Popen OSError returns
    ``exit_code=None`` plus an ``"error"`` key describing the failure.
    """
    started = time.perf_counter()
    if isinstance(argv, (str, bytes, os.PathLike)):
        record = _blank_record([], cwd)
        record["argv"] = os.fsdecode(os.fspath(argv))
        record["error"] = (
            "argv must be a sequence of arguments, not a single path/string; "
            "this module never executes through a shell"
        )
        record["elapsed_seconds"] = round(time.perf_counter() - started, 6)
        return record

    record = _blank_record(_argv_list(argv), cwd)
    stdout: bytes = b""
    stderr: bytes = b""
    try:
        process = subprocess.Popen(
            record["argv"],
            cwd=None if cwd is None else os.fspath(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            env=None if env is None else dict(env),
            **({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
               else {"start_new_session": True}),
        )
    except (OSError, ValueError, TypeError) as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["elapsed_seconds"] = round(time.perf_counter() - started, 6)
        return record

    try:
        stdout, stderr = process.communicate(timeout=timeout)
        record["exit_code"] = process.returncode
    except subprocess.TimeoutExpired as exc:
        record["timed_out"] = True
        record["exit_code"] = None
        stdout = _normalize_bytes(exc.stdout)
        stderr = _normalize_bytes(exc.stderr)
        record["cleanup"] = {
            "kill_attempted": True,
            "kill_ok": kill_process_tree(process.pid),
        }
        try:
            stdout, stderr = process.communicate(timeout=_FINAL_COMMUNICATE_TIMEOUT)
        except subprocess.TimeoutExpired as second:
            stdout = _normalize_bytes(second.stdout) or stdout
            stderr = _normalize_bytes(second.stderr) or stderr
            if os.name != "nt":
                _close_pipes(process)
        except OSError as exc:
            record["error"] = f"timeout cleanup failed: {type(exc).__name__}: {exc}"
            if os.name != "nt":
                _close_pipes(process)
        except Exception as exc:  # boundary guarantee: never raise
            record["error"] = f"timeout cleanup failed: {type(exc).__name__}: {exc}"
            if os.name != "nt":
                _close_pipes(process)
    except OSError as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["cleanup"] = {
            "kill_attempted": True,
            "kill_ok": kill_process_tree(process.pid),
        }
    except Exception as exc:  # boundary guarantee: never raise
        record["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        record["stdout_bytes"] = _normalize_bytes(stdout)
        record["stderr_bytes"] = _normalize_bytes(stderr)
        record["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    return record


def text_of(raw: bytes) -> str:
    """Decode raw bytes for display/diagnostics only: UTF-8, replace errors."""
    if not isinstance(raw, (bytes, bytearray)):
        return ""
    return bytes(raw).decode("utf-8", errors="replace")


def run_process_capture(argv: Sequence[Any], cwd: Any, timeout: float,
                        stdout_path: Any, stderr_path: Any,
                        env: Optional[Mapping[str, str]] = None) -> dict:
    """Run ``argv`` via :func:`run_process` and persist the raw byte streams.

    Both paths are created/overwritten (parent directories are created as
    needed) with exactly the captured bytes. The returned dict carries the same
    metadata as :func:`run_process` but not the byte bodies; instead it adds the
    written paths, byte sizes, ``sha256`` digests, and ``stdout_text`` /
    ``stderr_text`` (display-only decode of the same bytes).

    Write failures do not raise: the failing file is reported in ``"error"`` and
    the other stream is still written.
    """
    run = run_process(argv, cwd, timeout, env=env)
    record = {
        "argv": run["argv"],
        "cwd": run["cwd"],
        "exit_code": run["exit_code"],
        "timed_out": run["timed_out"],
        "elapsed_seconds": run["elapsed_seconds"],
        "cleanup": run["cleanup"],
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout_sha256": None,
        "stderr_sha256": None,
        "stdout_size": 0,
        "stderr_size": 0,
        "stdout_text": "",
        "stderr_text": "",
    }
    if "error" in run:
        record["error"] = run["error"]

    write_errors = []
    for kind, path, data in (("stdout", stdout_path, run["stdout_bytes"]),
                             ("stderr", stderr_path, run["stderr_bytes"])):
        record[f"{kind}_text"] = text_of(data)
        try:
            target = Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        except OSError as exc:
            write_errors.append(f"{kind}: {type(exc).__name__}: {exc}")
        else:
            record[f"{kind}_sha256"] = hashlib.sha256(data).hexdigest()
            record[f"{kind}_size"] = len(data)
    if write_errors:
        message = "; ".join(write_errors)
        record["error"] = (
            f"{record['error']}; {message}" if record.get("error") else message
        )
    return record


def _call_summary(phase: str, run: dict) -> dict:
    summary = {
        "phase": phase,
        "argv": run["argv"],
        "exit_code": run["exit_code"],
        "timed_out": run["timed_out"],
        "elapsed_seconds": run["elapsed_seconds"],
        "cleanup": run["cleanup"],
        "stdout_text": text_of(run["stdout_bytes"]),
        "stderr_text": text_of(run["stderr_bytes"]),
    }
    if "error" in run:
        summary["error"] = run["error"]
    return summary


def session_cleanup(base_argv: Sequence[Any], session_id: str, *,
                    allow_global_cleanup: bool = False,
                    timeout: float = 30) -> dict:
    """Close one observation session through its CLI.

    The preferred call is ``[*base_argv, "--session", session_id, "close"]``.
    Only if that fails (non-zero exit, timeout, or spawn error) and the caller
    passed ``allow_global_cleanup=True`` is a single global ``close-all`` run
    attempted. With the default ``allow_global_cleanup=False`` the global
    command is never executed, protecting unrelated user sessions.

    Returns ``{"session_closed": bool, "global_cleanup_used": bool,
    "details": [call summaries]}``; ``session_closed`` is True when the targeted
    close succeeded, or when an allowed global fallback succeeded.
    """
    base = list(base_argv)
    result = {
        "session_closed": False,
        "global_cleanup_used": False,
        "details": [],
    }
    close_run = run_process(base + ["--session", str(session_id), "close"], None, timeout)
    result["details"].append(_call_summary("close", close_run))
    if close_run["exit_code"] == 0 and not close_run["timed_out"]:
        result["session_closed"] = True
        return result

    if allow_global_cleanup:
        result["global_cleanup_used"] = True
        all_run = run_process(base + ["close-all"], None, timeout)
        result["details"].append(_call_summary("close-all", all_run))
        if all_run["exit_code"] == 0 and not all_run["timed_out"]:
            result["session_closed"] = True
    return result


def cleanup_directory(path: Any) -> dict:
    """Remove ``path``; quarantine it once if removal is blocked.

    On ``shutil.rmtree`` OSError a single ``os.rename`` to
    ``<name>.orphaned-<timestamp>`` is attempted. If that also fails the result
    is ``{"removed": False, "locked": True, "detail": ..., "renamed_to": None}``
    and nothing is retried or renamed again. A successful removal (or an
    already-missing path) reports ``removed=True``.
    """
    target = Path(path)
    if not target.exists():
        return {
            "removed": True,
            "locked": False,
            "detail": "path does not exist",
            "renamed_to": None,
        }
    try:
        shutil.rmtree(target)
    except OSError as exc:
        detail = f"{type(exc).__name__}: {exc}"
        renamed = target.with_name(
            f"{target.name}.orphaned-{time.strftime('%Y%m%d-%H%M%S')}"
        )
        try:
            os.rename(target, renamed)
        except OSError as rename_exc:
            detail = (
                f"{detail}; quarantine rename failed: "
                f"{type(rename_exc).__name__}: {rename_exc}"
            )
            return {
                "removed": False,
                "locked": True,
                "detail": detail,
                "renamed_to": None,
            }
        return {
            "removed": True,
            "locked": False,
            "detail": detail,
            "renamed_to": str(renamed),
        }
    return {"removed": True, "locked": False, "detail": "", "renamed_to": None}
