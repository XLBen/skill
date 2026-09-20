import contextlib
import io
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from runtime_trace import (  # noqa: E402
    TRACE_SCHEMA,
    export_trace,
    load_dispatch,
    load_trace,
    validate_chain,
)


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


def skill_part(pid, session, name, status="completed"):
    return {
        "id": pid,
        "session_id": session,
        "data": {
            "type": "tool",
            "tool": "skill",
            "state": {"status": status, "input": {"name": name}, "output": "<skill_content>"},
            "metadata": {"name": name, "dir": "D:/proj"},
        },
    }


def task_part(pid, controller, subagent, child=None, status="completed"):
    out = f'<task id="{child}" state="completed"><task_result>ok</task_result></task>' if child else "no id"
    return {
        "id": pid,
        "session_id": controller,
        "data": {
            "type": "tool",
            "tool": "task",
            "state": {"status": status, "input": {"subagent_type": subagent, "prompt": "x"}, "output": out},
        },
    }


GOOD_SESSIONS = [
    {"id": "ses_ctrl", "parent_id": None, "agent": None},
    {"id": "ses_worker", "parent_id": "ses_ctrl", "agent": "mvp-worker"},
    {"id": "ses_rev", "parent_id": "ses_ctrl", "agent": "mvp-reviewer"},
]
GOOD_PARTS = [
    task_part("p1", "ses_ctrl", "mvp-worker", child="ses_worker"),
    skill_part("p2", "ses_worker", "task-worker"),
    task_part("p3", "ses_ctrl", "mvp-reviewer", child="ses_rev"),
    skill_part("p4", "ses_rev", "reviewer"),
    skill_part("p5", "ses_rev", "pua"),
]
GOOD_DISPATCH = {
    "schema_version": 2,
    "goal_id": "G-X",
    "tasks": [
        {
            "task_id": "T-01",
            "role": "worker",
            "status": "done",
            "provenance": {"session_id": "ses_worker", "agent": "mvp-worker"},
            "acceptance": {"verdict": "satisfied", "pending_actions": []},
        },
        {
            "task_id": "T-02",
            "role": "reviewer",
            "status": "done",
            "review_scope": "goal",
            "provenance": {"session_id": "ses_rev", "agent": "mvp-reviewer"},
            "acceptance": {"verdict": "satisfied", "pending_actions": []},
        },
    ],
}


