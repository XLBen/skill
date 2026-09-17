"""Protocol contract regression tests.

These verify real interface and state constraints, not keyword existence:

- the dispatch-record v2 example is valid JSON with the required runtime fields;
- the engine's goal definition hash really does change when runtime pointers are
  added to the goal JSON (justifying the dispatch-record storage boundary);
- the test-author agent's permission globs actually match the documented manifest
  paths (package and legacy) and still deny contracts/PLAN/product code;
- the Audited seat-selection table yields exactly one seat for every
  profile x interaction combination;
- PUA goal-finish separates pre-gate from post-gate evidence;
- the reviewer output example is valid JSON with the adjudication fields;
- every role format named in the Return Format Matrix exists in its skill.
"""

import copy
import fnmatch
import json
import re
import unittest
from pathlib import Path

from scripts import check

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def extract_json_block(text, marker):
    tail = text.split(marker, 1)[1]
    match = re.search(r"```json\n(.*?)```", tail, re.DOTALL)
    assert match, f"no json block after {marker}"
    return json.loads(match.group(1))


class DispatchRecordSchemaTests(unittest.TestCase):
    def test_dispatch_record_v2_example_has_required_runtime_fields(self):
        orchestration = read("mvp-delivery/references/subagent-orchestration.md")
        record = extract_json_block(orchestration, "## Dispatch Record")
        self.assertEqual(record["schema_version"], 2)
        slice_routing = record["active_slice"]
        for field in ("slice_id", "rigor", "basis", "package", "brief_path"):
            self.assertIn(field, slice_routing)
        counter = record["failure_counters"][0]
        for field in ("target", "signature", "actual_failures", "evidence_refs"):
            self.assertIn(field, counter)
        task = record["tasks"][0]
        for field in (
            "task_id", "role", "status", "provenance",
            "dispatch_ref", "result_ref", "artifact_baseline",
            "review_scope", "acceptance", "rounds",
        ):
            self.assertIn(field, task)
        for field in ("pre", "post"):
            self.assertIn(field, task["artifact_baseline"])
        for field in ("verdict", "pending_actions"):
            self.assertIn(field, task["acceptance"])

    def test_runtime_pointers_in_goal_json_would_invalidate_evidence_hash(self):
        meta, goal = check.read_artifact(str(ROOT / "tests/fixtures/goal-valid.md"), "goal")
        base = check.goal_definition_hash(goal)

        with_pointer = copy.deepcopy(goal)
        with_pointer["recovery_pointer"] = {"package": "docs/audit-slices/g/S-01/"}
        self.assertNotEqual(check.goal_definition_hash(with_pointer), base)

        with_status = copy.deepcopy(goal)
        with_status["status"] = "blocked"
        self.assertEqual(check.goal_definition_hash(with_status), base)

        with_evidence = copy.deepcopy(goal)
        with_evidence["outcomes"][0]["evidence"] = {
            "path": ".opencode/mvp/evidence/g-O-01-01.json", "sha256": "0" * 64,
        }
        with_evidence["outcomes"][0]["status"] = "verified"
        self.assertEqual(check.goal_definition_hash(with_evidence), base)


class AgentPermissionTests(unittest.TestCase):
    @staticmethod
    def edit_rules(agent_text):
        rules = []
        in_block = False
        for line in agent_text.splitlines():
            if re.match(r"^\s*edit:\s*$", line):
                in_block = True
                continue
            if in_block:
                matched = re.match(r'^\s+"([^"]+)":\s*(allow|deny)\s*$', line)
                if matched:
                    rules.append((matched.group(1), matched.group(2)))
                    continue
                if re.match(r"^  \S", line):
                    in_block = False
        return rules

    @staticmethod
    def resolve(rules, path):
        action = "deny" if not rules else None
        for pattern, act in rules:
            if fnmatch.fnmatch(path, pattern):
                action = act
        return action

    def test_test_author_manifest_paths_match_permissions(self):
        agent = read(".opencode/agents/mvp-test-author.md")
        rules = self.edit_rules(agent)
        self.assertTrue(rules)
        allowed = {
            "tests/test_greeting.py": "allow",
            "test/test_greeting.py": "allow",
            "src/greeting.test.ts": "allow",
            "src/__tests__/greeting.ts": "allow",
            "src/greeting.spec.js": "allow",
            "docs/test-manifests/S-01.md": "allow",
            "docs/audit-slices/g-report/S-01/test-manifests/S-01.md": "allow",
            "docs/audit-slices/g-report/S-01/contract.md": "deny",
            "docs/audit-slices/g-report/S-01/PLAN.md": "deny",
            "docs/audit-slices/g-report/S-01/workflow-events.jsonl": "deny",
            "src/product.py": "deny",
        }
        for path, expected in allowed.items():
            self.assertEqual(self.resolve(rules, path), expected, path)

    def test_skill_documented_package_manifest_path_is_writable(self):
        skill = read("test-author/SKILL.md")
        template = re.search(
            r"`(docs/audit-slices/<goal-slug>/<slice-id>/test-manifests/<slice-id>\.md)`",
            skill,
        )
        self.assertIsNotNone(template)
        concrete = (
            template.group(1)
            .replace("<goal-slug>", "g-report")
            .replace("<slice-id>", "S-01")
        )
        agent = read(".opencode/agents/mvp-test-author.md")
        self.assertEqual(self.resolve(self.edit_rules(agent), concrete), "allow")

    def test_researcher_agent_documents_side_effect_boundary(self):
        agent = read(".opencode/agents/mvp-researcher.md")
        self.assertIn("CONTROLLER_ACTION", agent)
        self.assertNotIn("(tests, git log/diff, builds)", agent)


