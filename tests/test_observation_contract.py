import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import observation_contract as oc  # noqa: E402

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "product-observation"
CONTRACT_DOC = ROOT / "product-observer" / "references" / "result-contract.md"
PACKET_HASH = "a" * 64
BAD_ENUM_VALUES = ({}, [], 0, None)


def load_fixture(name):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def controller_fields(attempt=1):
    return {
        "goal_id": "G-OBS",
        "candidate_id": "cand-1",
        "observer_session_id": "ses_observer",
        "model": "provider/model",
        "packet_hash": PACKET_HASH,
        "received_at": "2026-09-21T00:00:00Z",
        "attempt": attempt,
    }


class FixtureTests(unittest.TestCase):
    def test_discover_fixture_passes(self):
        payload = load_fixture("discover-valid.json")
        self.assertEqual(oc.validate_result_payload(payload, "discover"), [])

    def test_compare_fixture_passes(self):
        payload = load_fixture("compare-valid.json")
        self.assertEqual(oc.validate_result_payload(payload, phase="compare"), [])
        self.assertEqual(oc.validate_result_payload(payload), [])

    def test_budget_fixture_passes(self):
        payload = load_fixture("budget-valid.json")
        self.assertEqual(oc.validate_result_payload(payload), [])

    def test_blocked_fixture_passes(self):
        payload = load_fixture("blocked-valid.json")
        self.assertEqual(oc.validate_result_payload(payload), [])

    def test_review_valid_fixture_passes(self):
        review = load_fixture("review-valid.json")
        self.assertEqual(oc.validate_review_payload(review), [])

    def test_review_needs_repair_fixture_passes(self):
        review = load_fixture("review-needs-repair.json")
        self.assertEqual(oc.validate_review_payload(review), [])


class TemplateTests(unittest.TestCase):
    def test_result_templates_pass_for_their_phase(self):
        for phase in oc.PHASES:
            with self.subTest(phase=phase):
                template = oc.result_template(phase)
                self.assertEqual(template["phase"], phase)
                self.assertEqual(oc.validate_result_payload(template, phase), [])

    def test_result_template_rejects_unknown_phase(self):
        with self.assertRaises(ValueError):
            oc.result_template("review")

    def test_review_template_passes(self):
        self.assertEqual(oc.validate_review_payload(oc.review_template()), [])

    def test_review_template_is_minimal(self):
        template = oc.review_template()
        self.assertEqual(template["schema"], oc.SCHEMA_REVIEW)
        self.assertTrue(template["notes"].strip())


class EnumTypeRobustnessTests(unittest.TestCase):
    def assert_rejected(self, validator, payload, phase=None):
        try:
            problems = validator(payload) if phase is None else validator(payload, phase)
        except Exception as exc:  # pragma: no cover - failure path
            self.fail(f"{validator.__name__} raised {type(exc).__name__}: {exc}")
        self.assertTrue(problems, "expected a non-empty problem list")

    def test_result_enum_fields_never_raise(self):
        mutations = (
            ("stop_reason", lambda payload, value: payload.update(stop_reason=value)),
            (
                "surface importance",
                lambda payload, value: payload["surfaces"][0].update(importance=value),
            ),
            (
                "journey outcome",
                lambda payload, value: payload["journeys"][0].update(outcome=value),
            ),
            (
                "finding severity",
                lambda payload, value: payload["findings"][0].update(severity=value),
            ),
            (
                "finding status",
                lambda payload, value: payload["findings"][0].update(status=value),
            ),
            (
                "finding confidence",
                lambda payload, value: payload["findings"][0].update(confidence=value),
            ),
        )
        for label, mutate in mutations:
            for value in BAD_ENUM_VALUES:
                with self.subTest(field=label, value=repr(value)):
                    payload = load_fixture("compare-valid.json")
                    mutate(payload, value)
                    self.assert_rejected(
                        oc.validate_result_payload, payload, phase="compare"
                    )

    def test_review_enum_fields_never_raise(self):
        for field in ("findings_validity", "coverage_adequacy", "verdict"):
            for value in BAD_ENUM_VALUES:
                with self.subTest(field=field, value=repr(value)):
                    review = load_fixture("review-valid.json")
                    review[field] = value
                    self.assert_rejected(oc.validate_review_payload, review)

    def test_non_object_payloads_do_not_raise(self):
        for value in BAD_ENUM_VALUES:
            with self.subTest(value=repr(value)):
                self.assertTrue(oc.validate_result_payload(value))
                self.assertTrue(oc.validate_review_payload(value))
                self.assertTrue(oc.validate_result_envelope(value))


