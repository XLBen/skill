import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import product_observation as po  # noqa: E402

from scripts import check  # noqa: E402


def sha(payload) -> str:
    raw = payload if isinstance(payload, bytes) else json.dumps(payload, indent=2).encode()
    return hashlib.sha256(raw).hexdigest()


GOAL_V2 = {
    "schema_version": 2,
    "id": "G-OBS",
    "status": "active",
    "source": {"type": "direct", "raw_request": "Deliver the demo app."},
    "goal": "A user can use the demo app end to end",
    "rigor": "normal",
    "risk": {"factors": ["none"], "rationale": "Local disposable demonstration"},
    "first_slice": "CLI entry",
    "demo": "Run the app entry",
    "constraints": [],
    "deferred": [],
    "product_observation": {"required": True},
    "outcomes": [{
        "id": "O-01",
        "statement": "The app entry runs",
        "status": "pending",
        "user_entry": True,
        "verification": {
            "command": f'"{sys.executable}" -c "print(\'ok\')"',
            "expected": "The app runs",
            "assertion_kind": "user-visible",
            "empty_result_policy": "Empty stdout fails",
            "assertion": {"type": "stdout-contains", "literal": "ok"},
            "timeout_seconds": 30,
        },
    }],
}


def write_goal(goal_path: Path, goal: dict) -> None:
    body = (
        "---\nstatus: active\n---\n\n# Goal\n\n```json goal\n"
        + json.dumps(goal, indent=2, ensure_ascii=False)
        + "\n```\n"
    )
    goal_path.write_text(body, encoding="utf-8", newline="\n")


def finding(**overrides):
    item = {
        "id": "F-01",
        "surface_ids": ["S-01"],
        "severity": "high",
        "category": "functional",
        "confidence": "observed",
        "observed": "button does nothing",
        "expected_basis": "public docs promise the action",
        "reproduction": "journey J-01 replay",
        "evidence_refs": ["candidate.json"],
        "status": "confirmed",
    }
    item.update(overrides)
    return item


def base_report(phase: str, findings=None, unobserved=None, stop_reason="coverage-completed"):
    phase_findings = []
    for item in findings or []:
        entry = dict(item)
        if phase == "compare":
            entry.setdefault("difference_classification", "confirmed-defect")
        else:
            entry.pop("difference_classification", None)
        phase_findings.append(entry)
    return {
        "schema": po.REPORT_SCHEMA,
        "phase": phase,
        "stop_reason": stop_reason,
        "surfaces": [
            {"id": "S-01", "name": "main entry", "importance": "material", "modes": ["default"]},
            {"id": "S-02", "name": "settings page", "importance": "peripheral"},
        ],
        "journeys": [
            {
                "id": "J-01",
                "surface_ids": ["S-01"],
                "evidence_refs": ["candidate.json"],
                "outcome": "covered",
            }
        ],
        "findings": phase_findings,
        "unobserved": unobserved or [],
        "capability_gaps": [],
        "continuation": None,
        "evidence_refs": ["candidate.json"],
        "goal_id": "G-OBS",
        "candidate_id": "cand-1",
        "observer_session_id": "ses_observer",
        "model": "provider/model",
        "packet_hash": "0" * 64,
        "received_at": "2026-09-21T00:00:00Z",
        "attempt": 1,
    }


