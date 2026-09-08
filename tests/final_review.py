"""Regression tests invoked by check.py --selftest."""
import copy
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


def run(check):
    class FinalReviewTests(unittest.TestCase):
        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.addCleanup(self.temp.cleanup)
            self.root = Path(self.temp.name)
            self.plan_path = self.root / "PLAN.md"
            self.contract_path = self.root / "contract.md"
            self.ledger = self.root / "events.jsonl"
            _, self.contract = check.read_artifact(check.FIXTURES / "contract-valid.md", "contract")
            self.contract["workflow_protocol"] = "v0.2"
            self.contract["nodes"]["V"][0]["assertion"] = {"type": "stdout-contains", "literal": "compiler fixture PASS"}
            human = copy.deepcopy(self.contract["nodes"]["V"][0])
            human.update(id="V-02", type="human", observation="Inspect the rendered result")
            human.pop("command")
            self.contract["nodes"]["V"].append(human)
            unit = copy.deepcopy(self.contract["nodes"]["I"][0])
            unit.update(id="I-02", kind="validation", realizes=[], validates=["V-02"])
            unit["variants"][0]["segments"][0]["segment_verifications"] = ["V-02"]
            self.contract["nodes"]["I"].append(unit)
            self.assertEqual(check.validate_contract(self.contract), [])
            self.plan = check.compile_plan(self.contract)
            self.plan_path.write_text(check.render_plan(self.plan, "test"), encoding="utf-8")
            mocked = patch.object(check, "read_checked_contract", return_value=({}, self.contract))
            mocked.start()
            self.addCleanup(mocked.stop)
            self.bindings = {key: self.plan[key] for key in ("contract_hash", "plan_structure_hash")}
            check.append_immutable_event(self.ledger, dict(
                self.bindings, id="OWNER-PLAN", type="owner-decision",
                decision="plan-confirmation", result="accepted"))
            selection = self.root / "selection.json"
            selection.write_text(json.dumps(dict(
                id="CONFIRM", authorization="owner-confirmed", owner_event="OWNER-PLAN",
                selections={unit: {"variant": "base", "selector_evidence": "default"}
                            for unit in ("I-01", "I-02")})), encoding="utf-8")
            check.confirm_plan(self.plan_path, selection, self.contract_path, self.ledger)

        def transition(self, step, state, **extra):
            _, plan = check.read_artifact(self.plan_path, "plan")
            revision = plan["runtime"]["revision"]
            event = dict(self.bindings, id=f"TRANSITION-{revision}", type="step-transition",
                         step_id=step["id"], step_hash=check.step_hash(step), to_state=state,
                         expected_revision=revision, **extra)
            path = self.root / "transition.json"
            path.write_text(json.dumps(event), encoding="utf-8")
            check.apply_plan_event(self.plan_path, path, self.contract_path, self.ledger)

        def verifying(self, index):
            step = self.plan["steps"][index]
            for state in ("selected", "executing", "verifying"):
                self.transition(step, state)
            return step

        def test_human_completion_and_bindings(self):
            step = self.verifying(1)
            args = ["check.py", "record-human-step", str(self.plan_path), step["id"], "V-02",
                    "--contract", str(self.contract_path), "--ledger", str(self.ledger),
                    "--owner-event", "OWNER-HUMAN", "--event-id", "HUMAN-PROOF"]
            self.assertEqual(check.main(args), 2)
            owner = dict(self.bindings, id="OWNER-HUMAN", type="owner-decision",
                         decision="human-verification", result="accepted", step_id=step["id"],
                         step_hash=check.step_hash(step), v_id="V-02", observation="Result inspected")
            path = self.root / "owner.json"
            path.write_text(json.dumps(owner), encoding="utf-8")
            check.record_evidence_event(self.ledger, path)
            self.assertEqual(check.main(args), 0)
            self.assertEqual(check.main(args), 0)
            with self.assertRaises(check.ValidationError):
                check.verify_step(self.plan_path, step["id"], "V-02", self.contract_path,
                                  self.ledger, self.root / "evidence" / "human.json", "COMMAND")
            attempt = dict(self.bindings, id="ATTEMPT", type="attempt", step_id=step["id"],
                           step_hash=check.step_hash(step), result="passed", subagent_id="local-claim",
                           verification_events=["HUMAN-PROOF"])
            check.append_immutable_event(self.ledger, attempt)
            self.transition(step, "complete", attempt_id="ATTEMPT")
            self.assertEqual(check.main(args), 0)
            _, plan = check.read_artifact(self.plan_path, "plan")
            events = check.load_ledger(self.ledger)
            self.assertEqual(check.validate_plan(plan, self.contract, events), [])
            for field in ("contract_hash", "plan_structure_hash", "step_hash", "step_id", "v_id",
                          "decision", "result", "observation"):
                altered = copy.deepcopy(events)
                next(item for item in altered if item["id"] == "OWNER-HUMAN")[field] = ""
                self.assertTrue(check.validate_plan(plan, self.contract, altered), field)
            altered = copy.deepcopy(events)
            proof = next(item for item in altered if item["id"] == "HUMAN-PROOF")
            proof["producer"] = "check.py/verify-step-v1"
            self.assertTrue(check.validate_plan(plan, self.contract, altered))

        def test_human_requires_verifying_selected_step(self):
            step = self.plan["steps"][1]
            owner = dict(self.bindings, id="OWNER", type="owner-decision",
                         decision="human-verification", result="accepted", step_id=step["id"],
                         step_hash=check.step_hash(step), v_id="V-02", observation="Inspected")
            check.append_immutable_event(self.ledger, owner)
            for state in (None, "selected", "executing"):
                if state:
                    self.transition(step, state)
                with self.assertRaises(check.ValidationError):
                    check.verify_step(self.plan_path, step["id"], "V-02", self.contract_path,
                                      self.ledger, None, "PROOF", owner_event="OWNER")
            self.assertFalse(any(item["id"] == "PROOF" for item in check.load_ledger(self.ledger)))

        def test_orphan_recovery(self):
            step = self.verifying(0)
            for mode in ("passed", "nonzero", "assertion", "timeout"):
                event_id = f"ORPHAN-{mode}"
                evidence = self.root / "evidence" / f"{event_id}.json"
                args = (self.plan_path, step["id"], "V-01", self.contract_path,
                        self.ledger, evidence, event_id)
                # Simulate a crash after evidence publication but before ledger append.
                with patch.object(check, "append_immutable_event", side_effect=OSError("crash")):
                    with self.assertRaises(OSError):
                        check.verify_step(*args)
                payload = json.loads(evidence.read_bytes())
                if mode == "nonzero":
                    payload.update(exit_code=7, result="failed")
                elif mode == "assertion":
                    payload.update(stdout="wrong", assertion_passed=False, result="failed")
                elif mode == "timeout":
                    payload.update(exit_code=None, timed_out=True, result="failed")
                evidence.write_text(json.dumps(payload), encoding="utf-8")
                original = evidence.read_bytes()
                with patch.object(check.subprocess, "Popen", side_effect=AssertionError("reran command")):
                    for field in ("event_id", "contract_hash", "plan_structure_hash", "step_hash",
                                  "step_id", "v_id", "command", "cwd", "timeout_seconds",
                                  "assertion", "assertion_passed", "result", "exit_code",
                                  "timed_out", "stdout", "stderr", "started_at", "elapsed_seconds"):
                        altered = dict(payload, **{field: "invalid" if payload.get(field) is None else None})
                        evidence.write_text(json.dumps(altered), encoding="utf-8")
                        with self.assertRaises(check.ValidationError, msg=field):
                            check.verify_step(*args)
                    evidence.write_bytes(original)
                    event = check.verify_step(*args)
                    self.assertEqual(event["result"], "passed" if mode == "passed" else "failed")
                    self.assertEqual(check.verify_step(*args), event)
                    self.assertEqual(evidence.read_bytes(), original)

        def test_compile_preserves_existing_plan(self):
            args = ["check.py", "compile", str(self.contract_path), str(self.plan_path),
                    "--change-orders", str(self.root / "changes.json"),
                    "--ledger", str(self.ledger)]
            with patch.object(check, "enforce_cr_gate", return_value=None):
                for status in ("confirmed", "complete"):
                    _, plan = check.read_artifact(self.plan_path, "plan")
                    plan["runtime"]["status"] = status
                    self.plan_path.write_text(check.render_plan(plan, "test"), encoding="utf-8")
                    original = self.plan_path.read_bytes()
                    self.assertEqual(check.main(args), 2)
                    self.assertEqual(self.plan_path.read_bytes(), original)
                self.plan_path.unlink()
                self.assertEqual(check.main(args), 0)
                _, compiled = check.read_artifact(self.plan_path, "plan")
                self.assertEqual(compiled, check.compile_plan(self.contract))

        def test_temporary_evidence_blocks_execution(self):
            evidence = self.root / "blocked.json"
            temporary = evidence.with_suffix(".json.tmp")
            temporary.write_bytes(b"interrupted evidence")
            with patch.object(check.subprocess, "Popen") as launch:
                with self.assertRaisesRegex(check.ValidationError, "temporary evidence file already exists"):
                    check.run_command_evidence("command", self.root, evidence, {}, 1)
                launch.assert_not_called()
            self.assertEqual(temporary.read_bytes(), b"interrupted evidence")
            self.assertFalse(evidence.exists())

        def test_evidence_reserved_before_execution(self):
            evidence = self.root / "reserved.json"
            temporary = evidence.with_suffix(".json.tmp")

            def launch(*args, **kwargs):
                self.assertTrue(temporary.exists())
                raise OSError("launch interrupted")

            with patch.object(check.subprocess, "Popen", side_effect=launch):
                with self.assertRaisesRegex(OSError, "launch interrupted"):
                    check.run_command_evidence("command", self.root, evidence, {}, 1)
            self.assertTrue(temporary.exists())
            self.assertFalse(evidence.exists())

        def test_timeout_kills_descendant(self):
            marker = self.root / "survived"
            child = self.root / "child.py"
            child.write_text("import time\nfrom pathlib import Path\ntime.sleep(3)\n"
                             f"Path({str(marker)!r}).touch()\n", encoding="utf-8")
            parent = self.root / "parent.py"
            parent.write_text("import subprocess, sys, time\n"
                              f"subprocess.Popen([sys.executable, {str(child)!r}])\n"
                              "print('before timeout', flush=True)\ntime.sleep(30)\n", encoding="utf-8")
            command = f'"{sys.executable}" "{parent}"'
            started = time.monotonic()
            payload, _ = check.run_command_evidence(command, self.root, self.root / "timeout.json", {}, 1)
            self.assertLess(time.monotonic() - started, 12)
            self.assertTrue(payload["timed_out"])
            self.assertEqual(payload["result"], "failed")
            self.assertIn("before timeout", payload["stdout"])
            time.sleep(3)
            self.assertFalse(marker.exists(), "descendant survived timeout")

        def test_timeout_cleanup_is_bounded(self):
            from subprocess import TimeoutExpired
            from unittest.mock import MagicMock
            process = MagicMock()
            process.communicate.side_effect = [
                TimeoutExpired("command", 1, output=b"partial", stderr=b"error"),
                TimeoutExpired("command", 5, output=b"partial tail", stderr=b"error"),
            ]
            with patch.object(check.subprocess, "Popen", return_value=process), \
                    patch.object(check.subprocess, "run", side_effect=TimeoutExpired("taskkill", 5)), \
                    patch.object(check.os, "killpg", create=True, side_effect=ProcessLookupError):
                payload, _ = check.run_command_evidence(
                    "command", self.root, self.root / "bounded.json", {}, 1)
            self.assertEqual([call.kwargs["timeout"] for call in process.communicate.call_args_list], [1, 5])
            self.assertEqual(payload["result"], "failed")
            self.assertEqual(payload["stdout"], "partial tail")
            self.assertEqual(payload["stderr"], "error")

    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(FinalReviewTests))
    return 0 if result.wasSuccessful() else 1