class UnknownFieldTests(unittest.TestCase):
    def test_unknown_top_level_field_rejected(self):
        payload = load_fixture("discover-valid.json")
        payload["surprise"] = True
        problems = oc.validate_result_payload(payload, "discover")
        self.assertTrue(any("surprise" in problem for problem in problems), problems)

    def test_unknown_finding_field_rejected(self):
        payload = load_fixture("compare-valid.json")
        payload["findings"][0]["mystery"] = "x"
        problems = oc.validate_result_payload(payload, "compare")
        self.assertTrue(any("mystery" in problem for problem in problems), problems)

    def test_unknown_surface_field_rejected(self):
        payload = load_fixture("discover-valid.json")
        payload["surfaces"][0]["extra"] = 1
        problems = oc.validate_result_payload(payload, "discover")
        self.assertTrue(any("extra" in problem for problem in problems), problems)

    def test_unknown_resolution_ref_field_rejected(self):
        payload = load_fixture("compare-valid.json")
        finding = payload["findings"][0]
        finding["status"] = "resolved"
        finding["resolution_ref"] = {
            "candidate_id": "cand-2",
            "finding_id": "F-01",
            "note": "extra",
        }
        problems = oc.validate_result_payload(payload, "compare")
        self.assertTrue(any("resolution_ref" in p and "note" in p for p in problems), problems)

    def test_unknown_review_field_rejected(self):
        review = load_fixture("review-valid.json")
        review["mystery"] = 1
        problems = oc.validate_review_payload(review)
        self.assertTrue(any("mystery" in problem for problem in problems), problems)