class ObservationProject(unittest.TestCase):
    def setUp(self):
        import shutil

        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = self.tmp / "proj"
        (self.root / ".opencode" / "mvp").mkdir(parents=True)
        self.goal_path = self.root / ".opencode" / "mvp" / "g-obs.md"
        write_goal(self.goal_path, GOAL_V2)
        self.app = self.root / "app.py"
        self.app.write_text("print('ok')\n", encoding="utf-8")
        self.cdir = self.root / ".opencode" / "mvp" / "observation" / "G-OBS" / "cand-1"
        (self.cdir / "evidence").mkdir(parents=True)
        self.sidecar_path = self.root / ".opencode" / "mvp" / "g-obs.product-audit.json"

    def _write_candidate(self):
        manifest = {
            "schema": po.CANDIDATE_SCHEMA,
            "candidate_id": "cand-1",
            "entry": "python app.py",
            "environment": "local windows",
            "backend": "agent-browser",
            "files": [{"path": "app.py", "sha256": sha(self.app.read_bytes())}],
            "test_data": [],
            "channels": [],
            "baseline": {"kind": "none", "refs": []},
        }
        (self.cdir / "candidate.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8", newline="\n"
        )
        return manifest

    def _write_phase(self, phase: str, report: dict) -> None:
        packet = {"schema": "workflow-observer-packet/1", "phase": phase, "stub": True}
        (self.cdir / f"{phase}.packet.json").write_text(
            json.dumps(packet, indent=2), encoding="utf-8", newline="\n"
        )
        report = dict(report)
        report["packet_hash"] = sha((self.cdir / f"{phase}.packet.json").read_bytes())
        result_path = self.cdir / f"{phase}.result.json"
        result_path.write_text(
            json.dumps(report, indent=2), encoding="utf-8", newline="\n"
        )
        return result_path

    def _write_review(self, discover_path: Path, compare_path: Path, verdict="sufficient"):
        review = {
            "schema": po.REVIEW_SCHEMA,
            "findings_validity": "sufficient",
            "coverage_adequacy": "sufficient",
            "verdict": verdict,
            "notes": "Both phase payloads were checked against the archived packet.",
            "related_finding_ids": [],
            "reviewer_session_id": "ses_reviewer",
            "discover_hash": sha(discover_path.read_bytes()),
            "compare_hash": sha(compare_path.read_bytes()),
        }
        (self.cdir / "review.result.json").write_text(
            json.dumps(review, indent=2), encoding="utf-8", newline="\n"
        )

    def _write_sidecar(self):
        rel = ".opencode/mvp/observation/G-OBS/cand-1"
        sidecar = {
            "schema": po.AUDIT_SIDECAR_SCHEMA,
            "goal_id": "G-OBS",
            "current_candidate": "cand-1",
            "rounds": [
                {
                    "candidate_id": "cand-1",
                    "discover_ref": f"{rel}/discover.result.json",
                    "compare_ref": f"{rel}/compare.result.json",
                    "review_ref": f"{rel}/review.result.json",
                }
            ],
        }
        self.sidecar_path.write_text(
            json.dumps(sidecar, indent=2), encoding="utf-8", newline="\n"
        )

    def _write_evidence(self):
        for name in ("round.txt", "j01.png", "f01.png"):
            (self.cdir / "evidence" / name).write_text(
                f"{name}\n", encoding="utf-8", newline="\n"
            )

    def _bind_evidence_files(self, report):
        report = json.loads(json.dumps(report))
        report["evidence_refs"] = ["evidence/round.txt"]
        for journey in report.get("journeys", []):
            if isinstance(journey, dict):
                journey["evidence_refs"] = ["evidence/j01.png"]
        for item in report.get("findings", []):
            if isinstance(item, dict):
                item["evidence_refs"] = ["evidence/f01.png"]
        return report

    def _full_valid_round(self, findings=None, unobserved=None, stop_reason="coverage-completed"):
        self._write_candidate()
        self._write_evidence()
        discover = self._bind_evidence_files(
            base_report("discover", findings, unobserved, stop_reason)
        )
        compare = self._bind_evidence_files(
            base_report("compare", findings, unobserved, stop_reason)
        )
        discover_path = self._write_phase("discover", discover)
        compare_path = self._write_phase("compare", compare)
        self._write_review(discover_path, compare_path)
        self._write_sidecar()

    def _collect(self, trace=None):
        _, goal = check.read_artifact(str(self.goal_path), "goal")
        return po.collect_observation_problems(goal, self.goal_path, trace=trace)

    def test_schema2_goal_validates(self):
        _, _, problems = check.validate_goal_artifact(self.goal_path)
        self.assertEqual(problems, [], problems)

    def test_full_valid_round_passes_and_writes_gate(self):
        self._full_valid_round()
        self.assertEqual(self._collect(), [])
        _, goal = check.read_artifact(str(self.goal_path), "goal")
        gate_path = po.write_gate_record(goal, self.goal_path, [])
        self.assertIsNotNone(gate_path)
        gate = json.loads((self.cdir / "gate.json").read_text(encoding="utf-8"))
        self.assertEqual(gate["verdict"], "passed")
        self.assertEqual(gate["schema"], po.GATE_SCHEMA)
        self.assertEqual(po.GATE_SCHEMA, "product-audit-gate/2")

    def test_missing_sidecar_fails(self):
        self._write_candidate()
        problems = self._collect()
        self.assertTrue(any("sidecar" in p for p in problems), problems)

    def test_candidate_file_change_invalidates(self):
        self._full_valid_round()
        self.app.write_text("print('changed')\n", encoding="utf-8")
        problems = self._collect()
        self.assertTrue(any("changed after binding" in p for p in problems), problems)

    def test_missing_compare_phase_fails(self):
        self._write_candidate()
        self._write_phase("discover", base_report("discover"))
        self._write_sidecar()
        problems = self._collect()
        self.assertTrue(any("compare result missing" in p for p in problems), problems)

    def test_unresolved_high_finding_blocks(self):
        self._full_valid_round(findings=[finding()])
        problems = self._collect()
        self.assertTrue(any("unresolved critical/high" in p for p in problems), problems)

    def test_owner_decision_critical_finding_blocks(self):
        self._full_valid_round(
            findings=[
                finding(
                    severity="critical",
                    status="owner-decision",
                    difference_classification="owner-decision",
                )
            ]
        )
        problems = self._collect()
        self.assertTrue(
            any(
                "unresolved critical/high" in p and "owner-decision" in p
                for p in problems
            ),
            problems,
        )

    def test_dismissed_high_not_blocking(self):
        self._full_valid_round(
            findings=[
                finding(
                    status="dismissed",
                    dismissal_reason="Known cosmetic drift already tracked by the owner.",
                    owner_decision_ref="decisions/D-09.md",
                )
            ]
        )
        self.assertEqual(self._collect(), [])

    def test_material_surface_unobserved_blocks(self):
        self._full_valid_round(
            unobserved=[{"surface_id": "S-01", "reason": "budget"}]
        )
        problems = self._collect()
        self.assertTrue(
            any("unobserved" in p and "S-01" in p for p in problems), problems
        )

    def test_budget_exhausted_stop_reason_blocks(self):
        self._full_valid_round(stop_reason="budget-exhausted")
        problems = self._collect()
        self.assertTrue(any("stop_reason" in p for p in problems), problems)

    def test_review_hash_mismatch_blocks(self):
        self._full_valid_round()
        review_path = self.cdir / "review.result.json"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review["discover_hash"] = "1" * 64
        review_path.write_text(json.dumps(review, indent=2), encoding="utf-8")
        problems = self._collect()
        self.assertTrue(any("discover_hash does not match" in p for p in problems), problems)

    def test_insufficient_review_verdict_blocks(self):
        self._full_valid_round(findings=[finding()])
        review_path = self.cdir / "review.result.json"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review["verdict"] = "needs-repair"
        review_path.write_text(json.dumps(review, indent=2), encoding="utf-8")
        problems = self._collect()
        self.assertTrue(any("only sufficient clears the gate" in p for p in problems), problems)

    def test_schema1_goal_short_circuits(self):
        legacy = dict(GOAL_V2)
        legacy["schema_version"] = 1
        legacy.pop("product_observation")
        write_goal(self.goal_path, legacy)
        self.assertEqual(self._collect(), [])

    def test_enforce_raises_for_required_goal_without_sidecar(self):
        _, goal = check.read_artifact(str(self.goal_path), "goal")
        with self.assertRaises(check.ValidationError):
            check.enforce_product_observation(self.goal_path, goal)

    def test_finish_goal_enforces_observation(self):
        self._write_candidate()
        evidence = (
            self.root / ".opencode" / "mvp" / "evidence" / "g-obs-O-01-01.json"
        )
        check.verify_goal_outcome(self.goal_path, "O-01", evidence)
        with self.assertRaises(check.ValidationError) as ctx:
            check.finish_goal(self.goal_path)
        self.assertIn("product observation", str(ctx.exception))

    def test_trace_provenance_missing_session_blocks(self):
        self._full_valid_round()
        trace = {
            "schema": "runtime-trace/1",
            "sessions": [{"id": "ses_other"}],
            "skill_events": [],
            "tool_events": [],
        }
        problems = self._collect(trace=trace)
        self.assertTrue(any("ses_observer" in p for p in problems), problems)

    def test_trace_provenance_with_skill_load_passes(self):
        self._full_valid_round()
        trace = {
            "schema": "runtime-trace/1",
            "sessions": [{"id": "ses_observer"}],
            "skill_events": [
                {"session_id": "ses_observer", "skill": "product-observer", "status": "completed"}
            ],
            "tool_events": [],
        }
        self.assertEqual(self._collect(trace=trace), [])


