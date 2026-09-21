"""S18: observation resume planning, coverage merge, no-progress breaker, leases.

Everything here is offline: pure data transformations and validators. Real
resume runs (a live observer continuing a budget-exhausted phase) stay in S21
and are not exercised here.
"""

import datetime
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import observation_resume as resume  # noqa: E402


def budget_result(**overrides):
    result = {
        "schema": "product-observation/2",
        "phase": "discover",
        "stop_reason": "budget-exhausted",
        "candidate_id": "cand-1",
        "model": "provider/model-a",
        "environment": {"os": "win", "browser": "chromium-1"},
        "continuation": {
            "visited_surface_ids": ["s-1"],
            "pending_surface_ids": ["s-2"],
            "checkpoint": "after s-1",
        },
    }
    result.update(overrides)
    return result


def lease(acquired_at="2026-09-21T10:00:00Z", **overrides):
    record = resume.lease_record(
        "ui:web", "sess-1", "cand-1", acquired_at
    )
    record.update(overrides)
    return record


class ResumePlanTests(unittest.TestCase):
    def plan(self, previous, **kwargs):
        options = {
            "phase": "discover",
            "candidate_id": "cand-1",
            "model": "provider/model-a",
            "environment": {"os": "win", "browser": "chromium-1"},
        }
        options.update(kwargs)
        return resume.resume_plan(previous, **options)

    def test_non_object_previous_is_rejected(self):
        for value in (None, "result", 42, ["result"], object()):
            with self.subTest(value=value):
                outcome = self.plan(value)
                self.assertEqual(outcome["action"], "reject")
                self.assertTrue(outcome["reasons"])

    def test_non_budget_stop_reason_is_rejected(self):
        for stop_reason in ("coverage-completed", "blocked", "no-backend", "lease-lost", None):
            with self.subTest(stop_reason=stop_reason):
                outcome = self.plan(budget_result(stop_reason=stop_reason))
                self.assertEqual(outcome["action"], "reject")
                self.assertTrue(any("budget-exhausted" in r for r in outcome["reasons"]))

    def test_phase_mismatch_is_rejected(self):
        outcome = self.plan(budget_result(), phase="compare")
        self.assertEqual(outcome["action"], "reject")
        self.assertTrue(any("phase" in r for r in outcome["reasons"]))

    def test_invalid_phase_argument_is_rejected(self):
        for value in (None, "", "  ", 7):
            with self.subTest(value=value):
                outcome = resume.resume_plan(
                    budget_result(), phase=value, candidate_id="cand-1"
                )
                self.assertEqual(outcome["action"], "reject")

    def test_candidate_change_is_new_round(self):
        outcome = self.plan(budget_result(), candidate_id="cand-2")
        self.assertEqual(outcome["action"], "new-round")
        self.assertTrue(any("candidate changed" in r for r in outcome["reasons"]))
        self.assertNotIn("continuation", outcome)

    def test_missing_previous_candidate_is_new_round(self):
        previous = budget_result()
        del previous["candidate_id"]
        outcome = self.plan(previous)
        self.assertEqual(outcome["action"], "new-round")

    def test_invalid_candidate_argument_is_rejected(self):
        for value in (None, "", "   ", 3):
            with self.subTest(value=value):
                outcome = self.plan(budget_result(), candidate_id=value)
                self.assertEqual(outcome["action"], "reject")

    def test_phase_is_checked_before_candidate(self):
        previous = budget_result(stop_reason="coverage-completed")
        outcome = self.plan(previous, candidate_id="cand-2")
        self.assertEqual(outcome["action"], "reject")

    def test_missing_or_malformed_continuation_is_rejected(self):
        for value in (None, [], "cursor", 1):
            with self.subTest(value=value):
                outcome = self.plan(budget_result(continuation=value))
                self.assertEqual(outcome["action"], "reject")
                self.assertTrue(any("continuation" in r for r in outcome["reasons"]))
        previous = budget_result()
        del previous["continuation"]
        self.assertEqual(self.plan(previous)["action"], "reject")

    def test_model_change_is_new_run(self):
        outcome = self.plan(budget_result(), model="provider/model-b")
        self.assertEqual(outcome["action"], "new-run")
        self.assertTrue(any("model changed" in r for r in outcome["reasons"]))

    def test_environment_change_is_new_run(self):
        outcome = self.plan(
            budget_result(), environment={"os": "linux", "browser": "chromium-1"}
        )
        self.assertEqual(outcome["action"], "new-run")
        self.assertTrue(any("environment changed" in r for r in outcome["reasons"]))

    def test_model_and_environment_changes_report_both_reasons(self):
        outcome = self.plan(
            budget_result(), model="provider/model-b", environment={"os": "linux"}
        )
        self.assertEqual(outcome["action"], "new-run")
        self.assertEqual(len(outcome["reasons"]), 2)

    def test_matching_everything_resumes(self):
        previous = budget_result()
        outcome = self.plan(previous)
        self.assertEqual(outcome["action"], "resume")
        self.assertEqual(outcome["continuation"], previous["continuation"])

    def test_missing_recorded_model_and_environment_only_match_none(self):
        previous = budget_result()
        del previous["model"]
        del previous["environment"]
        self.assertEqual(self.plan(previous, model=None, environment=None)["action"], "resume")
        self.assertEqual(
            self.plan(previous, model="provider/model-a")["action"], "new-run"
        )
        self.assertEqual(self.plan(previous, environment={"os": "win"})["action"], "new-run")

    def test_recorded_model_change_to_missing_is_new_run(self):
        previous = budget_result()
        outcome = self.plan(previous, model=None)
        self.assertEqual(outcome["action"], "new-run")

    def test_every_branch_carries_a_reasons_list(self):
        outcomes = [
            self.plan(None),
            self.plan(budget_result(stop_reason="blocked")),
            self.plan(budget_result(), phase="compare"),
            self.plan(budget_result(), candidate_id="cand-2"),
            self.plan(budget_result(), model="provider/model-b"),
            self.plan(budget_result()),
        ]
        for outcome in outcomes:
            with self.subTest(action=outcome.get("action")):
                self.assertIsInstance(outcome.get("reasons"), list)
                self.assertTrue(all(isinstance(r, str) for r in outcome["reasons"]))

    def test_weird_previous_values_never_raise(self):
        cases = [
            budget_result(phase=["discover"]),
            budget_result(candidate_id={"id": "cand-1"}),
            budget_result(model={"id": "m"}),
            budget_result(environment=["win"]),
        ]
        for previous in cases:
            with self.subTest(previous=previous):
                outcome = resume.resume_plan(
                    previous, phase="discover", candidate_id="cand-1"
                )
                self.assertIn(
                    outcome["action"], ("reject", "new-round", "new-run", "resume")
                )
                self.assertIsInstance(outcome["reasons"], list)