class ResultRuleTests(unittest.TestCase):
    def test_dismissed_requires_dismissal_reason(self):
        payload = load_fixture("compare-valid.json")
        payload["findings"][0]["status"] = "dismissed"
        problems = oc.validate_result_payload(payload, "compare")
        self.assertTrue(any("dismissal_reason" in p for p in problems), problems)

    def test_dismissed_with_reason_is_valid(self):
        payload = load_fixture("compare-valid.json")
        finding = payload["findings"][0]
        finding["status"] = "dismissed"
        finding["dismissal_reason"] = "Known cosmetic drift already tracked by the owner."
        problems = oc.validate_result_payload(payload, "compare")
        self.assertEqual(problems, [])

    def test_resolved_requires_resolution_ref(self):
        payload = load_fixture("compare-valid.json")
        payload["findings"][0]["status"] = "resolved"
        problems = oc.validate_result_payload(payload, "compare")
        self.assertTrue(any("resolution_ref" in p for p in problems), problems)

    def test_resolved_resolution_ref_fields_required(self):
        payload = load_fixture("compare-valid.json")
        finding = payload["findings"][0]
        finding["status"] = "resolved"
        finding["resolution_ref"] = {"candidate_id": "", "finding_id": "F-01"}
        problems = oc.validate_result_payload(payload, "compare")
        self.assertTrue(
            any("resolution_ref.candidate_id" in p for p in problems), problems
        )

    def test_resolved_with_resolution_ref_is_valid(self):
        payload = load_fixture("compare-valid.json")
        finding = payload["findings"][0]
        finding["status"] = "resolved"
        finding["resolution_ref"] = {"candidate_id": "cand-2", "finding_id": "F-01"}
        problems = oc.validate_result_payload(payload, "compare")
        self.assertEqual(problems, [])

    def test_compare_requires_difference_classification(self):
        payload = load_fixture("compare-valid.json")
        del payload["findings"][0]["difference_classification"]
        problems = oc.validate_result_payload(payload, "compare")
        self.assertTrue(any("difference_classification" in p for p in problems), problems)

    def test_compare_rejects_null_difference_classification(self):
        payload = load_fixture("compare-valid.json")
        payload["findings"][0]["difference_classification"] = None
        problems = oc.validate_result_payload(payload, "compare")
        self.assertTrue(any("required in the compare phase" in p for p in problems), problems)

    def test_discover_forbids_difference_classification(self):
        finding = load_fixture("compare-valid.json")["findings"][0]
        payload = load_fixture("discover-valid.json")
        payload["findings"].append(finding)
        problems = oc.validate_result_payload(payload, "discover")
        self.assertTrue(
            any("must be absent in the discover phase" in p for p in problems), problems
        )

    def test_budget_exhausted_requires_continuation(self):
        payload = load_fixture("budget-valid.json")
        payload["continuation"] = None
        problems = oc.validate_result_payload(payload)
        self.assertTrue(any("continuation is required" in p for p in problems), problems)

    def test_non_budget_rejects_continuation(self):
        payload = load_fixture("discover-valid.json")
        payload["continuation"] = {
            "visited_surface_ids": [],
            "pending_surface_ids": [],
            "checkpoint": "unexpected",
        }
        problems = oc.validate_result_payload(payload, "discover")
        self.assertTrue(any("must be null" in p for p in problems), problems)

    def test_coverage_completed_rejects_material_unobserved(self):
        payload = load_fixture("discover-valid.json")
        payload["unobserved"] = [{"surface_id": "S-01", "reason": "skipped"}]
        problems = oc.validate_result_payload(payload, "discover")
        self.assertTrue(any("coverage is incomplete" in p for p in problems), problems)

    def test_coverage_completed_requires_material_covered(self):
        payload = load_fixture("discover-valid.json")
        del payload["journeys"][0]
        problems = oc.validate_result_payload(payload, "discover")
        self.assertTrue(any("neither covered nor unobserved" in p for p in problems), problems)

    def test_coverage_completed_requires_evidence(self):
        payload = load_fixture("discover-valid.json")
        payload["evidence_refs"] = []
        problems = oc.validate_result_payload(payload, "discover")
        self.assertTrue(any("stop_state is completed" in p for p in problems), problems)

    def test_blocked_needs_notes_or_capability_gaps(self):
        payload = load_fixture("blocked-valid.json")
        payload["capability_gaps"] = []
        payload["notes"] = None
        problems = oc.validate_result_payload(payload)
        self.assertTrue(any("blocked rounds need" in p for p in problems), problems)

    def test_blocked_zero_touch_with_gap_passes(self):
        payload = load_fixture("blocked-valid.json")
        payload["notes"] = None
        self.assertEqual(oc.validate_result_payload(payload), [])

    def test_controller_fields_are_ignored(self):
        payload = load_fixture("compare-valid.json")
        payload.update(
            {
                "goal_id": "G-OBS",
                "candidate_id": "cand-1",
                "observer_session_id": "ses_observer",
                "model": "provider/model",
                "packet_hash": "not-even-a-hash",
                "received_at": 12345,
                "attempt": "first",
            }
        )
        self.assertEqual(oc.validate_result_payload(payload, "compare"), [])


class ReviewRuleTests(unittest.TestCase):
    def test_review_requires_notes(self):
        review = load_fixture("review-valid.json")
        del review["notes"]
        problems = oc.validate_review_payload(review)
        self.assertTrue(any("notes" in p for p in problems), problems)

    def test_sufficient_verdict_requires_sufficient_judgments(self):
        review = load_fixture("review-valid.json")
        review["findings_validity"] = "insufficient"
        problems = oc.validate_review_payload(review)
        self.assertTrue(
            any("findings_validity to be sufficient" in p for p in problems), problems
        )

    def test_needs_repair_verdict_allows_insufficient_judgment(self):
        review = load_fixture("review-needs-repair.json")
        self.assertEqual(oc.validate_review_payload(review), [])

    def test_review_envelope_fields_are_ignored(self):
        review = load_fixture("review-valid.json")
        review.update(
            {
                "reviewer_session_id": "ses_reviewer",
                "model": "provider/model",
                "discover_hash": "b" * 64,
                "compare_hash": "c" * 64,
                "reviewed_at": "2026-09-21T01:00:00Z",
                "received_at": "2026-09-21T01:00:01Z",
                "attempt": 2,
            }
        )
        self.assertEqual(oc.validate_review_payload(review), [])