class ObservationSpecTests(unittest.TestCase):
    def test_schema2_requires_spec(self):
        goal = dict(GOAL_V2)
        goal.pop("product_observation")
        self.assertTrue(any("required for schema_version 2" in p for p in po.observation_spec_problems(goal)))

    def test_required_false_needs_reason_and_basis(self):
        goal = dict(GOAL_V2)
        goal["product_observation"] = {"required": False}
        problems = po.observation_spec_problems(goal)
        self.assertTrue(any("reason" in p for p in problems), problems)
        self.assertTrue(any("basis" in p for p in problems), problems)

    def test_schema1_without_spec_ok(self):
        goal = dict(GOAL_V2)
        goal["schema_version"] = 1
        goal.pop("product_observation")
        self.assertEqual(po.observation_spec_problems(goal), [])

    def test_report_schema_validation(self):
        problems = po.validate_observation_report(base_report("discover"))
        self.assertEqual(problems, [], problems)
        bad = base_report("discover")
        bad["findings"] = [{
            "id": "F-01",
            "surface_ids": ["S-XX"],
            "severity": "huge",
            "category": "functional",
            "confidence": "observed",
            "observed": "x",
            "expected_basis": "y",
            "reproduction": "z",
            "evidence_refs": ["e"],
            "status": "confirmed",
        }]
        problems = po.validate_observation_report(bad)
        self.assertTrue(any("unknown surface" in p for p in problems), problems)
        self.assertTrue(any("severity" in p for p in problems), problems)