class ExportTests(unittest.TestCase):
    def test_export_normalizes_sessions_skills_and_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            db = tmp / "opencode.db"
            make_db(db, GOOD_SESSIONS, GOOD_PARTS)
            trace = export_trace(Path("D:/proj"), str(db), None)
            self.assertEqual(trace["schema"], TRACE_SCHEMA)
            self.assertEqual(len(trace["sessions"]), 3)
            by_id = {s["id"]: s for s in trace["sessions"]}
            self.assertEqual(by_id["ses_worker"]["parent_id"], "ses_ctrl")
            self.assertEqual(len(trace["skill_events"]), 3)
            self.assertEqual(len(trace["task_events"]), 2)
            task = next(t for t in trace["task_events"] if t["child_session"] == "ses_rev")
            self.assertEqual(task["child_agent"], "mvp-reviewer")
            self.assertEqual(task["status"], "completed")

    def test_export_filters_by_directory_and_includes_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            db = tmp / "opencode.db"
            sessions = GOOD_SESSIONS + [
                {"id": "ses_other", "parent_id": None, "directory": "D:/elsewhere", "agent": None}
            ]
            make_db(db, sessions, GOOD_PARTS)
            trace = export_trace(Path("D:/proj"), str(db), None)
            self.assertNotIn("ses_other", {s["id"] for s in trace["sessions"]})


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        db = self.tmp / "opencode.db"
        make_db(db, GOOD_SESSIONS, GOOD_PARTS)
        self.trace = export_trace(Path("D:/proj"), str(db), None)
        self.reviewer_result = self.tmp / "reviewer-result.json"
        self.reviewer_result.write_text(json.dumps({
            "mode": "review",
            "issues": [],
            "checked_scope": ["acceptance items"],
            "not_checked": [],
            "pua_acceptance": {"stage_id": "review-verdict", "result": "satisfied"},
        }), encoding="utf-8")
        self.dispatch = json.loads(json.dumps(GOOD_DISPATCH))
        self.dispatch["tasks"][1]["result_ref"] = str(self.reviewer_result)

    def test_good_chain_passes(self):
        self.assertEqual(validate_chain(self.trace, self.dispatch, None), [])

    def test_missing_child_session_fails(self):
        self.trace["sessions"] = [s for s in self.trace["sessions"] if s["id"] != "ses_rev"]
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("missing from trace" in f for f in failures), failures)

    def test_session_without_parent_fails(self):
        for s in self.trace["sessions"]:
            if s["id"] == "ses_rev":
                s["parent_id"] = None
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("no parent" in f for f in failures), failures)

    def test_failed_skill_load_fails(self):
        for ev in self.trace["skill_events"]:
            if ev["skill"] == "reviewer":
                ev["status"] = "error"
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("reviewer" in f and "no completed load" in f for f in failures), failures)

    def test_missing_pua_load_for_reviewer_fails(self):
        self.trace["skill_events"] = [e for e in self.trace["skill_events"] if e["skill"] != "pua"]
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("'pua' has no completed load" in f for f in failures), failures)

    def test_normal_reviewer_does_not_require_pua(self):
        self.trace["skill_events"] = [e for e in self.trace["skill_events"] if e["skill"] != "pua"]
        self.dispatch["tasks"][1]["review_scope"] = "task"
        failures = validate_chain(self.trace, self.dispatch, None, rigor="normal")
        self.assertFalse(any("'pua' has no completed load" in f for f in failures), failures)

    def test_declared_pua_stage_requires_matching_acceptance(self):
        payload = json.loads(self.reviewer_result.read_text(encoding="utf-8"))
        payload["pua_acceptance"] = {"stage_id": "goal-finish", "result": "satisfied"}
        self.reviewer_result.write_text(json.dumps(payload), encoding="utf-8")
        self.dispatch["tasks"][1]["pua_stage_id"] = "review-verdict"
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("does not match" in f for f in failures), failures)
        payload["pua_acceptance"] = {"stage_id": "review-verdict", "result": "satisfied"}
        self.reviewer_result.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(validate_chain(self.trace, self.dispatch, None), [])

    def test_declared_pua_stage_requires_pua_load(self):
        self.trace["skill_events"] = [e for e in self.trace["skill_events"] if e["skill"] != "pua"]
        self.dispatch["tasks"][1]["pua_stage_id"] = "review-verdict"
        failures = validate_chain(self.trace, self.dispatch, None, rigor="normal")
        self.assertTrue(any("'pua' has no completed load" in f for f in failures), failures)

    def test_goal_rigor_blocks_downgrade_even_on_normal_slice(self):
        policy = {"schema": "runtime-policy/1", "allow_independence_downgrade": True}
        failures = validate_chain(
            self.trace, self.dispatch, policy, rigor="normal", goal_rigor="audited"
        )
        self.assertTrue(any("cannot apply to an audited goal" in f for f in failures), failures)

    def test_unresolved_controller_action_fails(self):
        self.dispatch["tasks"][0]["actions"] = [
            {"action_id": "A-T01-01", "kind": "engine-verify", "status": "requested", "evidence_ref": None}
        ]
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("A-T01-01" in f and "requested" in f for f in failures), failures)

    def test_completed_action_requires_evidence_ref(self):
        self.dispatch["tasks"][0]["actions"] = [
            {"action_id": "A-T01-01", "kind": "run-command", "status": "completed"}
        ]
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("lacks evidence_ref" in f for f in failures), failures)
        self.dispatch["tasks"][0]["actions"][0]["evidence_ref"] = "evidence/x.json"
        self.assertEqual(validate_chain(self.trace, self.dispatch, None), [])

    def test_duplicate_action_id_fails(self):
        action = {
            "action_id": "A-1", "kind": "run-command", "status": "completed",
            "evidence_ref": "e.json",
        }
        self.dispatch["tasks"][0]["actions"] = [action, dict(action)]
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("duplicate action_id" in f for f in failures), failures)

    def test_reviewer_invalid_envelope_status_fails(self):
        payload = json.loads(self.reviewer_result.read_text(encoding="utf-8"))
        payload["status"] = "banana"
        self.reviewer_result.write_text(json.dumps(payload), encoding="utf-8")
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("invalid envelope status" in f for f in failures), failures)

    def test_validate_cli_derives_slice_rigor_from_dispatch(self):
        from runtime_trace import main as trace_main

        self.trace["skill_events"] = [e for e in self.trace["skill_events"] if e["skill"] != "pua"]
        self.dispatch["tasks"][1]["review_scope"] = "task"
        self.dispatch["active_slice"] = {"rigor": "normal"}
        trace_path = self.tmp / "cli-normal-trace.json"
        trace_path.write_text(json.dumps(self.trace), encoding="utf-8")
        dispatch_path = self.tmp / "cli-normal-dispatch.json"
        dispatch_path.write_text(json.dumps(self.dispatch), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = trace_main(["validate", str(trace_path), "--dispatch", str(dispatch_path)])
        self.assertEqual(code, 0, output.getvalue())

    def test_reviewer_fallback_to_general_fails(self):
        for s in self.trace["sessions"]:
            if s["id"] == "ses_rev":
                s["agent"] = "general"
        self.dispatch["tasks"][1]["provenance"]["agent"] = "general"
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("fallback forbidden" in f for f in failures), failures)

    def test_undisclosed_worker_fallback_fails_and_disclosed_passes(self):
        for s in self.trace["sessions"]:
            if s["id"] == "ses_worker":
                s["agent"] = "general"
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("fallback to 'general' not disclosed" in f for f in failures), failures)
        self.dispatch["tasks"][0]["provenance"]["agent"] = "general-fallback-as-worker"
        next(
            ev for ev in self.trace["task_events"] if ev["child_session"] == "ses_worker"
        )["requested_agent"] = "general"
        self.assertEqual(validate_chain(self.trace, self.dispatch, None), [])

    def test_provenance_agent_mismatch_fails(self):
        self.dispatch["tasks"][0]["provenance"]["agent"] = "mvp-reviewer"
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("!= trace child agent" in f for f in failures), failures)

    def test_unresolved_owner_pending_actions_fail(self):
        self.dispatch["tasks"][1]["acceptance"] = {
            "verdict": "owner",
            "pending_actions": ["owner accepts slice"],
        }
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("unresolved owner pending actions" in f for f in failures), failures)

    def test_skip_reason_whitelist_enforced(self):
        self.dispatch["tasks"] = [
            {"task_id": "T-09", "role": "worker", "status": "skipped", "skip_reason": "felt unnecessary"}
        ]
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("skip_reason" in f for f in failures), failures)

    def test_independence_skip_blocked_without_policy(self):
        self.dispatch["tasks"] = [
            {"task_id": "T-10", "role": "reviewer", "status": "skipped", "skip_reason": "capability-unavailable"}
        ]
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("independence seat" in f for f in failures), failures)

    def test_reviewer_same_session_as_implementer_fails(self):
        # reviewer claimed same child session as worker
        self.dispatch["tasks"][1]["provenance"]["session_id"] = "ses_worker"
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("also an implementer session" in f for f in failures), failures)

    def test_policy_review_satisfied_goal_requires_goal_scope_verdict(self):
        policy = {
            "schema": "runtime-policy/1",
            "requirements": [{"kind": "review-satisfied-goal"}],
        }
        self.assertEqual(validate_chain(self.trace, self.dispatch, policy), [])
        self.dispatch["tasks"][1]["review_scope"] = "task"
        failures = validate_chain(self.trace, self.dispatch, policy)
        self.assertTrue(any("no satisfied goal-scope reviewer" in f for f in failures), failures)

    def test_policy_unknown_requirement_fails(self):
        policy = {"schema": "runtime-policy/1", "requirements": [{"kind": "bogus"}]}
        failures = validate_chain(self.trace, self.dispatch, policy)
        self.assertTrue(any("unknown requirement kind" in f for f in failures), failures)

    def test_satisfied_verdict_on_non_done_task_fails(self):
        self.dispatch["tasks"][1]["status"] = "pending"
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("only valid on a done task" in f for f in failures), failures)

    def test_review_floor_requires_done_status(self):
        policy = {"schema": "runtime-policy/1", "requirements": [{"kind": "review-satisfied-goal"}]}
        self.dispatch["tasks"][1]["status"] = "pending"
        failures = validate_chain(self.trace, self.dispatch, policy)
        self.assertTrue(any("no satisfied goal-scope reviewer" in f for f in failures), failures)

    def test_validate_cli_rejects_unsupported_store(self):
        from runtime_trace import main as trace_main

        planted = self.tmp / "planted.db"
        make_db(planted, [{"id": "ses_other", "parent_id": None, "agent": None}], [])
        trace = json.loads(json.dumps(self.trace))
        trace["source"] = {"kind": "opencode-sqlite", "path": str(planted)}
        trace_path = self.tmp / "cli-trace.json"
        trace_path.write_text(json.dumps(trace), encoding="utf-8")
        dispatch_path = self.tmp / "cli-dispatch.json"
        dispatch_path.write_text(json.dumps(self.dispatch), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = trace_main(["validate", str(trace_path), "--dispatch", str(dispatch_path)])
        self.assertEqual(code, 1, output.getvalue())

    def test_verify_native_trace_accepts_matching_failed_records(self):
        from runtime_trace import verify_native_trace

        db = self.tmp / "mixed.db"
        failed_part = {
            "id": "m2",
            "session_id": "ses_ctrl",
            "data": {
                "type": "tool",
                "tool": "bash",
                "callID": "call_err",
                "state": {"status": "error", "input": {}, "output": "boom"},
            },
        }
        make_db(db, [{"id": "ses_ctrl", "parent_id": None, "agent": None}], [failed_part])
        trace = export_trace(Path("D:/proj"), str(db), None)
        self.assertEqual(verify_native_trace(trace), [])

    def test_verify_native_trace_accepts_retry_after_failed_skill_load(self):
        from runtime_trace import verify_native_trace

        db = self.tmp / "retry.db"
        make_db(
            db,
            [{"id": "ses_ctrl", "parent_id": None, "agent": None}],
            [
                skill_part("r1", "ses_ctrl", "computer-use", status="error"),
                skill_part("r2", "ses_ctrl", "computer-use", status="completed"),
            ],
        )
        trace = export_trace(Path("D:/proj"), str(db), None)
        statuses = [ev["status"] for ev in trace["skill_events"] if ev["skill"] == "computer-use"]
        self.assertEqual(sorted(statuses), ["completed", "error"])
        self.assertEqual(verify_native_trace(trace), [])

    def test_verify_native_trace_accepts_retry_after_failed_tool_call(self):
        from runtime_trace import verify_native_trace

        def bash_call(pid, status):
            return {
                "id": pid,
                "session_id": "ses_ctrl",
                "data": {
                    "type": "tool",
                    "tool": "bash",
                    "callID": "call_retry",
                    "state": {"status": status, "input": {}, "output": "x"},
                },
            }

        db = self.tmp / "tool-retry.db"
        make_db(
            db,
            [{"id": "ses_ctrl", "parent_id": None, "agent": None}],
            [bash_call("t1", "error"), bash_call("t2", "completed")],
        )
        trace = export_trace(Path("D:/proj"), str(db), None)
        statuses = [ev["status"] for ev in trace["tool_events"] if ev["call_id"] == "call_retry"]
        self.assertIn("completed", statuses)
        self.assertIn("error", statuses)
        self.assertEqual(verify_native_trace(trace), [])

    def test_non_native_trace_cannot_pass(self):
        self.trace.pop("source", None)
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("native provenance" in f for f in failures), failures)

    def test_truncated_trace_cannot_pass(self):
        self.trace["truncated"] = True
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("truncated" in f for f in failures), failures)

    def test_satisfied_reviewer_requires_result_ref(self):
        self.dispatch["tasks"][1].pop("result_ref")
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("result_ref" in f for f in failures), failures)

    def test_reviewer_issues_override_satisfied_claim(self):
        payload = json.loads(self.reviewer_result.read_text(encoding="utf-8"))
        payload["issues"] = [{"issue_id": "ISSUE-1", "severity": "high"}]
        self.reviewer_result.write_text(json.dumps(payload), encoding="utf-8")
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("issue(s)" in f for f in failures), failures)

    def test_pua_repair_overrides_satisfied_claim(self):
        payload = json.loads(self.reviewer_result.read_text(encoding="utf-8"))
        payload["pua_acceptance"]["result"] = "repair"
        self.reviewer_result.write_text(json.dumps(payload), encoding="utf-8")
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("pua_acceptance" in f for f in failures), failures)

    def test_unlinked_child_session_fails(self):
        self.trace["task_events"] = [
            ev for ev in self.trace["task_events"] if ev["child_session"] != "ses_rev"
        ]
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("no matching task dispatch event" in f for f in failures), failures)

    def test_unknown_status_and_duplicate_ids_fail(self):
        self.dispatch["tasks"].append(dict(self.dispatch["tasks"][0]))
        self.dispatch["tasks"][1]["status"] = "weird"
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("duplicate task_id" in f for f in failures), failures)
        self.assertTrue(any("invalid status" in f for f in failures), failures)

    def test_failed_task_is_not_reusable(self):
        self.dispatch["tasks"][0]["status"] = "failed"
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("failed dispatch" in f for f in failures), failures)

    def test_agent_name_substring_is_not_disclosure(self):
        self.dispatch["tasks"][1]["provenance"]["agent"] = "mvp-reviewer-extra"
        failures = validate_chain(self.trace, self.dispatch, None)
        self.assertTrue(any("!= trace child agent" in f for f in failures), failures)

    def test_load_trace_rejects_wrong_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "t.json"
            p.write_text(json.dumps({"schema": "nope", "sessions": [], "skill_events": [], "task_events": []}))
            from runtime_trace import TraceValidationError

            with self.assertRaises(TraceValidationError):
                load_trace(p)

    def test_load_dispatch_rejects_unknown_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "d.json"
            p.write_text(json.dumps({"schema_version": 9, "tasks": []}))
            from runtime_trace import TraceValidationError

            with self.assertRaises(TraceValidationError):
                load_dispatch(p)


