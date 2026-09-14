import json
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
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            db = tmp / "opencode.db"
            make_db(db, GOOD_SESSIONS, GOOD_PARTS)
            self.trace = export_trace(Path("D:/proj"), str(db), None)
        (tmp2 := Path(tempfile.mkdtemp()))  # keep dispatch load helper exercised
        self.addCleanup(lambda: None)
        self.dispatch = json.loads(json.dumps(GOOD_DISPATCH))

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
        self.assertEqual(self.routing["schema_version"], 1)
        ids = [s["stage_id"] for s in self.routing["stages"]]
        self.assertEqual(len(ids), len(set(ids)), "stage ids must be unique")
        for expected in (
            "brief-final",
            "goal-validation",
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
        self.trace = {
            "schema": "runtime-trace/1",
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
