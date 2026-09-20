import contextlib
import hashlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_runtime  # noqa: E402
import install  # noqa: E402


def make_host_db(path: Path, directory: str, created_ms: int):
    con = sqlite3.connect(path)
    con.executescript(
        """
        create table session (id text primary key, parent_id text, directory text,
                              agent text, time_created integer, time_updated integer);
        create table part (id text primary key, message_id text, session_id text,
                           time_created integer, time_updated integer, data text);
        """
    )
    con.execute(
        "insert into session values (?,?,?,?,?,?)",
        ("ses_a", None, directory, "build", created_ms, created_ms),
    )
    con.commit()
    con.close()


class ConfigParsingTests(unittest.TestCase):
    def test_jsonc_trailing_commas_are_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.jsonc"
            path.write_text('{"skills": {"paths": ["a",],},}', encoding="utf-8")
            data, note = check_runtime.load_config_file(path)
            self.assertEqual(note, "ok")
            self.assertEqual(data["skills"]["paths"], ["a"])

    def test_deep_merge_keeps_nested_permissions(self):
        global_data = {"permission": {"edit": "ask", "bash": {"git *": "allow"}}, "skills": {"paths": ["g"]}}
        project_data = {"permission": {"edit": "deny"}, "skills": {"paths": ["p"]}}
        merged = check_runtime.merge_config(project_data, global_data)
        self.assertEqual(merged["permission"]["edit"], "deny")
        self.assertEqual(merged["permission"]["bash"], {"git *": "allow"})
        self.assertEqual(merged["skills"]["paths"], ["p"])


class HostDoctorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.project = self.tmp / "proj"
        self.project.mkdir()
        self.db = self.tmp / "opencode.db"
        import datetime as dt

        created = int(dt.datetime.now().timestamp() * 1000)
        make_host_db(self.db, str(self.project), created)

    def test_lookback_keeps_recent_sessions(self):
        report = check_runtime.host_doctor(self.project, str(self.db), lookback_days=7)
        self.assertEqual(report["coverage"]["sessions_found"], 1)

    def test_lookback_excludes_old_sessions(self):
        old = self.tmp / "old.db"
        make_host_db(old, str(self.project), 1_000_000)
        report = check_runtime.host_doctor(self.project, str(old), lookback_days=7)
        self.assertEqual(report["coverage"]["sessions_found"], 0)

    def test_windows_data_directory_is_discovered(self):
        home = self.tmp / "home"
        db_dir = home / "AppData" / "Local" / "opencode"
        db_dir.mkdir(parents=True)
        make_host_db(db_dir / "opencode.db", str(self.project), 1_000_000)
        with mock.patch.object(check_runtime.sys, "platform", "win32"), \
                mock.patch.object(check_runtime.Path, "home", return_value=home):
            con, note = check_runtime.open_runtime_db(None)
            try:
                self.assertIsNotNone(con, note)
            finally:
                if con is not None:
                    con.close()


class StrictModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.project = self.tmp / "proj"
        (self.project / ".opencode" / "skills" / "good").mkdir(parents=True)
        (self.project / ".opencode" / "skills" / "good" / "SKILL.md").write_text(
            "---\nname: good\ndescription: A valid skill\n---\n", encoding="utf-8"
        )

    def test_valid_project_exits_zero(self):
        self.assertEqual(check_runtime.main(["static", str(self.project), "--strict"]), 0)

    def test_invalid_frontmatter_exits_nonzero(self):
        (self.project / ".opencode" / "skills" / "bad").mkdir()
        (self.project / ".opencode" / "skills" / "bad" / "SKILL.md").write_text(
            "---\nname: bad\n---\n", encoding="utf-8"
        )
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            code = check_runtime.main(["doctor", str(self.project), "--db", str(self.tmp / "none.db"), "--strict"])
        self.assertEqual(code, 3)
        self.assertIn("strict:", errors.getvalue())


