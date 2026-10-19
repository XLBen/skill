import json
import os
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
        self.target = Path(self.tmp.name) / "project"
        self.target.mkdir()
        # 不读用户真实的全局配置：放一个只有 godot 服务器的假全局配置
        self.xdg = Path(self.tmp.name) / "xdg"
        (self.xdg / "opencode").mkdir(parents=True)
        (self.xdg / "opencode" / "opencode.jsonc").write_text(
            '{\n  // 注释\n  "mcp": {"godot": {"type": "local", "command": ["x"], "url": "http://a//b"},},\n}\n', encoding="utf-8")
        self.old_xdg = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = str(self.xdg)

    def tearDown(self):
        if self.old_xdg is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self.old_xdg
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
        text = '{ // 注释\n  "mcp": {"playwright": {"type": "local", "command": ["npx"]}}\n}\n'
        jsonc.write_text(text, encoding="utf-8")
        result = install(self.target, "--profile", "frontend")
        self.assertEqual(jsonc.read_text(encoding="utf-8"), text)
        self.assertIn("permission.skill", result.stdout)
        self.assertIn('"playwright_*": true', result.stdout)
        self.assertNotIn('"command": [\n          "npx",\n          "-y",\n          "@playwright', result.stdout)  # 已定义的不重复补

    def test_mcp_tools_follow_profiles(self):
        install(self.target, "--profile", "frontend")
        config = json.loads((self.target / "opencode.json").read_text(encoding="utf-8"))
        tools = config["tools"]
        self.assertTrue(tools["playwright_*"])
        self.assertTrue(tools["context7_*"])
        self.assertFalse(tools["computer-use_*"])
        self.assertFalse(tools["godot_*"])  # 全局配置里的服务器在本项目关闭
        self.assertIn("context7", config["mcp"])  # 档案需要但没定义的服务器会补上定义
        self.assertFalse(config["agent"]["worker"]["tools"]["playwright_*"])
        self.assertTrue(config["agent"]["worker-strong"]["tools"]["context7_*"])
        self.assertTrue(config["agent"]["reviewer"]["tools"]["playwright_*"])
        self.assertFalse(config["agent"]["reviewer"]["tools"]["context7_*"])

    def test_extra_mcp_is_kept_across_switches(self):
        install(self.target)
        skills.apply(self.target, ROOT, ["automation"], ["godot"])
        skills.apply(self.target, ROOT, ["backend"])  # 不传 --mcp 时沿用上次的
        tools = json.loads((self.target / "opencode.json").read_text(encoding="utf-8"))["tools"]
        self.assertTrue(tools["godot_*"])
        self.assertFalse(tools["playwright_*"])
        with self.assertRaises(SystemExit):
            skills.apply(self.target, ROOT, [], ["no-such-server"])

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(SystemExit):
            skills.permissions(ROOT, ["nope"])


if __name__ == "__main__":
    unittest.main()
