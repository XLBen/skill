"""S05: full-diagnosis gate, evidence verification, cross-round resolution and
the gate-record v2 finish/check-current closed loop."""

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import observation_contract as oc  # noqa: E402
import product_observation as po  # noqa: E402

from scripts import check  # noqa: E402
from test_product_observation import (  # noqa: E402
    GOAL_V2,
    base_report,
    finding,
    sha,
    write_goal,
)

SQLITE_HEADER = b"SQLite format 3\x00"


def phase_report(phase, findings=None, stop_reason="coverage-completed"):
    return base_report(phase, findings, None, stop_reason)


def use_evidence(
    report,
    report_ref="evidence/round.txt",
    journey_ref="evidence/j01.png",
    finding_ref="evidence/f01.png",
):
    report = json.loads(json.dumps(report))
    report["evidence_refs"] = [report_ref]
    for journey in report.get("journeys", []):
        if isinstance(journey, dict):
            journey["evidence_refs"] = [journey_ref]
    for item in report.get("findings", []):
        if isinstance(item, dict):
            item["evidence_refs"] = [finding_ref]
    return report


class GateProject(unittest.TestCase):
    def setUp(self):
        self._make_project()

    def _make_project(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = self.tmp / "proj"
        self.mvp = self.root / ".opencode" / "mvp"
        self.mvp.mkdir(parents=True)
        self.goal_path = self.mvp / "g-obs.md"
        write_goal(self.goal_path, GOAL_V2)
        self.app = self.root / "app.py"
        self.app.write_text("print('ok')\n", encoding="utf-8")
        self.cdir = self._cdir("cand-1")
        (self.cdir / "evidence").mkdir(parents=True)
        self.sidecar_path = self.mvp / "g-obs.product-audit.json"

    def _cdir(self, candidate_id):
        return self.mvp / "observation" / "G-OBS" / candidate_id

    def _write_candidate(self, candidate_id="cand-1"):
        manifest = {
            "schema": po.CANDIDATE_SCHEMA,
            "candidate_id": candidate_id,
            "entry": "python app.py",
            "environment": "local windows",
            "backend": "agent-browser",
            "files": [{"path": "app.py", "sha256": sha(self.app.read_bytes())}],
            "test_data": [],
            "channels": [],
            "baseline": {"kind": "none", "refs": []},
        }
        cdir = self._cdir(candidate_id)
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "candidate.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8", newline="\n"
        )
        return manifest

    def _write_evidence(self, candidate_id="cand-1", names=("round.txt", "j01.png", "f01.png")):
        target = self._cdir(candidate_id) / "evidence"
        target.mkdir(parents=True, exist_ok=True)
        for name in names:
            (target / name).write_text(f"{name}\n", encoding="utf-8", newline="\n")

    def _write_phase(self, phase, report, candidate_id="cand-1", result_path=None):
        cdir = self._cdir(candidate_id)
        cdir.mkdir(parents=True, exist_ok=True)
        packet_path = cdir / f"{phase}.packet.json"
        packet_path.write_text(
            json.dumps(
                {"schema": "workflow-observer-packet/1", "phase": phase, "stub": True},
                indent=2,
            ),
            encoding="utf-8",
            newline="\n",
        )
        report = json.loads(json.dumps(report))
        report.setdefault("candidate_id", candidate_id)
        report["packet_hash"] = sha(packet_path.read_bytes())
        target = Path(result_path) if result_path is not None else cdir / f"{phase}.result.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, indent=2), encoding="utf-8", newline="\n"
        )
        return target

    def _write_review(
        self, discover_path, compare_path, candidate_id="cand-1", verdict="sufficient"
    ):
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
        target = self._cdir(candidate_id) / "review.result.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(review, indent=2), encoding="utf-8", newline="\n"
        )
        return target

    def _round_entry(self, candidate_id, discover_ref=None, compare_ref=None, review_ref=None):
        base = f".opencode/mvp/observation/G-OBS/{candidate_id}"
        return {
            "candidate_id": candidate_id,
            "discover_ref": discover_ref or f"{base}/discover.result.json",
            "compare_ref": compare_ref or f"{base}/compare.result.json",
            "review_ref": review_ref or f"{base}/review.result.json",
        }

    def _write_sidecar(self, rounds=None, current="cand-1"):
        if rounds is None:
            rounds = [self._round_entry(current)]
        sidecar = {
            "schema": po.AUDIT_SIDECAR_SCHEMA,
            "goal_id": "G-OBS",
            "current_candidate": current,
            "rounds": rounds,
        }
        self.sidecar_path.write_text(
            json.dumps(sidecar, indent=2), encoding="utf-8", newline="\n"
        )
        return sidecar

    def _valid_round(
        self,
        candidate_id="cand-1",
        discover_findings=None,
        compare_findings=None,
        discover=None,
        compare=None,
        review_verdict="sufficient",
    ):
        self._write_candidate(candidate_id)
        self._write_evidence(candidate_id)
        if discover is None:
            discover = use_evidence(
                phase_report("discover", findings=discover_findings or [])
            )
        if compare is None:
            compare = use_evidence(
                phase_report("compare", findings=compare_findings or [])
            )
        discover["candidate_id"] = candidate_id
        compare["candidate_id"] = candidate_id
        discover_path = self._write_phase("discover", discover, candidate_id)
        compare_path = self._write_phase("compare", compare, candidate_id)
        self._write_review(discover_path, compare_path, candidate_id, verdict=review_verdict)
        return discover_path, compare_path

    def _write_earlier_round(self, candidate_id, finding_ids, readable=True):
        cdir = self._cdir(candidate_id)
        cdir.mkdir(parents=True, exist_ok=True)
        if not readable:
            return
        for phase in ("discover", "compare"):
            report = {
                "schema": po.REPORT_SCHEMA,
                "phase": phase,
                "findings": [{"id": fid} for fid in finding_ids],
            }
            (cdir / f"{phase}.result.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8", newline="\n"
            )

    def _write_native_trace(self, name="trace.json", session_id="ses_observer"):
        store = self.tmp / "session-store.db"
        store.write_bytes(SQLITE_HEADER)
        trace = {
            "schema": "runtime-trace/1",
            "source": {"kind": "opencode-sqlite", "path": str(store)},
            "sessions": [{"id": session_id}],
            "skill_events": [
                {
                    "session_id": session_id,
                    "skill": "product-observer",
                    "status": "completed",
                }
            ],
            "task_events": [],
            "tool_events": [],
        }
        trace_path = self.tmp / name
        trace_path.write_text(
            json.dumps(trace, indent=2), encoding="utf-8", newline="\n"
        )
        return trace_path

    def _write_unverified_trace(self, name="plain-trace.json", session_id="ses_observer"):
        trace = {
            "schema": "runtime-trace/1",
            "sessions": [{"id": session_id}],
            "skill_events": [
                {
                    "session_id": session_id,
                    "skill": "product-observer",
                    "status": "completed",
                }
            ],
            "task_events": [],
            "tool_events": [],
        }
        trace_path = self.tmp / name
        trace_path.write_text(
            json.dumps(trace, indent=2), encoding="utf-8", newline="\n"
        )
        return trace_path

    def _trace_binding(self, trace_path, provenance="native"):
        return {
            "path": str(trace_path),
            "sha256": sha(trace_path.read_bytes()),
            "provenance": provenance,
        }

    def _write_gate(
        self,
        verdict="passed",
        goal_hash=None,
        trace=None,
        failures=None,
        candidate="cand-1",
    ):
        if goal_hash is None:
            goal_hash = check.goal_definition_hash(self._goal())
        record = {
            "schema": po.GATE_SCHEMA,
            "goal_id": "G-OBS",
            "candidate_id": candidate,
            "verdict": verdict,
            "failures": failures if failures is not None else ([] if verdict == "passed" else ["gate failure"]),
            "goal_definition_hash": goal_hash,
            "trace": trace,
        }
        target = self._cdir(candidate) / "gate.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(record, indent=2), encoding="utf-8", newline="\n"
        )
        return target

    def _verify_outcome(self):
        evidence = self.mvp / "evidence" / "g-obs-O-01-01.json"
        return check.verify_goal_outcome(self.goal_path, "O-01", evidence)

    def _goal(self):
        _, goal = check.read_artifact(str(self.goal_path), "goal")
        return goal

    def _collect(self, trace=None):
        return po.collect_observation_problems(self._goal(), self.goal_path, trace=trace)

    def _run_cli(self, *extra):
        argv = ["check.py", "product-audit-gate", str(self.goal_path), *extra]
        with redirect_stdout(io.StringIO()) as output:
            rc = check.main(argv)
        return rc, output.getvalue()


