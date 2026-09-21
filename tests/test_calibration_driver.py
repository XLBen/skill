# -*- coding: utf-8 -*-
"""S20B: tests for the product-observation calibration driver core.

Covers the pure functions in ``validation/observation-calibration/driver_core.py``
plus one real ``adopt_result`` round trip through ``adoption_result`` that proves
no default success values, no latest-session binding and no file fallback.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "validation" / "observation-calibration"))

import driver_core as dc  # noqa: E402
import observation_contract as contract  # noqa: E402

_UNSET = object()


def agent_text(mode="subagent"):
    return (
        "---\n"
        "description: Product observer calibration mirror.\n"
        f"mode: {mode}\n"
        "permission:\n"
        "  read: allow\n"
        "---\n"
        "Load the skill tool `name: product-observer` and follow it.\n"
        "Deliver your final phase result ONLY as the closing ```json block of "
        "your reply; do not write result files yourself.\n"
    )


class MakePrimaryMirrorTests(unittest.TestCase):
    def test_subagent_mode_is_flipped_to_primary(self):
        text = agent_text()
        mirrored = dc.make_primary_mirror(text)
        self.assertIn("\nmode: primary\n", mirrored)
        self.assertNotIn("mode: subagent", mirrored)
        self.assertIn("description: Product observer calibration mirror.", mirrored)
        self.assertIn("Deliver your final phase result ONLY", mirrored)

    def test_only_the_mode_token_changes(self):
        text = agent_text()
        mirrored = dc.make_primary_mirror(text)
        self.assertEqual(
            mirrored.replace("mode: primary", "mode: subagent", 1), text
        )

    def test_primary_is_returned_unchanged(self):
        text = agent_text("primary")
        self.assertEqual(dc.make_primary_mirror(text), text)
        self.assertEqual(dc.make_primary_mirror(dc.make_primary_mirror(text)), text)

    def test_round_trip_is_idempotent(self):
        once = dc.make_primary_mirror(agent_text())
        self.assertEqual(dc.make_primary_mirror(once), once)

    def test_missing_frontmatter_raises(self):
        with self.assertRaises(ValueError):
            dc.make_primary_mirror("just a body, no frontmatter\n")

    def test_unterminated_frontmatter_raises(self):
        with self.assertRaises(ValueError):
            dc.make_primary_mirror("---\nmode: subagent\nbody without close\n")

    def test_missing_mode_key_raises(self):
        text = "---\ndescription: no mode here\n---\nbody\n"
        with self.assertRaises(ValueError):
            dc.make_primary_mirror(text)

    def test_unknown_mode_value_raises(self):
        with self.assertRaises(ValueError):
            dc.make_primary_mirror(agent_text("all"))

    def test_non_string_raises(self):
        with self.assertRaises(ValueError):
            dc.make_primary_mirror(None)


class AssertSingleChannelTests(unittest.TestCase):
    def test_closing_json_block_statement_hits(self):
        self.assertEqual(dc.assert_single_channel(agent_text()), [])

    def test_one_fenced_json_statement_hits(self):
        text = "Return ONE fenced ```json block and nothing else."
        self.assertEqual(dc.assert_single_channel(text), [])

    def test_chinese_marker_hits(self):
        text = "整条消息必须恰好包含一个 json 围栏块。"
        self.assertEqual(dc.assert_single_channel(text), [])

    def test_missing_statement_is_reported(self):
        problems = dc.assert_single_channel("Return your report as you like.")
        self.assertEqual(len(problems), 1)
        self.assertIn("single-channel", problems[0])

    def test_blank_text_is_reported(self):
        self.assertTrue(dc.assert_single_channel("   "))
        self.assertTrue(dc.assert_single_channel(None))


class SeedRedactionTests(unittest.TestCase):
    seed = {
        "case": "B",
        "seed": "mode B of the two-mode product goes silent",
        "expected_findings": ["audio disappears while mode A still works"],
        "defect_notes": {"inner": "remove the second mode handler"},
    }

    def test_clean_packet_has_no_problems(self):
        packet = {
            "goal_id": "G-OBS",
            "brief": {"purpose": "exercise both modes"},
            "candidate": {"files": ["app/app.py"]},
        }
        self.assertEqual(dc.seed_redaction_problems(self.seed, packet), [])

    def test_deep_string_leak_is_reported(self):
        packet = {
            "brief": {
                "notes": [
                    {
                        "detail": "confirm mode B of the two-mode product "
                        "goes silent before dispatch"
                    }
                ]
            },
            "output": {"rules": "audio disappears while mode A still works"},
        }
        problems = dc.seed_redaction_problems(self.seed, packet)
        self.assertEqual(len(problems), 2)
        self.assertTrue(any("brief.notes[0].detail" in p for p in problems), problems)
        self.assertTrue(any("output.rules" in p for p in problems), problems)

    def test_nested_seed_key_value_leak_is_reported(self):
        packet = {"output": {"hint": "remove the second mode handler"}}
        problems = dc.seed_redaction_problems(self.seed, packet)
        self.assertEqual(len(problems), 1)
        self.assertIn("remove the second mode handler", problems[0])

    def test_malformed_inputs_are_reported(self):
        self.assertTrue(dc.seed_redaction_problems(None, {}))
        self.assertTrue(dc.seed_redaction_problems({}, None))


class PacketGuardTests(unittest.TestCase):
    def test_failed_packet_aborts(self):
        self.assertEqual(
            dc.packet_guard(False),
            {
                "abort": True,
                "reason": "phase packet generation failed; do not dispatch",
            },
        )

    def test_ok_packet_does_not_abort(self):
        self.assertEqual(dc.packet_guard(True), {"abort": False})


class StateResetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_removes_existing_and_lists_missing(self):
        first = self.tmp / "gate.json"
        second = self.tmp / "trace.json"
        first.write_text("{}", encoding="utf-8")
        result = dc.state_reset([first, second])
        self.assertEqual(result["removed"], [str(first)])
        self.assertEqual(result["missing"], [str(second)])
        self.assertEqual(result["problems"], [])
        self.assertFalse(first.exists())

    def test_single_path_is_accepted(self):
        target = self.tmp / "one.json"
        target.write_text("x", encoding="utf-8")
        result = dc.state_reset(target)
        self.assertEqual(result["removed"], [str(target)])

    def test_directory_is_a_problem_not_a_removal(self):
        folder = self.tmp / "runs"
        folder.mkdir()
        result = dc.state_reset([folder])
        self.assertEqual(result["removed"], [])
        self.assertTrue(any("refusing to delete directory" in p for p in result["problems"]))
        self.assertTrue(folder.exists())

    def test_deletion_failure_is_a_problem(self):
        target = self.tmp / "locked.json"
        target.write_text("x", encoding="utf-8")
        with mock.patch.object(Path, "unlink", side_effect=OSError("in use")):
            result = dc.state_reset([target])
        self.assertEqual(result["removed"], [])
        self.assertTrue(any("failed to delete" in p for p in result["problems"]))


class ServerOrderPlanTests(unittest.TestCase):
    def test_valid_order_is_normalized(self):
        steps = [" setup", "server-start ", "candidate-freeze", "packet", "dispatch"]
        self.assertEqual(
            dc.server_order_plan(steps),
            ["setup", "server-start", "candidate-freeze", "packet", "dispatch"],
        )

    def test_server_before_setup_raises(self):
        with self.assertRaises(ValueError):
            dc.server_order_plan(["server-start", "setup", "packet"])

    def test_server_without_setup_raises(self):
        with self.assertRaises(ValueError):
            dc.server_order_plan(["server-start", "packet"])

    def test_no_server_step_keeps_order(self):
        steps = ["candidate-freeze", "packet", "dispatch"]
        self.assertEqual(dc.server_order_plan(steps), steps)

    def test_bad_inputs_raise(self):
        for steps in ("setup", [], ["setup", "  "], None):
            with self.assertRaises(ValueError):
                dc.server_order_plan(steps)


class ResultSourceSingleTests(unittest.TestCase):
    def test_single_block_without_write_claim_is_clean(self):
        text = (
            "Here is the phase result.\n"
            '```json\n{"phase": "discover", "findings": []}\n```\n'
        )
        self.assertEqual(dc.result_source_is_single(text), [])

    def test_two_blocks_are_reported(self):
        text = (
            '```json\n{"a": 1}\n```\n'
            '```json\n{"a": 2}\n```\n'
        )
        problems = dc.result_source_is_single(text)
        self.assertTrue(any("more than one" in p for p in problems), problems)

    def test_no_block_is_reported(self):
        problems = dc.result_source_is_single("plain prose only")
        self.assertTrue(any("no ```json fenced block" in p for p in problems), problems)

    def test_write_result_json_declaration_is_reported(self):
        text = (
            "Write the completed result to "
            "G-OBS/cand-01/discover.result.json before you answer.\n"
            '```json\n{"phase": "discover"}\n```\n'
        )
        problems = dc.result_source_is_single(text)
        self.assertTrue(any("dual-channel" in p for p in problems), problems)

    def test_negated_write_statement_is_not_reported(self):
        text = (
            "Do not write a result.json file; return only the fenced block.\n"
            '```json\n{"phase": "discover"}\n```\n'
        )
        self.assertEqual(dc.result_source_is_single(text), [])

    def test_non_string_is_reported(self):
        self.assertTrue(dc.result_source_is_single(None))


class AdoptionResultTests(unittest.TestCase):
    received_at = "2026-09-21T12:00:00Z"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.cdir = self.tmp / "cand"
        self.project_root = self.tmp / "project"
        self.project_root.mkdir()
        for name in ("evidence/j01.png", "evidence/round.md"):
            target = self.cdir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"evidence")
        self.payload = json.loads(json.dumps(contract.result_template("discover")))
        self.envelope = {
            "goal_id": "G-OBS",
            "candidate_id": "C-01",
            "observer_session_id": "ses_observer",
            "model": "test-model",
            "packet_hash": "a" * 64,
            "attempt": 1,
        }
        self.trace = {
            "sessions": [{"id": "ses_observer", "parent_id": None}],
            "skill_events": [
                {
                    "session_id": "ses_observer",
                    "skill": "product-observer",
                    "status": "completed",
                }
            ],
        }

    def adopt(self, payload=_UNSET, envelope=_UNSET, trace=_UNSET, **kw):
        if payload is _UNSET:
            payload = self.payload
        if envelope is _UNSET:
            envelope = self.envelope
        if trace is _UNSET:
            trace = self.trace
        kw.setdefault("received_at", self.received_at)
        return dc.adoption_result(
            payload, envelope, trace, self.cdir, self.project_root, "discover", **kw
        )

    def test_valid_round_trip_writes_result(self):
        path, problems = self.adopt()
        self.assertEqual(problems, [])
        self.assertEqual(path, self.cdir / "discover" / "run-001" / "result.json")
        stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(stored["goal_id"], "G-OBS")
        self.assertEqual(stored["received_at"], self.received_at)
        self.assertEqual(stored["stop_reason"], self.payload["stop_reason"])

    def test_missing_trace_is_rejected_not_defaulted(self):
        path, problems = self.adopt(trace=None, run_id="run-002")
        self.assertIsNone(path)
        self.assertTrue(any("unavailable" in p for p in problems), problems)
        self.assertFalse(
            (self.cdir / "discover" / "run-002" / "result.json").exists()
        )

    def test_missing_envelope_field_is_rejected_not_filled(self):
        envelope = dict(self.envelope)
        del envelope["packet_hash"]
        path, problems = self.adopt(envelope=envelope, run_id="run-003")
        self.assertIsNone(path)
        self.assertTrue(any("packet_hash" in p for p in problems), problems)

    def test_no_default_stop_reason_is_supplied(self):
        payload = dict(self.payload)
        del payload["stop_reason"]
        path, problems = self.adopt(payload=payload, run_id="run-004")
        self.assertIsNone(path)
        self.assertTrue(any("stop_reason" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