class FreshnessTests(unittest.TestCase):
    def test_reference_change_is_detected(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        project = tmp / "proj"
        skill = project / "skills" / "demo"
        (skill / "references").mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: demo\ndescription: Demo\n---\n", encoding="utf-8")
        reference = skill / "references" / "protocol.md"
        reference.write_text("v1\n", encoding="utf-8")
        expected = check_runtime.skill_tree_hash(skill)
        manifest = project / ".opencode" / "workflow" / "install-manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({
            "files": {},
            "install_mode": "live-paths",
            "skills": {"demo": {"path": skill.as_posix(), "algorithm": "tree-sha256/1", "sha256": expected}},
        }), encoding="utf-8")
        static = check_runtime.static_doctor(project, False)
        self.assertEqual(static["skills_freshness"]["status"], "ok")
        reference.write_text("v2\n", encoding="utf-8")
        static = check_runtime.static_doctor(project, False)
        self.assertEqual(static["skills_freshness"]["status"], "drift")

    def test_freshness_drift_is_diagnostic_unless_requested(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        project = tmp / "proj"
        manifest = project / ".opencode" / "workflow" / "install-manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({
            "files": {},
            "install_mode": "live-paths",
            "skills": {"demo": {"path": (project / "missing").as_posix(), "algorithm": "tree-sha256/1", "sha256": "0" * 64}},
        }), encoding="utf-8")
        static = check_runtime.static_doctor(project, False)
        report = {"static": static}
        self.assertEqual(check_runtime.strict_problems(report), [])
        self.assertTrue(check_runtime.strict_problems(report, strict_freshness=True))

    def test_manifest_without_fingerprints_is_not_reported_fresh(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        project = tmp / "proj"
        manifest = project / ".opencode" / "workflow" / "install-manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"files": {}, "install_mode": "live-paths"}), encoding="utf-8")
        static = check_runtime.static_doctor(project, False)
        self.assertEqual(static["skills_freshness"]["status"], "not-checked")

    def test_installed_file_change_is_detected(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        project = tmp / "proj"
        engine = project / ".opencode" / "workflow" / "scripts"
        engine.mkdir(parents=True)
        installed = engine / "check.py"
        installed.write_text("# engine\n", encoding="utf-8")
        digest = hashlib.sha256(installed.read_bytes()).hexdigest()
        manifest = project / ".opencode" / "workflow" / "install-manifest.json"
        manifest.write_text(json.dumps({"files": {"scripts/check.py": digest}, "install_mode": "live-paths"}), encoding="utf-8")
        static = check_runtime.static_doctor(project, False)
        self.assertEqual(static["installed_integrity"]["status"], "ok")
        installed.write_text("# tampered\n", encoding="utf-8")
        static = check_runtime.static_doctor(project, False)
        self.assertEqual(static["installed_integrity"]["status"], "problems")
        self.assertTrue(
            any("installed scripts/check.py" in problem for problem in check_runtime.strict_problems({"static": static}))
        )


class CommandsOnlyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name).resolve()
        sources = {
            ".opencode/commands/build.md": "command\n",
            ".opencode/agents/mvp-worker.md": "agent\n",
            "scripts/check.py": "# check\n",
            "scripts/assurance_policy.py": "# assurance\n",
            "scripts/evidence_registry.py": "# registry\n",
            "scripts/package_seal.py": "# seal\n",
            "scripts/verification_runner.py": "# runner\n",
            "scripts/runtime_trace.py": "# trace\n",
            "scripts/workflow_metrics.py": "# metrics\n",
            "scripts/workflow_packets.py": "# packets\n",
            "scripts/workflow_runtime.py": "# runtime\n",
            "scripts/workflow_protocol.py": "# protocol\n",
            "scripts/worktree_tasks.py": "# worktrees\n",
            "scripts/check_runtime.py": "# doctor\n",
            "mvp-delivery/references/stage-routing.json": '{"schema_version": 2, "stages": [], "seat_selection": {}}\n',
            "tests/final_review.py": "# review\n",
            "tests/fixtures/example.md": "fixture\n",
            "demo/SKILL.md": "---\nname: demo\ndescription: Demo\n---\n",
        }
        for relative, content in sources.items():
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.target = self.repo / "target"
        self.target.mkdir()

    def run_install(self, *args):
        previous = Path.cwd()
        try:
            os.chdir(self.repo)
            with mock.patch.object(install, "__file__", str(self.repo / "scripts/install.py")), \
                    mock.patch("sys.argv", ["install.py", *args]), \
                    contextlib.redirect_stdout(io.StringIO()):
                install.main()
        finally:
            os.chdir(previous)

    def test_commands_only_skips_agents_and_engine(self):
        self.run_install(str(self.target), "--commands-only")
        self.assertTrue((self.target / ".opencode" / "commands" / "build.md").is_file())
        self.assertFalse((self.target / ".opencode" / "agents").exists())
        self.assertFalse((self.target / ".opencode" / "workflow" / "scripts" / "check.py").exists())
        self.assertFalse((self.target / "opencode.json").exists())

    def test_commands_only_preserves_previous_engine_manifest_entries(self):
        self.run_install(str(self.target))
        self.run_install(str(self.target), "--commands-only")
        manifest = json.loads(
            (self.target / ".opencode" / "workflow" / "install-manifest.json").read_text(encoding="utf-8")
        )
        self.assertIn("scripts/check.py", manifest["files"])
        self.assertIn("agents/mvp-worker.md", manifest["files"])
        self.assertIn("demo", manifest["skills"])
        for relative in ("scripts/check.py", "scripts/assurance_policy.py",
                         "scripts/evidence_registry.py", "scripts/package_seal.py",
                         "scripts/verification_runner.py",
                         "scripts/runtime_trace.py", "scripts/workflow_metrics.py",
                         "scripts/workflow_packets.py", "scripts/workflow_runtime.py",
                         "scripts/workflow_protocol.py",
                         "scripts/worktree_tasks.py", "scripts/check_runtime.py"):
            self.assertTrue((self.target / ".opencode" / "workflow" / relative).is_file(), relative)
        self.assertTrue((self.target / ".opencode" / "workflow" / "stage-routing.json").is_file())
        self.assertTrue((self.target / ".opencode" / "agents" / "mvp-worker.md").is_file())


if __name__ == "__main__":
    unittest.main()
