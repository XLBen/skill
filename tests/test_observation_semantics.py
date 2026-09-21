import json
import shutil
import sys
import tempfile
import unittest
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

README_ONLY = (
    "The candidate README says the entry was intentionally removed; "
    "the implementer confirms the change is deliberate."
)


def review_payload(
    verdict="sufficient",
    findings_validity="sufficient",
    coverage_adequacy="sufficient",
):
    return {
        "schema": oc.SCHEMA_REVIEW,
        "findings_validity": findings_validity,
        "coverage_adequacy": coverage_adequacy,
        "verdict": verdict,
        "notes": "Both phase payloads were checked against the archived packet.",
    }


def write_round(
    tmp: Path,
    findings=None,
    stop_reason="coverage-completed",
    review_verdict="sufficient",
    findings_validity="sufficient",
    coverage_adequacy="sufficient",
) -> Path:
    """Write a structurally valid accepted round and return the goal path."""

    root = tmp / "proj"
    mvp = root / ".opencode" / "mvp"
    mvp.mkdir(parents=True)
    goal_path = mvp / "g-obs.md"
    write_goal(goal_path, GOAL_V2)
    app = root / "app.py"
    app.write_text("print('ok')\n", encoding="utf-8")
    cdir = mvp / "observation" / "G-OBS" / "cand-1"
    (cdir / "evidence").mkdir(parents=True)

    manifest = {
        "schema": po.CANDIDATE_SCHEMA,
        "candidate_id": "cand-1",
        "entry": "python app.py",
        "environment": "local windows",
        "backend": "agent-browser",
        "files": [{"path": "app.py", "sha256": sha(app.read_bytes())}],
    }
    (cdir / "candidate.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8", newline="\n"
    )

    result_paths = {}
    for phase in ("discover", "compare"):
        packet_path = cdir / f"{phase}.packet.json"
        packet_path.write_text(
            json.dumps(
                {"schema": "workflow-observer-packet/1", "phase": phase, "stub": True},
                indent=2,
            ),
            encoding="utf-8",
            newline="\n",
        )
        report = base_report(phase, findings, None, stop_reason)
        report["packet_hash"] = sha(packet_path.read_bytes())
        result_path = cdir / f"{phase}.result.json"
        result_path.write_text(
            json.dumps(report, indent=2), encoding="utf-8", newline="\n"
        )
        result_paths[phase] = result_path

    review = review_payload(verdict=review_verdict,
                            findings_validity=findings_validity,
                            coverage_adequacy=coverage_adequacy)
    review.update(
        {
            "related_finding_ids": [],
            "reviewer_session_id": "ses_reviewer",
            "discover_hash": sha(result_paths["discover"].read_bytes()),
            "compare_hash": sha(result_paths["compare"].read_bytes()),
        }
    )
    (cdir / "review.result.json").write_text(
        json.dumps(review, indent=2), encoding="utf-8", newline="\n"
    )

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
    (mvp / "g-obs.product-audit.json").write_text(
        json.dumps(sidecar, indent=2), encoding="utf-8", newline="\n"
    )
    return goal_path


class BlockingSemanticsTests(unittest.TestCase):
    def test_confirmed_high_is_blocking(self):
        self.assertTrue(oc.is_blocking_finding(finding()))

    def test_owner_decision_high_is_blocking(self):
        self.assertTrue(
            oc.is_blocking_finding(
                finding(status="owner-decision", difference_classification="owner-decision")
            )
        )

    def test_dismissed_and_resolved_are_not_blocking(self):
        for status in ("dismissed", "resolved"):
            with self.subTest(status=status):
                self.assertFalse(oc.is_blocking_finding(finding(status=status)))

    def test_medium_confirmed_is_not_blocking(self):
        self.assertFalse(oc.is_blocking_finding(finding(severity="medium")))

    def test_malformed_values_do_not_raise(self):
        for value in ({}, [], 0, None):
            with self.subTest(value=repr(value)):
                self.assertFalse(oc.is_blocking_finding(value))
                self.assertFalse(oc.is_blocking_finding({"severity": value, "status": "confirmed"}))
                self.assertFalse(oc.is_blocking_finding({"severity": "high", "status": value}))


