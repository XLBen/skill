import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import observation_capture as oc  # noqa: E402


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(self._cleanup)
        self.evidence = self.tmp / "evidence"
        self.evidence.mkdir()

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_capture_writes_stdout_stderr_and_meta(self):
        out = self.evidence / "mode-a.txt"
        code, message = oc.capture(
            self.evidence, out,
            [sys.executable, "-c", "import sys;print('hello');print('boom', file=sys.stderr)"],
            self.tmp, 30,
        )
        self.assertEqual(code, 0, message)
        self.assertEqual(out.read_bytes().replace(b"\r\n", b"\n"), b"hello\n")
        self.assertIn("hello", message)
        stderr_path = out.with_suffix(out.suffix + ".stderr.txt")
        self.assertEqual(stderr_path.read_bytes().replace(b"\r\n", b"\n"), b"boom\n")
        meta = json.loads(out.with_suffix(out.suffix + ".meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["schema"], "observation-capture/1")
        self.assertEqual(meta["exit_code"], 0)
        self.assertFalse(meta["timed_out"])
        self.assertEqual(len(meta["stdout_sha256"]), 64)
        self.assertTrue(meta["stdout_path"].endswith("mode-a.txt"))

    def test_capture_preserves_non_utf8_bytes(self):
        out = self.evidence / "raw.bin"
        code, _ = oc.capture(
            self.evidence, out,
            [sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'\\xff\\xfe')"],
            self.tmp, 30,
        )
        self.assertEqual(code, 0)
        self.assertEqual(out.read_bytes(), b"\xff\xfe")

    def test_refuses_outside_evidence_root(self):
        out = self.tmp / "outside.txt"
        code, message = oc.capture(self.evidence, out,
                                   [sys.executable, "-c", "print('x')"], self.tmp, 30)
        self.assertEqual(code, 2)
        self.assertIn("outside the evidence root", message)
        self.assertFalse(out.exists())

    def test_requires_existing_evidence_root(self):
        code, message = oc.capture(self.tmp / "missing", self.tmp / "missing" / "x.txt",
                                   [sys.executable, "-c", "print('x')"], self.tmp, 30)
        self.assertEqual(code, 2)
        self.assertIn("evidence root", message)

    def test_requires_command(self):
        code, message = oc.capture(self.evidence, self.evidence / "x.txt", [], self.tmp, 30)
        self.assertEqual(code, 2)
        self.assertIn("no command", message)

    def test_records_timeout(self):
        out = self.evidence / "slow.txt"
        code, _ = oc.capture(
            self.evidence, out,
            [sys.executable, "-c", "import time;time.sleep(30)"],
            self.tmp, 2,
        )
        self.assertEqual(code, 0)
        meta = json.loads(out.with_suffix(out.suffix + ".meta.json").read_text(encoding="utf-8"))
        self.assertTrue(meta["timed_out"])
        self.assertIsNone(meta["exit_code"])

    def test_cli_accepts_double_dash(self):
        out = self.evidence / "cli.txt"
        code = oc.main([
            "--evidence-root", str(self.evidence),
            "--out", str(out),
            "--cwd", str(self.tmp),
            "--", sys.executable, "-c", "print('cli')",
        ])
        self.assertEqual(code, 0)
        self.assertEqual(out.read_bytes().replace(b"\r\n", b"\n"), b"cli\n")


if __name__ == "__main__":
    unittest.main()