class MergeCoverageTests(unittest.TestCase):
    def surface(self, sid, importance="material"):
        return {"id": sid, "name": sid, "importance": importance}

    def test_covered_journey_marks_surface_and_merges_evidence(self):
        result = {
            "surfaces": [self.surface("s-1")],
            "journeys": [
                {
                    "id": "j-1",
                    "surface_ids": ["s-1"],
                    "outcome": "covered",
                    "evidence_refs": ["evidence/a.png"],
                }
            ],
        }
        merged = resume.merge_coverage([result])
        self.assertTrue(merged["surfaces"]["s-1"]["covered"])
        self.assertEqual(merged["surfaces"]["s-1"]["evidence_refs"], ["evidence/a.png"])
        self.assertEqual(merged["covered_material"], ["s-1"])
        self.assertEqual(merged["uncovered_material"], [])

    def test_partial_journey_counts_as_covered(self):
        result = {
            "surfaces": [self.surface("s-1")],
            "journeys": [
                {
                    "id": "j-1",
                    "surface_ids": ["s-1"],
                    "outcome": "partial",
                    "evidence_refs": ["evidence/b.png"],
                }
            ],
        }
        merged = resume.merge_coverage([result])
        self.assertTrue(merged["surfaces"]["s-1"]["covered"])

    def test_empty_evidence_refs_do_not_cover(self):
        for refs in ([], None, "evidence/a.png"):
            with self.subTest(refs=refs):
                result = {
                    "surfaces": [self.surface("s-1")],
                    "journeys": [
                        {
                            "id": "j-1",
                            "surface_ids": ["s-1"],
                            "outcome": "covered",
                            "evidence_refs": refs,
                        }
                    ],
                }
                merged = resume.merge_coverage([result])
                self.assertFalse(merged["surfaces"]["s-1"]["covered"])
                self.assertEqual(merged["uncovered_material"], ["s-1"])

    def test_failed_journey_with_evidence_does_not_cover(self):
        result = {
            "surfaces": [self.surface("s-1")],
            "journeys": [
                {
                    "id": "j-1",
                    "surface_ids": ["s-1"],
                    "outcome": "failed",
                    "evidence_refs": ["evidence/crash.log"],
                }
            ],
        }
        merged = resume.merge_coverage([result])
        self.assertFalse(merged["surfaces"]["s-1"]["covered"])
        self.assertEqual(merged["surfaces"]["s-1"]["evidence_refs"], [])

    def test_finding_goes_to_finding_refs_only(self):
        result = {
            "surfaces": [self.surface("s-1")],
            "findings": [
                {
                    "id": "f-1",
                    "surface_ids": ["s-1"],
                    "evidence_refs": ["evidence/error.png"],
                }
            ],
        }
        merged = resume.merge_coverage([result])
        record = merged["surfaces"]["s-1"]
        self.assertFalse(record["covered"])
        self.assertEqual(record["finding_refs"], ["f-1"])
        self.assertEqual(record["evidence_refs"], [])
        self.assertEqual(merged["uncovered_material"], ["s-1"])

    def test_duplicate_findings_are_deduplicated(self):
        result = {
            "surfaces": [self.surface("s-1")],
            "findings": [
                {"id": "f-1", "surface_ids": ["s-1"]},
                {"id": "f-1", "surface_ids": ["s-1", "s-9"]},
            ],
        }
        merged = resume.merge_coverage([result])
        self.assertEqual(merged["surfaces"]["s-1"]["finding_refs"], ["f-1"])

    def test_multiple_results_union_evidence_and_dedup(self):
        first = {
            "surfaces": [self.surface("s-1"), self.surface("s-2")],
            "journeys": [
                {
                    "id": "j-1",
                    "surface_ids": ["s-1"],
                    "outcome": "covered",
                    "evidence_refs": ["evidence/a.png", "evidence/shared.png"],
                }
            ],
        }
        second = {
            "surfaces": [self.surface("s-1")],
            "journeys": [
                {
                    "id": "j-2",
                    "surface_ids": ["s-1", "s-2"],
                    "outcome": "partial",
                    "evidence_refs": ["evidence/shared.png", "evidence/b.png"],
                }
            ],
        }
        merged = resume.merge_coverage([first, second])
        self.assertEqual(
            merged["surfaces"]["s-1"]["evidence_refs"],
            ["evidence/a.png", "evidence/shared.png", "evidence/b.png"],
        )
        self.assertTrue(merged["surfaces"]["s-2"]["covered"])
        self.assertEqual(merged["covered_material"], ["s-1", "s-2"])
        self.assertEqual(merged["uncovered_material"], [])

    def test_material_and_uncovered_lists_exclude_peripheral(self):
        result = {
            "surfaces": [
                self.surface("s-material"),
                self.surface("s-peripheral", importance="peripheral"),
            ],
            "journeys": [
                {
                    "id": "j-1",
                    "surface_ids": ["s-peripheral"],
                    "outcome": "covered",
                    "evidence_refs": ["evidence/p.png"],
                }
            ],
        }
        merged = resume.merge_coverage([result])
        self.assertTrue(merged["surfaces"]["s-peripheral"]["covered"])
        self.assertEqual(merged["covered_material"], [])
        self.assertEqual(merged["uncovered_material"], ["s-material"])

    def test_importance_union_across_results(self):
        first = {"surfaces": [self.surface("s-1", importance="peripheral")]}
        second = {"surfaces": [self.surface("s-1", importance="material")]}
        merged = resume.merge_coverage([first, second])
        self.assertTrue(merged["surfaces"]["s-1"]["material"])
        self.assertEqual(merged["uncovered_material"], ["s-1"])

    def test_unknown_surface_references_are_ignored(self):
        result = {
            "surfaces": [self.surface("s-1")],
            "journeys": [
                {
                    "id": "j-1",
                    "surface_ids": ["s-missing"],
                    "outcome": "covered",
                    "evidence_refs": ["evidence/a.png"],
                }
            ],
            "findings": [{"id": "f-1", "surface_ids": ["s-missing"]}],
        }
        merged = resume.merge_coverage([result])
        self.assertEqual(sorted(merged["surfaces"]), ["s-1"])
        self.assertEqual(merged["uncovered_material"], ["s-1"])

    def test_non_string_refs_and_ids_are_ignored(self):
        result = {
            "surfaces": [self.surface("s-1"), {"id": None}, {"id": 3}, "surface", None],
            "journeys": [
                {
                    "id": "j-1",
                    "surface_ids": ["s-1"],
                    "outcome": "covered",
                    "evidence_refs": ["evidence/a.png", None, 5, ""],
                }
            ],
        }
        merged = resume.merge_coverage([result])
        self.assertEqual(merged["surfaces"]["s-1"]["evidence_refs"], ["evidence/a.png"])
        self.assertEqual(sorted(merged["surfaces"]), ["s-1"])

    def test_malformed_results_never_raise(self):
        garbage = [
            None,
            42,
            "result",
            {"surfaces": "nope"},
            {"surfaces": [None], "journeys": [None], "findings": [None]},
            {"journeys": {"surface_ids": ["s-1"]}},
            {"findings": [{"id": "f-1", "surface_ids": "s-1"}]},
        ]
        merged = resume.merge_coverage(garbage)
        self.assertEqual(
            merged,
            {"surfaces": {}, "covered_material": [], "uncovered_material": []},
        )

    def test_non_list_input_returns_empty_shape(self):
        for value in (None, {"surfaces": []}, "results"):
            with self.subTest(value=value):
                merged = resume.merge_coverage(value)
                self.assertEqual(merged["surfaces"], {})
                self.assertEqual(merged["covered_material"], [])
                self.assertEqual(merged["uncovered_material"], [])


