"""Behavioral regression tests for planning and incremental real-boundary gates.

The journey starts an actual Python CLI and reads an actual input file. Its
negative control disconnects that input. No fake subprocess/driver is used.
This is a CLI calibration, not a desktop/game certification.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import check


ROOT = Path(__file__).resolve().parents[1]
APP = '''import pathlib, sys
try:
    value = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "input.txt").read_text().strip()
except FileNotFoundError:
    print("input boundary unavailable")
    sys.exit(3)
print("VALUE:" + value)
'''


class EngineeringDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.card = self.root / ".opencode/mvp/demo.md"
        self.card.parent.mkdir(parents=True)
        self.design = self.root / "docs/plans/demo.md"
        self.design.parent.mkdir(parents=True)
        self.observation = self.card.parent / "observation-input.json"
        _, self.goal = check.read_artifact(ROOT / "tests/fixtures/goal-valid.md", "goal")
        self.goal.update(schema_version=3, source={"type": "direct", "raw_request": "Read the real input through the CLI"},
                         product_observation={"required": True},
                         ui={"required": False, "reason": "CLI only; no graphical journey", "outcome_ids": []})
        command = f'"{sys.executable}" app.py'
        verification = {"command": command, "expected": "VALUE:42", "assertion_kind": "content",
                        "empty_result_policy": "fail", "assertion": {"type": "stdout-contains", "literal": "VALUE:42"}}
        self.goal["outcomes"] = [{"id": "O-01", "statement": "Read the actual file through app.py", "status": "pending",
                                  "user_entry": True, "verification": verification}]
        self.plan = {
            "schema": "engineering-plan/1", "goal_id": self.goal["id"],
            "architecture": "A CLI calls the file adapter, then renders the retrieved value.",
            "data_flow": "input.txt -> read_value() -> CLI stdout; missing input -> nonzero exit",
            "components": [{"id": "C-01", "responsibility": "Read and display a value", "files": ["app.py"],
                            "interfaces": ["read_value(path: Path) -> str; FileNotFoundError on absent input"]}],
            "boundaries": [{"id": "B-01", "kind": "filesystem", "external": True,
                            "target": "input.txt on this host", "driver": "pathlib via delivered app.py",
                            "probe": {"command": f'"{sys.executable}" -c "from pathlib import Path; print(Path(\'input.txt\').read_text().strip())"',
                                      "assertion": {"type": "stdout-contains", "literal": "42"}}}],
            "journeys": [{"id": "J-01", "outcome_ids": ["O-01"], "boundary_ids": ["B-01"],
                          "entry": "python app.py", "preconditions": "input.txt contains 42",
                          "actions": ["Launch delivered CLI", "Read stdout"],
                          "expected": "Actual input value is displayed", "verification": verification,
                          "negative_control": {"command": command + " absent-input.txt", "expected_exit_code": 3,
                                               "assertion": {"type": "stdout-contains", "literal": "input boundary unavailable"},
                                               "reason": "Same CLI with its input boundary disconnected must fail"}}],
            "steps": [{"id": "S-01", "depends_on": [], "component_ids": ["C-01"], "journey_ids": ["J-01"],
                       "context": "Connect the public CLI to actual file input", "files": ["app.py"],
                       "change": "def read_value(path: Path) -> str: return path.read_text().strip()",
                       "bounds": ["Missing input fails", "Empty input is not success"], "rollback": "Remove app.py"}],
        }
        (self.root / "input.txt").write_text("42", encoding="utf-8")
        self.save()

    def save(self):
        self.design.write_text("# Engineering design\n\n```json engineering-plan\n" + json.dumps(self.plan) + "\n```\n", encoding="utf-8")
        self.goal["engineering_plan"] = {"path": "docs/plans/demo.md", "sha256": hashlib.sha256(self.design.read_bytes()).hexdigest()}
        self.card.write_text(check.render_goal(self.goal), encoding="utf-8")

    def cli(self, command, *args, expected=0):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/check.py"), command, str(self.card), *args],
                                cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def begin(self, step="S-01", expected=0):
        return self.cli("begin-cycle", step, expected=expected)

    def verify(self, expected=0):
        return self.cli("verify-cycle", expected=expected)

    def observe(self, decision="advance", expected=0):
        self.observation.write_text(json.dumps({"actual": "CLI output and disconnected-input exit inspected",
                                                "interpretation": "Readback matches expected value; boundary failure is detected",
                                                "decision": decision, "next_action": "Next dependency-ready step"}), encoding="utf-8")
        return self.cli("observe-cycle", str(self.observation), expected=expected)

    def install_app(self, source=APP):
        (self.root / "app.py").write_text(source, encoding="utf-8")

    def test_schema3_requires_an_engineering_plan_and_explicit_ui_decision(self):
        for key in ("engineering_plan", "ui"):
            broken = copy.deepcopy(self.goal)
            del broken[key]
            self.assertTrue(any(key in error for error in check.validate_goal(broken)), key)

    def test_plan_rejects_missing_interfaces_unknown_references_and_dependency_cycle(self):
        for mutate in (
            lambda p: p["components"][0].pop("interfaces"),
            lambda p: p["steps"][0].update(component_ids=["C-UNKNOWN"]),
            lambda p: p["steps"][0].update(depends_on=["S-01"]),
            lambda p: p["journeys"][0].update(outcome_ids=[]),
            lambda p: p["steps"][0].update(change="TODO"),
        ):
            original = copy.deepcopy(self.plan)
            mutate(self.plan)
            self.save()
            self.cli("engineering-plan", expected=1)
            self.plan = original

    def test_ui_boundary_cannot_be_declared_cli_only(self):
        self.plan["boundaries"][0]["kind"] = "desktop"
        self.save()
        self.assertIn("UI", self.cli("engineering-plan", expected=1))

    def test_goal_verification_must_match_a_real_journey(self):
        self.goal["outcomes"][0]["verification"] = copy.deepcopy(self.goal["outcomes"][0]["verification"])
        self.goal["outcomes"][0]["verification"]["command"] = "echo PASS"
        self.save()
        self.assertIn("journey", self.cli("goal", expected=1))

    def test_plan_file_changes_invalidate_binding(self):
        self.design.write_text(self.design.read_text(encoding="utf-8") + "Changed design", encoding="utf-8")
        self.assertIn("sha256", self.cli("goal", expected=1))

    def test_missing_external_prerequisite_blocks_before_implementation(self):
        (self.root / "input.txt").unlink()
        self.begin(expected=1)
        self.assertFalse((self.root / "app.py").exists())
        self.verify(expected=2)

    def test_real_cli_round_requires_observation_before_advancing(self):
        self.begin()
        self.install_app()
        self.verify()
        self.assertIn("observation", self.cli("cycle-gate", expected=2))
        self.begin(expected=2)
        self.observe()
        self.cli("cycle-gate")

    def test_missing_product_is_a_real_failed_run_and_cannot_advance(self):
        self.begin()
        self.verify(expected=1)
        self.observe(expected=2)
        self.begin(expected=2)
        self.observe("retry")
        self.begin()
        self.install_app()
        self.verify()
        self.observe()
        self.cli("cycle-gate")

    def test_always_success_driver_is_caught_by_negative_control(self):
        self.begin()
        self.install_app('print("VALUE:42")\n')
        self.assertIn("failed", self.verify(expected=1))
        self.observe(expected=2)
        self.cli("cycle-gate", expected=2)

    def test_mutation_after_verification_cannot_be_observed_as_passed(self):
        self.begin()
        self.install_app()
        self.verify()
        self.install_app('print("VALUE:wrong")\n')
        self.observe(expected=2)

    def test_final_gate_rechecks_evidence_and_workspace(self):
        self.begin()
        self.install_app()
        self.verify()
        self.observe()
        self.cli("cycle-gate")
        self.install_app('print("VALUE:wrong")\n')
        self.cli("cycle-gate", expected=2)

    def test_next_step_cannot_start_before_dependency_is_observed(self):
        step = copy.deepcopy(self.plan["steps"][0])
        step.update(id="S-02", depends_on=["S-01"], context="Check compatibility after integration")
        self.plan["steps"].append(step)
        self.save()
        self.begin("S-02", expected=2)
        self.begin()
        self.install_app()
        self.verify()
        self.begin("S-02", expected=2)
        self.observe()
        self.begin("S-02")
        self.verify()
        self.observe()
        self.cli("cycle-gate")

    def test_verified_outcome_cannot_bypass_cycles_at_finish(self):
        self.install_app()
        self.cli("verify-goal", "O-01", "--evidence", ".opencode/mvp/evidence/final.json")
        self.assertIn("observed real verification", self.cli("finish-goal", expected=2))

    def test_cycle_gate_does_not_replace_independent_product_observation(self):
        self.begin()
        self.install_app()
        self.verify()
        self.observe()
        self.cli("verify-goal", "O-01", "--evidence", ".opencode/mvp/evidence/final.json")
        self.assertIn("observation", self.cli("finish-goal", expected=2))

    def test_tampered_receipt_is_rejected(self):
        self.begin()
        self.install_app()
        self.verify()
        self.observe()
        receipt = next(self.card.parent.glob("cycles/*/*/*/J-01-verification.json"))
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        payload["stdout"] = "VALUE:tampered"
        receipt.write_text(json.dumps(payload), encoding="utf-8")
        self.assertIn("sha256", self.cli("cycle-gate", expected=2))

    def test_retrying_upstream_invalidates_downstream(self):
        step = copy.deepcopy(self.plan["steps"][0])
        step.update(id="S-02", depends_on=["S-01"])
        self.plan["steps"].append(step)
        self.save()
        self.install_app()
        for sid in ("S-01", "S-02", "S-01"):
            self.begin(sid)
            self.verify()
            self.observe()
        self.assertIn("S-02", self.cli("cycle-gate", expected=2))

    def test_malformed_plan_does_not_crash_validator(self):
        for field in ("components", "boundaries", "steps", "journeys"):
            original = self.plan[field]
            for bad in (None, 42, {}, [None], [{"id": []}]):
                self.plan[field] = bad
                self.save()
                output = self.cli("engineering-plan", expected=1)
                self.assertNotIn("Traceback", output)
            self.plan[field] = original

    def test_installed_engine_runs_the_same_real_cycle(self):
        installed = subprocess.run([sys.executable, str(ROOT / "scripts/install.py"), str(self.root)],
                                   cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        engine = self.root / ".opencode/workflow/scripts/check.py"
        self.assertTrue(engine.with_name("engineering_delivery.py").is_file())
        for command, args in (("engineering-plan", []), ("begin-cycle", ["S-01"])):
            result = subprocess.run([sys.executable, str(engine), command, str(self.card), *args],
                                    cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.install_app()
        result = subprocess.run([sys.executable, str(engine), "verify-cycle", str(self.card)],
                                cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.observe()
        self.cli("cycle-gate")


class LayeredDeliveryTests(unittest.TestCase):
    save = EngineeringDeliveryTests.save
    cli = EngineeringDeliveryTests.cli
    begin = EngineeringDeliveryTests.begin
    verify = EngineeringDeliveryTests.verify
    observe = EngineeringDeliveryTests.observe
    install_app = EngineeringDeliveryTests.install_app

    def setUp(self):
        EngineeringDeliveryTests.setUp(self)
        self.plan.update(schema="engineering-plan/2", shared_context=["UTF-8; CLI must use the reader, no fixture fallback"],
                         decisions=[{"decision": "Use pathlib", "reason": "Read-only local file I/O needs no package", "evidence": "Python pathlib documentation"}],
                         contracts=[{"id": "K-01", "owner": "C-01", "signature": "read_value(path: Path) -> str",
                                     "definition": "def read_value(path: Path) -> str: ... # FileNotFoundError if absent"}])
        self.plan["components"] = [
            {"id": "C-01", "responsibility": "Read actual input", "files": ["reader.py"], "interfaces": ["K-01"]},
            {"id": "C-02", "responsibility": "CLI entry", "files": ["app.py"], "interfaces": ["main(argv) -> exit code"]},
        ]
        check_command = f'"{sys.executable}" -c "from pathlib import Path; from reader import read_value; assert read_value(Path(\'input.txt\')) == \'42\'; print(\'READER_OK\')"'

        def step(ident, dependencies, component, level):
            return {"id": ident, "depends_on": dependencies, "component_ids": [component], "journey_ids": [],
                    "context": "Deliver " + ident, "files": ["reader.py" if component == "C-01" else "app.py"],
                    "read_files": [], "consumes": [] if ident == "S-01" else ["K-01"],
                    "produces": ["K-01"] if ident == "S-01" else [],
                    "implementation": ["Use pathlib UTF-8 read", "Strip whitespace", "Propagate FileNotFoundError"],
                    "change": "def read_value(path: Path) -> str: return path.read_text(encoding='utf-8').strip()",
                    "bounds": ["Absent input raises FileNotFoundError"], "rollback": "Revert this step's files",
                    "failure_routes": {"implementation": "Repair local reader logic", "environment": "Restore disposable input", "design": "Return to plan if the input API differs"},
                    "checks": [{"id": "T-01", "level": level, "boundary_ids": ["B-01"] if level == "boundary" else [],
                                "command": check_command, "assertion": {"type": "stdout-contains", "literal": "READER_OK"}}],
                    "preflight_boundary_ids": ["B-01"] if level == "boundary" else []}
        self.plan["steps"] = [step("S-01", [], "C-01", "component"), step("S-02", ["S-01"], "C-01", "boundary"),
                              step("S-03", ["S-02"], "C-02", "component")]
        self.plan["steps"][2].update(checks=[], journey_ids=["J-01"], read_files=["reader.py"],
                                    implementation=["Import read_value from reader", "Catch absent input as exit 3", "Render VALUE:<readback>"],
                                    change="from reader import read_value\n# main uses K-01 and maps FileNotFoundError to exit 3")
        self.save()

    def reader(self):
        (self.root / "reader.py").write_text("def read_value(path):\n    return path.read_text(encoding='utf-8').strip()\n", encoding="utf-8")

    def complete_reader(self):
        self.begin("S-01")
        self.reader()
        self.verify()
        self.observe()

    def test_component_passes_without_the_unbuilt_cli_or_future_journey(self):
        self.complete_reader()
        self.assertFalse((self.root / "app.py").exists())
        packet = json.loads(self.cli("next-step"))
        self.assertEqual(packet["step"]["id"], "S-02")
        self.assertEqual([k["id"] for k in packet["contracts"]], ["K-01"])
        self.assertNotIn("journeys", packet)
        self.assertNotIn("S-03", json.dumps(packet["step"]))

    def test_interface_consumer_needs_a_dependency_on_its_producer(self):
        self.plan["steps"][1]["depends_on"] = []
        self.save()
        self.assertIn("producer", self.cli("engineering-plan", expected=1))

    def test_later_steps_must_be_fully_specified(self):
        self.plan["steps"][2].pop("implementation")
        self.save()
        self.assertIn("implementation", self.cli("engineering-plan", expected=1))

    def test_boundary_check_must_precede_the_integration_milestone(self):
        self.plan["steps"][2]["depends_on"] = ["S-01"]
        self.save()
        self.assertIn("boundary", self.cli("engineering-plan", expected=1))

    def test_one_real_boundary_then_milestone_no_forced_negative_on_component(self):
        self.complete_reader()
        self.begin("S-02")
        self.verify()
        self.observe()
        self.begin("S-03")
        self.install_app(APP.replace("import pathlib, sys", "import pathlib, sys\nfrom reader import read_value").replace(
            'pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "input.txt").read_text().strip()',
            'read_value(pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "input.txt"))'))
        result = json.loads(self.verify())
        self.assertIn("observed", result)
        self.cli("observe-cycle", "--decision", "advance", "--interpretation", "CLI uses real reader; absent file fails")
        self.cli("cycle-gate")
        self.assertEqual(json.loads(self.cli("next-step"))["action"], "final-acceptance")

    def test_design_failure_routes_back_to_planning_not_another_retry(self):
        self.begin()
        self.verify(expected=1)
        self.cli("observe-cycle", "--decision", "replan", "--interpretation", "Input requires an asynchronous API")
        packet = json.loads(self.cli("next-step"))
        self.assertEqual(packet["action"], "replan")
        self.assertIn("design", packet["step"]["failure_routes"])
        self.begin(expected=2)

    def test_prepare_plan_derives_ui_and_hash_at_any_relative_path(self):
        self.design = self.root / "design.md"
        self.save()
        # The publisher takes the path, not an agent-maintained hash or UI flag.
        self.goal.pop("engineering_plan")
        self.goal.pop("ui")
        self.card.write_text(check.render_goal(self.goal), encoding="utf-8")
        self.cli("prepare-plan", "design.md")
        _, goal = check.read_artifact(self.card, "goal")
        self.assertEqual(goal["engineering_plan"]["path"], "design.md")
        self.assertFalse(goal["ui"]["required"])
        self.cli("engineering-plan")

    def test_nested_bad_types_return_errors_not_tracebacks(self):
        for field in ("consumes", "checks", "read_files", "failure_routes"):
            saved = copy.deepcopy(self.plan["steps"][1])
            self.plan["steps"][1][field] = [None, {}]
            self.save()
            self.assertNotIn("Traceback", self.cli("engineering-plan", expected=1))
            self.plan["steps"][1] = saved

    def test_prepare_failure_does_not_replace_current_card(self):
        before = self.card.read_bytes()
        self.plan["contracts"][0]["owner"] = "C-MISSING"
        self.design.write_text("```json engineering-plan\n" + json.dumps(self.plan) + "\n```", encoding="utf-8")
        self.cli("prepare-plan", "docs/plans/demo.md", expected=2)
        self.assertEqual(self.card.read_bytes(), before)

    def test_prepare_is_idempotent_but_new_design_releases_replan(self):
        self.cli("prepare-plan", "docs/plans/demo.md")
        before = self.card.read_bytes()
        self.assertFalse(json.loads(self.cli("prepare-plan", "docs/plans/demo.md"))["changed"])
        self.assertEqual(self.card.read_bytes(), before)
        self.begin()
        self.cli("observe-cycle", "--decision", "replan", "--interpretation", "Input contract needs revision")
        self.begin(expected=2)
        self.plan["shared_context"].append("Reconfirmed text input on the current platform")
        self.design.write_text("```json engineering-plan\n" + json.dumps(self.plan) + "\n```", encoding="utf-8")
        self.assertTrue(json.loads(self.cli("prepare-plan", "docs/plans/demo.md"))["changed"])
        self.assertEqual(json.loads(self.cli("next-step"))["action"], "begin-cycle")

    def test_prepare_derives_desktop_obligation_without_user_flag(self):
        self.plan["boundaries"][0]["kind"] = "desktop"
        self.design.write_text("```json engineering-plan\n" + json.dumps(self.plan) + "\n```", encoding="utf-8")
        self.cli("prepare-plan", "docs/plans/demo.md")
        _, goal = check.read_artifact(self.card, "goal")
        self.assertTrue(goal["ui"]["required"])
        self.assertEqual(goal["ui"]["outcome_ids"], ["O-01"])

    def test_interrupted_verification_returns_blocked_not_implement(self):
        self.begin()
        folder = next(self.card.parent.glob("cycles/*/*/0001"))
        (folder / "T-01-component.json.tmp").write_text("", encoding="utf-8")
        self.assertEqual(json.loads(self.cli("next-step"))["action"], "blocked")

    def test_observation_auto_captures_outputs_not_agent_actual(self):
        self.begin()
        self.reader()
        self.verify()
        result = json.loads(self.cli("observe-cycle", "--decision", "advance", "--interpretation", "Component passed"))
        actual = json.loads(result["actual"])
        self.assertEqual(actual[0]["exit_code"], 0)
        self.assertIn("READER_OK", actual[0]["stdout"])

    def test_published_plan_has_a_readable_generated_view_of_every_task(self):
        result = json.loads(self.cli("prepare-plan", "docs/plans/demo.md"))
        view = Path(result["readable_plan"]).read_text(encoding="utf-8")
        self.assertIn("### S-01", view)
        self.assertIn("### S-03", view)
        self.assertIn("def read_value", view)
        self.assertIn("```text", view)
        self.assertIn("K-01", view)
        self.assertNotIn("```json engineering-plan", view)

    def test_prepare_preserves_unowned_readable_plan_file(self):
        view = self.design.with_name(self.design.stem + ".readable.md")
        view.write_text("My hand-written design", encoding="utf-8")
        original = self.card.read_bytes()
        self.cli("prepare-plan", "docs/plans/demo.md", expected=2)
        self.assertEqual(view.read_text(encoding="utf-8"), "My hand-written design")
        self.assertEqual(self.card.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