class FullDiagnosisTests(GateProject):
    def test_one_pass_reports_multiple_independent_problem_classes(self):
        self._write_candidate()
        self._write_evidence()
        discover = use_evidence(
            phase_report("discover"), report_ref="evidence/missing.png"
        )
        discover["stop_reason"] = "weird"
        discover_path = self._write_phase("discover", discover)
        compare_path = self._write_phase("compare", use_evidence(phase_report("compare")))
        self._write_review(discover_path, compare_path, verdict="needs-repair")
        self._write_sidecar()
        self.app.write_text("print('changed')\n", encoding="utf-8")

        problems = self._collect()
        self.assertTrue(any("changed after binding" in p for p in problems), problems)
        self.assertTrue(any(p.startswith("discover:") for p in problems), problems)
        self.assertTrue(any(p.startswith("review:") for p in problems), problems)
        self.assertTrue(
            any("not found" in p and "evidence/missing.png" in p for p in problems),
            problems,
        )
        self.assertTrue(
            any("stop_reason" in p for p in problems), problems
        )

    def test_missing_manifest_still_checks_phases_review_and_evidence(self):
        self._valid_round(review_verdict="needs-repair")
        self._write_sidecar()
        (self.cdir / "candidate.json").unlink()
        (self.cdir / "evidence" / "j01.png").unlink()
        problems = self._collect()
        self.assertTrue(any("candidate manifest missing" in p for p in problems), problems)
        self.assertTrue(
            any(p.startswith("discover:") and "not found" in p for p in problems), problems
        )
        self.assertTrue(any(p.startswith("review:") for p in problems), problems)

    def test_sidecar_structure_problem_still_runs_other_checks(self):
        discover_path, compare_path = self._valid_round(review_verdict="needs-repair")
        self._write_sidecar(
            rounds=[
                {
                    "candidate_id": "cand-1",
                    "discover_ref": discover_path.relative_to(self.root).as_posix(),
                    "compare_ref": compare_path.relative_to(self.root).as_posix(),
                }
            ]
        )
        problems = self._collect()
        self.assertTrue(any(p.startswith("sidecar:") for p in problems), problems)
        self.assertTrue(any(p.startswith("review:") for p in problems), problems)

    def test_missing_review_does_not_skip_report_provenance(self):
        self._valid_round()
        (self.cdir / "review.result.json").unlink()
        self._write_sidecar()
        trace = {
            "sessions": [{"id": "ses_other"}],
            "skill_events": [],
        }
        problems = self._collect(trace=trace)
        self.assertTrue(any("observation review missing" in p for p in problems), problems)
        self.assertTrue(any("ses_observer" in p for p in problems), problems)

    def test_malformed_finding_skips_redundant_semantic_diagnostics(self):
        item = finding(id=None, status="dismissed")
        self._valid_round(compare_findings=[item])
        self._write_sidecar()
        problems = self._collect()
        self.assertTrue(
            any("result.findings[0]" in p and ".id" in p for p in problems), problems
        )
        self.assertFalse(
            any("dismissed" in p and "owner_decision_ref" in p for p in problems),
            problems,
        )


