import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import install


class ParseJsoncTests(unittest.TestCase):
    def test_preserves_strings_while_removing_trailing_commas(self):
        values = ['a,]b', 'a,}b', 'a,  ]b', 'quote" ,]b', 'slash\\', '// /* */']
        text = '{"values": [' + ','.join(map(json.dumps, values)) + ',],}'
        self.assertEqual(install.parse_jsonc(text, "test.jsonc"), {"values": values})

    def test_comments_and_trailing_commas(self):
        text = '// header\n{"values": [1, /* item */ 2, // end\n], /* end */}'
        self.assertEqual(install.parse_jsonc(text, "test.jsonc"), {"values": [1, 2]})

    def test_comments_do_not_join_tokens(self):
        for text in ('[1/* gap */2]', '[tr/* gap */ue]', '[1// gap\n2]'):
            with self.subTest(text=text):
                with self.assertRaisesRegex(SystemExit, "cannot inspect test.jsonc"):
                    install.parse_jsonc(text, "test.jsonc")

    def test_unterminated_comment(self):
        with self.assertRaisesRegex(SystemExit, "unterminated JSONC comment"):
            install.parse_jsonc('{"value": 1 /*', "test.jsonc")


class InstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name).resolve()
        self.sources = {
            ".opencode/commands/build.md": "command\n",
            "scripts/check.py": "# check\n",
            "tests/final_review.py": "# review\n",
            "tests/fixtures/example.md": "fixture\n",
        }
        for relative, content in self.sources.items():
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def run_install(self, *args):
        previous_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            with mock.patch.object(install, "__file__", str(self.repo / "scripts/install.py")), \
                    mock.patch("sys.argv", ["install.py", *args]), \
                    contextlib.redirect_stdout(io.StringIO()):
                install.main()
        finally:
            os.chdir(previous_cwd)

    def test_default_root_skips_same_file_and_records_manifest(self):
        with mock.patch.object(install.shutil, "copy2", wraps=install.shutil.copy2) as copy:
            self.run_install()
            self.run_install()
        self.assertEqual(copy.call_count, 6)
        for call in copy.call_args_list:
            self.assertFalse(call.args[0].samefile(call.args[1]))
        engine = self.repo / ".opencode/workflow"
        manifest = json.loads((engine / "install-manifest.json").read_text(encoding="utf-8"))
        expected = {}
        for relative in self.sources:
            source = self.repo / relative
            key = relative.removeprefix(".opencode/")
            expected[key] = hashlib.sha256(source.read_bytes()).hexdigest()
            destination = source if key.startswith("commands/") else engine / key
            self.assertEqual(destination.read_bytes(), source.read_bytes())
        self.assertEqual(manifest, {"files": expected})
        config = json.loads((self.repo / "opencode.json").read_text(encoding="utf-8"))
        self.assertEqual(config["skills"]["paths"], [self.repo.as_posix()])

    def test_invalid_manifest_files_type_fails_before_copying(self):
        manifest = self.repo / ".opencode/workflow/install-manifest.json"
        manifest.parent.mkdir(parents=True)
        for files in (None, [], "invalid", 1, False):
            with self.subTest(files=files):
                content = json.dumps({"files": files})
                manifest.write_text(content, encoding="utf-8")
                with mock.patch.object(install.shutil, "copy2") as copy:
                    with self.assertRaisesRegex(SystemExit, "files must be an object"):
                        self.run_install()
                    copy.assert_not_called()
                self.assertEqual(manifest.read_text(encoding="utf-8"), content)
                self.assertFalse((self.repo / "opencode.json").exists())


if __name__ == "__main__":
    unittest.main()
