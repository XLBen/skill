import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from runtime_trace import export_trace, validate_chain  # noqa: E402

from scripts import check  # noqa: E402


def make_db(path: Path, sessions, parts):
    con = sqlite3.connect(path)
    con.executescript(
        """
        create table session (
            id text primary key, parent_id text, directory text,
            agent text, time_created integer, time_updated integer
        );
        create table part (
            id text primary key, message_id text, session_id text,
            time_created integer, time_updated integer, data text
        );
        """
    )
    for s in sessions:
        con.execute(
            "insert into session (id, parent_id, directory, agent, time_created, time_updated) values (?,?,?,?,?,?)",
            (s["id"], s.get("parent_id"), s.get("directory", "D:/proj"), s.get("agent"), 1, 1),
        )
    for p in parts:
        con.execute(
            "insert into part (id, message_id, session_id, time_created, time_updated, data) values (?,?,?,?,?,?)",
            (p["id"], "m-" + p["id"], p["session_id"], 1, 1, json.dumps(p["data"])),
        )
    con.commit()
    con.close()


def browser_call(pid, session, tool="browser_click", status="completed", call_id=None):
    return {
        "id": pid,
        "session_id": session,
        "data": {
            "type": "tool",
            "tool": tool,
            "callID": call_id or ("call_" + pid),
            "state": {"status": status, "input": {"x": 1}, "output": "ok"},
        },
    }


def skill_part(pid, session, name, status="completed"):
    return {
        "id": pid,
        "session_id": session,
        "data": {
            "type": "tool",
            "tool": "skill",
            "callID": "call_s" + pid,
            "state": {"status": status, "input": {"name": name}, "output": "<skill_content>"},
            "metadata": {"name": name, "dir": "D:/proj"},
        },
    }


UI_SESSIONS = [{"id": "ses_ctrl", "parent_id": None, "agent": "build"}]
UI_PARTS = [
    dict(skill_part("cu", "ses_ctrl", "computer-use")),
    dict(browser_call("b1", "ses_ctrl", call_id="call_ui1")),
    dict(browser_call("b2", "ses_ctrl", call_id="call_ui2")),
    {  # noise: excluded context tool must not appear in tool_events
        "id": "noise",
        "session_id": "ses_ctrl",
        "data": {"type": "tool", "tool": "read", "callID": "call_n", "state": {"status": "completed"}},
    },
]


class ToolEventsExportTests(unittest.TestCase):
    def setUp(self):
        import shutil

        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.db = self.tmp / "opencode.db"
        make_db(self.db, UI_SESSIONS, UI_PARTS)

    def test_export_includes_mcp_calls_excludes_context_tools(self):
        trace = export_trace(Path("D:/proj"), str(self.db), None)
        tools = {(e["tool"], e["call_id"], e["status"]) for e in trace["tool_events"]}
        self.assertIn(("browser_click", "call_ui1", "completed"), tools)
        self.assertNotIn("read", {t[0] for t in tools})
        self.assertEqual(len(trace["tool_events"]), 2)

    def test_native_tool_calls_policy_requirement(self):
        trace = export_trace(Path("D:/proj"), str(self.db), None)
        dispatch = {"schema_version": 2, "goal_id": "G", "tasks": []}
        ok = {"schema": "runtime-policy/1", "requirements": [
            {"kind": "native-tool-calls", "refs": ["ses_ctrl:call_ui1"]}]}
        self.assertEqual(validate_chain(trace, dispatch, ok), [])
        bad = {"schema": "runtime-policy/1", "requirements": [
            {"kind": "native-tool-calls", "refs": ["ses_ctrl:call_missing"]}]}
        failures = validate_chain(trace, dispatch, bad)
        self.assertTrue(any("call_missing" in f for f in failures), failures)