class SemanticFindingTests(unittest.TestCase):
    def test_confirmed_defect_high_has_no_semantic_problem(self):
        item = finding(difference_classification="confirmed-defect")
        self.assertEqual(oc.semantic_finding_problems(item, "compare"), [])

    def test_dismissed_high_without_owner_decision_is_a_problem(self):
        item = finding(status="dismissed", dismissal_reason=README_ONLY)
        problems = oc.semantic_finding_problems(item, "compare")
        self.assertTrue(any("owner_decision_ref" in p for p in problems), problems)

    def test_readme_only_dismissal_keeps_blocking(self):
        item = finding(
            status="dismissed",
            dismissal_reason=README_ONLY,
            notes="Candidate README states the deletion is intentional.",
        )
        problems = oc.semantic_finding_problems(item, "compare")
        self.assertTrue(any("dismissed high finding" in p for p in problems), problems)

    def test_dismissed_high_with_owner_decision_passes(self):
        item = finding(
            status="dismissed",
            dismissal_reason="Owner approved the removal.",
            owner_decision_ref="decisions/D-09.md",
        )
        self.assertEqual(oc.semantic_finding_problems(item, "compare"), [])

    def test_intended_change_high_without_owner_decision_is_a_problem(self):
        item = finding(
            difference_classification="intended-change",
            notes="README documents this as an intentional deletion.",
        )
        problems = oc.semantic_finding_problems(item, "compare")
        self.assertTrue(any("intended-change" in p for p in problems), problems)
        self.assertTrue(any("owner_decision_ref" in p for p in problems), problems)

    def test_intended_change_high_with_owner_decision_passes(self):
        item = finding(
            difference_classification="intended-change",
            owner_decision_ref="decisions/D-09.md",
        )
        self.assertEqual(oc.semantic_finding_problems(item, "compare"), [])

    def test_intended_change_medium_without_owner_decision_passes(self):
        item = finding(
            severity="medium",
            difference_classification="intended-change",
            notes="README documents the cosmetic change.",
        )
        self.assertEqual(oc.semantic_finding_problems(item, "compare"), [])

    def test_resolved_without_resolution_ref_is_a_problem(self):
        problems = oc.semantic_finding_problems(finding(status="resolved"), "compare")
        self.assertTrue(any("resolution_ref.candidate_id" in p for p in problems), problems)

    def test_resolved_with_resolution_ref_passes(self):
        item = finding(
            status="resolved",
            difference_classification="confirmed-defect",
            resolution_ref={"candidate_id": "cand-2", "finding_id": "F-01"},
        )
        self.assertEqual(oc.semantic_finding_problems(item, "compare"), [])

    def test_known_old_issue_needs_evidence(self):
        item = finding(difference_classification="known-old-issue", evidence_refs=[])
        problems = oc.semantic_finding_problems(item, "compare")
        self.assertTrue(any("known-old-issue" in p for p in problems), problems)

    def test_owner_decision_classification_needs_basis(self):
        item = finding(difference_classification="owner-decision")
        problems = oc.semantic_finding_problems(item, "compare")
        self.assertTrue(any("owner-decision classification" in p for p in problems), problems)

    def test_owner_decision_classification_with_notes_passes(self):
        item = finding(
            difference_classification="owner-decision",
            notes="Owner will choose between option A and option B.",
        )
        self.assertEqual(oc.semantic_finding_problems(item, "compare"), [])

    def test_non_dict_finding_returns_problem(self):
        for value in (None, [], "F-01", 1):
            with self.subTest(value=repr(value)):
                self.assertTrue(oc.semantic_finding_problems(value, "compare"))


