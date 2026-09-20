"""WP4 lifecycle contracts: single-round test-author binding and reviewer reuse.

These tests verify the mechanical binding command and the documentation
invariants that keep the lifecycle unambiguous:

- the test-author authors, runs and freezes in one dispatch with
  `pending-binding` provenance;
- the controller binds the runtime-recorded ID via `bind-test-author`;
- reviewer repair rechecks may resume the same independent seat, while final
  and converge audits stay fresh;
- the final stable slice may return two separately scoped verdicts.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import runtime_trace  # noqa: E402
from workflow_runtime import (  # noqa: E402
    RuntimeStateError,
    bind_test_author,
    load_dispatch,
    main,
)

MANIFEST_TEMPLATE = """# Test Manifest: S-01

| Field | Value |
|---|---|
| Spec source | docs/audit-slices/g/S-01/contract.md |
| Spec hash | abc123 |
| Test author ID | pending-binding |
| Provenance status | pending-binding |
| Implementation author ID | pending |
| Frozen at | 2026-09-19T00:00:00Z |
"""


class BindTestAuthorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.manifest = self.tmp / "S-01.md"
        self.manifest.write_text(MANIFEST_TEMPLATE, encoding="utf-8")
        self.dispatch = self.tmp / "g.dispatch.json"
        self.dispatch.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "goal_id": "G-X",
                    "active_slice": {"rigor": "audited"},
                    "tasks": [
                        {
                            "task_id": "T-01",
                            "role": "test-author",
                            "status": "done",
                            "attempt": 1,
                            "provenance": {
                                "session_id": "ses_author",
                                "agent": "mvp-test-author",
                            },
                            "result_ref": "result.json",
                            "acceptance": {"verdict": None, "pending_actions": []},
                            "actions": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_binding_updates_manifest_and_dispatch(self):
        record = bind_test_author(self.manifest, self.dispatch, "T-01")
        text = self.manifest.read_text(encoding="utf-8")
        self.assertIn("| Test author ID | ses_author (mvp-test-author) |", text)
        self.assertIn("| Provenance status | bound |", text)
        task = record["tasks"][0]
        self.assertEqual(task["test_author_binding"]["session_id"], "ses_author")
        self.assertEqual(task["test_author_binding"]["sha256"], record["tasks"][0]["test_author_binding"]["sha256"])
        self.assertEqual(record["revision"], 1)
        self.assertEqual(load_dispatch(self.dispatch)["revision"], 1)

    def test_rebinding_same_session_is_idempotent(self):
        first = bind_test_author(self.manifest, self.dispatch, "T-01")
        second = bind_test_author(self.manifest, self.dispatch, "T-01")
        self.assertEqual(second["revision"], first["revision"])

    def test_rebinding_other_session_is_rejected(self):
        bind_test_author(self.manifest, self.dispatch, "T-01")
        record = load_dispatch(self.dispatch)
        record["tasks"][0]["provenance"]["session_id"] = "ses_other"
        self.dispatch.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeStateError, "already bound"):
            bind_test_author(self.manifest, self.dispatch, "T-01")

    def test_missing_provenance_is_rejected(self):
        record = load_dispatch(self.dispatch)
        record["tasks"][0]["provenance"] = {"session_id": None, "agent": None}
        self.dispatch.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeStateError, "dispatch-result"):
            bind_test_author(self.manifest, self.dispatch, "T-01")

    def test_manifest_without_binding_rows_is_rejected(self):
        self.manifest.write_text("# Manifest\n\nno table\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeStateError, "table rows"):
            bind_test_author(self.manifest, self.dispatch, "T-01")

    def test_cli_bind_reports_bound_session(self):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = main(
                [
                    "bind-test-author",
                    str(self.manifest),
                    "--dispatch",
                    str(self.dispatch),
                    "--task",
                    "T-01",
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("test author bound: T-01", stdout.getvalue())


class ReviewerReuseTests(unittest.TestCase):
    def test_reviewer_payload_with_dual_verdicts_passes_existing_validator(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "mode": "review",
                "checked_scope": ["slice", "whole goal"],
                "not_checked": [],
                "issues": [],
                "verdicts": {
                    "slice_converge": "satisfied",
                    "whole_goal": "satisfied",
                },
            }
            result = Path(tmp) / "result.json"
            result.write_text(json.dumps(payload), encoding="utf-8")
            task = {
                "task_id": "T-02",
                "role": "reviewer",
                "status": "done",
                "review_scope": "goal",
                "result_ref": str(result),
                "acceptance": {"verdict": "satisfied", "pending_actions": []},
            }
            problems = runtime_trace.reviewer_result_problems("T-02", task, None)
            self.assertEqual(problems, [])


class DocumentationInvariantTests(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_test_author_is_single_round_with_binding(self):
        skill = self.read("test-author/SKILL.md")
        self.assertIn("pending-binding", skill)
        self.assertIn("bind-test-author", skill)
        self.assertNotIn("two-step bootstrap", skill)
        self.assertNotIn("第一轮 bootstrap", skill)

    def test_test_author_agent_no_longer_demands_the_id_first(self):
        agent = self.read(".opencode/agents/mvp-test-author.md")
        self.assertIn("pending-binding", agent)
        self.assertNotIn("two-step bootstrap", agent)

    def test_construction_binds_before_implementation(self):
        construction = self.read("construction/SKILL.md")
        self.assertIn("bind-test-author", construction)
        self.assertIn("must not authorize implementation", construction)

    def test_reviewer_reuse_and_dual_verdict_rules_exist(self):
        orchestration = self.read("mvp-delivery/references/subagent-orchestration.md")
        self.assertIn("可以 resume\n  原独立 reviewer 席位", orchestration)
        self.assertIn("slice converge 与 whole-goal", orchestration)
        protocol = self.read("contract-review/references/reviewer-protocol.md")
        self.assertIn("slice_converge", protocol)
        self.assertIn("never satisfies the\nwhole-goal gate", protocol)
        reviewer = self.read("reviewer/SKILL.md")
        self.assertIn("slice_converge", reviewer)
        finish = self.read("mvp-delivery/references/delivery-finish.md")
        self.assertIn("separately scoped", finish)


if __name__ == "__main__":
    unittest.main()