class UiAcceptanceValidationTests(unittest.TestCase):
    def setUp(self):
        self.check = check
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(self._cleanup)
        self.root = self.tmp / "proj"
        (self.root / ".opencode" / "mvp" / "evidence").mkdir(parents=True)
        (self.root / "ui-evidence").mkdir()
        (self.root / "ui-evidence" / "obs.md").write_text("observed: greeting rendered\n", encoding="utf-8")
        (self.root / "ui-evidence" / "result.json").write_text('{"result": "ok"}\n', encoding="utf-8")
        (self.root / "ui-evidence" / "runner.log").write_text("runner: click -> assert\n", encoding="utf-8")
        self.card = self.root / ".opencode" / "mvp" / "g-fixture.md"
        self.card.write_text((ROOT / "tests/fixtures/goal-valid.md").read_text(encoding="utf-8"))
        (self.root / "greeter.py").write_text("print('Hello user')\n", encoding="utf-8")
        self.trace = {
            "schema": "runtime-trace/1",
            "sessions": [{"id": "ses_ctrl", "parent_id": None, "agent": "build"}],
            "skill_events": [
                {"session_id": "ses_ctrl", "skill": "computer-use", "status": "completed"}
            ],
            "task_events": [],
            "tool_events": [
                {"session_id": "ses_ctrl", "call_id": "call_ui1", "tool": "browser_click", "status": "completed"}
            ],
        }
        self.trace_path = self.root / ".opencode" / "mvp" / "trace.json"
        self.trace_path.write_text(json.dumps(self.trace), encoding="utf-8")
        self.sidecar_path = self.root / ".opencode" / "mvp" / "g-fixture.ui-acceptance.json"

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_sidecar(self, mutate=None):
        sidecar = base_sidecar()
        if mutate:
            mutate(sidecar)
        self.sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        return sidecar

    def _validate(self, bind=False, sidecar_mutate=None, rewrite=True, rebind=False):
        if rewrite or sidecar_mutate is not None:
            self._write_sidecar(sidecar_mutate)
        _, goal, problems = self.check.validate_goal_artifact(self.card)
        self.assertEqual(problems, [])
        return self.check.validate_ui_acceptance(
            self.card, goal, trace=self.trace, bind=bind, rebind=rebind
        )

    def test_bind_then_validate_passes(self):
        _, _, failures = self._validate(bind=True)
        self.assertEqual(failures, [])
        self.assertIn("artifact_identity", json.loads(self.sidecar_path.read_text(encoding="utf-8")))

    def test_unbound_identity_fails_until_bind(self):
        _, _, failures = self._validate(bind=False)
        self.assertTrue(any("not bound yet" in f for f in failures), failures)

    def test_changed_artifact_invalidates(self):
        self._validate(bind=True)
        (self.root / "greeter.py").write_text("print('changed')\n", encoding="utf-8")
        _, _, failures = self._validate(bind=False, rewrite=False)
        self.assertTrue(any("artifact_identity mismatch" in f for f in failures), failures)

    def test_rebind_after_change_is_rejected_without_new_execution(self):
        self._validate(bind=True)
        (self.root / "greeter.py").write_text("print('changed')\n", encoding="utf-8")
        _, _, failures = self._validate(bind=True, rewrite=False)
        self.assertTrue(any("artifact_identity mismatch" in f for f in failures), failures)

    def test_rebind_with_stale_execution_is_rejected(self):
        self._validate(bind=True)
        (self.root / "greeter.py").write_text("print('changed')\n", encoding="utf-8")
        _, _, failures = self._validate(rewrite=False, rebind=True)
        self.assertTrue(any("no execution recorded after" in f for f in failures), failures)

    def test_rebind_after_reset_and_reexecution_passes(self):
        self._validate(bind=True)
        (self.root / "greeter.py").write_text("print('changed')\n", encoding="utf-8")
        import datetime as dt

        sidecar = json.loads(self.sidecar_path.read_text(encoding="utf-8"))
        self.assertIsNotNone(sidecar.get("artifact_identity"))
        sidecar["scenarios"][0]["execution"]["executed_at"] = (
            dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=5)
        ).isoformat(timespec="seconds")
        self.sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        _, _, failures = self._validate(rewrite=False, rebind=True)
        self.assertEqual(failures, [])
        updated = json.loads(self.sidecar_path.read_text(encoding="utf-8"))
        self.assertIn("bound_at", updated)
        self.assertIsNotNone(updated.get("artifact_identity"))

    def test_pending_required_scenario_fails(self):
        def mutate(s):
            s["scenarios"][0]["status"] = "pending"

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("required scenario is pending" in f for f in failures), failures)

    def test_blocked_scenario_fails_and_is_not_applicability(self):
        def mutate(s):
            s["scenarios"][0]["status"] = "blocked"

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("required scenario is blocked" in f for f in failures), failures)

    def test_required_scenario_cannot_be_not_applicable(self):
        def mutate(s):
            s["scenarios"][0]["status"] = "not-applicable"
            s["scenarios"][0]["not_applicable_reason"] = "not this time"

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("cannot be not-applicable" in f for f in failures), failures)

    def test_required_must_be_boolean(self):
        def mutate(s):
            s["scenarios"][0]["required"] = "yes"

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("required must be a boolean" in f for f in failures), failures)

    def test_empty_outcome_coverage_fails(self):
        def mutate(s):
            s["scenarios"][0]["outcome_ids"] = []

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("outcome_ids must list" in f for f in failures), failures)

    def test_not_applicable_without_reason_fails(self):
        def mutate(s):
            s["scenarios"][0]["status"] = "not-applicable"
            s["scenarios"][0]["required"] = False
            s["scenarios"][0]["outcome_ids"] = []

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("not-applicable requires a reason" in f for f in failures), failures)

    def test_applicability_none_without_reason_fails(self):
        def mutate(s):
            s["applicability"] = "none"
            s["scenarios"] = []

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("applicability_reason" in f for f in failures), failures)

    def test_declared_without_scenarios_fails(self):
        def mutate(s):
            s["scenarios"] = []

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("requires at least one scenario" in f for f in failures), failures)

    def test_passed_without_session_evidence_fails(self):
        def mutate(s):
            s["scenarios"][0]["execution"]["session_id"] = None

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("without execution.session_id" in f for f in failures), failures)

    def test_passed_without_execution_metadata_fails(self):
        def mutate(s):
            s["scenarios"][0]["execution"].pop("target")

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("without execution.target" in f for f in failures), failures)

    def test_passed_without_result_refs_fails(self):
        def mutate(s):
            s["scenarios"][0]["execution"]["result_refs"] = []

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("without result_refs" in f for f in failures), failures)

    def test_passed_without_observation_refs_fails(self):
        def mutate(s):
            s["scenarios"][0]["execution"]["observation_refs"] = []

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("without observation_refs" in f for f in failures), failures)

    def test_missing_result_file_fails(self):
        def mutate(s):
            s["scenarios"][0]["execution"]["result_refs"] = ["ui-evidence/missing.json"]

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("does not exist" in f for f in failures), failures)

    def test_passed_without_native_call_refs_fails(self):
        def mutate(s):
            s["scenarios"][0]["execution"]["native_call_refs"] = []

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("without native_call_refs" in f for f in failures), failures)

    def test_passed_with_fabricated_call_ref_fails(self):
        def mutate(s):
            s["scenarios"][0]["execution"]["native_call_refs"] = ["ses_ctrl:call_fabricated"]

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("call_fabricated" in f for f in failures), failures)

    def test_foreign_session_call_ref_fails(self):
        def mutate(s):
            s["scenarios"][0]["execution"]["native_call_refs"] = ["ses_other:call_ui1"]

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("does not belong to the declared execution session" in f for f in failures), failures)

    def test_passed_without_computer_use_load_fails(self):
        self.trace["skill_events"] = []
        self.trace_path.write_text(json.dumps(self.trace), encoding="utf-8")
        _, _, failures = self._validate(bind=True)
        self.assertTrue(any("no completed computer-use/webapp-testing load" in f for f in failures), failures)

    def test_without_ui_tools_a_runner_evidence_is_required(self):
        def mutate(s):
            s["scenarios"][0]["execution"]["runner_refs"] = []

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("runner_refs" in f for f in failures), failures)

    def test_policy_ui_tools_rejects_unrelated_tool(self):
        policy = self.root / ".opencode" / "mvp" / "runtime-policy.json"
        policy.write_text(json.dumps({
            "schema": "runtime-policy/1", "goals": "all", "ui_tools": ["browser_*"],
        }), encoding="utf-8")
        self.trace["tool_events"] = [
            {"session_id": "ses_ctrl", "call_id": "call_bash", "tool": "bash", "status": "completed"}
        ]
        self.trace_path.write_text(json.dumps(self.trace), encoding="utf-8")

        def mutate(s):
            s["scenarios"][0]["execution"]["native_call_refs"] = ["ses_ctrl:call_bash"]
            s["scenarios"][0]["execution"]["runner_refs"] = []

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("ui_tools" in f for f in failures), failures)

    def test_policy_ui_tools_accepts_matching_tool_without_runner(self):
        policy = self.root / ".opencode" / "mvp" / "runtime-policy.json"
        policy.write_text(json.dumps({
            "schema": "runtime-policy/1", "goals": "all", "ui_tools": ["browser_*"],
        }), encoding="utf-8")

        def mutate(s):
            s["scenarios"][0]["execution"]["runner_refs"] = []

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertEqual(failures, [])

    def test_unknown_outcome_reference_fails(self):
        def mutate(s):
            s["scenarios"][0]["outcome_ids"] = ["O-99"]

        _, _, failures = self._validate(bind=True, sidecar_mutate=mutate)
        self.assertTrue(any("unknown outcome" in f for f in failures), failures)

    def test_wrong_schema_raises(self):
        self.sidecar_path.write_text(json.dumps({"schema": "bogus"}), encoding="utf-8")
        _, goal, _ = self.check.validate_goal_artifact(self.card)
        with self.assertRaises(self.check.ValidationError):
            self.check.validate_ui_acceptance(self.card, goal, trace=self.trace)


