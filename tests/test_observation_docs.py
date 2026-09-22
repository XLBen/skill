"""S19c: offline doc/implementation consistency for product observation.

Reads repository files and parses source text; runs no CLI and touches no
network. Any mismatch found here is either fixed minimally on the document
side or reported as an implementation gap in the failure message.
"""

import importlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

DOCS = (
    "product-observer/SKILL.md",
    "product-observer/references/observation-protocol.md",
    "product-observer/references/finding-rules.md",
    "product-observer/references/backend-routing.md",
    "reviewer/SKILL.md",
    "mvp-delivery/references/delivery-execution.md",
    "mvp-delivery/references/delivery-finish.md",
    "mvp-delivery/references/subagent-templates.md",
    "mvp-delivery/references/subagent-orchestration.md",
    "mvp-delivery/SKILL.md",
    "mvp-delivery/references/engineering-delivery.md",
    "writing-plans/SKILL.md",
    "writing-plans/references/design-template.md",
)

LEGACY_SCHEMAS = ("product-observation/1", "product-observation-review/1")
CURRENT_SCHEMAS = ("product-observation/2", "product-observation-review/2")
REQUIRED_CHECK_COMMANDS = (
    "prepare-plan",
    "next-step",
    "product-audit-gate",
    "finish-goal",
    "check-current",
    "runtime-gate",
)
OBSERVATION_MODULES = (
    "observation_contract",
    "observation_candidate",
    "observation_results",
    "observation_resume",
    "observation_vision",
    "observation_media",
    "observation_process",
    "observation_backend",
    "visibility_config",
    "runtime_state_policy",
)


def read(rel_path):
    path = ROOT / rel_path
    if not path.is_file():
        raise AssertionError(f"missing repository file: {rel_path}")
    return path.read_text(encoding="utf-8")


def line_of(text, index):
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    return text[start:end if end != -1 else len(text)]


class SchemaDriftTests(unittest.TestCase):
    def test_legacy_schema_only_with_legacy_context(self):
        for rel_path in DOCS:
            text = read(rel_path)
            for legacy in LEGACY_SCHEMAS:
                for match in re.finditer(re.escape(legacy), text):
                    context = text[max(0, match.start() - 100):match.start()]
                    context += line_of(text, match.start())
                    self.assertIn(
                        "legacy",
                        context.lower(),
                        f"{rel_path}: {legacy} mentioned without a legacy "
                        f"(historical compatibility) context",
                    )

    def test_current_schema_versions_are_consistent(self):
        union = "\n".join(read(rel_path) for rel_path in DOCS)
        for current in CURRENT_SCHEMAS:
            self.assertIn(current, union)
        for rel_path in DOCS:
            text = read(rel_path)
            for match in re.finditer(r"product-observation(?:-review)?/(\d+)", text):
                self.assertEqual(
                    match.group(1),
                    "2",
                    f"{rel_path}: unexpected schema version {match.group(0)}",
                )

    def test_result_contract_exists_with_contract_enums(self):
        rel_path = "product-observer/references/result-contract.md"
        text = read(rel_path)
        fence = re.search(
            r"```json contract-enums\n(.*?)\n```", text, re.DOTALL
        )
        self.assertIsNotNone(fence, f"{rel_path}: missing contract-enums block")
        json.loads(fence.group(1))