class SeatSelectionTests(unittest.TestCase):
    @staticmethod
    def seat_table():
        text = read("mvp-delivery/references/subagent-orchestration.md")
        section = text.split("### Audited Execution Seat Selection", 1)[1]
        rows = {}
        for line in section.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            cells = [cell.strip().replace("`", "") for cell in stripped.strip("|").split("|")]
            if len(cells) != 3 or cells[0] not in ("direct", "full", "light"):
                continue
            rows[(cells[0], cells[1])] = cells[2]
        return rows

    def test_every_profile_interaction_has_exactly_one_seat(self):
        rows = self.seat_table()
        for profile in ("direct", "full", "light"):
            for interaction in ("autonomous", "checkpoints/stepwise"):
                matched = [
                    seat for (prof, inter), seat in rows.items()
                    if prof == profile and interaction in inter.replace("任意", "autonomous checkpoints/stepwise")
                ]
                self.assertEqual(len(matched), 1, (profile, interaction))

    def test_canonical_combinations(self):
        rows = self.seat_table()
        direct = rows[("direct", "任意")]
        self.assertIn("主控同会话", direct)
        self.assertIn("禁止派", direct)
        self.assertIn("step-executor", rows[("full", "autonomous")])
        self.assertIn("step-executor", rows[("full", "checkpoints/stepwise")])
        self.assertIn("step-executor", rows[("light", "checkpoints/stepwise")])
        self.assertIn("主控同会话", rows[("light", "autonomous")])

    def test_step_protocol_and_construction_reference_the_authority_table(self):
        protocol = read("construction/references/step-protocol.md").replace("\n", " ")
        self.assertNotIn("interaction stays in-session by default", protocol)
        self.assertIn("Audited Execution Seat Selection", protocol)
        construction = read("construction/SKILL.md")
        self.assertIn("Audited Execution Seat Selection table", construction)


class PuaStageTimingTests(unittest.TestCase):
    def test_goal_finish_card_splits_pre_and_post_gate_evidence(self):
        cards = read("pua/references/stage-checks.md")
        self.assertIn("Card Roles And Gate Phases", cards)
        card = read("pua/references/stage-checks/10-goal-finish.md")
        evidence = next(
            line for line in card.splitlines() if line.startswith("**证据**")
        )
        self.assertIn("门前", evidence)
        self.assertIn("门后", evidence)
        self.assertLess(evidence.index("门后"), evidence.index("`finish-goal`"))

    def test_engine_gates_in_cards_are_assigned_to_the_controller(self):
        for card in (
            "pua/references/stage-checks/03-contract-release.md",
            "pua/references/stage-checks/04-plan-confirmation.md",
        ):
            section = read(card)
            gate_line = next(
                line for line in section.splitlines()
                if "gate" in line and ("归主控" in line or "由主控执行" in line)
            )
            self.assertTrue(gate_line.strip())

    def test_stage_check_index_links_every_card(self):
        index = read("pua/references/stage-checks.md")
        for name in (
            "02-goal-validation.md", "03-contract-release.md",
            "04-plan-confirmation.md", "05-test-freeze.md", "06-step-verification.md",
            "07-slice-acceptance.md", "08-review-verdict.md", "09-goal-verification.md",
            "10-goal-finish.md",
        ):
            self.assertIn(name, index)
            self.assertTrue((ROOT / "pua/references/stage-checks" / name).is_file())


class ReviewerInterfaceTests(unittest.TestCase):
    def test_output_example_is_valid_json_with_adjudication_fields(self):
        protocol = read("contract-review/references/reviewer-protocol.md")
        payload = extract_json_block(protocol, "## Output")
        for field in ("mode", "checked_scope", "not_checked", "issues"):
            self.assertIn(field, payload)
        issue = payload["issues"][0]
        self.assertIn("classification", issue)
        self.assertIn("evidence", issue)
        resolved = payload["resolved"][0]
        self.assertIn("disposition", resolved)
        self.assertIn(resolved["disposition"], ("resolved", "invalid"))

    def test_role_formats_named_in_matrix_exist_in_role_skills(self):
        templates = read("mvp-delivery/references/subagent-templates.md")
        section = templates.split("## Return Format Matrix", 1)[1].split("\n## ", 1)[0]
        formats = {
            "RESULT": "task-worker/SKILL.md",
            "TEST_AUTHOR_HANDOFF": "test-author/SKILL.md",
            "STEP_HANDBACK": "step-executor/SKILL.md",
        }
        for token in formats:
            self.assertIn(token, section)
        for token, relative in formats.items():
            self.assertIn(token, read(relative))
        self.assertIn("checked_scope", read("contract-review/references/reviewer-protocol.md"))
        self.assertIn("CONTROLLER_ACTION", templates)


if __name__ == "__main__":
    unittest.main()
