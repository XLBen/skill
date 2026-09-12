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
        for relative in (
            "computer-use/SKILL.md",
            "planning/SKILL.md",
            "validation/frozen/computer-use/SKILL.md",
            "validation/frozen/planning/SKILL.md",
        ):
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"---\nname: {path.parent.name}\ndescription: Test skill\n---\n",
                encoding="utf-8",
            )
        self.live_paths = [(self.repo / name).as_posix() for name in ("computer-use", "planning")]

    def run_install(self, *args):
        previous_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            with mock.patch.object(install, "__file__", str(self.repo / "scripts/install.py")), \
                    mock.patch("sys.argv", ["install.py", *args]), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                install.main()
                return output.getvalue()
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
        self.assertEqual(config["skills"]["paths"], self.live_paths)

    def test_only_live_skills_registered_without_automatic_mcp(self):
        target = self.repo / "target"
        target.mkdir()
        with mock.patch("subprocess.Popen") as launch:
            self.run_install(str(target))
            launch.assert_not_called()
        config = json.loads((target / "opencode.json").read_text(encoding="utf-8"))
        self.assertEqual(config, {
            "$schema": "https://opencode.ai/config.json",
            "skills": {"paths": self.live_paths},
        })
        discovered = [
            path.parent.name for root in config["skills"]["paths"]
            for path in Path(root).rglob("SKILL.md")
        ]
        self.assertEqual(sorted(discovered), ["computer-use", "planning"])
        self.assertEqual(
            sorted(path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file()),
            sorted([
                "opencode.json", ".opencode/commands/build.md",
                ".opencode/workflow/install-manifest.json",
                ".opencode/workflow/scripts/check.py",
                ".opencode/workflow/tests/final_review.py",
                ".opencode/workflow/tests/fixtures/example.md",
            ]),
        )

    def test_real_repository_install_discovers_computer_use_once(self):
        target = self.repo / "real-install"
        target.mkdir()
        source = Path(install.__file__).resolve().parent.parent
        with mock.patch("sys.argv", ["install.py", str(target)]), \
                contextlib.redirect_stdout(io.StringIO()):
            install.main()
        config = json.loads((target / "opencode.json").read_text(encoding="utf-8"))
        roots = [Path(path) for path in config["skills"]["paths"]]
        self.assertIn(source / "computer-use", roots)
        self.assertIn(source / "i-have-adhd", roots)
        self.assertIn(source / "pua", roots)
        names = []
        for root in roots:
            self.assertEqual(root.parent, source)
            for skill in root.rglob("SKILL.md"):
                frontmatter = skill.read_text(encoding="utf-8").split("---", 2)[1]
                name = next(line.removeprefix("name: ") for line in frontmatter.splitlines()
                            if line.startswith("name: "))
                self.assertEqual(name, skill.parent.name)
                self.assertTrue(any(line.startswith("description: ") for line in frontmatter.splitlines()))
                names.append(name)
        self.assertEqual(names.count("computer-use"), 1)
        self.assertEqual(len(names), len(set(names)))
        self.assertNotIn("mcp", config)
        self.assertNotIn("permission", config)
        self.assertEqual(
            (target / ".opencode/workflow/scripts/check.py").read_bytes(),
            (source / "scripts/check.py").read_bytes(),
        )

    def test_upgrade_preserves_unrelated_config_and_deduplicates_live_paths(self):
        unrelated = ["../other-skills", self.repo.as_posix() + "/", "../other-skills"]
        config = {
            "$schema": "https://opencode.ai/config.json",
            "skills": {
                "paths": [self.repo.as_posix(), *unrelated, self.live_paths[0],
                          self.live_paths[0], self.repo.as_posix()],
                "urls": ["https://example.com/skills/"],
            },
            "mcp": {"existing": {"type": "local", "command": ["existing-server"], "enabled": False}},
            "permission": {"bash": {"*": "ask", "git *": "allow"}, "edit": "deny"},
            "model": "provider/model",
        }
        path = self.repo / "opencode.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        self.run_install()
        config["skills"]["paths"] = unrelated + self.live_paths
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), config)
        first_install = path.read_bytes()
        self.run_install()
        self.assertEqual(path.read_bytes(), first_install)

    def test_jsonc_hint_lists_live_paths_without_editing_config(self):
        path = self.repo / "opencode.jsonc"
        original = '// keep comment\n' + json.dumps({"skills": {"paths": [self.repo.as_posix()]}})
        path.write_text(original, encoding="utf-8")
        output = self.run_install()
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        self.assertFalse((self.repo / "opencode.json").exists())
        hint = next(line for line in output.splitlines() if line.startswith("add or merge"))
        self.assertEqual(json.loads("{" + hint.split(": ", 1)[1] + "}"), {
            "skills": {"paths": self.live_paths},
        })
        self.assertIn(f"remove only the exact old skills.paths entry, if present: {json.dumps(self.repo.as_posix())}", output)

    def test_commands_only_leaves_config_untouched(self):
        path = self.repo / "opencode.json"
        self.run_install("--commands-only")
        self.assertFalse(path.exists())
        original = json.dumps({"skills": {"paths": [self.repo.as_posix()]}, "permission": "ask"})
        path.write_text(original, encoding="utf-8")
        output = self.run_install("--commands-only")
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        self.assertNotIn("registered skills", output)
        self.assertNotIn("add or merge", output)

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
