"""Keep live skill, reference, command and agent links resolvable.

Historical validation fixtures deliberately retain their original instructions.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INLINE = re.compile(r"`([^`\r\n]+)`")
MARKDOWN_LINK = re.compile(r"\]\(([^)]+)\)")
SKILLS = {path.parent.name for path in ROOT.glob("*/SKILL.md")}
PREFIXES = ("../", "./", "references/", "scripts/") + tuple(
    name + "/" for name in sorted(SKILLS)
)


class SkillLinkTests(unittest.TestCase):
    def test_local_instruction_links(self):
        sources = [
            *(ROOT / ".opencode" / "commands").glob("*.md"),
            *(ROOT / ".opencode" / "agents").glob("*.md"),
            *(ROOT / "mvp-delivery" / "references").glob("*.json"),
        ]
        sources.extend(ROOT.glob("*/SKILL.md"))
        sources.extend(ROOT.glob("*/references/**/*.md"))
        missing = []
        for source in sources:
            text = source.read_text(encoding="utf-8")
            tokens = [(token, False) for token in INLINE.findall(text)]
            tokens.extend((token, True) for token in MARKDOWN_LINK.findall(text))
            for token, markdown_link in tokens:
                path = token.split("#", 1)[0]
                if path.startswith(("http://", "https://", "mailto:")):
                    continue
                if not path.endswith((".md", ".json")) or any(
                    mark in path for mark in ("<", ">", "*", "...", " ", "$", "{")
                ):
                    continue
                if not markdown_link and not path.startswith(PREFIXES):
                    continue
                # 'references/...' is skill-root-relative; ../ links are
                # always relative to the file containing the instruction.
                candidates = [source.parent / path]
                if "references" in source.parts and path.startswith("references/"):
                    candidates.append(source.parent.parent / path)
                if not path.startswith((".", "references/", "scripts/")):
                    candidates.append(ROOT / path)
                if source.parent.name in ("agents", "commands"):
                    candidates.append(ROOT / path)
                if not any(candidate.is_file() for candidate in candidates):
                    missing.append(f"{source.relative_to(ROOT)} -> {path}")
        self.assertEqual(sorted(set(missing)), [], "Unresolvable local instruction links:\n" + "\n".join(sorted(set(missing))))

    def test_skill_names_and_stage_references(self):
        for name in SKILLS:
            body = (ROOT / name / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=name):
                self.assertRegex(body, rf"(?m)^name: {re.escape(name)}$")
                self.assertRegex(body, r"(?m)^description: .+")
        routing = json.loads(
            (ROOT / "mvp-delivery/references/stage-routing.json").read_text(encoding="utf-8")
        )
        cards = (ROOT / "pua/references/stage-checks.md").read_text(encoding="utf-8")
        for stage in routing["stages"]:
            for required in stage["required_skills"]:
                with self.subTest(stage=stage["stage_id"], required=required["name"]):
                    self.assertIn(required["name"], SKILLS)
                    if "stage_card" in required:
                        self.assertIn(f"`{required['stage_card']}`", cards)
        for capability in routing["domain_capabilities"]["capabilities"]:
            with self.subTest(domain=capability["name"]):
                self.assertIn(capability["name"], SKILLS)


if __name__ == "__main__":
    unittest.main()