class ReviewVerdictConsistencyTests(unittest.TestCase):
    def test_insufficient_coverage_with_sufficient_verdict_is_a_problem(self):
        problems = oc.review_verdict_consistency_problems(
            review_payload(coverage_adequacy="insufficient"), open_blocking=False
        )
        self.assertTrue(any("needs-observation" in p for p in problems), problems)

    def test_insufficient_findings_validity_with_sufficient_verdict_is_a_problem(self):
        problems = oc.review_verdict_consistency_problems(
            review_payload(findings_validity="insufficient"), open_blocking=False
        )
        self.assertTrue(any("needs-observation" in p for p in problems), problems)

    def test_insufficient_with_needs_observation_passes(self):
        problems = oc.review_verdict_consistency_problems(
            review_payload(verdict="needs-observation", coverage_adequacy="insufficient"),
            open_blocking=False,
        )
        self.assertEqual(problems, [])

    def test_insufficient_with_needs_repair_is_still_a_problem(self):
        problems = oc.review_verdict_consistency_problems(
            review_payload(verdict="needs-repair", coverage_adequacy="insufficient"),
            open_blocking=True,
        )
        self.assertTrue(any("needs-observation" in p for p in problems), problems)

    def test_open_blocking_with_sufficient_verdict_is_a_problem(self):
        problems = oc.review_verdict_consistency_problems(
            review_payload(), open_blocking=True
        )
        self.assertTrue(any("needs-repair" in p for p in problems), problems)

    def test_open_blocking_with_needs_repair_passes(self):
        problems = oc.review_verdict_consistency_problems(
            review_payload(verdict="needs-repair"), open_blocking=True
        )
        self.assertEqual(problems, [])

    def test_no_blocking_with_sufficient_passes(self):
        problems = oc.review_verdict_consistency_problems(
            review_payload(), open_blocking=False
        )
        self.assertEqual(problems, [])

    def test_no_blocking_with_needs_repair_is_a_problem(self):
        problems = oc.review_verdict_consistency_problems(
            review_payload(verdict="needs-repair"), open_blocking=False
        )
        self.assertTrue(any("must be 'sufficient'" in p for p in problems), problems)

    def test_no_blocking_with_needs_observation_is_a_problem(self):
        problems = oc.review_verdict_consistency_problems(
            review_payload(verdict="needs-observation"), open_blocking=False
        )
        self.assertTrue(any("must be 'sufficient'" in p for p in problems), problems)

    def test_blocked_verdict_is_unconstrained(self):
        for insufficient in (False, True):
            for open_blocking in (False, True):
                with self.subTest(insufficient=insufficient, open_blocking=open_blocking):
                    problems = oc.review_verdict_consistency_problems(
                        review_payload(
                            verdict="blocked",
                            coverage_adequacy=(
                                "insufficient" if insufficient else "sufficient"
                            ),
                        ),
                        open_blocking=open_blocking,
                    )
                    self.assertEqual(problems, [])

    def test_invalid_verdict_is_reported_without_raising(self):
        for value in ({}, [], 0, None):
            with self.subTest(value=repr(value)):
                problems = oc.review_verdict_consistency_problems(
                    review_payload(verdict=value), open_blocking=False
                )
                self.assertTrue(any("verdict" in p for p in problems), problems)

    def test_non_dict_review_returns_problem(self):
        for value in (None, [], "review", 1):
            with self.subTest(value=repr(value)):
                self.assertTrue(
                    oc.review_verdict_consistency_problems(value, open_blocking=False)
                )


