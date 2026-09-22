import contextlib
import hashlib
import importlib.util
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
        self.engine_scripts = (
            "check.py",
            "assurance_policy.py",
            "evidence_registry.py",
            "package_seal.py",
            "verification_runner.py",
            "runtime_trace.py",
            "product_observation.py",
            "workflow_metrics.py",
            "workflow_packets.py",
            "workflow_runtime.py",
            "workflow_protocol.py",
            "worktree_tasks.py",
            "check_runtime.py",
            "observation_contract.py",
            "observation_candidate.py",
            "observation_results.py",
            "observation_resume.py",
            "observation_vision.py",
            "observation_media.py",
            "observation_process.py",
            "observation_capture.py",
            "observation_backend.py",
            "visibility_config.py",
            "runtime_state_policy.py",
            "engineering_delivery.py",
        )
        self.sources = {
            ".opencode/commands/build.md": "command\n",
            ".opencode/agents/mvp-worker.md": "agent\n",
            ".opencode/agents/mvp-reviewer.md": "agent\n",
            ".opencode/plugins/workflow-visibility.js": "// visibility plugin\n",
            "mvp-delivery/references/stage-routing.json": '{"schema_version": 2, "stages": [], "seat_selection": {}}\n',
            "tests/final_review.py": "# review\n",
            "tests/fixtures/example.md": "fixture\n",
        }
        for script_name in self.engine_scripts:
            self.sources[f"scripts/{script_name}"] = f"# {script_name}\n"
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
        engine_sources = [
            relative for relative in self.sources if not relative.startswith(".opencode/")
        ]
        with mock.patch.object(install.shutil, "copy2", wraps=install.shutil.copy2) as copy:
            self.run_install()
            self.run_install()
        self.assertEqual(copy.call_count, 2 * len(engine_sources))
        for call in copy.call_args_list:
            self.assertFalse(call.args[0].samefile(call.args[1]))
        engine = self.repo / ".opencode/workflow"
        manifest = json.loads((engine / "install-manifest.json").read_text(encoding="utf-8"))
        expected = {}
        for relative in self.sources:
            source = self.repo / relative
            key = relative.removeprefix(".opencode/")
            if relative == "mvp-delivery/references/stage-routing.json":
                key = "stage-routing.json"
            expected[key] = hashlib.sha256(source.read_bytes()).hexdigest()
            destination = source if key.startswith(("commands/", "agents/", "plugins/")) else engine / key
            self.assertEqual(destination.read_bytes(), source.read_bytes())
        expected_skills = {}
        for name in ("computer-use", "planning"):
            skill_dir = self.repo / name
            digest = hashlib.sha256()
            for path in sorted(item for item in skill_dir.rglob("*") if item.is_file()):
                relative = path.relative_to(skill_dir).as_posix()
                digest.update(relative.encode("utf-8") + b"\0")
                digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
            expected_skills[name] = {
                "path": skill_dir.as_posix(),
                "algorithm": "tree-sha256/1",
                "sha256": digest.hexdigest(),
            }
        self.assertEqual(
            manifest,
            {"files": expected, "install_mode": "live-paths", "skills": expected_skills},
        )
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
        expected_files = [
            "opencode.json", ".opencode/commands/build.md",
            ".opencode/agents/mvp-reviewer.md", ".opencode/agents/mvp-worker.md",
            ".opencode/plugins/workflow-visibility.js",
            ".opencode/workflow/install-manifest.json",
            ".opencode/workflow/stage-routing.json",
            *[f".opencode/workflow/scripts/{name}" for name in self.engine_scripts],
            ".opencode/workflow/tests/final_review.py",
            ".opencode/workflow/tests/fixtures/example.md",
        ]
        self.assertEqual(
            sorted(path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file()),
            sorted(expected_files),
        )
        manifest = json.loads(
            (target / ".opencode/workflow/install-manifest.json").read_text(encoding="utf-8")
        )
        self.assertIn("plugins/workflow-visibility.js", manifest["files"])
        for name in self.engine_scripts:
            self.assertIn(f"scripts/{name}", manifest["files"])
            self.assertEqual(
                (target / ".opencode/workflow/scripts" / name).read_bytes(),
                (self.repo / "scripts" / name).read_bytes(),
            )
        self.assertEqual(
            (target / ".opencode/plugins/workflow-visibility.js").read_bytes(),
            (self.repo / ".opencode/plugins/workflow-visibility.js").read_bytes(),
        )

    def test_plugin_dependency_hint_when_node_modules_missing(self):
        target = self.repo / "pluginhint"
        target.mkdir()
        output = self.run_install(str(target))
        self.assertIn(
            "plugin dependency missing: "
            f'run "npm install" in {(target / ".opencode").as_posix()} '
            "(package.json must include @opencode-ai/plugin)",
            output,
        )

    def test_plugin_dependency_hint_omitted_when_node_modules_present(self):
        target = self.repo / "pluginpresent"
        (target / ".opencode/node_modules/@opencode-ai/plugin").mkdir(parents=True)
        output = self.run_install(str(target))
        self.assertNotIn("plugin dependency missing", output)

    def test_commands_only_skips_plugins_and_engine_scripts(self):
        target = self.repo / "commandsonly"
        target.mkdir()
        output = self.run_install(str(target), "--commands-only")
        self.assertTrue((target / ".opencode/commands/build.md").is_file())
        self.assertFalse((target / ".opencode/plugins").exists())
        self.assertFalse((target / ".opencode/workflow/scripts").exists())
        manifest = json.loads(
            (target / ".opencode/workflow/install-manifest.json").read_text(encoding="utf-8")
        )
        self.assertFalse(any(key.startswith(("scripts/", "plugins/")) for key in manifest["files"]))
        self.assertNotIn("plugin dependency missing", output)

    def test_refuses_unowned_plugin_overwrite_and_force_replaces(self):
        target = self.repo / "pluginowned"
        (target / ".opencode/plugins").mkdir(parents=True)
        existing = target / ".opencode/plugins/workflow-visibility.js"
        existing.write_text("local plugin\n", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "refusing to overwrite unowned file"):
            self.run_install(str(target))
        self.assertEqual(existing.read_text(encoding="utf-8"), "local plugin\n")
        self.run_install(str(target), "--force")
        self.assertEqual(
            existing.read_bytes(),
            (self.repo / ".opencode/plugins/workflow-visibility.js").read_bytes(),
        )

    def test_installed_engine_resolves_its_own_routing_copy(self):
        real_root = Path(install.__file__).resolve().parent.parent
        engine = self.repo / "engine-layout" / ".opencode" / "workflow"
        (engine / "scripts").mkdir(parents=True)
        (engine / "scripts" / "workflow_protocol.py").write_bytes(
            (real_root / "scripts" / "workflow_protocol.py").read_bytes()
        )
        (engine / "stage-routing.json").write_bytes(
            (real_root / "mvp-delivery" / "references" / "stage-routing.json").read_bytes()
        )
        spec = importlib.util.spec_from_file_location(
            "installed_workflow_protocol", engine / "scripts" / "workflow_protocol.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(
            module.default_routing_path().resolve(),
            (engine / "stage-routing.json").resolve(),
        )
        routing = module.load_routing()
        self.assertEqual(module.validate_routing(routing), [])

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

    def test_inline_agent_conflict_fails_before_copying(self):
        target = self.repo / "conflict"
        target.mkdir()
        config = {"agent": {"mvp-worker": {"description": "existing"}}}
        (target / "opencode.json").write_text(json.dumps(config), encoding="utf-8")
        with mock.patch.object(install.shutil, "copy2") as copy:
            with self.assertRaisesRegex(SystemExit, "conflicting inline agents"):
                self.run_install(str(target))
            copy.assert_not_called()

    def test_local_jsonc_inline_agent_conflict_fails_before_copying(self):
        target = self.repo / "localjsonc"
        local_dir = target / ".opencode"
        local_dir.mkdir(parents=True)
        (local_dir / "opencode.jsonc").write_text(
            '{\n  // project-local config\n'
            '  "agent": {"mvp-worker": {"description": "existing"}}\n'
            '}\n',
            encoding="utf-8",
        )
        with mock.patch.object(install.shutil, "copy2") as copy:
            with self.assertRaisesRegex(SystemExit, "conflicting inline agents"):
                self.run_install(str(target))
            copy.assert_not_called()

    def test_singular_agent_dir_conflict_fails_before_copying(self):
        target = self.repo / "singularagent"
        agent_dir = target / ".opencode" / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "mvp-reviewer.md").write_text("local version\n", encoding="utf-8")
        with mock.patch.object(install.shutil, "copy2") as copy:
            with self.assertRaisesRegex(
                SystemExit, "conflicting agents exist under .opencode/agent/"
            ):
                self.run_install(str(target))
            copy.assert_not_called()

    def test_singular_agent_dir_without_conflict_installs(self):
        target = self.repo / "singularclean"
        agent_dir = target / ".opencode" / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "unrelated-agent.md").write_text("local\n", encoding="utf-8")
        self.run_install(str(target))
        self.assertTrue((target / ".opencode/agents/mvp-worker.md").is_file())
        self.assertTrue((agent_dir / "unrelated-agent.md").is_file())

    def test_refuses_unowned_agent_overwrite_and_force_replaces(self):
        target = self.repo / "owned"
        (target / ".opencode/agents").mkdir(parents=True)
        existing = target / ".opencode/agents/mvp-worker.md"
        existing.write_text("local version\n", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "refusing to overwrite unowned file"):
            self.run_install(str(target))
        self.assertEqual(existing.read_text(encoding="utf-8"), "local version\n")
        self.run_install(str(target), "--force")
        self.assertEqual(existing.read_bytes(), (self.repo / ".opencode/agents/mvp-worker.md").read_bytes())

    def test_upgrade_retires_removed_agent_files(self):
        target = self.repo / "retire"
        target.mkdir()
        self.run_install(str(target))
        retired = target / ".opencode/agents/mvp-reviewer.md"
        self.assertTrue(retired.is_file())
        (self.repo / ".opencode/agents/mvp-reviewer.md").unlink()
        output = self.run_install(str(target))
        self.assertFalse(retired.exists())
        self.assertIn("removed retired commands: mvp-reviewer", output)
        manifest = json.loads((target / ".opencode/workflow/install-manifest.json").read_text(encoding="utf-8"))
        self.assertNotIn("agents/mvp-reviewer.md", manifest["files"])
        self.assertIn("agents/mvp-worker.md", manifest["files"])

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
