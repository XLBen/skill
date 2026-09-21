"""S14: process and encoding boundary.

Covers argv-direct execution, exact byte capture, timeout tree kill, scoped
session cleanup, and locked-directory quarantine. Platform-specific behavior is
selected with ``os.name``; no Windows-only assertion runs on POSIX.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import observation_process as op  # noqa: E402

PY = sys.executable
NEWLINE = os.linesep.encode("ascii")
SLEEPING = "import time; time.sleep(30)"

STUB_SOURCE = (
    "import json\n"
    "import os\n"
    "import sys\n"
    "\n"
    'log = os.environ["S14_SESSION_LOG"]\n'
    'with open(log, "a", encoding="utf-8") as handle:\n'
    '    handle.write(json.dumps(sys.argv[1:]) + "\\n")\n'
    'if os.environ.get("S14_CLOSE_OK") == "1":\n'
    "    sys.exit(0)\n"
    'sys.exit(0 if sys.argv[-1] == "close-all" else 7)\n'
)


class RunProcessTests(unittest.TestCase):
    def test_success_records_exact_bytes(self):
        result = op.run_process([PY, "-c", "print('hello')"], cwd=None, timeout=30)
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout_bytes"], b"hello" + NEWLINE)
        self.assertEqual(result["stderr_bytes"], b"")
        self.assertEqual(result["argv"], [PY, "-c", "print('hello')"])
        self.assertEqual(result["cleanup"], {"kill_attempted": False, "kill_ok": False})
        self.assertNotIn("error", result)
        self.assertGreaterEqual(result["elapsed_seconds"], 0.0)

    def test_nonzero_exit_is_reported(self):
        result = op.run_process([PY, "-c", "import sys; sys.exit(3)"], cwd=None, timeout=30)
        self.assertEqual(result["exit_code"], 3)
        self.assertFalse(result["timed_out"])

    def test_timeout_kills_tree_and_bounds_elapsed(self):
        started = time.monotonic()
        result = op.run_process([PY, "-c", SLEEPING], cwd=None, timeout=2)
        wall = time.monotonic() - started
        self.assertTrue(result["timed_out"])
        self.assertIsNone(result["exit_code"])
        self.assertLess(wall, 20)
        self.assertLess(result["elapsed_seconds"], 20)
        self.assertTrue(result["cleanup"]["kill_attempted"])
        self.assertIsInstance(result["cleanup"]["kill_ok"], bool)

    def test_cwd_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = op.run_process(
                [PY, "-c", "import os; print(os.getcwd())"], cwd=tmp, timeout=30
            )
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(result["cwd"], tmp)
            reported = op.text_of(result["stdout_bytes"]).strip()
            self.assertEqual(
                os.path.normcase(os.path.realpath(reported)),
                os.path.normcase(os.path.realpath(tmp)),
            )

    def test_non_utf8_output_does_not_raise(self):
        code = "import sys; sys.stdout.buffer.write(b'\\xff\\xfe')"
        result = op.run_process([PY, "-c", code], cwd=None, timeout=30)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout_bytes"], b"\xff\xfe")
        self.assertEqual(op.text_of(result["stdout_bytes"]), "\ufffd\ufffd")

    def test_text_of_replaces_invalid_bytes(self):
        self.assertEqual(op.text_of(b"plain"), "plain")
        self.assertEqual(op.text_of(b"\xff\xfe"), "\ufffd\ufffd")

    def test_env_is_forwarded(self):
        env = dict(os.environ, S14_ENV_MARKER="s14-marker")
        result = op.run_process(
            [PY, "-c", "import os; print(os.environ.get('S14_ENV_MARKER', ''))"],
            cwd=None, timeout=30, env=env,
        )
        self.assertIn("s14-marker", op.text_of(result["stdout_bytes"]))

    def test_missing_binary_returns_error_instead_of_raising(self):
        result = op.run_process(["definitely-not-a-real-binary-s14"], cwd=None, timeout=10)
        self.assertIsNone(result["exit_code"])
        self.assertFalse(result["timed_out"])
        self.assertIn("error", result)
        self.assertTrue(result["error"])

    def test_shell_string_argv_is_rejected(self):
        result = op.run_process("echo hello", cwd=None, timeout=10)
        self.assertIsNone(result["exit_code"])
        self.assertIn("error", result)
        self.assertIn("never executes through a shell", result["error"])


class RunProcessCaptureTests(unittest.TestCase):
    def test_capture_writes_exact_bytes_sha256_and_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            stdout_path = Path(tmp) / "nested" / "stdout.bin"
            stderr_path = Path(tmp) / "nested" / "stderr.bin"
            code = (
                "import sys; sys.stdout.buffer.write(b'out\\xff'); "
                "sys.stderr.buffer.write(b'err')"
            )
            result = op.run_process_capture(
                [PY, "-c", code], cwd=None, timeout=30,
                stdout_path=stdout_path, stderr_path=stderr_path,
            )
            self.assertEqual(result["exit_code"], 0)
            stdout_bytes = stdout_path.read_bytes()
            stderr_bytes = stderr_path.read_bytes()
            self.assertEqual(stdout_bytes, b"out\xff")
            self.assertEqual(stderr_bytes, b"err")
            self.assertEqual(result["stdout_sha256"], hashlib.sha256(stdout_bytes).hexdigest())
            self.assertEqual(result["stderr_sha256"], hashlib.sha256(stderr_bytes).hexdigest())
            self.assertEqual(result["stdout_size"], len(stdout_bytes))
            self.assertEqual(result["stderr_size"], len(stderr_bytes))
            self.assertEqual(result["stdout_text"], "out\ufffd")
            self.assertEqual(result["stderr_text"], "err")
            self.assertEqual(result["stdout_path"], str(stdout_path))
            self.assertEqual(result["stderr_path"], str(stderr_path))
            self.assertNotIn("stdout_bytes", result)
            self.assertNotIn("stderr_bytes", result)

    def test_capture_overwrites_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            stdout_path = Path(tmp) / "stdout.bin"
            stderr_path = Path(tmp) / "stderr.bin"
            stdout_path.write_bytes(b"stale")
            stderr_path.write_bytes(b"stale")
            result = op.run_process_capture(
                [PY, "-c", "print('fresh')"], cwd=None, timeout=30,
                stdout_path=stdout_path, stderr_path=stderr_path,
            )
            self.assertEqual(stdout_path.read_bytes(), b"fresh" + NEWLINE)
            self.assertEqual(stderr_path.read_bytes(), b"")
            self.assertEqual(result["stderr_sha256"], hashlib.sha256(b"").hexdigest())


class KillProcessTreeTests(unittest.TestCase):
    def _popen_kwargs(self):
        return ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
                else {"start_new_session": True})

    def test_exited_pid_returns_bool_without_raising(self):
        process = subprocess.Popen(
            [PY, "-c", "pass"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            **self._popen_kwargs(),
        )
        process.communicate(timeout=30)
        result = op.kill_process_tree(process.pid)
        self.assertIsInstance(result, bool)

    def test_live_process_tree_is_killed(self):
        process = subprocess.Popen(
            [PY, "-c", SLEEPING], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            **self._popen_kwargs(),
        )
        try:
            self.assertTrue(op.kill_process_tree(process.pid))
            process.communicate(timeout=15)
            self.assertIsNotNone(process.returncode)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=15)


class SessionCleanupTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.stub = self.tmp / "session_stub.py"
        self.stub.write_text(STUB_SOURCE, encoding="utf-8")
        self.log = self.tmp / "calls.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def calls(self):
        if not self.log.exists():
            return []
        return [
            json.loads(line)
            for line in self.log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_close_only_when_global_cleanup_disallowed(self):
        with mock.patch.dict(os.environ, {"S14_SESSION_LOG": str(self.log),
                                          "S14_CLOSE_OK": "0"}):
            result = op.session_cleanup(
                [PY, str(self.stub)], "session-1",
                allow_global_cleanup=False, timeout=30,
            )
        calls = self.calls()
        self.assertEqual(calls, [["--session", "session-1", "close"]])
        self.assertFalse(result["session_closed"])
        self.assertFalse(result["global_cleanup_used"])
        self.assertEqual(len(result["details"]), 1)
        self.assertEqual(result["details"][0]["phase"], "close")
        self.assertEqual(result["details"][0]["exit_code"], 7)

    def test_global_cleanup_fallback_when_allowed(self):
        with mock.patch.dict(os.environ, {"S14_SESSION_LOG": str(self.log),
                                          "S14_CLOSE_OK": "0"}):
            result = op.session_cleanup(
                [PY, str(self.stub)], "session-2",
                allow_global_cleanup=True, timeout=30,
            )
        self.assertEqual(
            self.calls(),
            [["--session", "session-2", "close"], ["close-all"]],
        )
        self.assertTrue(result["global_cleanup_used"])
        self.assertTrue(result["session_closed"])
        self.assertEqual([d["phase"] for d in result["details"]], ["close", "close-all"])

    def test_successful_close_skips_global_cleanup_even_when_allowed(self):
        with mock.patch.dict(os.environ, {"S14_SESSION_LOG": str(self.log),
                                          "S14_CLOSE_OK": "1"}):
            result = op.session_cleanup(
                [PY, str(self.stub)], "session-3",
                allow_global_cleanup=True, timeout=30,
            )
        self.assertEqual(self.calls(), [["--session", "session-3", "close"]])
        self.assertTrue(result["session_closed"])
        self.assertFalse(result["global_cleanup_used"])


class CleanupDirectoryTests(unittest.TestCase):
    def test_removes_directory_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "locked"
            (target / "sub").mkdir(parents=True)
            (target / "sub" / "file.txt").write_text("x", encoding="utf-8")
            result = op.cleanup_directory(target)
            self.assertTrue(result["removed"])
            self.assertFalse(result["locked"])
            self.assertIsNone(result["renamed_to"])
            self.assertFalse(target.exists())

    def test_missing_path_reports_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = op.cleanup_directory(Path(tmp) / "not-there")
        self.assertTrue(result["removed"])
        self.assertFalse(result["locked"])
        self.assertIsNone(result["renamed_to"])

    def test_locked_directory_is_quarantined_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "locked"
            target.mkdir()
            with mock.patch.object(op.shutil, "rmtree",
                                   side_effect=OSError("locked by another process")) as rmtree_mock, \
                 mock.patch.object(op.os, "rename",
                                   side_effect=OSError("still locked")):
                result = op.cleanup_directory(target)
            self.assertEqual(rmtree_mock.call_count, 1)
            self.assertFalse(result["removed"])
            self.assertTrue(result["locked"])
            self.assertTrue(result["detail"])
            self.assertIsNone(result["renamed_to"])
            self.assertTrue(target.exists())

    def test_rename_quarantine_when_rmtree_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "locked"
            target.mkdir()
            (target / "file.txt").write_text("x", encoding="utf-8")
            with mock.patch.object(op.shutil, "rmtree",
                                   side_effect=OSError("in use")):
                result = op.cleanup_directory(target)
            self.assertTrue(result["removed"])
            self.assertFalse(result["locked"])
            self.assertFalse(target.exists())
            renamed_to = Path(result["renamed_to"])
            self.assertTrue(renamed_to.exists())
            self.assertTrue(renamed_to.name.startswith("locked.orphaned-"))


if __name__ == "__main__":
    unittest.main()