class StageRoutingContractTests(unittest.TestCase):
    def setUp(self):
        self.routing = json.loads(
            (ROOT / "mvp-delivery/references/stage-routing.json").read_text(encoding="utf-8")
        )

    def test_schema_and_stage_ids(self):
        self.assertEqual(self.routing["schema_version"], 3)
        ids = [s["stage_id"] for s in self.routing["stages"]]
        self.assertEqual(len(ids), len(set(ids)), "stage ids must be unique")
        for expected in (
            "brief-final",
            "goal-validation",
            "goal-verification",
            "slice-implementation",
            "review-verdict",
            "contract-release",
            "plan-confirmation",
            "test-freeze",
            "step-verification",
            "slice-acceptance",
            "goal-finish",
        ):
            self.assertIn(expected, ids)

    def test_every_stage_has_entry_and_required_skills(self):
        for stage in self.routing["stages"]:
            with self.subTest(stage=stage["stage_id"]):
                self.assertTrue(stage.get("entry"))
                self.assertTrue(stage.get("required_skills"))
                for skill in stage["required_skills"]:
                    self.assertIn("name", skill)
                    self.assertIn("seat", skill)

    def test_reviewer_stages_declare_mode(self):
        for stage in self.routing["stages"]:
            rv = stage.get("reviewer") or {}
            if rv.get("dispatch") not in (None, "none-for-this-stage"):
                self.assertIn("mode", rv, f"{stage['stage_id']} reviewer must declare mode")

    def test_dispatch_levels_reference_known_values(self):
        levels = self.routing["dispatch_levels"]
        self.assertIn("capability-available-mandatory", levels)
        self.assertIn("blocking", levels)

    def test_reviewer_conditions_are_consistent_with_entry_rigors(self):
        for stage in self.routing["stages"]:
            condition = stage["reviewer"]["condition"]
            optional = condition.get("optional_rigors") or []
            for rigor in (condition["rigors"] or []) + optional:
                self.assertIn(rigor, stage.get("rigors", []), stage["stage_id"])
            if not condition["dispatch"]:
                self.assertEqual(condition["rigors"], [], stage["stage_id"])
                self.assertEqual(optional, [], stage["stage_id"])

    def test_pua_entries_carry_explicit_roles(self):
        for stage in self.routing["stages"]:
            for entry in stage["required_skills"]:
                if entry["name"] == "pua":
                    self.assertTrue(entry.get("roles"), stage["stage_id"])