class NoProgressBreakerTests(unittest.TestCase):
    def test_three_same_signatures_stop(self):
        outcome = resume.no_progress_breaker(["E_A", "E_A", "E_A"])
        self.assertTrue(outcome["stop"])
        self.assertEqual(outcome["signature"], "E_A")
        self.assertEqual(outcome["count"], 3)
        self.assertTrue(outcome["reason"])

    def test_two_same_signatures_do_not_stop(self):
        outcome = resume.no_progress_breaker(["E_A", "E_A"])
        self.assertFalse(outcome["stop"])
        self.assertEqual(outcome["signature"], "E_A")
        self.assertEqual(outcome["count"], 2)
        self.assertIsNone(outcome["reason"])

    def test_a_different_signature_resets_the_count(self):
        outcome = resume.no_progress_breaker(["E_A", "E_A", "E_B"])
        self.assertFalse(outcome["stop"])
        self.assertEqual(outcome["signature"], "E_B")
        self.assertEqual(outcome["count"], 1)

    def test_only_the_trailing_run_matters(self):
        outcome = resume.no_progress_breaker(["E_A", "E_A", "E_B", "E_B", "E_B"])
        self.assertTrue(outcome["stop"])
        self.assertEqual(outcome["signature"], "E_B")
        self.assertEqual(outcome["count"], 3)

    def test_custom_max_same(self):
        outcome = resume.no_progress_breaker(["E_A", "E_A"], max_same=2)
        self.assertTrue(outcome["stop"])

    def test_trailing_run_longer_than_limit_reports_full_count(self):
        outcome = resume.no_progress_breaker(["E_A"] * 5)
        self.assertTrue(outcome["stop"])
        self.assertEqual(outcome["count"], 5)

    def test_empty_and_malformed_input_do_not_stop_or_raise(self):
        for value in ([], (), None, "E_A", 42, {"E_A": 1}):
            with self.subTest(value=value):
                outcome = resume.no_progress_breaker(value)
                self.assertFalse(outcome["stop"])
                self.assertIsInstance(outcome, dict)
        empty = resume.no_progress_breaker([])
        self.assertIsNone(empty["signature"])
        self.assertEqual(empty["count"], 0)

    def test_invalid_max_same_falls_back_and_zero_clamps(self):
        self.assertTrue(resume.no_progress_breaker(["E"] * 3, max_same="bad")["stop"])
        self.assertTrue(resume.no_progress_breaker(["E"], max_same=0)["stop"])
        self.assertFalse(resume.no_progress_breaker(["E"], max_same=2)["stop"])

    def test_structured_signatures_compare_by_value(self):
        signature = {"step": "open", "error": "E_A"}
        outcome = resume.no_progress_breaker([signature, dict(signature), dict(signature)])
        self.assertTrue(outcome["stop"])


