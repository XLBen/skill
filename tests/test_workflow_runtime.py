import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from workflow_runtime import (  # noqa: E402
    RuntimeStateError,
    begin_dispatch,
    load_dispatch,
    main,
    next_action,
    record_action_result,
    record_dispatch_result,
)


def base_record(tasks=None):
    return {
        "schema_version": 2,
        "goal_id": "G-X",
        "active_slice": {
            "slice_id": "S-01",
            "rigor": "guarded",
            "basis": "test",
            "package": None,
            "brief_path": None,
        },
        "failure_counters": [],
        "tasks": tasks or [],
    }


class DispatchBeginTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.dispatch = self.tmp / "g.dispatch.json"
        self.dispatch.write_text(
            json.dumps(base_record(), ensure_ascii=False), encoding="utf-8"
        )

    def test_records_new_dispatch_and_archives_body(self):
        body = self.tmp / "dispatch-T01.md"
        body.write_text("DISPATCH body", encoding="utf-8")
        record = begin_dispatch(
            self.dispatch,
            {"task_id": "T-01", "role": "worker"},
            dispatch_body=body,
        )
        task = record["tasks"][0]
        self.assertEqual(task["status"], "dispatched")
        self.assertEqual(task["attempt"], 1)
        self.assertEqual(record["revision"], 1)
        archived = Path(task["dispatch_ref"])
        self.assertTrue(archived.is_file())
        self.assertEqual(archived.read_text(encoding="utf-8"), "DISPATCH body")
        self.assertEqual(load_dispatch(self.dispatch)["revision"], 1)

    def test_duplicate_requires_force_attempt(self):
        begin_dispatch(self.dispatch, {"task_id": "T-01", "role": "worker"})
        with self.assertRaisesRegex(RuntimeStateError, "already|force-attempt"):
            begin_dispatch(
                self.dispatch,
                {"task_id": "T-01", "role": "worker"},
                dispatch_body=None,
            )
        # the failed call must not have mutated the record
        self.assertEqual(load_dispatch(self.dispatch)["revision"], 1)

    def test_pending_task_dispatches_without_force(self):
        record = load_dispatch(self.dispatch)
        record["tasks"].append(
            {
                "task_id": "T-09",
                "role": "worker",
                "status": "pending",
                "attempt": 1,
                "acceptance": {"verdict": None, "pending_actions": []},
                "actions": [],
            }
        )
        self.dispatch.write_text(json.dumps(record), encoding="utf-8")
        updated = begin_dispatch(self.dispatch, {"task_id": "T-09", "role": "worker"})
        task = next(item for item in updated["tasks"] if item["task_id"] == "T-09")
        self.assertEqual(task["status"], "dispatched")
        self.assertEqual(task["attempt"], 1)

    def test_force_attempt_increments_attempt(self):
        begin_dispatch(self.dispatch, {"task_id": "T-01", "role": "worker"})
        record = begin_dispatch(
            self.dispatch, {"task_id": "T-01", "role": "worker"}, force_attempt=True
        )
        self.assertEqual(record["tasks"][0]["attempt"], 2)
        self.assertEqual(record["revision"], 2)

    def test_revision_conflict_rejected(self):
        begin_dispatch(self.dispatch, {"task_id": "T-01", "role": "worker"})
        with self.assertRaisesRegex(RuntimeStateError, "revision conflict"):
            begin_dispatch(
                self.dispatch,
                {"task_id": "T-02", "role": "worker"},
                expect_revision=0,
            )

    def test_unknown_role_rejected_without_mutation(self):
        before = self.dispatch.read_bytes()
        with self.assertRaises(RuntimeStateError):
            begin_dispatch(self.dispatch, {"task_id": "T-01", "role": "wizard"})
        self.assertEqual(self.dispatch.read_bytes(), before)


class DispatchResultTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.dispatch = self.tmp / "g.dispatch.json"
        record = base_record(
            [
                {
                    "task_id": "T-01",
                    "role": "reviewer",
                    "status": "dispatched",
                    "attempt": 1,
                    "acceptance": {"verdict": None, "pending_actions": []},
                    "actions": [],
                }
            ]
        )
        self.dispatch.write_text(json.dumps(record), encoding="utf-8")

    def test_completed_requires_provenance_for_independence_roles(self):
        with self.assertRaisesRegex(RuntimeStateError, "provenance"):
            record_dispatch_result(
                self.dispatch,
                {"task_id": "T-01", "result_status": "completed"},
            )

    def test_completed_records_verdict_and_result_ref(self):
        raw = self.tmp / "review-result.json"
        raw.write_text(json.dumps({"mode": "review", "issues": [], "checked_scope": [], "not_checked": []}), encoding="utf-8")
        record = record_dispatch_result(
            self.dispatch,
            {
                "task_id": "T-01",
                "result_status": "completed",
                "provenance": {"session_id": "ses_rev", "agent": "mvp-reviewer"},
                "result_ref": str(raw),
                "verdict": "satisfied",
            },
        )
        task = record["tasks"][0]
        self.assertEqual(task["status"], "done")
        self.assertEqual(task["provenance"]["session_id"], "ses_rev")
        self.assertEqual(task["acceptance"]["verdict"], "satisfied")
        self.assertEqual(record["revision"], 1)

    def test_result_archive_body_is_copied(self):
        body = self.tmp / "return.json"
        body.write_text("{}", encoding="utf-8")
        record = record_dispatch_result(
            self.dispatch,
            {
                "task_id": "T-01",
                "result_status": "blocked",
                "provenance": {"session_id": "ses_rev", "agent": "mvp-reviewer"},
            },
            result_body=body,
        )
        archived = Path(record["tasks"][0]["result_ref"])
        self.assertTrue(archived.is_file())

    def test_missing_result_ref_fails_without_mutation(self):
        before = self.dispatch.read_bytes()
        with self.assertRaisesRegex(RuntimeStateError, "does not exist"):
            record_dispatch_result(
                self.dispatch,
                {
                    "task_id": "T-01",
                    "result_status": "completed",
                    "provenance": {"session_id": "ses_rev", "agent": "mvp-reviewer"},
                    "result_ref": str(self.tmp / "missing.json"),
                },
            )
        self.assertEqual(self.dispatch.read_bytes(), before)

    def test_failed_status_maps_to_failed(self):
        record = record_dispatch_result(
            self.dispatch,
            {"task_id": "T-01", "result_status": "failed"},
        )
        self.assertEqual(record["tasks"][0]["status"], "failed")


class ActionResultTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.dispatch = self.tmp / "g.dispatch.json"
        record = base_record(
            [
                {
                    "task_id": "T-01",
                    "role": "reviewer",
                    "status": "dispatched",
                    "attempt": 1,
                    "acceptance": {"verdict": None, "pending_actions": []},
                    "actions": [
                        {
                            "action_id": "A-01",
                            "kind": "run-command",
                            "status": "requested",
                            "evidence_ref": None,
                        }
                    ],
                }
            ]
        )
        self.dispatch.write_text(json.dumps(record), encoding="utf-8")

    def test_completed_requires_evidence(self):
        before = self.dispatch.read_bytes()
        with self.assertRaisesRegex(RuntimeStateError, "evidence_ref"):
            record_action_result(
                self.dispatch,
                {"task_id": "T-01", "action_id": "A-01", "status": "completed"},
            )
        self.assertEqual(self.dispatch.read_bytes(), before)

    def test_completed_with_evidence_and_idempotent_replay(self):
        first = record_action_result(
            self.dispatch,
            {
                "task_id": "T-01",
                "action_id": "A-01",
                "status": "completed",
                "evidence_ref": "ev.json",
            },
        )
        self.assertEqual(first["tasks"][0]["actions"][0]["status"], "completed")
        second = record_action_result(
            self.dispatch,
            {
                "task_id": "T-01",
                "action_id": "A-01",
                "status": "completed",
                "evidence_ref": "ev.json",
            },
        )
        self.assertEqual(second["revision"], first["revision"])

    def test_terminal_state_change_needs_force(self):
        record_action_result(
            self.dispatch,
            {
                "task_id": "T-01",
                "action_id": "A-01",
                "status": "completed",
                "evidence_ref": "ev.json",
            },
        )
        with self.assertRaisesRegex(RuntimeStateError, "terminal|force"):
            record_action_result(
                self.dispatch,
                {"task_id": "T-01", "action_id": "A-01", "status": "failed"},
            )
        record = record_action_result(
            self.dispatch,
            {
                "task_id": "T-01",
                "action_id": "A-01",
                "status": "failed",
                "force": True,
            },
        )
        self.assertEqual(record["tasks"][0]["actions"][0]["status"], "failed")

    def test_new_action_inserted(self):
        record = record_action_result(
            self.dispatch,
            {
                "task_id": "T-01",
                "action_id": "A-02",
                "status": "running",
                "kind": "gui-scenario",
            },
        )
        ids = [action["action_id"] for action in record["tasks"][0]["actions"]]
        self.assertEqual(ids, ["A-01", "A-02"])