def base_sidecar():
    return {
        "schema": "ui-acceptance/1",
        "goal_id": "G-FIXTURE",
        "applicability": "declared",
        "applicability_reason": None,
        "files": ["greeter.py"],
        "artifact_identity": None,
        "scenarios": [
            {
                "scenario_id": "UI-01",
                "outcome_ids": ["O-01"],
                "required": True,
                "backend": "browser",
                "journey": {
                    "precondition": "open the app",
                    "input": "hello",
                    "actions": ["click go"],
                    "expected": ["greeting shown"],
                },
                "status": "passed",
                "not_applicable_reason": None,
                "execution": {
                    "session_id": "ses_ctrl",
                    "executed_at": "2020-01-01T00:00:00+00:00",
                    "target": "test app window",
                    "build": "greeter.py working copy",
                    "native_call_refs": ["ses_ctrl:call_ui1"],
                    "runner_refs": ["ui-evidence/runner.log"],
                    "observation_refs": ["ui-evidence/obs.md"],
                    "result_refs": ["ui-evidence/result.json"],
                },
                "limitations": None,
            }
        ],
    }


class UiGateEngineTests(unittest.TestCase):
    """finish-goal enforcement through real verify-goal runs."""

    def setUp(self):
        self.check = check
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(self._cleanup)
        self.root = self.tmp / "proj"
        (self.root / ".opencode" / "mvp" / "evidence").mkdir(parents=True)
        (self.root / "ui-evidence").mkdir()
        (self.root / "ui-evidence" / "obs.md").write_text("observed\n", encoding="utf-8")
        (self.root / "ui-evidence" / "result.json").write_text('{"ok": true}\n', encoding="utf-8")
        (self.root / "ui-evidence" / "runner.log").write_text("runner output\n", encoding="utf-8")
        self.card = self.root / ".opencode" / "mvp" / "g-fixture.md"
        self.card.write_text((ROOT / "tests/fixtures/goal-valid.md").read_text(encoding="utf-8"))
        (self.root / "greeter.py").write_text("print('Hello user')\n", encoding="utf-8")
        session_db = self.root / "session-store.db"
        make_db(
            session_db,
            [{"id": "ses_ctrl", "parent_id": None, "agent": "build"}],
            [
                skill_part("gu1", "ses_ctrl", "computer-use"),
                browser_call("gu2", "ses_ctrl", call_id="call_ui1"),
            ],
        )
        self.trace = {
            "schema": "runtime-trace/1",
            "source": {"kind": "opencode-sqlite", "path": str(session_db)},
            "sessions": [{"id": "ses_ctrl", "parent_id": None, "agent": "build"}],
            "skill_events": [
                {"session_id": "ses_ctrl", "skill": "computer-use", "status": "completed"}
            ],
            "task_events": [],
            "tool_events": [
                {"session_id": "ses_ctrl", "call_id": "call_ui1", "tool": "browser_click", "status": "completed"}
            ],
        }
        self.trace_path = self.root / ".opencode" / "mvp" / "trace.json"
        self.trace_path.write_text(json.dumps(self.trace), encoding="utf-8")
        self.sidecar_path = self.root / ".opencode" / "mvp" / "g-fixture.ui-acceptance.json"

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def _verify_all_outcomes(self):
        evidence = self.root / ".opencode" / "mvp" / "evidence" / "g-fixture-O-01-01.json"
        self.check.verify_goal_outcome(self.card, "O-01", evidence)

    def _write_sidecar(self, status="passed"):
        sidecar = base_sidecar()
        sidecar["scenarios"][0]["status"] = status
        if status != "passed":
            sidecar["scenarios"][0]["execution"] = {
                "session_id": None, "native_call_refs": [], "runner_refs": [],
                "observation_refs": [], "result_refs": [],
            }
        self.sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        return sidecar

    def _declare_goal_ui(self, outcome_ids=None):
        _, goal = self.check.read_artifact(self.card, "goal")
        goal["ui"] = {"required": True}
        if outcome_ids is not None:
            goal["ui"]["outcome_ids"] = outcome_ids
        self.card.write_text(self.check.render_goal(goal), encoding="utf-8")

    def test_no_sidecar_and_no_policy_keeps_legacy_behavior(self):
        self._verify_all_outcomes()
        goal = self.check.finish_goal(self.card)
        self.assertEqual(goal["status"], "complete")

    def test_sidecar_without_gate_blocks_finish(self):
        self._verify_all_outcomes()
        self._write_sidecar()
        with self.assertRaises(self.check.ValidationError) as ctx:
            self.check.finish_goal(self.card)
        self.assertIn("ui-gate", str(ctx.exception))

    def test_ui_gate_bind_then_pass_allows_finish(self):
        self._verify_all_outcomes()
        self._write_sidecar()
        gate, gate_path = self.check.ui_gate(self.card, self.trace_path, bind=True)
        self.assertEqual(gate["verdict"], "pass", gate["failures"])
        goal = self.check.finish_goal(self.card)
        self.assertEqual(goal["status"], "complete")

    def test_failed_scenario_gate_blocks_finish(self):
        self._verify_all_outcomes()
        self._write_sidecar(status="failed")
        gate, _ = self.check.ui_gate(self.card, self.trace_path, bind=True)
        self.assertEqual(gate["verdict"], "fail")
        with self.assertRaises(self.check.ValidationError):
            self.check.finish_goal(self.card)

    def test_goal_declared_ui_blocks_when_sidecar_deleted(self):
        self._declare_goal_ui()
        self._verify_all_outcomes()
        self._write_sidecar()
        self.check.ui_gate(self.card, self.trace_path, bind=True)
        self.sidecar_path.unlink()
        with self.assertRaisesRegex(self.check.ValidationError, "requires ui-acceptance"):
            self.check.finish_goal(self.card)

    def test_goal_declared_ui_rejects_applicability_none(self):
        self._declare_goal_ui()
        self._verify_all_outcomes()
        sidecar = base_sidecar()
        sidecar["applicability"] = "none"
        sidecar["applicability_reason"] = "nothing to check"
        sidecar["scenarios"] = []
        self.sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        gate, _ = self.check.ui_gate(self.card, self.trace_path, bind=True)
        self.assertEqual(gate["verdict"], "fail")
        with self.assertRaises(self.check.ValidationError):
            self.check.finish_goal(self.card)

    def test_goal_declared_ui_outcome_coverage_enforced(self):
        self._declare_goal_ui(outcome_ids=["O-99"])
        _, _, problems = self.check.validate_goal_artifact(self.card)
        self.assertTrue(any("unknown outcome" in p for p in problems), problems)

    def test_gate_rejects_non_native_trace(self):
        self._verify_all_outcomes()
        self._write_sidecar()
        self.trace.pop("source", None)
        self.trace_path.write_text(json.dumps(self.trace), encoding="utf-8")
        gate, _ = self.check.ui_gate(self.card, self.trace_path, bind=True)
        self.assertEqual(gate["verdict"], "fail")
        self.assertTrue(any("native provenance" in f for f in gate["failures"]), gate["failures"])

    def test_gate_rejects_calls_missing_from_the_source_store(self):
        self._verify_all_outcomes()
        self._write_sidecar()
        empty_db = self.root / "empty-store.db"
        make_db(empty_db, [{"id": "ses_ctrl", "parent_id": None, "agent": "build"}],
                [skill_part("x1", "ses_ctrl", "computer-use")])
        self.trace["source"]["path"] = str(empty_db)
        self.trace_path.write_text(json.dumps(self.trace), encoding="utf-8")
        gate, _ = self.check.ui_gate(self.card, self.trace_path, bind=True)
        self.assertEqual(gate["verdict"], "fail")
        self.assertTrue(any("tool call" in f for f in gate["failures"]), gate["failures"])

    def test_artifact_change_after_gate_blocks_finish(self):
        self._verify_all_outcomes()
        self._write_sidecar()
        gate, _ = self.check.ui_gate(self.card, self.trace_path, bind=True)
        self.assertEqual(gate["verdict"], "pass")
        (self.root / "greeter.py").write_text("print('changed after gate')\n", encoding="utf-8")
        with self.assertRaisesRegex(self.check.ValidationError, "workspace binding|stale"):
            self.check.finish_goal(self.card)

    def test_policy_change_after_gate_blocks_finish(self):
        self._verify_all_outcomes()
        policy = self.root / ".opencode" / "mvp" / "runtime-policy.json"
        policy.write_text(json.dumps({
            "schema": "runtime-policy/1", "goals": "all",
            "requirements": [{"kind": "ui-acceptance"}], "ui_tools": ["browser_*"],
        }), encoding="utf-8")
        self._write_sidecar()
        gate, _ = self.check.ui_gate(self.card, self.trace_path, bind=True)
        self.assertEqual(gate["verdict"], "pass", gate["failures"])
        policy.write_text(json.dumps({
            "schema": "runtime-policy/1", "goals": "all",
            "requirements": [{"kind": "ui-acceptance"}], "ui_tools": ["desktop_*"],
        }), encoding="utf-8")
        _, goal, _ = self.check.validate_goal_artifact(self.card)
        with self.assertRaisesRegex(self.check.ValidationError, "policy state changed"):
            self.check.enforce_ui_gate(self.card, goal)

    def test_policy_created_after_ui_gate_blocks_finish(self):
        self._verify_all_outcomes()
        self._write_sidecar()
        gate, _ = self.check.ui_gate(self.card, self.trace_path, bind=True)
        self.assertEqual(gate["verdict"], "pass", gate["failures"])
        policy = self.root / ".opencode" / "mvp" / "runtime-policy.json"
        policy.write_text(json.dumps({
            "schema": "runtime-policy/1", "goals": "all",
            "requirements": [{"kind": "ui-acceptance"}], "ui_tools": ["browser_*"],
        }), encoding="utf-8")
        _, goal, _ = self.check.validate_goal_artifact(self.card)
        with self.assertRaisesRegex(self.check.ValidationError, "policy state changed"):
            self.check.enforce_ui_gate(self.card, goal)

    def test_stale_ui_gate_blocks_finish_after_sidecar_change(self):
        self._verify_all_outcomes()
        self._write_sidecar()
        self.check.ui_gate(self.card, self.trace_path, bind=True)
        sidecar = json.loads(self.sidecar_path.read_text(encoding="utf-8"))
        sidecar["scenarios"][0]["journey"]["expected"] = ["different result"]
        self.sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        with self.assertRaises(self.check.ValidationError) as ctx:
            self.check.finish_goal(self.card)
        self.assertIn("stale", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