class LeaseRecordTests(unittest.TestCase):
    def test_default_record_shape(self):
        record = resume.lease_record(
            "ui:web", "sess-1", "cand-1", "2026-09-21T10:00:00Z"
        )
        self.assertEqual(record["schema"], "observation-lease/1")
        self.assertEqual(record["resource_id"], "ui:web")
        self.assertEqual(record["owner_session"], "sess-1")
        self.assertEqual(record["candidate_id"], "cand-1")
        self.assertEqual(record["acquired_at"], "2026-09-21T10:00:00Z")
        self.assertEqual(record["status"], "active")
        self.assertIsNone(record["note"])

    def test_custom_status_and_note(self):
        record = resume.lease_record(
            "desktop:1", "sess-2", "cand-2", "2026-09-21T10:00:00Z",
            status="released", note="handed back",
        )
        self.assertEqual(record["status"], "released")
        self.assertEqual(record["note"], "handed back")

    def test_valid_record_validates_clean(self):
        self.assertEqual(resume.validate_lease(lease()), [])

    def test_validate_never_raises_on_malformed_input(self):
        for value in (None, "lease", 42, [], {"schema": "observation-lease/1"}):
            with self.subTest(value=value):
                problems = resume.validate_lease(value)
                self.assertIsInstance(problems, list)
                self.assertTrue(problems)

    def test_validate_reports_each_missing_field(self):
        problems = resume.validate_lease({"schema": "observation-lease/1"})
        joined = " ".join(problems)
        for field in ("resource_id", "owner_session", "candidate_id", "acquired_at", "status"):
            self.assertIn(field, joined)

    def test_validate_rejects_wrong_schema(self):
        problems = resume.validate_lease(lease(schema="observation-lease/2"))
        self.assertTrue(any("schema" in p for p in problems))

    def test_validate_note_type(self):
        self.assertEqual(resume.validate_lease(lease(note="ok")), [])
        self.assertTrue(resume.validate_lease(lease(note=7)))


