import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from verification_runner import RunnerError, main, run_verification  # noqa: E402


class HostModeTests(unittest.TestCase):
    def test_host_success_reports_non_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_verification("echo hello", "host", Path(tmp), 30)
            self.assertEqual(report["schema"], "verification-run/1")
            self.assertEqual(report["mode"], "host")
            self.assertFalse(report["isolated"])
            self.assertEqual(report["exit_code"], 0)
            self.assertIn("hello", report["stdout"])
            self.assertIn("not a sandbox", report["note"])
            self.assertIsNotNone(report["duration_seconds"])

    def test_host_failure_exit_code_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_verification("exit 3", "host", Path(tmp), 30)
            self.assertEqual(report["exit_code"], 3)

    def test_host_timeout_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            command = (
                f'"{sys.executable}" -c "import time; time.sleep(5)"'
            )
            report = run_verification(command, "host", Path(tmp), 1)
            self.assertTrue(report["timed_out"])
            self.assertIsNone(report["exit_code"])

    def test_require_isolation_refuses_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RunnerError, "require-isolation"):
                run_verification("echo x", "host", Path(tmp), 30, require_isolation=True)

    def test_output_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            command = (
                f'"{sys.executable}" -c "print(\'x\' * 400000)"'
            )
            report = run_verification(command, "host", Path(tmp), 30)
            self.assertTrue(report["stdout_truncated"])
            self.assertLessEqual(len(report["stdout"].encode("utf-8")), 200_000)

    def test_invalid_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RunnerError):
                run_verification("echo x", "host", Path(tmp) / "missing", 30)
            with self.assertRaises(RunnerError):
                run_verification("echo x", "host", Path(tmp), 0)
            with self.assertRaises(RunnerError):
                run_verification("echo x", "bogus", Path(tmp), 30)


class ContainerModeTests(unittest.TestCase):
    def test_missing_engine_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RunnerError, "not available|cannot be"):
                run_verification(
                    "echo x",
                    "container",
                    Path(tmp),
                    30,
                    container_image="alpine",
                    container_engine="definitely-not-a-real-engine",
                )

    def test_missing_image_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            # docker may exist on a developer machine; the check order must
            # still refuse a container run without an image.
            with self.assertRaises(RunnerError):
                run_verification("echo x", "container", Path(tmp), 30, container_image=None)


class CliTests(unittest.TestCase):
    def test_cli_writes_report_and_maps_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            out = tmp / "report.json"
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = main(
                    [
                        "run",
                        "--command",
                        "echo ok",
                        "--mode",
                        "host",
                        "--cwd",
                        str(tmp),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertIn("verification report written", stdout.getvalue())
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["exit_code"], 0)
            self.assertFalse(report["isolated"])

    def test_cli_failure_maps_to_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    ["run", "--command", "exit 5", "--mode", "host", "--cwd", str(tmp)]
                )
            self.assertEqual(code, 1)

    def test_cli_isolation_error_maps_to_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stderr(io.StringIO()):
                code = main(
                    [
                        "run",
                        "--command",
                        "echo x",
                        "--mode",
                        "host",
                        "--cwd",
                        str(tmp),
                        "--require-isolation",
                    ]
                )
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