class ReviewHashBindingTests(GateProject):
    def test_review_hashes_use_sidecar_referenced_files(self):
        self._write_candidate()
        self._write_evidence()
        archive = self.root / "archive"
        archive.mkdir()
        discover_path = self._write_phase(
            "discover",
            use_evidence(phase_report("discover")),
            result_path=archive / "discover.json",
        )
        compare_path = self._write_phase(
            "compare",
            use_evidence(phase_report("compare")),
            result_path=archive / "compare.json",
        )
        (self.cdir / "discover.result.json").write_text(
            json.dumps(phase_report("discover"), indent=2), encoding="utf-8", newline="\n"
        )
        (self.cdir / "compare.result.json").write_text(
            json.dumps(phase_report("compare"), indent=2), encoding="utf-8", newline="\n"
        )
        self._write_review(discover_path, compare_path)
        self._write_sidecar(
            rounds=[
                self._round_entry(
                    "cand-1",
                    discover_ref=discover_path.relative_to(self.root).as_posix(),
                    compare_ref=compare_path.relative_to(self.root).as_posix(),
                )
            ]
        )
        self.assertEqual(self._collect(), [])

        changed = phase_report("compare")
        changed["notes"] = "mutated after the review"
        compare_path.write_text(
            json.dumps(changed, indent=2), encoding="utf-8", newline="\n"
        )
        problems = self._collect()
        self.assertTrue(
            any("review.compare_hash does not match" in p for p in problems), problems
        )
        self.assertFalse(any("review.discover_hash" in p for p in problems), problems)