class EnvelopeTests(unittest.TestCase):
    def accepted(self):
        payload = load_fixture("compare-valid.json")
        payload.update(controller_fields())
        return payload

    def test_valid_envelope_passes(self):
        accepted = self.accepted()
        self.assertEqual(
            oc.validate_result_envelope(
                accepted, "G-OBS", "cand-1", PACKET_HASH, "compare"
            ),
            [],
        )
        self.assertEqual(oc.validate_result_envelope(accepted), [])

    def test_envelope_identity_fields_required(self):
        for field in ("goal_id", "candidate_id", "observer_session_id", "model"):
            with self.subTest(field=field):
                accepted = self.accepted()
                accepted[field] = ""
                problems = oc.validate_result_envelope(accepted)
                self.assertTrue(any(field in p for p in problems), problems)

    def test_envelope_packet_hash_shape(self):
        for value in ("A" * 64, "abc", 123, None, "a" * 63):
            with self.subTest(value=repr(value)):
                accepted = self.accepted()
                accepted["packet_hash"] = value
                problems = oc.validate_result_envelope(accepted)
                self.assertTrue(any("packet_hash" in p for p in problems), problems)

    def test_envelope_attempt_shape(self):
        for value in (0, -1, "1", True, None):
            with self.subTest(value=repr(value)):
                accepted = self.accepted()
                accepted["attempt"] = value
                problems = oc.validate_result_envelope(accepted)
                self.assertTrue(any("attempt" in p for p in problems), problems)

    def test_envelope_received_at_required(self):
        accepted = self.accepted()
        accepted["received_at"] = "  "
        problems = oc.validate_result_envelope(accepted)
        self.assertTrue(any("received_at" in p for p in problems), problems)

    def test_envelope_phase_mismatch(self):
        accepted = self.accepted()
        problems = oc.validate_result_envelope(accepted, expected_phase="discover")
        self.assertTrue(any("expected 'discover'" in p for p in problems), problems)

    def test_envelope_expectation_mismatches(self):
        accepted = self.accepted()
        problems = oc.validate_result_envelope(
            accepted, "G-OTHER", "cand-9", "b" * 64, "compare"
        )
        joined = "\n".join(problems)
        self.assertIn("G-OTHER", joined)
        self.assertIn("cand-9", joined)
        self.assertIn("b" * 64, joined)


class StopStateTests(unittest.TestCase):
    def test_stop_state_mapping(self):
        self.assertEqual(oc.result_stop_state("coverage-completed"), "completed")
        self.assertEqual(oc.result_stop_state("budget-exhausted"), "incomplete")
        for reason in ("blocked", "no-backend", "lease-lost"):
            with self.subTest(reason=reason):
                self.assertEqual(oc.result_stop_state(reason), "blocked")

    def test_stop_state_invalid_values(self):
        for value in ("bogus", None, {}, []):
            with self.subTest(value=repr(value)):
                self.assertIsNone(oc.result_stop_state(value))


class ContractDocTests(unittest.TestCase):
    def test_contract_enums_block_matches_module(self):
        text = CONTRACT_DOC.read_text(encoding="utf-8")
        marker = "```json contract-enums"
        self.assertIn(marker, text)
        start = text.index(marker)
        body_start = text.index("\n", start) + 1
        end = text.index("\n```", body_start)
        block = text[body_start:end]
        expected = json.dumps(oc.contract_enums(), indent=2, sort_keys=True)
        self.assertEqual(block, expected)

    def test_doc_points_to_fixtures(self):
        text = CONTRACT_DOC.read_text(encoding="utf-8")
        self.assertIn("tests/fixtures/product-observation/", text)


if __name__ == "__main__":
    unittest.main()