class CommandSurfaceTests(unittest.TestCase):
    def test_check_py_exposes_required_commands(self):
        source = read("scripts/check.py")
        for command in REQUIRED_CHECK_COMMANDS:
            self.assertIn(
                f'"{command}"',
                source,
                f"scripts/check.py does not mention the {command!r} command",
            )
        implemented = set(re.findall(r'command == "([a-z0-9-]+)"', source))
        missing = sorted(set(REQUIRED_CHECK_COMMANDS) - implemented)
        self.assertEqual(missing, [], f"check.py dispatch missing commands: {missing}")

    def test_doc_backticked_check_commands_are_implemented(self):
        source = read("scripts/check.py")
        implemented = set(re.findall(r'command == "([a-z0-9-]+)"', source))
        referenced = {}
        for rel_path in DOCS:
            found = set(re.findall(r"`check\.py ([a-z-]+)", read(rel_path)))
            if found:
                referenced[rel_path] = found
        self.assertTrue(referenced, "no document references a check.py subcommand")
        flat = set().union(*referenced.values())
        self.assertIn("product-audit-gate", flat)
        unknown = sorted(flat - implemented)
        self.assertEqual(
            unknown,
            [],
            f"documents reference check.py subcommands the engine does not "
            f"dispatch: {unknown}",
        )

    def test_workflow_packets_observer_and_validate_subcommands(self):
        source = read("scripts/workflow_packets.py")
        for subcommand in ("observer", "validate"):
            self.assertRegex(
                source,
                r'sub\.add_parser\(\s*"%s"' % re.escape(subcommand),
                f"workflow_packets.py has no {subcommand!r} subcommand",
            )
        self.assertIn("workflow-observer-packet/2", source)
        self.assertIn('OBSERVER_PACKET_SCHEMA = "workflow-observer-packet/2"', source)

    def test_visibility_config_subcommands(self):
        source = read("scripts/visibility_config.py")
        for subcommand in ("set", "show", "select", "mark"):
            self.assertRegex(
                source,
                r'sub\.add_parser\(\s*"%s"' % re.escape(subcommand),
                f"visibility_config.py has no {subcommand!r} subcommand",
            )

    def test_command_wrappers_reference_existing_scripts(self):
        for rel_path in (".opencode/commands/visibility.md", ".opencode/commands/resume.md"):
            text = read(rel_path)
            referenced = set(re.findall(r"scripts/([A-Za-z0-9_]+\.py)", text))
            self.assertTrue(referenced, f"{rel_path} references no workflow script")
            for name in sorted(referenced):
                self.assertTrue(
                    (ROOT / "scripts" / name).is_file(),
                    f"{rel_path} references missing scripts/{name}",
                )
        visibility = read(".opencode/commands/visibility.md")
        self.assertIn("visibility_config.py", visibility)
        self.assertTrue((ROOT / "scripts" / "visibility_config.py").is_file())


class BackendRoutingTests(unittest.TestCase):
    def test_routing_json_names_implemented_backends(self):
        routing_text = read("mvp-delivery/references/stage-routing.json")
        routing = json.loads(routing_text)
        self.assertIn("stages", routing)
        for name in ("direct-multimodal", "playwright-cli", "midscene", "ui-tars", "ffmpeg"):
            self.assertIn(name, routing_text, f"stage-routing.json omits {name!r}")
        self.assertNotIn(
            "browser-use",
            routing_text,
            "stage-routing.json still names the unimplemented browser-use backend",
        )

        backend = importlib.import_module("observation_backend")
        vision = importlib.import_module("observation_vision")
        browser_backends = set(backend.BACKENDS)
        vision_adapters = set(vision.ADAPTERS)
        self.assertIn("playwright-cli", browser_backends)
        self.assertEqual(
            vision_adapters,
            {"direct-multimodal", "midscene", "ui-tars"},
            f"observation_vision adapters drifted: {sorted(vision_adapters)}",
        )
        for name in ("direct-multimodal", "playwright-cli", "midscene", "ui-tars"):
            self.assertIn(
                name,
                browser_backends | vision_adapters,
                f"routing names {name!r} but no observation module implements it",
            )
        source = read("scripts/observation_backend.py") + read("scripts/observation_vision.py")
        self.assertNotIn("browser-use", source)

    def test_backend_routing_doc_names_four_backends_and_ffmpeg(self):
        text = read("product-observer/references/backend-routing.md")
        low = text.lower()
        self.assertRegex(low, r"direct[ -]multimodal")
        for name in ("playwright-cli", "midscene", "ui-tars", "ffmpeg"):
            self.assertIn(name, low, f"backend-routing.md omits {name!r}")
        self.assertNotIn("browser-use", low)