class NextActionTests(unittest.TestCase):
    def test_circuit_break_takes_precedence(self):
        record = base_record()
        record["failure_counters"] = [
            {
                "target": "V-01",
                "signature": "AssertionError",
                "actual_failures": 3,
                "evidence_refs": [],
            }
        ]
        report = next_action(record)
        self.assertEqual(report["action"]["kind"], "circuit-break")
        self.assertEqual(report["blocked_by"][0]["signature"], "AssertionError")

    def test_unresolved_action_before_await_task(self):
        record = base_record(
            [
                {
                    "task_id": "T-01",
                    "status": "dispatched",
                    "acceptance": {"verdict": None, "pending_actions": []},
                    "actions": [
                        {"action_id": "A-01", "status": "running", "evidence_ref": None}
                    ],
                }
            ]
        )
        report = next_action(record)
        self.assertEqual(report["action"]["kind"], "resolve-action")

    def test_owner_decision_reported(self):
        record = base_record(
            [
                {
                    "task_id": "T-01",
                    "status": "done",
                    "acceptance": {"verdict": "owner", "pending_actions": ["ask"]},
                    "actions": [],
                }
            ]
        )
        report = next_action(record)
        self.assertEqual(report["action"]["kind"], "owner-decision")

    def test_in_flight_and_failed_tasks(self):
        record = base_record(
            [
                {"task_id": "T-01", "status": "pending", "acceptance": {}, "actions": []},
            ]
        )
        self.assertEqual(next_action(record)["action"]["kind"], "dispatch")
        record = base_record(
            [
                {"task_id": "T-01", "status": "failed", "acceptance": {}, "actions": []},
            ]
        )
        self.assertEqual(next_action(record)["action"]["kind"], "rebuild-failed-task")

    def test_audited_missing_package_is_blocker(self):
        record = base_record()
        record["active_slice"]["rigor"] = "audited"
        report = next_action(record)
        self.assertEqual(report["action"]["kind"], "controller-decision")
        self.assertIn("missing-audited-package", [item["kind"] for item in report["blocked_by"]])

    def test_idle_record_yields_controller_decision_with_candidates(self):
        report = next_action(base_record())
        self.assertEqual(report["action"]["kind"], "controller-decision")
        self.assertTrue(report["candidates"])
        self.assertTrue(any("never approves" in note for note in report["notes"]))


class CliTests(unittest.TestCase):
    def test_next_action_cli_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            dispatch = tmp / "g.dispatch.json"
            dispatch.write_text(json.dumps(base_record()), encoding="utf-8")
            out = tmp / "next.json"
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = main(["next-action", str(dispatch), "--out", str(out)])
            self.assertEqual(code, 0)
            self.assertIn("next action written", stdout.getvalue())
            self.assertEqual(
                json.loads(out.read_text(encoding="utf-8"))["schema"],
                "workflow-next-action/1",
            )

    def test_invalid_update_returns_1_and_preserves_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            dispatch = tmp / "g.dispatch.json"
            dispatch.write_text(json.dumps(base_record()), encoding="utf-8")
            before = dispatch.read_bytes()
            update = tmp / "u.json"
            update.write_text(json.dumps({"task_id": "T-99", "action_id": "A"}), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                code = main(["action-result", str(dispatch), "--update", str(update)])
            self.assertEqual(code, 1)
            self.assertEqual(dispatch.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
