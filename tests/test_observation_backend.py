"""S15: observation backend planning and batched journey execution.

Covers the preflight skip plan, backend selection, argv construction for
agent-browser / playwright-cli, and the stop-on-first-problem batch runner.
Every runner is a fake; no browser, subprocess or product is started here.
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import observation_backend as ob  # noqa: E402

CONTEXT = {
    "host_id": "host-1",
    "provider_id": "openai",
    "model_id": "gpt-5.6-luna",
    "candidate_id": "cand-1",
    "session_id": "sess-1",
}


def make_preflight(
    host_status="passed",
    model_status="passed",
    candidate_status="passed",
    session_status="passed",
    host_extra=None,
    model_extra=None,
):
    host = {"status": host_status, "host_id": "host-1"}
    model = {
        "status": model_status,
        "provider_id": "openai",
        "model_id": "gpt-5.6-luna",
    }
    if host_extra:
        host.update(host_extra)
    if model_extra:
        model.update(model_extra)
    return {
        "schema": "observation-preflight/1",
        "performed_at": "2026-09-21T00:00:00Z",
        "performed_by": "controller",
        "covers": {
            "host": host,
            "model": model,
            "candidate": {"status": candidate_status, "candidate_id": "cand-1"},
            "session": {"status": session_status, "session_id": "sess-1"},
        },
    }


class FakeClock:
    def __init__(self, values):
        self.values = list(values)
        self.calls = 0

    def __call__(self):
        index = min(self.calls, len(self.values) - 1)
        self.calls += 1
        return self.values[index]


def ok_result(marker=b"out"):
    return {
        "exit_code": 0,
        "timed_out": False,
        "stdout_bytes": marker,
        "stderr_bytes": b"",
    }


class ScriptedRunner:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, argv, timeout):
        self.calls.append((list(argv), timeout))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def step(step_id, evidence=None, timeout=None, argv=None):
    return {
        "id": step_id,
        "argv": argv if argv is not None else ["tool", step_id],
        "evidence": evidence,
        "timeout": timeout,
    }


class PreflightSkipPlanTests(unittest.TestCase):
    def test_none_preflight_blocks_every_item(self):
        plan = ob.preflight_skip_plan(None, CONTEXT)
        self.assertEqual(set(plan), {"host", "model", "candidate", "session"})
        for item in ("host", "model", "candidate", "session"):
            self.assertFalse(plan[item]["skip"])
            self.assertEqual(plan[item]["reason"], "no preflight")

    def test_non_dict_preflight_blocks_every_item(self):
        for bad in ([], "passed", 42):
            plan = ob.preflight_skip_plan(bad, CONTEXT)
            self.assertTrue(all(not entry["skip"] for entry in plan.values()))

    def test_passed_matching_covers_skip(self):
        plan = ob.preflight_skip_plan(make_preflight(), CONTEXT)
        for item in ("host", "model", "candidate", "session"):
            self.assertTrue(plan[item]["skip"])
            self.assertIn("matches context", plan[item]["reason"])

    def test_failed_status_blocks_only_that_item(self):
        preflight = make_preflight(model_status="failed")
        plan = ob.preflight_skip_plan(preflight, CONTEXT)
        self.assertFalse(plan["model"]["skip"])
        self.assertIn("not passed", plan["model"]["reason"])
        self.assertTrue(plan["host"]["skip"])
        self.assertTrue(plan["session"]["skip"])

    def test_model_mismatch_blocks_model_only(self):
        context = dict(CONTEXT, model_id="gpt-other")
        plan = ob.preflight_skip_plan(make_preflight(), context)
        self.assertFalse(plan["model"]["skip"])
        self.assertIn("model_id", plan["model"]["reason"])
        self.assertTrue(plan["host"]["skip"])
        self.assertTrue(plan["candidate"]["skip"])

    def test_context_none_blocks_every_item(self):
        plan = ob.preflight_skip_plan(make_preflight(), None)
        for item in ("host", "model", "candidate", "session"):
            self.assertFalse(plan[item]["skip"])
            self.assertIn("context", plan[item]["reason"])

    def test_missing_context_field_blocks_that_item(self):
        context = {key: value for key, value in CONTEXT.items() if key != "session_id"}
        plan = ob.preflight_skip_plan(make_preflight(), context)
        self.assertFalse(plan["session"]["skip"])
        self.assertIn("session_id", plan["session"]["reason"])
        self.assertTrue(plan["candidate"]["skip"])

    def test_covers_not_object_fails_closed(self):
        for bad in ({"covers": "x"}, {"covers": []}, {}):
            plan = ob.preflight_skip_plan(bad, CONTEXT)
            self.assertTrue(all(not entry["skip"] for entry in plan.values()))

    def test_host_cover_without_host_id_matches_provider_model(self):
        preflight = make_preflight()
        preflight["covers"]["host"] = {
            "status": "passed",
            "provider_id": "openai",
            "model_id": "gpt-5.6-luna",
        }
        plan = ob.preflight_skip_plan(preflight, CONTEXT)
        self.assertTrue(plan["host"]["skip"])

    def test_cover_without_comparable_fields_fails_closed(self):
        preflight = make_preflight()
        preflight["covers"]["session"] = {"status": "passed"}
        plan = ob.preflight_skip_plan(preflight, CONTEXT)
        self.assertFalse(plan["session"]["skip"])
        self.assertIn("no comparable identity fields", plan["session"]["reason"])


class ChooseBackendTests(unittest.TestCase):
    def test_preferred_verified_by_passed_host(self):
        preflight = make_preflight(host_extra={"backend": "playwright-cli"})
        picked = ob.choose_backend(preflight, preferred="playwright-cli")
        self.assertEqual(picked["backend"], "playwright-cli")
        self.assertTrue(picked["verified"])

    def test_preferred_with_passed_host_without_backend_hint(self):
        picked = ob.choose_backend(make_preflight(), preferred="playwright-cli")
        self.assertEqual(picked["backend"], "playwright-cli")
        self.assertTrue(picked["verified"])

    def test_invalid_preferred_returns_none(self):
        picked = ob.choose_backend(make_preflight(), preferred="selenium")
        self.assertIsNone(picked["backend"])
        self.assertIn("unsupported preferred backend", picked["reason"])

    def test_host_unavailable_returns_none(self):
        preflight = make_preflight(host_status="unavailable")
        for preferred in (None, "agent-browser", "playwright-cli"):
            picked = ob.choose_backend(preflight, preferred=preferred)
            self.assertIsNone(picked["backend"])
            self.assertIn("unavailable", picked["reason"])

    def test_backend_hint_mismatch_returns_none(self):
        preflight = make_preflight(host_extra={"backend": "agent-browser"})
        picked = ob.choose_backend(preflight, preferred="playwright-cli")
        self.assertIsNone(picked["backend"])
        self.assertIn("does not match", picked["reason"])

    def test_no_preflight_defaults_unverified_agent_browser(self):
        for preflight in (None, {}, {"covers": {}}):
            picked = ob.choose_backend(preflight)
            self.assertEqual(picked["backend"], "agent-browser")
            self.assertFalse(picked["verified"])
            self.assertEqual(picked["reason"], "default, unverified preflight")

    def test_valid_preferred_without_passed_host_defaults(self):
        preflight = make_preflight(host_status="failed")
        picked = ob.choose_backend(preflight, preferred="playwright-cli")
        self.assertEqual(picked["backend"], "agent-browser")
        self.assertFalse(picked["verified"])

    def test_passed_host_hint_is_adopted_without_preference(self):
        preflight = make_preflight(host_extra={"backend": "playwright-cli"})
        picked = ob.choose_backend(preflight)
        self.assertEqual(picked["backend"], "playwright-cli")
        self.assertTrue(picked["verified"])


class AgentBrowserArgvTests(unittest.TestCase):
    def test_open_builds_session_prefixed_argv(self):
        argv = ob.agent_browser_argv("s1", "open", url="http://127.0.0.1:8000")
        self.assertEqual(
            argv,
            ["agent-browser", "--session", "s1", "open", "http://127.0.0.1:8000"],
        )

    def test_type_keeps_text_as_one_element(self):
        argv = ob.agent_browser_argv("s1", "type", target="@e1", text="a b & c")
        self.assertEqual(argv[-1], "a b & c")
        self.assertIn("@e1", argv)
        self.assertEqual(len(argv), 6)

    def test_snapshot_filename_inside_evidence_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence"
            evidence.mkdir()
            filename = evidence / "snap.png"
            argv = ob.agent_browser_argv(
                "s1", "snapshot", filename=str(filename), evidence_dir=str(evidence)
            )
            self.assertEqual(argv[-2:], ["--filename", str(filename)])
            self.assertNotIn(str(evidence), argv[:-1])

    def test_screenshot_requires_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                ob.agent_browser_argv("s1", "screenshot", evidence_dir=tmp)

    def test_screenshot_inside_evidence_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence"
            evidence.mkdir()
            filename = evidence / "shot.png"
            argv = ob.agent_browser_argv(
                "s1", "screenshot", filename=str(filename), evidence_dir=str(evidence)
            )
            self.assertEqual(
                argv,
                [
                    "agent-browser",
                    "--session",
                    "s1",
                    "screenshot",
                    "--filename",
                    str(filename),
                ],
            )

    def test_screenshot_escape_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence"
            evidence.mkdir()
            outside = Path(tmp) / "outside.png"
            with self.assertRaises(ValueError):
                ob.agent_browser_argv(
                    "s1", "screenshot", filename=str(outside), evidence_dir=str(evidence)
                )

    def test_screenshot_traversal_escape_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence"
            evidence.mkdir()
            sneaky = evidence / ".." / "outside.png"
            with self.assertRaises(ValueError):
                ob.agent_browser_argv(
                    "s1", "screenshot", filename=str(sneaky), evidence_dir=str(evidence)
                )

    def test_filename_requires_evidence_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            filename = Path(tmp) / "shot.png"
            with self.assertRaises(ValueError):
                ob.agent_browser_argv("s1", "screenshot", filename=str(filename))

    def test_evidence_dir_requires_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                ob.agent_browser_argv("s1", "snapshot", evidence_dir=tmp)

    def test_non_string_params_raise(self):
        for kwargs in (
            {"url": 42},
            {"url": None},
            {"click": 1},
        ):
            action = "open" if "url" in kwargs else "click"
            with self.assertRaises(ValueError):
                ob.agent_browser_argv("s1", action, **kwargs)

    def test_empty_values_raise(self):
        for kwargs in (
            {"url": ""},
            {"url": "   "},
            {"text": ""},
        ):
            action = "open" if "url" in kwargs else "type"
            if action == "type":
                kwargs = {"target": "@e1", **kwargs}
            with self.assertRaises(ValueError):
                ob.agent_browser_argv("s1", action, **kwargs)

    def test_session_id_must_be_non_empty_string(self):
        for bad in (None, "", "  ", 7):
            with self.assertRaises(ValueError):
                ob.agent_browser_argv(bad, "close")

    def test_unsupported_action_raises(self):
        with self.assertRaises(ValueError):
            ob.agent_browser_argv("s1", "record", start="x")

    def test_unknown_parameter_raises(self):
        with self.assertRaises(ValueError):
            ob.agent_browser_argv("s1", "close", extra=1)

    def test_wait_requires_exactly_one_mode(self):
        argv = ob.agent_browser_argv("s1", "wait", text="Ready")
        self.assertEqual(argv[-2:], ["--text", "Ready"])
        with self.assertRaises(ValueError):
            ob.agent_browser_argv("s1", "wait")
        with self.assertRaises(ValueError):
            ob.agent_browser_argv("s1", "wait", text="a", url="b")

    def test_console_and_errors_actions(self):
        self.assertEqual(
            ob.agent_browser_argv("s1", "console"),
            ["agent-browser", "--session", "s1", "console"],
        )
        self.assertEqual(
            ob.agent_browser_argv("s1", "errors"),
            ["agent-browser", "--session", "s1", "errors"],
        )


class PlaywrightCliArgvTests(unittest.TestCase):
    def test_playwright_base_prefix(self):
        argv = ob.playwright_cli_argv("s2", "click", target="@e1")
        self.assertEqual(argv, ["playwright-cli", "-s=s2", "click", "@e1"])

    def test_playwright_screenshot_is_restricted(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence"
            evidence.mkdir()
            inside = evidence / "shot.png"
            argv = ob.playwright_cli_argv(
                "s2", "screenshot", filename=str(inside), evidence_dir=str(evidence)
            )
            self.assertEqual(argv[-2:], ["--filename", str(inside)])
            outside = Path(tmp) / "outside.png"
            with self.assertRaises(ValueError):
                ob.playwright_cli_argv(
                    "s2", "screenshot", filename=str(outside), evidence_dir=str(evidence)
                )

    def test_playwright_has_no_errors_action(self):
        with self.assertRaises(ValueError):
            ob.playwright_cli_argv("s2", "errors")


class RunStepSequenceTests(unittest.TestCase):
    def test_all_success_reports_completed_and_first_action(self):
        runner = ScriptedRunner([ok_result(b"one"), ok_result(b"two"), ok_result()])
        steps = [
            step("s1", evidence="evidence/one.png"),
            step("s2", evidence="evidence/two.png"),
            step("s3"),
        ]
        result = ob.run_step_sequence(steps, runner)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["completed"], 3)
        self.assertIsNone(result["failed_step"])
        self.assertEqual(result["remaining"], [])
        self.assertEqual(len(result["steps"]), 3)
        self.assertIsNotNone(result["first_action_at"])
        self.assertEqual(
            result["evidence_refs"], ["evidence/one.png", "evidence/two.png"]
        )
        self.assertEqual(result["steps"][0]["result"]["stdout_bytes"], b"one")
        self.assertEqual(result["steps"][0]["argv"], ["tool", "s1"])

    def test_failure_stops_and_preserves_remaining(self):
        failure = {"exit_code": 3, "timed_out": False, "stdout_bytes": b"bad"}
        runner = ScriptedRunner([ok_result(), ok_result(), failure, ok_result()])
        steps = [
            step("s1", evidence="evidence/s1.txt"),
            step("s2", evidence="evidence/s2.txt"),
            step("s3", evidence="evidence/s3.txt"),
            step("s4", evidence="evidence/s4.txt"),
        ]
        result = ob.run_step_sequence(steps, runner)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["completed"], 2)
        self.assertEqual(result["failed_step"], "s3")
        self.assertEqual(result["remaining"], ["s4"])
        self.assertEqual([record["id"] for record in result["steps"]], ["s1", "s2", "s3"])
        self.assertEqual(len(runner.calls), 3)
        self.assertIn("evidence/s3.txt", result["evidence_refs"])

    def test_timeout_counts_as_failure(self):
        timeout = {"exit_code": None, "timed_out": True}
        runner = ScriptedRunner([timeout])
        result = ob.run_step_sequence([step("s1"), step("s2")], runner)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failed_step"], "s1")
        self.assertEqual(result["remaining"], ["s2"])

    def test_runner_error_key_counts_as_failure(self):
        runner = ScriptedRunner(
            [{"exit_code": None, "timed_out": False, "error": "spawn failed"}]
        )
        result = ob.run_step_sequence([step("s1")], runner)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failed_step"], "s1")
        self.assertEqual(result["steps"][0]["result"]["error"], "spawn failed")

    def test_runner_exception_is_captured_not_raised(self):
        runner = ScriptedRunner([RuntimeError("kaboom")])
        result = ob.run_step_sequence([step("s1"), step("s2")], runner)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failed_step"], "s1")
        self.assertEqual(result["remaining"], ["s2"])
        self.assertIn("RuntimeError: kaboom", result["steps"][0]["result"]["error"])

    def test_non_dict_runner_result_keeps_raw_value(self):
        runner = ScriptedRunner([b"raw-bytes"])
        result = ob.run_step_sequence([step("s1")], runner)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["steps"][0]["result"]["value"], b"raw-bytes")

    def test_budget_exhausted_with_fake_clock(self):
        clock = FakeClock([0.0, 0.5, 1.0, 2.0, 9.0])
        runner = ScriptedRunner([ok_result(), ok_result()])
        steps = [step("s1"), step("s2"), step("s3"), step("s4")]
        result = ob.run_step_sequence(
            steps, runner, deadline_seconds=1.5, clock=clock
        )
        self.assertEqual(result["status"], "budget-exhausted")
        self.assertEqual(result["completed"], 2)
        self.assertIsNone(result["failed_step"])
        self.assertEqual(result["remaining"], ["s3", "s4"])
        self.assertEqual(result["first_action_at"], 0.5)
        self.assertEqual(result["elapsed_seconds"], 9.0)
        self.assertEqual(len(runner.calls), 2)

    def test_budget_exhausted_before_first_step(self):
        clock = FakeClock([3.0, 4.0, 5.0])
        runner = ScriptedRunner([ok_result()])
        result = ob.run_step_sequence(
            [step("s1"), step("s2")], runner, deadline_seconds=0, clock=clock
        )
        self.assertEqual(result["status"], "budget-exhausted")
        self.assertEqual(result["completed"], 0)
        self.assertIsNone(result["first_action_at"])
        self.assertEqual(result["remaining"], ["s1", "s2"])
        self.assertEqual(runner.calls, [])

    def test_runner_receives_argv_and_timeout(self):
        runner = ScriptedRunner([ok_result()])
        steps = [step("s1", timeout=7.5, argv=["product", "--flag", "a b"])]
        ob.run_step_sequence(steps, runner)
        self.assertEqual(runner.calls[0], (["product", "--flag", "a b"], 7.5))

    def test_default_clock_runs_without_deadline(self):
        runner = ScriptedRunner([ok_result()])
        result = ob.run_step_sequence([step("s1")], runner)
        self.assertEqual(result["status"], "completed")
        self.assertGreaterEqual(result["elapsed_seconds"], 0.0)

    def test_malformed_steps_raise(self):
        runner = ScriptedRunner([])
        for bad in (
            None,
            "steps",
            [None],
            [{"argv": ["x"]}],
            [{"id": "s1", "argv": []}],
            [{"id": "s1", "argv": ["x", 2]}],
            [{"id": "s1", "argv": ["x"], "evidence": ""}],
            [{"id": "s1", "argv": ["x"], "timeout": 0}],
        ):
            with self.assertRaises(ValueError):
                ob.run_step_sequence(bad, runner)

    def test_runner_must_be_callable(self):
        with self.assertRaises(ValueError):
            ob.run_step_sequence([step("s1")], "runner")


if __name__ == "__main__":
    unittest.main()