class EvidenceReferenceTests(GateProject):
    def test_existing_evidence_files_pass(self):
        self._valid_round()
        self._write_sidecar()
        self.assertEqual(self._collect(), [])

    def test_missing_evidence_file_is_reported(self):
        discover = use_evidence(
            phase_report("discover"), report_ref="evidence/missing.png"
        )
        self._write_candidate()
        self._write_evidence()
        discover_path = self._write_phase("discover", discover)
        compare_path = self._write_phase("compare", use_evidence(phase_report("compare")))
        self._write_review(discover_path, compare_path)
        self._write_sidecar()
        problems = self._collect()
        self.assertTrue(
            any("not found" in p and "evidence/missing.png" in p for p in problems),
            problems,
        )

    def test_evidence_ref_escaping_the_candidate_scope_is_reported(self):
        discover = use_evidence(
            phase_report("discover"), journey_ref="../outside.txt"
        )
        self._write_candidate()
        self._write_evidence()
        discover_path = self._write_phase("discover", discover)
        compare_path = self._write_phase("compare", use_evidence(phase_report("compare")))
        self._write_review(discover_path, compare_path)
        self._write_sidecar()
        problems = self._collect()
        self.assertTrue(
            any("escapes the candidate evidence scope" in p for p in problems),
            problems,
        )

    def test_absolute_evidence_ref_is_reported(self):
        discover = use_evidence(
            phase_report("discover"), report_ref=str(self.root / "outside.txt")
        )
        self._write_candidate()
        self._write_evidence()
        discover_path = self._write_phase("discover", discover)
        compare_path = self._write_phase("compare", use_evidence(phase_report("compare")))
        self._write_review(discover_path, compare_path)
        self._write_sidecar()
        problems = self._collect()
        self.assertTrue(
            any("escapes the candidate evidence scope" in p for p in problems),
            problems,
        )

    def test_check_covers_findings_journeys_and_report_refs(self):
        for slot in ("report", "journey", "finding"):
            with self.subTest(slot=slot):
                self._make_project()
                refs = {
                    "report_ref": "evidence/round.txt",
                    "journey_ref": "evidence/j01.png",
                    "finding_ref": "evidence/f01.png",
                }
                refs[f"{slot}_ref"] = "../outside.txt"
                findings = [finding()] if slot == "finding" else []
                self._write_candidate()
                self._write_evidence()
                discover_path = self._write_phase(
                    "discover",
                    use_evidence(phase_report("discover", findings=findings), **refs),
                )
                compare_path = self._write_phase(
                    "compare",
                    use_evidence(phase_report("compare", findings=findings)),
                )
                self._write_review(discover_path, compare_path)
                self._write_sidecar()
                problems = self._collect()
                self.assertTrue(
                    any("escapes the candidate evidence scope" in p for p in problems),
                    problems,
                )