class StructuralBridgeTests(unittest.TestCase):
    def build_compare(self, item):
        payload = oc.result_template("compare")
        payload["findings"] = [item]
        return payload

    def test_resolved_missing_resolution_ref_fails_contract(self):
        item = finding(status="resolved", difference_classification="confirmed-defect")
        payload = self.build_compare(item)
        problems = oc.validate_result_payload(payload, "compare")
        self.assertTrue(any("resolution_ref" in p for p in problems), problems)
        self.assertTrue(oc.semantic_finding_problems(item, "compare"))

    def test_resolved_with_resolution_ref_and_evidence_passes_contract(self):
        item = finding(
            status="resolved",
            difference_classification="confirmed-defect",
            resolution_ref={"candidate_id": "cand-2", "finding_id": "F-01"},
        )
        payload = self.build_compare(item)
        self.assertEqual(oc.validate_result_payload(payload, "compare"), [])
        self.assertEqual(oc.semantic_finding_problems(item, "compare"), [])


class CollectSemanticIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def collect_problems(self, **kwargs):
        goal_path = write_round(self.tmp, **kwargs)
        _, goal = check.read_artifact(str(goal_path), "goal")
        return po.collect_observation_problems(goal, goal_path)

    def test_readme_only_dismissal_fails_the_gate(self):
        problems = self.collect_problems(
            findings=[
                finding(
                    status="dismissed",
                    dismissal_reason=README_ONLY,
                    notes="Candidate README states the deletion is intentional.",
                )
            ]
        )
        self.assertTrue(any("owner_decision_ref" in p for p in problems), problems)

    def test_dismissed_high_with_owner_decision_passes_the_gate(self):
        problems = self.collect_problems(
            findings=[
                finding(
                    status="dismissed",
                    dismissal_reason="Owner approved the removal.",
                    owner_decision_ref="decisions/D-09.md",
                )
            ]
        )
        self.assertEqual(problems, [])

    def test_intended_change_high_without_owner_decision_fails_the_gate(self):
        problems = self.collect_problems(
            findings=[
                finding(
                    difference_classification="intended-change",
                    notes="README documents this as an intentional deletion.",
                )
            ]
        )
        self.assertTrue(
            any("intended-change" in p and "owner_decision_ref" in p for p in problems),
            problems,
        )

    def test_owner_decision_high_still_blocks_with_needs_repair_review(self):
        problems = self.collect_problems(
            findings=[
                finding(
                    status="owner-decision",
                    difference_classification="owner-decision",
                    owner_decision_ref="decisions/D-07.md",
                )
            ],
            review_verdict="needs-repair",
        )
        self.assertTrue(
            any(
                "unresolved critical/high" in p and "owner-decision" in p
                for p in problems
            ),
            problems,
        )
        self.assertFalse(any("must be 'needs-repair'" in p for p in problems), problems)

    def test_open_blocking_with_sufficient_review_fails_consistency(self):
        problems = self.collect_problems(findings=[finding()])
        self.assertTrue(any("must be 'needs-repair'" in p for p in problems), problems)

    def test_open_blocking_with_needs_repair_review_is_consistent(self):
        problems = self.collect_problems(
            findings=[finding()], review_verdict="needs-repair"
        )
        self.assertFalse(any("must be 'needs-repair'" in p for p in problems), problems)
        self.assertTrue(any("unresolved critical/high" in p for p in problems), problems)

    def test_insufficient_coverage_with_sufficient_verdict_fails_consistency(self):
        problems = self.collect_problems(
            coverage_adequacy="insufficient", review_verdict="sufficient"
        )
        self.assertTrue(any("must be 'needs-observation'" in p for p in problems), problems)

    def test_insufficient_coverage_with_needs_observation_is_consistent(self):
        problems = self.collect_problems(
            coverage_adequacy="insufficient", review_verdict="needs-observation"
        )
        self.assertFalse(any("must be 'needs-observation'" in p for p in problems), problems)
        self.assertFalse(any("must be 'needs-repair'" in p for p in problems), problems)
        self.assertTrue(any("only sufficient clears the gate" in p for p in problems), problems)

    def test_clean_round_still_passes(self):
        self.assertEqual(self.collect_problems(), [])


if __name__ == "__main__":
    unittest.main()
