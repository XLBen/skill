import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import skills  # noqa: E402


def install(target, *args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "install.py"), str(target), *args],
                          capture_output=True, text=True, encoding="utf-8", check=True)


def skill_rules(target):
    return json.loads((Path(target) / "opencode.json").read_text(encoding="utf-8"))["permission"]["skill"]


class ProfileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_profile_skill_exists(self):
        extras = set(skills.skill_names(ROOT / "extras"))
        for name, profile in skills.load_profiles(ROOT).items():
            self.assertTrue(set(profile["skills"]) <= extras, name)

    def test_install_defaults_to_core_only(self):
        install(self.target)
        rules = skill_rules(self.target)
        self.assertEqual(rules["build"], "allow")
        self.assertEqual(rules["mcp-builder"], "deny")
        self.assertEqual(rules["computer-use"], "deny")

    def test_profile_switch_and_add(self):
        install(self.target, "--profile", "backend")
        self.assertEqual(skill_rules(self.target)["api-and-interface-design"], "allow")
        skills.apply(self.target, ROOT, ["frontend", "automation"])
        rules = skill_rules(self.target)
        self.assertEqual(rules["api-and-interface-design"], "deny")
        self.assertEqual(rules["computer-use"], "allow")
        self.assertEqual(skills.current_profiles(self.target), ["frontend", "automation"])
        install(self.target)  # 重装时沿用上次的档案
        self.assertEqual(skill_rules(self.target)["computer-use"], "allow")

    def test_user_entries_are_kept(self):
        (self.target / "opencode.json").write_text(
            json.dumps({"permission": {"skill": {"my-own-skill": "ask"}}}), encoding="utf-8")
        install(self.target, "--profile", "ai")
        rules = skill_rules(self.target)
        self.assertEqual(rules["my-own-skill"], "ask")
        self.assertEqual(rules["mcp-builder"], "allow")

    def test_string_permission_is_preserved_as_wildcard(self):
        (self.target / "opencode.json").write_text(json.dumps({"permission": {"skill": "ask"}}), encoding="utf-8")
        skills.apply(self.target, ROOT, [])
        self.assertEqual(skill_rules(self.target)["*"], "ask")

    def test_jsonc_is_not_modified(self):
        jsonc = self.target / "opencode.jsonc"
        jsonc.write_text("{ // 注释\n}\n", encoding="utf-8")
        result = install(self.target, "--profile", "release")
        self.assertEqual(jsonc.read_text(encoding="utf-8"), "{ // 注释\n}\n")
        self.assertIn("permission.skill", result.stdout)

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(SystemExit):
            skills.permissions(ROOT, ["nope"])


if __name__ == "__main__":
    unittest.main()