class ResolutionBindingFunctionTests(unittest.TestCase):
    def _resolved(self, candidate_id="cand-1", finding_id="F-01"):
        return finding(
            status="resolved",
            difference_classification="confirmed-defect",
            resolution_ref={"candidate_id": candidate_id, "finding_id": finding_id},
        )

    def test_known_round_with_matching_finding_passes(self):
        self.assertEqual(
            oc.resolution_binding_problems(
                self._resolved(), "cand-2", {"cand-1": {"F-01", "F-02"}}
            ),
            [],
        )

    def test_current_candidate_is_rejected(self):
        problems = oc.resolution_binding_problems(
            self._resolved("cand-2"), "cand-2", {"cand-1": {"F-01"}}
        )
        self.assertTrue(any("current candidate" in p for p in problems), problems)

    def test_unknown_round_is_rejected(self):
        problems = oc.resolution_binding_problems(
            self._resolved("cand-9"), "cand-2", {"cand-1": {"F-01"}}
        )
        self.assertTrue(any("not a known earlier round" in p for p in problems), problems)

    def test_unreadable_round_is_rejected(self):
        problems = oc.resolution_binding_problems(
            self._resolved(), "cand-2", {"cand-1": None}
        )
        self.assertTrue(any("cannot verify resolution" in p for p in problems), problems)

    def test_missing_finding_id_is_rejected(self):
        problems = oc.resolution_binding_problems(
            self._resolved("cand-1", "F-99"), "cand-2", {"cand-1": {"F-01"}}
        )
        self.assertTrue(any("is not present in round" in p for p in problems), problems)

    def test_non_resolved_finding_is_ignored(self):
        item = finding(status="confirmed")
        self.assertEqual(
            oc.resolution_binding_problems(item, "cand-2", {"cand-1": {"F-01"}}), []
        )


class CrossRoundResolutionTests(GateProject):
    def _resolution_round(self, resolution_ref):
        item = finding(
            status="resolved",
            difference_classification="confirmed-defect",
            resolution_ref=resolution_ref,
        )
        self._valid_round(candidate_id="cand-2", compare_findings=[item])
        self._write_sidecar(
            rounds=[self._round_entry("cand-1"), self._round_entry("cand-2")],
            current="cand-2",
        )

    def test_resolution_to_known_earlier_finding_passes(self):
        self._write_earlier_round("cand-1", ["F-01"])
        self._resolution_round({"candidate_id": "cand-1", "finding_id": "F-01"})
        self.assertEqual(self._collect(), [])

    def test_unknown_earlier_round_is_reported(self):
        self._write_earlier_round("cand-1", ["F-01"])
        self._resolution_round({"candidate_id": "cand-9", "finding_id": "F-01"})
        problems = self._collect()
        self.assertTrue(
            any("not a known earlier round" in p for p in problems), problems
        )

    def test_missing_finding_in_earlier_round_is_reported(self):
        self._write_earlier_round("cand-1", ["F-01"])
        self._resolution_round({"candidate_id": "cand-1", "finding_id": "F-99"})
        problems = self._collect()
        self.assertTrue(
            any("is not present in round" in p for p in problems), problems
        )

    def test_unreadable_earlier_round_is_reported(self):
        self._write_earlier_round("cand-1", ["F-01"], readable=False)
        self._resolution_round({"candidate_id": "cand-1", "finding_id": "F-01"})
        problems = self._collect()
        self.assertTrue(any("cannot verify resolution" in p for p in problems), problems)

    def test_current_candidate_resolution_is_reported(self):
        self._write_earlier_round("cand-1", ["F-01"])
        self._resolution_round({"candidate_id": "cand-2", "finding_id": "F-01"})
        problems = self._collect()
        self.assertTrue(any("current candidate" in p for p in problems), problems)