class LeaseRequiredTests(unittest.TestCase):
    def test_ui_activities_require_a_lease(self):
        for activity in ("ui-operate", "backend-run"):
            self.assertTrue(resume.lease_required(activity))

    def test_media_and_read_only_activities_need_no_lease(self):
        for activity in ("media-analysis", "evidence-review", "read-only"):
            self.assertFalse(resume.lease_required(activity))

    def test_unknown_or_malformed_activity_requires_a_lease(self):
        for activity in ("", "deploy", None, 42, ["ui-operate"], {"activity": "read-only"}):
            with self.subTest(activity=activity):
                self.assertTrue(resume.lease_required(activity))


class LeaseProblemsTests(unittest.TestCase):
    def test_active_fresh_registered_lease_has_no_problems(self):
        self.assertEqual(
            resume.lease_problems(
                lease(),
                resources=["ui:web", "desktop:1"],
                now="2026-09-21T10:30:00Z",
            ),
            [],
        )

    def test_unregistered_resource_is_reported(self):
        problems = resume.lease_problems(
            lease(), resources=["desktop:1"], now="2026-09-21T10:30:00Z"
        )
        self.assertTrue(any("not registered" in p for p in problems))

    def test_non_active_status_is_not_held(self):
        problems = resume.lease_problems(
            lease(status="released"),
            resources=["ui:web"],
            now="2026-09-21T10:30:00Z",
        )
        self.assertTrue(any("not held" in p for p in problems))

    def test_stale_lease_is_reported(self):
        problems = resume.lease_problems(
            lease(acquired_at="2026-09-21T09:00:00Z"),
            resources=["ui:web"],
            now="2026-09-21T10:30:00Z",
            max_age_seconds=3600,
        )
        self.assertTrue(any("stale" in p for p in problems))

    def test_age_equal_to_max_is_not_stale(self):
        problems = resume.lease_problems(
            lease(acquired_at="2026-09-21T10:00:00Z"),
            resources=["ui:web"],
            now="2026-09-21T11:00:00Z",
            max_age_seconds=3600,
        )
        self.assertEqual(problems, [])

    def test_unparsable_acquired_at_is_stale(self):
        problems = resume.lease_problems(
            lease(acquired_at="yesterday"),
            resources=["ui:web"],
            now="2026-09-21T10:30:00Z",
        )
        self.assertTrue(any("stale" in p for p in problems))

    def test_missing_owner_session_is_reported(self):
        problems = resume.lease_problems(
            lease(owner_session="  "), resources=["ui:web"], now=1758450600.0
        )
        self.assertTrue(any("owner_session" in p for p in problems))

    def test_non_object_lease_returns_structure_problem(self):
        self.assertEqual(
            resume.lease_problems(None, resources=[], now=0),
            ["lease must be a JSON object"],
        )

    def test_unparsable_now_is_reported(self):
        problems = resume.lease_problems(
            lease(), resources=["ui:web"], now="not-a-time"
        )
        self.assertTrue(any("now" in p for p in problems))

    def test_resources_must_be_a_collection(self):
        for resources in (None, "ui:web", b"ui:web"):
            with self.subTest(resources=resources):
                problems = resume.lease_problems(
                    lease(), resources=resources, now="2026-09-21T10:30:00Z"
                )
                self.assertTrue(any("resources" in p for p in problems))

    def test_epoch_seconds_are_accepted_for_now(self):
        moment = datetime.datetime(
            2026, 9, 21, 10, 30, tzinfo=datetime.timezone.utc
        ).timestamp()
        fresh = resume.lease_problems(
            lease(), resources={"ui:web"}, now=moment, max_age_seconds=3600
        )
        self.assertEqual(fresh, [])
        stale = resume.lease_problems(
            lease(acquired_at="2026-09-21T09:00:00Z"),
            resources={"ui:web"},
            now=moment,
            max_age_seconds=1800,
        )
        self.assertTrue(any("stale" in p for p in stale))

    def test_invalid_max_age_falls_back_to_default(self):
        problems = resume.lease_problems(
            lease(), resources=["ui:web"], now="2026-09-21T10:30:00Z",
            max_age_seconds="soon",
        )
        self.assertEqual(problems, [])

    def test_never_raises_on_garbage(self):
        for lease_value in (None, "lease", 3, [], {"schema": 1}):
            for resources in (None, 7, object()):
                with self.subTest(lease=lease_value, resources=resources):
                    problems = resume.lease_problems(
                        lease_value, resources=resources, now=None
                    )
                    self.assertIsInstance(problems, list)


class DocstringTests(unittest.TestCase):
    def test_module_docstring_pins_the_resume_rules(self):
        text = " ".join((resume.__doc__ or "").split())
        for phrase in (
            "budget-exhausted",
            "new run",
            "new round",
            "never overwritten",
            "media-analysis",
            "lease",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