class V2ContractBridgeTests(unittest.TestCase):
    def test_legacy_schemas_get_single_migration_diagnostic(self):
        report = base_report("discover")
        report["schema"] = "product-observation/1"
        self.assertEqual(
            po.validate_observation_report(report),
            [
                "legacy schema product-observation/1 is not accepted; "
                "re-observe with product-observation/2"
            ],
        )
        self.assertEqual(
            po.validate_observation_review({"schema": "product-observation-review/1"}),
            [
                "legacy schema product-observation-review/1 is not accepted; "
                "re-review with product-observation-review/2"
            ],
        )
        self.assertEqual(
            po.validate_candidate_manifest({"schema": "product-candidate/1"}),
            [
                "legacy schema product-candidate/1 is not accepted; "
                "re-bind the candidate with product-candidate/2"
            ],
        )

    def test_v2_report_requires_controller_envelope(self):
        for field in (
            "goal_id",
            "candidate_id",
            "observer_session_id",
            "model",
            "packet_hash",
            "received_at",
            "attempt",
        ):
            with self.subTest(field=field):
                report = base_report("discover")
                del report[field]
                problems = po.validate_observation_report(report)
                self.assertTrue(any(field in p for p in problems), problems)

    def test_v2_attempt_must_be_positive_integer(self):
        for value in (0, -1, "1", True, None):
            with self.subTest(value=repr(value)):
                report = base_report("discover")
                report["attempt"] = value
                problems = po.validate_observation_report(report)
                self.assertTrue(any("attempt" in p for p in problems), problems)

    def test_v2_review_requires_structural_envelope(self):
        review = {
            "schema": po.REVIEW_SCHEMA,
            "findings_validity": "sufficient",
            "coverage_adequacy": "sufficient",
            "verdict": "sufficient",
            "notes": "checked",
        }
        problems = po.validate_observation_review(review)
        for field in ("reviewer_session_id", "discover_hash", "compare_hash"):
            self.assertTrue(any(field in p for p in problems), problems)
        review.update(
            {
                "reviewer_session_id": "ses_reviewer",
                "discover_hash": "a" * 64,
                "compare_hash": "b" * 64,
            }
        )
        self.assertEqual(po.validate_observation_review(review), [])

    def test_resolved_without_resolution_ref_is_reported(self):
        report = base_report("compare", findings=[finding(status="resolved")])
        problems = po.validate_observation_report(report)
        self.assertTrue(any("resolution_ref" in p for p in problems), problems)

    def test_compare_requires_difference_classification(self):
        report = base_report("compare", findings=[finding()])
        del report["findings"][0]["difference_classification"]
        problems = po.validate_observation_report(report)
        self.assertTrue(
            any("difference_classification" in p for p in problems), problems
        )

    def test_discover_rejects_difference_classification(self):
        report = base_report("discover", findings=[finding()])
        report["findings"][0]["difference_classification"] = "confirmed-defect"
        problems = po.validate_observation_report(report)
        self.assertTrue(
            any("difference_classification" in p for p in problems), problems
        )

    def test_candidate_runtime_state_type_checked(self):
        manifest = {
            "schema": po.CANDIDATE_SCHEMA,
            "candidate_id": "cand-1",
            "entry": "python app.py",
            "environment": "local",
            "backend": "agent-browser",
            "files": [{"path": "app.py", "sha256": "a" * 64}],
            "runtime_state": {"bad": True},
        }
        problems = po.validate_candidate_manifest(manifest)
        self.assertTrue(any("runtime_state" in p for p in problems), problems)
        manifest["runtime_state"] = []
        self.assertEqual(po.validate_candidate_manifest(manifest), [])

    def test_audit_sidecar_accepts_both_versions(self):
        for schema in ("product-audit/1", "product-audit/2"):
            with self.subTest(schema=schema):
                sidecar = {
                    "schema": schema,
                    "goal_id": "G-OBS",
                    "current_candidate": "cand-1",
                    "rounds": [
                        {
                            "candidate_id": "cand-1",
                            "discover_ref": "a.json",
                            "compare_ref": "b.json",
                            "review_ref": "c.json",
                        }
                    ],
                }
                self.assertEqual(po.validate_audit_sidecar(sidecar), [])

    def test_audit_sidecar_rejects_unknown_schema(self):
        sidecar = {
            "schema": "product-audit/3",
            "goal_id": "G-OBS",
            "current_candidate": "cand-1",
            "rounds": [{"candidate_id": "cand-1"}],
        }
        problems = po.validate_audit_sidecar(sidecar)
        self.assertTrue(any("sidecar.schema" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