class GateRecordClosedLoopTests(GateProject):
    def _observation_artifacts(self):
        self._write_candidate()
        self._write_sidecar()

    def test_finish_and_check_current_require_a_gate_record(self):
        self._observation_artifacts()
        self._verify_outcome()
        for action in (check.finish_goal, check.check_current):
            with self.subTest(action=action.__name__):
                with self.assertRaises(check.ValidationError) as ctx:
                    action(self.goal_path)
                self.assertIn("product observation", str(ctx.exception))
                self.assertIn("product-audit-gate", str(ctx.exception))

    def test_failed_gate_verdict_blocks_finish(self):
        self._observation_artifacts()
        self._write_gate(verdict="failed", failures=["discover: evidence missing"])
        self._verify_outcome()
        with self.assertRaises(check.ValidationError) as ctx:
            check.finish_goal(self.goal_path)
        message = str(ctx.exception)
        self.assertIn("product observation", message)
        self.assertIn("verdict is not passed", message)

    def test_stale_goal_definition_hash_blocks_finish(self):
        self._observation_artifacts()
        self._write_gate(goal_hash="0" * 64)
        self._verify_outcome()
        with self.assertRaises(check.ValidationError) as ctx:
            check.finish_goal(self.goal_path)
        message = str(ctx.exception)
        self.assertIn("product observation", message)
        self.assertIn("stale", message)

    def test_changed_trace_file_blocks_check_current(self):
        self._observation_artifacts()
        trace_path = self._write_native_trace()
        self._write_gate(trace=self._trace_binding(trace_path))
        trace_path.write_text('{"tampered": true}\n', encoding="utf-8", newline="\n")
        with self.assertRaises(check.ValidationError) as ctx:
            check.check_current(self.goal_path)
        message = str(ctx.exception)
        self.assertIn("product observation", message)
        self.assertIn("stale", message)

    def test_unverified_trace_provenance_blocks_check_current(self):
        self._observation_artifacts()
        trace_path = self._write_native_trace()
        self._write_gate(trace=self._trace_binding(trace_path, provenance="unverified"))
        with self.assertRaises(check.ValidationError) as ctx:
            check.check_current(self.goal_path)
        message = str(ctx.exception)
        self.assertIn("product observation", message)
        self.assertIn("native", message)

    def test_gate_cli_requires_a_trace(self):
        self._observation_artifacts()
        rc, output = self._run_cli()
        self.assertEqual(rc, 2, output)
        self.assertIn("--trace", output)

    def test_gate_cli_marks_unverified_provenance_failed(self):
        self._valid_round()
        self._write_sidecar()
        trace_path = self._write_unverified_trace()
        rc, output = self._run_cli("--trace", str(trace_path))
        self.assertEqual(rc, 1, output)
        self.assertIn("trace provenance is not native", output)
        gate = json.loads((self.cdir / "gate.json").read_text(encoding="utf-8"))
        self.assertEqual(gate["verdict"], "failed")
        self.assertEqual(gate["trace"]["provenance"], "unverified")

    def test_gate_cli_short_circuits_when_not_required(self):
        legacy = dict(GOAL_V2)
        legacy["schema_version"] = 1
        legacy.pop("product_observation")
        write_goal(self.goal_path, legacy)
        rc, output = self._run_cli()
        self.assertEqual(rc, 0, output)
        self.assertIn("not required", output)

    def test_gate_cli_writes_passed_gate_and_finish_goal_completes(self):
        self._valid_round()
        self._write_sidecar()
        self._verify_outcome()
        trace_path = self._write_native_trace()
        rc, output = self._run_cli("--trace", str(trace_path))
        self.assertEqual(rc, 0, output)
        gate = json.loads((self.cdir / "gate.json").read_text(encoding="utf-8"))
        self.assertEqual(gate["schema"], po.GATE_SCHEMA)
        self.assertEqual(gate["verdict"], "passed")
        self.assertEqual(gate["goal_definition_hash"], check.goal_definition_hash(self._goal()))
        self.assertEqual(gate["trace"]["provenance"], "native")
        self.assertEqual(check.check_current(self.goal_path)["id"], "G-OBS")
        finished = check.finish_goal(self.goal_path)
        self.assertEqual(finished["status"], "complete")


class ObservationRegressionTests(GateProject):
    def test_owner_decision_finding_still_blocks(self):
        item = finding(
            severity="critical",
            status="owner-decision",
            difference_classification="owner-decision",
            owner_decision_ref="decisions/D-07.md",
        )
        self._valid_round(compare_findings=[item], review_verdict="needs-repair")
        self._write_sidecar()
        problems = self._collect()
        self.assertTrue(
            any(
                "unresolved critical/high" in p and "owner-decision" in p
                for p in problems
            ),
            problems,
        )

    def test_capability_gap_still_blocks(self):
        compare = use_evidence(phase_report("compare"))
        compare["capability_gaps"] = [
            {"channel": "web", "reason": "backend unavailable"}
        ]
        self._valid_round(compare=compare)
        self._write_sidecar()
        problems = self._collect()
        self.assertTrue(
            any(
                "unresolved capability gaps" in p and "web" in p for p in problems
            ),
            problems,
        )


if __name__ == "__main__":
    unittest.main()
