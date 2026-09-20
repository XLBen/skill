import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from package_seal import SealError, main, seal_package, verify_seal  # noqa: E402


def make_package(root):
    package = root / "S-01"
    (package / "evidence").mkdir(parents=True)
    (package / "contract.md").write_text("# contract\n", encoding="utf-8")
    (package / "PLAN.md").write_text("# plan\n", encoding="utf-8")
    (package / "workflow-events.jsonl").write_text('{"id":"EV-1"}\n', encoding="utf-8")
    (package / "evidence" / "v-01.json").write_text('{"result":"passed"}\n', encoding="utf-8")
    return package


class SealTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.package = make_package(self.root)

    def test_seal_verifies_clean_package(self):
        seal = seal_package(self.package)
        self.assertEqual(seal["schema"], "package-seal/1")
        self.assertEqual(seal["file_count"], 4)
        report = verify_seal(self.package / "package-seal.json")
        self.assertEqual(report["verdict"], "pass", report["problems"])
        self.assertEqual(report["root_hash"], seal["root_hash"])

    def test_changed_file_fails_verification(self):
        seal_package(self.package)
        (self.package / "contract.md").write_text("# contract v2\n", encoding="utf-8")
        report = verify_seal(self.package / "package-seal.json")
        self.assertEqual(report["verdict"], "fail")
        self.assertIn("contract.md", report["changed"])

    def test_added_and_removed_files_are_reported(self):
        seal_package(self.package)
        (self.package / "extra.md").write_text("new\n", encoding="utf-8")
        (self.package / "PLAN.md").unlink()
        report = verify_seal(self.package / "package-seal.json")
        self.assertIn("extra.md", report["added"])
        self.assertIn("PLAN.md", report["removed"])

    def test_seal_file_itself_is_not_sealed(self):
        seal = seal_package(self.package)
        paths = [entry["path"] for entry in seal["files"]]
        self.assertNotIn("package-seal.json", paths)
        # re-sealing must not see the previous seal as a package change
        second = seal_package(self.package)
        self.assertEqual(second["root_hash"], seal["root_hash"])

    def test_parent_lineage_is_recorded(self):
        parent_dir = self.root / "S-00"
        parent_dir.mkdir()
        (parent_dir / "contract.md").write_text("old\n", encoding="utf-8")
        parent = seal_package(parent_dir)
        child = seal_package(self.package, parent_seal=parent_dir / "package-seal.json")
        self.assertEqual(child["parent"]["root_hash"], parent["root_hash"])

    def test_invalid_parent_and_missing_package_fail(self):
        with self.assertRaises(SealError):
            seal_package(self.root / "nope")
        with self.assertRaises(SealError):
            seal_package(self.package, parent_seal=self.root / "missing.json")

    def test_cli_seal_and_verify(self):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = main(["seal", str(self.package)])
        self.assertEqual(code, 0)
        self.assertIn("package sealed", stdout.getvalue())

        (self.package / "contract.md").write_text("changed\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = main(["verify-package", str(self.package)])
        self.assertEqual(code, 1)
        self.assertIn("seal FAIL", stdout.getvalue())

    def test_cli_verify_missing_seal(self):
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["verify", str(self.root / "missing.json")])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