class AgentContractTests(unittest.TestCase):
    AGENT = ".opencode/agents/mvp-product-observer.md"
    REVIEWER = "reviewer/SKILL.md"

    def frontmatter(self):
        text = read(self.AGENT)
        self.assertTrue(text.startswith("---\n"), "agent file has no frontmatter")
        end = text.index("\n---", 4)
        return text[4:end], text

    def test_permission_boundary(self):
        frontmatter, text = self.frontmatter()
        self.assertIsNotNone(
            re.search(r"^  edit: deny$", frontmatter, re.MULTILINE),
            "edit: deny missing",
        )
        self.assertIsNotNone(
            re.search(r"^  task: deny$", frontmatter, re.MULTILINE),
            "task: deny missing",
        )
        bash = re.search(r"^  bash:\n((?: {4}.*\n)+)", frontmatter, re.MULTILINE)
        self.assertIsNotNone(bash, "permission.bash object missing")
        self.assertIn('"*": allow', bash.group(1))
        self.assertNotIn("write: deny", text)
        self.assertNotIn("relations", text)

    def test_single_fenced_json_return(self):
        _, text = self.frontmatter()
        self.assertEqual(
            text.count("```json"),
            1,
            "observer contract must describe exactly one json fenced block",
        )
        fence_lines = [line.lower() for line in text.splitlines() if "```json" in line]
        self.assertTrue(
            any(
                ("one" in line or "single" in line) and "fenced" in line
                for line in fence_lines
            ),
            "observer contract lacks the one/single json fenced block keyword",
        )

    def test_reviewer_hash_semantics_bound_by_controller_or_engine(self):
        text = read(self.REVIEWER)
        self.assertIn("discover_hash", text)
        self.assertIn("compare_hash", text)
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if "discover_hash" in line or "compare_hash" in line:
                window = "\n".join(lines[max(0, index - 1):index + 3]).lower()
                self.assertTrue(
                    "controller" in window or "engine" in window,
                    f"reviewer/SKILL.md line {index + 1}: hash source not "
                    f"attributed to controller/engine",
                )
                self.assertTrue(
                    "bound" in window or "computed" in window,
                    f"reviewer/SKILL.md line {index + 1}: hash binding not "
                    f"described as computed/bound",
                )
        self.assertNotRegex(
            text,
            r"(?i)(report|return|provide|claim)[^\n]{0,40}(discover_hash|compare_hash)",
            "reviewer/SKILL.md still asks the reviewer to self-report hashes",
        )


class ModuleImportAndVersionTests(unittest.TestCase):
    def test_observation_modules_import(self):
        for name in OBSERVATION_MODULES:
            with self.subTest(module=name):
                try:
                    importlib.import_module(name)
                except Exception as exc:  # pragma: no cover - failure reporting
                    self.fail(
                        f"implementation gap: scripts/{name}.py failed to "
                        f"import ({type(exc).__name__}: {exc})"
                    )

    def test_schema_constants_match_contract_doc_and_docs(self):
        contract = importlib.import_module("observation_contract")
        self.assertEqual(contract.SCHEMA_RESULT, "product-observation/2")
        self.assertEqual(contract.SCHEMA_REVIEW, "product-observation-review/2")
        enums = contract.contract_enums()
        self.assertEqual(enums["schemas"]["result"], contract.SCHEMA_RESULT)
        self.assertEqual(enums["schemas"]["review"], contract.SCHEMA_REVIEW)

        contract_doc = read("product-observer/references/result-contract.md")
        self.assertIn(contract.SCHEMA_RESULT, contract_doc)
        self.assertIn(contract.SCHEMA_REVIEW, contract_doc)

        union = "\n".join(read(rel_path) for rel_path in DOCS)
        for current in CURRENT_SCHEMAS:
            self.assertIn(current, union)


if __name__ == "__main__":
    unittest.main()