class RuntimeGateEngineTests(unittest.TestCase):
    """check.py runtime-gate + finish-goal integration on a real card."""

    def setUp(self):
        from scripts import check

        self.check = check
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(self._cleanup)
        self.root = self.tmp / "proj"
        (self.root / ".opencode" / "mvp" / "evidence").mkdir(parents=True)
        self.card = self.root / ".opencode" / "mvp" / "g-fixture.md"
        self.card.write_text((ROOT / "tests/fixtures/goal-valid.md").read_text(encoding="utf-8"))
        self.trace_path = self.root / ".opencode" / "mvp" / "trace.json"
        self.dispatch_path = self.root / ".opencode" / "mvp" / "g-fixture.dispatch.json"
        session_db = self.root / "session-store.db"
        make_db(
            session_db,
            [
                {"id": "ses_ctrl", "parent_id": None, "agent": None},
                {"id": "ses_worker", "parent_id": "ses_ctrl", "agent": "mvp-worker"},
                {"id": "ses_rev", "parent_id": "ses_ctrl", "agent": "mvp-reviewer"},
            ],
            [
                skill_part("rg1", "ses_worker", "task-worker"),
                skill_part("rg2", "ses_rev", "reviewer"),
                skill_part("rg3", "ses_rev", "pua"),
                task_part("rg4", "ses_ctrl", "mvp-worker", child="ses_worker"),
                task_part("rg5", "ses_ctrl", "mvp-reviewer", child="ses_rev"),
            ],
        )
        reviewer_result = self.root / "dispatch-archive" / "T-02-reviewer.json"
        reviewer_result.parent.mkdir(parents=True)
        reviewer_result.write_text(json.dumps({
            "mode": "review",
            "issues": [],
            "checked_scope": ["goal finish acceptance"],
            "not_checked": [],
            "pua_acceptance": {"stage_id": "goal-finish", "result": "satisfied"},
        }), encoding="utf-8")
        self.trace = {
            "schema": "runtime-trace/1",
            "source": {"kind": "opencode-sqlite", "path": str(session_db)},
            "sessions": [
                {"id": "ses_ctrl", "parent_id": None, "agent": "(primary)"},
                {"id": "ses_worker", "parent_id": "ses_ctrl", "agent": "mvp-worker"},
                {"id": "ses_rev", "parent_id": "ses_ctrl", "agent": "mvp-reviewer"},
            ],
            "skill_events": [
                {"session_id": "ses_worker", "skill": "task-worker", "status": "completed"},
                {"session_id": "ses_rev", "skill": "reviewer", "status": "completed"},
                {"session_id": "ses_rev", "skill": "pua", "status": "completed"},
            ],
            "task_events": [
                {"controller_session": "ses_ctrl", "requested_agent": "mvp-worker",
                 "status": "completed", "child_session": "ses_worker", "child_agent": "mvp-worker"},
                {"controller_session": "ses_ctrl", "requested_agent": "mvp-reviewer",
                 "status": "completed", "child_session": "ses_rev", "child_agent": "mvp-reviewer"},
            ],
        }
        self.trace_path.write_text(json.dumps(self.trace), encoding="utf-8")
        self.dispatch = {
            "schema_version": 2,
            "goal_id": "G-FIXTURE",
            "tasks": [
                {"task_id": "T-01", "role": "worker", "status": "done",
                 "provenance": {"session_id": "ses_worker", "agent": "mvp-worker"},
                 "acceptance": {"verdict": "satisfied", "pending_actions": []}},
                {"task_id": "T-02", "role": "reviewer", "status": "done", "review_scope": "goal",
                 "provenance": {"session_id": "ses_rev", "agent": "mvp-reviewer"},
                 "result_ref": str(reviewer_result),
                 "acceptance": {"verdict": "satisfied", "pending_actions": []}},
            ],
        }
        self.dispatch_path.write_text(json.dumps(self.dispatch), encoding="utf-8")

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def _verify_all_outcomes(self):
        evidence = self.root / ".opencode" / "mvp" / "evidence" / "g-fixture-O-01-01.json"
        self.check.verify_goal_outcome(self.card, "O-01", evidence)
        return evidence

    def _write_policy(self):
        policy = self.root / ".opencode" / "mvp" / "runtime-policy.json"
        policy.write_text(
            json.dumps({"schema": "runtime-policy/1", "goals": "all"}), encoding="utf-8"
        )
        return policy

    def test_finish_goal_without_policy_keeps_legacy_behavior(self):
        self._verify_all_outcomes()
        goal = self.check.finish_goal(self.card)
        self.assertEqual(goal["status"], "complete")

    def test_runtime_gate_pass_writes_sidecar_and_allows_finish(self):
        self._verify_all_outcomes()
        self._write_policy()
        sidecar, gate_path = self.check.runtime_gate(self.card, self.trace_path)
        self.assertEqual(sidecar["verdict"], "pass")
        self.assertTrue(gate_path.exists())
        goal = self.check.finish_goal(self.card)
        self.assertEqual(goal["status"], "complete")

    def test_policy_without_gate_blocks_finish(self):
        self._verify_all_outcomes()
        self._write_policy()
        with self.assertRaises(self.check.ValidationError) as ctx:
            self.check.finish_goal(self.card)
        self.assertIn("runtime-gate", str(ctx.exception))

    def test_failed_gate_blocks_finish(self):
        self._verify_all_outcomes()
        self._write_policy()
        # break the chain: reviewer seat ran as built-in general
        self.trace["sessions"] = [
            s if s["id"] != "ses_rev" else {**s, "agent": "general"} for s in self.trace["sessions"]
        ]
        self.dispatch["tasks"][1]["provenance"]["agent"] = "general"
        self.trace_path.write_text(json.dumps(self.trace), encoding="utf-8")
        self.dispatch_path.write_text(json.dumps(self.dispatch), encoding="utf-8")
        sidecar, _ = self.check.runtime_gate(self.card, self.trace_path)
        self.assertEqual(sidecar["verdict"], "fail")
        with self.assertRaises(self.check.ValidationError):
            self.check.finish_goal(self.card)

    def test_stale_gate_blocks_finish_after_dispatch_changes(self):
        self._verify_all_outcomes()
        self._write_policy()
        self.check.runtime_gate(self.card, self.trace_path)
        self.dispatch["tasks"].append({"task_id": "T-03", "role": "research", "status": "done"})
        self.dispatch_path.write_text(json.dumps(self.dispatch), encoding="utf-8")
        with self.assertRaises(self.check.ValidationError) as ctx:
            self.check.finish_goal(self.card)
        self.assertIn("stale", str(ctx.exception))

    def test_empty_policy_requirements_cannot_remove_defaults(self):
        self._verify_all_outcomes()
        policy = self.root / ".opencode" / "mvp" / "runtime-policy.json"
        policy.write_text(
            json.dumps({"schema": "runtime-policy/1", "goals": "all", "requirements": []}),
            encoding="utf-8",
        )
        self.dispatch["tasks"] = []
        self.dispatch_path.write_text(json.dumps(self.dispatch), encoding="utf-8")
        sidecar, _ = self.check.runtime_gate(self.card, self.trace_path)
        self.assertEqual(sidecar["verdict"], "fail")
        self.assertTrue(any("reviewer" in f for f in sidecar["failures"]), sidecar["failures"])

    def test_policy_change_after_gate_blocks_finish(self):
        self._verify_all_outcomes()
        policy = self._write_policy()
        sidecar, _ = self.check.runtime_gate(self.card, self.trace_path)
        self.assertEqual(sidecar["verdict"], "pass")
        policy.write_text(
            json.dumps({"schema": "runtime-policy/1", "goals": "all",
                        "requirements": [{"kind": "independence"}]}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(self.check.ValidationError, "policy state changed"):
            self.check.finish_goal(self.card)

    def test_goal_definition_change_after_gate_blocks_finish(self):
        self._verify_all_outcomes()
        self._write_policy()
        sidecar, _ = self.check.runtime_gate(self.card, self.trace_path)
        self.assertEqual(sidecar["verdict"], "pass")
        _, goal = self.check.read_artifact(self.card, "goal")
        goal["demo"] = "changed after the gate"
        self.card.write_text(self.check.render_goal(goal), encoding="utf-8")
        with self.assertRaises(self.check.ValidationError):
            self.check.finish_goal(self.card)  # the evidence binding already blocks
        with self.assertRaisesRegex(self.check.ValidationError, "goal definition changed"):
            self.check.enforce_runtime_gate(self.card, goal)

    def test_hand_written_trace_fails_gate(self):
        self._verify_all_outcomes()
        self._write_policy()
        self.trace.pop("source", None)
        self.trace_path.write_text(json.dumps(self.trace), encoding="utf-8")
        sidecar, _ = self.check.runtime_gate(self.card, self.trace_path)
        self.assertEqual(sidecar["verdict"], "fail")
        self.assertTrue(any("native provenance" in f for f in sidecar["failures"]), sidecar["failures"])

    def test_trace_content_must_exist_in_the_source_store(self):
        self._verify_all_outcomes()
        empty_db = self.root / "empty-store.db"
        make_db(empty_db, [{"id": "ses_other", "parent_id": None, "agent": None}], [])
        self.trace["source"]["path"] = str(empty_db)
        self.trace_path.write_text(json.dumps(self.trace), encoding="utf-8")
        sidecar, _ = self.check.runtime_gate(self.card, self.trace_path)
        self.assertEqual(sidecar["verdict"], "fail")
        self.assertTrue(
            any("not present in the source store" in f for f in sidecar["failures"]),
            sidecar["failures"],
        )

    def test_store_record_must_be_completed(self):
        self._verify_all_outcomes()
        failed_db = self.root / "failed-store.db"
        make_db(
            failed_db,
            [
                {"id": "ses_ctrl", "parent_id": None, "agent": None},
                {"id": "ses_worker", "parent_id": "ses_ctrl", "agent": "mvp-worker"},
                {"id": "ses_rev", "parent_id": "ses_ctrl", "agent": "mvp-reviewer"},
            ],
            [
                skill_part("fg1", "ses_worker", "task-worker"),
                skill_part("fg2", "ses_rev", "reviewer", status="error"),
                skill_part("fg3", "ses_rev", "pua"),
                task_part("fg4", "ses_ctrl", "mvp-worker", child="ses_worker"),
                task_part("fg5", "ses_ctrl", "mvp-reviewer", child="ses_rev"),
            ],
        )
        self.trace["source"]["path"] = str(failed_db)
        self.trace_path.write_text(json.dumps(self.trace), encoding="utf-8")
        sidecar, _ = self.check.runtime_gate(self.card, self.trace_path)
        self.assertEqual(sidecar["verdict"], "fail")
        self.assertTrue(
            any("no completed record" in f for f in sidecar["failures"]),
            sidecar["failures"],
        )

    def test_custom_policy_path_gate_is_enforceable(self):
        custom_policy = self.root / "custom-policy.json"
        custom_policy.write_text(
            json.dumps({"schema": "runtime-policy/1", "goals": ["G-FIXTURE"]}),
            encoding="utf-8",
        )
        self._verify_all_outcomes()
        sidecar, _ = self.check.runtime_gate(self.card, self.trace_path, policy_path=str(custom_policy))
        self.assertEqual(sidecar["verdict"], "pass", sidecar["failures"])
        goal = self.check.finish_goal(self.card)
        self.assertEqual(goal["status"], "complete")

    def test_default_policy_created_after_custom_gate_blocks_finish(self):
        custom_policy = self.root / "custom-policy.json"
        custom_policy.write_text(
            json.dumps({"schema": "runtime-policy/1", "goals": ["G-FIXTURE"]}),
            encoding="utf-8",
        )
        self._verify_all_outcomes()
        sidecar, _ = self.check.runtime_gate(self.card, self.trace_path, policy_path=str(custom_policy))
        self.assertEqual(sidecar["verdict"], "pass", sidecar["failures"])
        self._write_policy()
        with self.assertRaisesRegex(self.check.ValidationError, "default runtime policy now gates"):
            self.check.finish_goal(self.card)

    def test_policy_deletion_after_gate_blocks_finish(self):
        self._verify_all_outcomes()
        policy = self._write_policy()
        sidecar, _ = self.check.runtime_gate(self.card, self.trace_path)
        self.assertEqual(sidecar["verdict"], "pass", sidecar["failures"])
        policy.unlink()
        with self.assertRaisesRegex(self.check.ValidationError, "policy not found"):
            self.check.finish_goal(self.card)

    def test_policy_rescope_after_gate_blocks_finish(self):
        self._verify_all_outcomes()
        policy = self._write_policy()
        sidecar, _ = self.check.runtime_gate(self.card, self.trace_path)
        self.assertEqual(sidecar["verdict"], "pass", sidecar["failures"])
        policy.write_text(
            json.dumps({"schema": "runtime-policy/1", "goals": ["G-OTHER"], "requirements": []}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(self.check.ValidationError, "policy state changed"):
            self.check.finish_goal(self.card)

    def test_policy_created_after_gate_blocks_finish(self):
        self._verify_all_outcomes()
        sidecar, _ = self.check.runtime_gate(self.card, self.trace_path)
        self.assertEqual(sidecar["verdict"], "pass", sidecar["failures"])
        self._write_policy()
        with self.assertRaisesRegex(self.check.ValidationError, "policy state changed"):
            self.check.finish_goal(self.card)

    def test_malformed_policy_is_an_error_not_a_pass(self):
        self._verify_all_outcomes()
        policy = self._write_policy()
        policy.write_text(json.dumps({"schema": "bogus"}), encoding="utf-8")
        with self.assertRaises(self.check.ValidationError):
            self.check.finish_goal(self.card)

    def test_runtime_gate_requires_trace_and_dispatch(self):
        with self.assertRaises(self.check.ValidationError):
            self.check.runtime_gate(self.card, self.root / "missing.json")


if __name__ == "__main__":
    unittest.main()
