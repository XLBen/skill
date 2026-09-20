import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check as check_module  # noqa: E402
import workflow_protocol as protocol  # noqa: E402
from workflow_packets import (  # noqa: E402
    HANDOFF_PACKET_SCHEMA,
    STAGE_PACKET_SCHEMA,
    build_handoff_packet,
    build_stage_packet,
    main,
    validate_packet,
)

GOAL_FIXTURE = ROOT / "tests/fixtures/goal-valid.md"
ROUTING = ROOT / "mvp-delivery/references/stage-routing.json"


class StagePacketTests(unittest.TestCase):
    def test_stage_packet_resolves_owners_and_formal_verification(self):
        packet = build_stage_packet(
            "step-verification", "audited", "reviewer", [], [], routing_path=str(ROUTING)
        )
        self.assertEqual(packet["schema"], STAGE_PACKET_SCHEMA)
        self.assertEqual(packet["routing"]["schema_version"], 3)
        self.assertEqual(packet["seat"], "reviewer-subagent")
        checks = {entry["check"]: entry["owner_seat"] for entry in packet["semantic_checks"]}
        self.assertEqual(checks["step-handoff"], "step-executor-subagent")
        self.assertEqual(checks["step-formal-evidence"], "controller")
        self.assertEqual(checks["step-review"], "reviewer-subagent")
        self.assertEqual(packet["formal_verification"]["owner_seat"], "controller")
        self.assertIn("verify-step", packet["formal_verification"]["gate"])
        self.assertEqual(packet["reviewer"]["mode"], "review")
        self.assertIsNone(packet["reviewer"]["mode_file"])
        self.assertTrue(packet["reviewer"]["condition"]["mandatory"])
        self.assertEqual(packet["rules"]["formal_v_owner"], "controller")

    def test_converge_audit_mode_names_its_mode_file(self):
        packet = build_stage_packet(
            "slice-acceptance", "audited", "reviewer", [], [], routing_path=str(ROUTING)
        )
        self.assertEqual(packet["reviewer"]["mode"], "converge-audit")
        self.assertEqual(
            packet["reviewer"]["mode_file"], "../reviewer/references/modes/converge-audit.md"
        )

    def test_missing_inputs_are_declared_not_omitted(self):
        packet = build_stage_packet(
            "test-freeze",
            "audited",
            "test-author",
            ["does/not/exist.md"],
            ["also/missing.json"],
            routing_path=str(ROUTING),
        )
        self.assertEqual(len(packet["inputs"]), 1)
        self.assertFalse(packet["inputs"][0]["exists"])
        self.assertEqual(len(packet["missing"]), 2)
        buckets = {entry["bucket"] for entry in packet["missing"]}
        self.assertEqual(buckets, {"inputs", "evidence_index"})

    def test_packet_is_deterministic_for_identical_inputs(self):
        first = build_stage_packet(
            "review-verdict", "guarded", "reviewer", [], [], routing_path=str(ROUTING)
        )
        second = build_stage_packet(
            "review-verdict", "guarded", "reviewer", [], [], routing_path=str(ROUTING)
        )
        self.assertEqual(
            json.dumps(first, ensure_ascii=False, sort_keys=True),
            json.dumps(second, ensure_ascii=False, sort_keys=True),
        )

    def test_unknown_stage_and_role_fail(self):
        with self.assertRaises((ValueError, KeyError, protocol.ProtocolError)):
            build_stage_packet("no-such-stage", "audited", "controller", [], [], routing_path=str(ROUTING))
        with self.assertRaises(ValueError):
            build_stage_packet("test-freeze", "audited", "wizard", [], [], routing_path=str(ROUTING))

    def test_validate_flags_stale_routing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            routing_copy = tmp / "stage-routing.json"
            shutil.copyfile(ROUTING, routing_copy)
            packet = build_stage_packet(
                "step-verification", "audited", "step-executor", [], [], routing_path=str(routing_copy)
            )
            out = tmp / "packet.json"
            out.write_text(json.dumps(packet), encoding="utf-8")
            self.assertEqual(validate_packet(out), [])
            routing_copy.write_text(routing_copy.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            problems = validate_packet(out)
            self.assertTrue(any("stale" in problem for problem in problems), problems)


class HandoffPacketTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)

    def _write_evidence(self, name, payload):
        path = self.tmp / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def test_handoff_collects_facts_and_gaps_with_empty_claims(self):
        meta, goal = check_module.read_artifact(str(GOAL_FIXTURE), "goal")
        goal_hash = check_module.goal_definition_hash(goal)
        evidence = self._write_evidence(
            "evidence-1.json",
            {
                "schema_version": 1,
                "kind": "goal-verification",
                "goal_id": goal["id"],
                "outcome_id": "O-01",
                "goal_definition_hash": goal_hash,
                "result": "passed",
                "started_at": "2026-09-19T00:00:00Z",
                "finished_at": "2026-09-19T00:00:01Z",
                "elapsed_seconds": 1.0,
            },
        )
        packet = build_handoff_packet(
            GOAL_FIXTURE,
            scope="goal",
            evidence_paths=[str(evidence)],
        )
        self.assertEqual(packet["schema"], HANDOFF_PACKET_SCHEMA)
        self.assertEqual(packet["goal"]["id"], "G-FIXTURE")
        self.assertEqual(len(packet["evidence_index"]), 1)
        self.assertEqual(packet["evidence_index"][0]["result"], "passed")
        self.assertIsNone(packet["claims"]["completion_claim"])
        self.assertEqual(packet["claims"]["not_verified"], [])
        self.assertIn("not a pass", packet["facts_note"])
        # passed evidence exists, so no outcome-without-passing-evidence gap
        gap_kinds = {gap["kind"] for gap in packet["gaps"]}
        self.assertNotIn("outcome-without-passing-evidence", gap_kinds)

    def test_handoff_surfaces_missing_stale_and_foreign_evidence(self):
        packet = build_handoff_packet(
            GOAL_FIXTURE,
            scope="goal",
            evidence_paths=[str(self.tmp / "missing.json")],
        )
        kinds = {gap["kind"] for gap in packet["gaps"]}
        self.assertIn("missing-evidence", kinds)
        self.assertIn("outcome-without-passing-evidence", kinds)

        stale = self._write_evidence(
            "stale.json",
            {
                "schema_version": 1,
                "kind": "goal-verification",
                "goal_id": "G-FIXTURE",
                "outcome_id": "O-01",
                "goal_definition_hash": "0" * 64,
                "result": "passed",
            },
        )
        foreign = self._write_evidence(
            "foreign.json",
            {
                "schema_version": 1,
                "kind": "goal-verification",
                "goal_id": "G-OTHER",
                "outcome_id": "O-09",
                "result": "failed",
            },
        )
        packet = build_handoff_packet(
            GOAL_FIXTURE, scope="goal", evidence_paths=[str(stale), str(foreign)]
        )
        kinds = {gap["kind"] for gap in packet["gaps"]}
        self.assertIn("stale-evidence", kinds)
        self.assertIn("foreign-evidence", kinds)
        self.assertIn("non-passing-evidence", kinds)

    def test_handoff_reads_dispatch_state_and_unresolved_actions(self):
        dispatch = {
            "schema_version": 2,
            "goal_id": "G-FIXTURE",
            "active_slice": {
                "slice_id": "S-01",
                "rigor": "guarded",
                "basis": "external boundary",
                "package": None,
                "brief_path": None,
            },
            "tasks": [
                {
                    "task_id": "T-01",
                    "role": "worker",
                    "status": "done",
                    "attempt": 1,
                    "acceptance": {"verdict": "owner", "pending_actions": ["confirm-ui"]},
                    "actions": [
                        {
                            "action_id": "A-01",
                            "kind": "run-command",
                            "status": "requested",
                            "evidence_ref": None,
                        },
                        {
                            "action_id": "A-02",
                            "kind": "engine-verify",
                            "status": "completed",
                            "evidence_ref": "ev.json",
                        },
                    ],
                }
            ],
            "failure_counters": [],
        }
        dispatch_path = self.tmp / "goal.dispatch.json"
        dispatch_path.write_text(json.dumps(dispatch), encoding="utf-8")
        packet = build_handoff_packet(GOAL_FIXTURE, dispatch_path=dispatch_path, scope="slice")
        self.assertEqual(packet["dispatch"]["active_slice"]["slice_id"], "S-01")
        self.assertEqual(packet["unresolved_actions"][0]["action_id"], "A-01")
        kinds = {gap["kind"] for gap in packet["gaps"]}
        self.assertIn("unresolved-controller-action", kinds)
        self.assertIn("unresolved-verdict", kinds)
        self.assertEqual(packet["scope"]["kind"], "slice")

    def test_handoff_is_deterministic(self):
        first = build_handoff_packet(GOAL_FIXTURE, scope="goal")
        second = build_handoff_packet(GOAL_FIXTURE, scope="goal")
        self.assertEqual(
            json.dumps(first, ensure_ascii=False, sort_keys=True),
            json.dumps(second, ensure_ascii=False, sort_keys=True),
        )

    def test_validate_flags_changed_goal_and_evidence(self):
        evidence = self._write_evidence(
            "ev.json",
            {
                "schema_version": 1,
                "goal_id": "G-FIXTURE",
                "outcome_id": "O-01",
                "result": "passed",
            },
        )
        goal_copy = self.tmp / "goal.md"
        shutil.copyfile(GOAL_FIXTURE, goal_copy)
        packet = build_handoff_packet(
            goal_copy, scope="goal", evidence_paths=[str(evidence)]
        )
        out = self.tmp / "handoff.json"
        out.write_text(json.dumps(packet), encoding="utf-8")
        self.assertEqual(validate_packet(out), [])
        goal_copy.write_text(goal_copy.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        problems = validate_packet(out)
        self.assertTrue(any("goal card changed" in problem for problem in problems), problems)

        # restore goal, change evidence
        shutil.copyfile(GOAL_FIXTURE, goal_copy)
        packet = build_handoff_packet(goal_copy, scope="goal", evidence_paths=[str(evidence)])
        out.write_text(json.dumps(packet), encoding="utf-8")
        evidence.write_text(json.dumps({"changed": True}), encoding="utf-8")
        problems = validate_packet(out)
        self.assertTrue(any("stale evidence binding" in problem for problem in problems), problems)


class ReadSurfaceTests(unittest.TestCase):
    def test_stage_packet_is_compact_and_excludes_other_modes(self):
        packet = build_stage_packet(
            "step-verification", "audited", "reviewer", [], [], routing_path=str(ROUTING)
        )
        text = json.dumps(packet, ensure_ascii=False)
        self.assertLess(len(text.encode("utf-8")), 8 * 1024)
        self.assertNotIn("Whole-Goal Boundary", text)
        self.assertNotIn("debate rhetoric", text)
        mode_file = ROOT / "reviewer/references/modes/converge-audit.md"
        self.assertIn("Whole-Goal Boundary", mode_file.read_text(encoding="utf-8"))

    def test_reviewer_skill_loads_mode_files_on_demand(self):
        skill = (ROOT / "reviewer/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/modes/final-audit.md", skill)
        self.assertIn("references/modes/converge-audit.md", skill)
        protocol = (ROOT / "contract-review/references/reviewer-protocol.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("modes/converge-audit.md", protocol)
        self.assertNotIn("### Whole-Goal Boundary", protocol)


class CliTests(unittest.TestCase):
    def test_stage_cli_writes_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "stage.json"
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = main(
                    [
                        "stage",
                        "goal-finish",
                        "--rigor",
                        "audited",
                        "--role",
                        "reviewer",
                        "--routing",
                        str(ROUTING),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertIn("stage packet written", stdout.getvalue())
            packet = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(packet["schema"], STAGE_PACKET_SCHEMA)

    def test_unknown_stage_cli_returns_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(
                ["stage", "nope", "--out", str(Path(tmp) / "x.json")]
            )
            self.assertEqual(code, 2)

    def test_validate_cli_reports_stale_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            packet = build_stage_packet(
                "review-verdict", "guarded", "reviewer", [], [], routing_path=str(ROUTING)
            )
            packet["routing"]["sha256"] = "f" * 64
            out = tmp / "p.json"
            out.write_text(json.dumps(packet), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["validate", str(out)])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
