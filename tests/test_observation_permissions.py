"""Permission-boundary tests for the product-observation seats.

These tests parse the agent frontmatter with a minimal stdlib parser (no
third-party yaml). They lock the declared boundaries only; host-side runtime
enforcement is verified in the S21 live checklist (see PROGRESS.md).
"""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

OBSERVER = ROOT / ".opencode/agents/mvp-product-observer.md"
REVIEWER = ROOT / ".opencode/agents/mvp-reviewer.md"
PROTOCOL = ROOT / "product-observer/references/observation-protocol.md"

BASH_DENY_PATTERNS = (
    "*> *",
    "*>>*",
    "*Out-File*",
    "*Set-Content*",
    "*Add-Content*",
    "*New-Item*",
    "*Remove-Item*",
    "*rm *",
    "*del *",
    "*move *",
    "*copy *",
    "*python -c*",
    "*node -e*",
)


def parse_frontmatter(text):
    """Parse the first --- block: `key: value` plus one nested mapping level."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise AssertionError("frontmatter opener missing")
    block = []
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        block.append(line)
    if not closed:
        raise AssertionError("frontmatter closer missing")

    data = {}
    parent = None
    child = None
    for raw in block:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        key, sep, value = raw.strip().partition(":")
        if not sep:
            raise AssertionError(f"unparsable frontmatter line: {raw!r}")
        key = key.strip().strip("\"'")
        value = value.strip().strip("\"'")
        if indent == 0:
            child = None
            if value:
                parent = None
                data[key] = value
            else:
                parent = key
                data[key] = {}
        elif indent == 2 and parent is not None:
            node = data.get(parent)
            if not isinstance(node, dict):
                raise AssertionError(f"unexpected nesting for {parent!r}")
            if value:
                node[key] = value
                child = None
            else:
                node[key] = {}
                child = key
        elif indent >= 4 and parent is not None and child is not None:
            node = data.get(parent)
            leaf = node.get(child) if isinstance(node, dict) else None
            if not isinstance(leaf, dict):
                raise AssertionError(f"unexpected nesting for {child!r}")
            leaf[key] = value
        else:
            raise AssertionError(f"unexpected indentation: {raw!r}")
    return data


class ObserverPermissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = OBSERVER.read_text(encoding="utf-8")
        cls.permission = parse_frontmatter(cls.text)["permission"]
        cls.bash = cls.permission["bash"]

    def test_edit_and_task_are_denied(self):
        self.assertEqual(self.permission["edit"], "deny")
        self.assertEqual(self.permission["task"], "deny")

    def test_read_only_tools_are_allowed(self):
        for tool in ("read", "glob", "grep", "list"):
            with self.subTest(tool=tool):
                self.assertEqual(self.permission[tool], "allow")

    def test_bash_is_a_command_pattern_mapping(self):
        self.assertIsInstance(self.permission["bash"], dict)
        self.assertIsInstance(self.bash, dict)

    def test_bash_default_allows_and_every_deny_pattern_is_present(self):
        keys = list(self.bash)
        self.assertEqual(keys[0], "*")
        self.assertEqual(self.bash["*"], "allow")
        for pattern in BASH_DENY_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, self.bash)
                self.assertEqual(self.bash[pattern], "deny")

    def test_deny_patterns_come_after_the_top_level_allow(self):
        keys = list(self.bash)
        allow_index = keys.index("*")
        for pattern in BASH_DENY_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertGreater(keys.index(pattern), allow_index)


class ReviewerPermissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = REVIEWER.read_text(encoding="utf-8")
        cls.permission = parse_frontmatter(cls.text)["permission"]

    def test_edit_bash_and_task_are_denied(self):
        self.assertEqual(self.permission["edit"], "deny")
        self.assertEqual(self.permission["bash"], "deny")
        self.assertEqual(self.permission["task"], "deny")

    def test_reviewer_rule_forbids_read_then_rewrite(self):
        self.assertIn("read-then-rewrite", self.text)


class UnverifiedPermissionKeyTests(unittest.TestCase):
    def test_agent_files_do_not_declare_write_permission_keys(self):
        for path in (OBSERVER, REVIEWER):
            with self.subTest(agent=path.name):
                self.assertNotIn("write: deny", path.read_text(encoding="utf-8"))
                self.assertNotIn("write: allow", path.read_text(encoding="utf-8"))


class ObservationProtocolTrustBoundaryTests(unittest.TestCase):
    def test_protocol_documents_the_two_layers(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        self.assertIn("两层", text)
        for token in ("edit deny", "bash", "host permissions", "prompt-level scope"):
            with self.subTest(token=token):
                self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
