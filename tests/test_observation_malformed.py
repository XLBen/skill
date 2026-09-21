"""S03: malformed-input matrix and real-corpus regression for observation validators.

Every validator covered here must return a ``list[str]`` for arbitrary JSON
input, never raise, and never require a well-formed nested object. The corpus
part replays the 21 archived v1 results from ``docs/po-repair/corpus/`` through
the v2 entry points and records the classification in
``docs/po-repair/baseline/s03-corpus-regression.json``.
"""

import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import observation_contract as oc  # noqa: E402
import product_observation as po  # noqa: E402

CORPUS_DIR = ROOT / "docs" / "po-repair" / "corpus"
REGRESSION_PATH = ROOT / "docs" / "po-repair" / "baseline" / "s03-corpus-regression.json"
PACKET_HASH = "a" * 64
HASH_RE = re.compile(r"^[0-9a-f]{64}$")

MUTATIONS = (
    None,
    {},
    [],
    0,
    1.5,
    True,
    "text",
    {"nested": {"list": [1, {"x": None}]}},
)


def clone(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def with_mutation(base, path, value):
    payload = clone(base)
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return payload


def controller_fields():
    return {
        "goal_id": "G-OBS",
        "candidate_id": "cand-1",
        "observer_session_id": "ses_observer",
        "model": "provider/model",
        "packet_hash": PACKET_HASH,
        "received_at": "2026-09-21T00:00:00Z",
        "attempt": 1,
    }


def result_payload(phase="compare"):
    payload = oc.result_template(phase)
    payload.update(controller_fields())
    payload["capability_gaps"] = [{"channel": "web", "reason": "backend unavailable"}]
    return payload


def review_payload():
    review = oc.review_template()
    review.update(
        {
            "reviewer_session_id": "ses_reviewer",
            "model": "provider/model",
            "discover_hash": "b" * 64,
            "compare_hash": "c" * 64,
            "reviewed_at": "2026-09-21T01:00:00Z",
            "received_at": "2026-09-21T01:00:01Z",
            "attempt": 1,
        }
    )
    return review


def candidate_manifest():
    return {
        "schema": po.CANDIDATE_SCHEMA,
        "candidate_id": "cand-1",
        "entry": "python app.py",
        "environment": "local",
        "backend": "agent-browser",
        "files": [{"path": "app.py", "sha256": "d" * 64}],
        "test_data": [],
        "channels": [],
        "baseline": {"kind": "none", "refs": []},
        "runtime_state": [],
    }


def audit_sidecar(schema):
    return {
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


RESULT_PATHS = (
    ("schema",),
    ("phase",),
    ("stop_reason",),
    ("surfaces",),
    ("surfaces", 0, "id"),
    ("surfaces", 0, "name"),
    ("surfaces", 0, "importance"),
    ("surfaces", 0, "modes"),
    ("journeys",),
    ("journeys", 0, "id"),
    ("journeys", 0, "surface_ids"),
    ("journeys", 0, "evidence_refs"),
    ("journeys", 0, "outcome"),
    ("findings",),
    ("findings", 0, "id"),
    ("findings", 0, "surface_ids"),
    ("findings", 0, "severity"),
    ("findings", 0, "category"),
    ("findings", 0, "confidence"),
    ("findings", 0, "observed"),
    ("findings", 0, "expected_basis"),
    ("findings", 0, "reproduction"),
    ("findings", 0, "evidence_refs"),
    ("findings", 0, "status"),
    ("findings", 0, "difference_classification"),
    ("findings", 0, "owner_decision_ref"),
    ("findings", 0, "resolution_ref"),
    ("unobserved",),
    ("capability_gaps",),
    ("capability_gaps", 0, "channel"),
    ("capability_gaps", 0, "reason"),
    ("capability_gaps", 0, "evidence_refs"),
    ("continuation",),
    ("evidence_refs",),
    ("notes",),
    ("goal_id",),
    ("candidate_id",),
    ("observer_session_id",),
    ("model",),
    ("packet_hash",),
    ("received_at",),
    ("attempt",),
)

REVIEW_PATHS = (
    ("schema",),
    ("findings_validity",),
    ("coverage_adequacy",),
    ("verdict",),
    ("notes",),
    ("related_finding_ids",),
    ("reviewer_session_id",),
    ("model",),
    ("discover_hash",),
    ("compare_hash",),
    ("reviewed_at",),
    ("received_at",),
    ("attempt",),
)

CANDIDATE_PATHS = (
    ("schema",),
    ("candidate_id",),
    ("entry",),
    ("environment",),
    ("backend",),
    ("files",),
    ("files", 0),
    ("files", 0, "path"),
    ("files", 0, "sha256"),
    ("test_data",),
    ("channels",),
    ("baseline",),
    ("baseline", "kind"),
    ("baseline", "refs"),
    ("runtime_state",),
)

SIDECAR_PATHS = (
    ("schema",),
    ("goal_id",),
    ("current_candidate",),
    ("rounds",),
    ("rounds", 0),
    ("rounds", 0, "candidate_id"),
    ("rounds", 0, "discover_ref"),
    ("rounds", 0, "compare_ref"),
    ("rounds", 0, "review_ref"),
)

ENVELOPE_PATHS = (
    ("goal_id",),
    ("candidate_id",),
    ("observer_session_id",),
    ("model",),
    ("packet_hash",),
    ("received_at",),
    ("attempt",),
    ("phase",),
)


class ProblemListAssertions(unittest.TestCase):
    def assert_problems(self, func, *args, label=""):
        try:
            result = func(*args)
        except Exception as exc:  # pragma: no cover - failure path
            self.fail(f"{label or func.__name__} raised {type(exc).__name__}: {exc}")
        self.assertIsInstance(result, list, label or func.__name__)
        for item in result:
            self.assertIsInstance(item, str, f"{label or func.__name__}: {item!r}")


class TypeMatrixTests(ProblemListAssertions):
    def test_result_matrix(self):
        base = result_payload()
        for path in RESULT_PATHS:
            for value in MUTATIONS:
                with self.subTest(path=path, value=repr(value)):
                    payload = with_mutation(base, path, value)
                    label = f"validate_observation_report {path}"
                    self.assert_problems(po.validate_observation_report, payload, label=label)
                    label = f"validate_result_payload {path}"
                    self.assert_problems(oc.validate_result_payload, payload, label=label)

    def test_review_matrix(self):
        base = review_payload()
        for path in REVIEW_PATHS:
            for value in MUTATIONS:
                with self.subTest(path=path, value=repr(value)):
                    payload = with_mutation(base, path, value)
                    label = f"validate_observation_review {path}"
                    self.assert_problems(po.validate_observation_review, payload, label=label)
                    label = f"validate_review_payload {path}"
                    self.assert_problems(oc.validate_review_payload, payload, label=label)

    def test_candidate_manifest_matrix(self):
        base = candidate_manifest()
        for path in CANDIDATE_PATHS:
            for value in MUTATIONS:
                with self.subTest(path=path, value=repr(value)):
                    manifest = with_mutation(base, path, value)
                    label = f"validate_candidate_manifest {path}"
                    self.assert_problems(po.validate_candidate_manifest, manifest, label=label)

    def test_audit_sidecar_matrix(self):
        for schema in (po.AUDIT_SIDECAR_SCHEMA, "product-audit/1"):
            base = audit_sidecar(schema)
            for path in SIDECAR_PATHS:
                for value in MUTATIONS:
                    with self.subTest(schema=schema, path=path, value=repr(value)):
                        sidecar = with_mutation(base, path, value)
                        label = f"validate_audit_sidecar {schema} {path}"
                        self.assert_problems(po.validate_audit_sidecar, sidecar, label=label)

    def test_envelope_matrix(self):
        base = result_payload()
        for path in ENVELOPE_PATHS:
            for value in MUTATIONS:
                with self.subTest(path=path, value=repr(value)):
                    payload = with_mutation(base, path, value)
                    self.assert_problems(
                        oc.validate_result_envelope, payload, label=f"envelope {path}"
                    )
                    self.assert_problems(
                        oc.validate_result_envelope,
                        payload,
                        "G-OBS",
                        "cand-1",
                        PACKET_HASH,
                        "compare",
                        label=f"envelope expected {path}",
                    )

    def test_bare_inputs_never_raise(self):
        validators = (
            po.validate_observation_report,
            po.validate_observation_review,
            po.validate_candidate_manifest,
            po.validate_audit_sidecar,
            oc.validate_result_payload,
            oc.validate_review_payload,
            oc.validate_result_envelope,
        )
        bare_inputs = (None, {}, [], 0, 1.5, True, "text", {"a": {"b": [1, {"c": None}]}})
        for func in validators:
            for value in bare_inputs:
                with self.subTest(func=func.__name__, value=repr(value)):
                    self.assert_problems(func, value, label=func.__name__)

    def test_enum_fields_with_dict_values(self):
        enum_paths = (
            ("phase",),
            ("stop_reason",),
            ("surfaces", 0, "importance"),
            ("journeys", 0, "outcome"),
            ("findings", 0, "severity"),
            ("findings", 0, "category"),
            ("findings", 0, "confidence"),
            ("findings", 0, "status"),
            ("findings", 0, "difference_classification"),
        )
        base = result_payload()
        for path in enum_paths:
            with self.subTest(path=path):
                payload = with_mutation(base, path, {"enum": "object"})
                self.assert_problems(
                    po.validate_observation_report,
                    payload,
                    label=f"dict enum {path}",
                )

    def test_container_fields_with_dict_values(self):
        container_paths = (
            ("surfaces",),
            ("journeys",),
            ("findings",),
            ("unobserved",),
            ("capability_gaps",),
            ("evidence_refs",),
            ("continuation",),
            ("findings", 0, "surface_ids"),
            ("findings", 0, "evidence_refs"),
            ("journeys", 0, "surface_ids"),
            ("surfaces", 0, "modes"),
        )
        base = result_payload()
        for path in container_paths:
            with self.subTest(path=path):
                payload = with_mutation(base, path, {"container": "object"})
                self.assert_problems(
                    po.validate_observation_report,
                    payload,
                    label=f"dict container {path}",
                )


class LoadJsonTests(unittest.TestCase):
    def setUp(self):
        import shutil

        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _write(self, name, text, encoding="utf-8"):
        path = self.tmp / name
        path.write_text(text, encoding=encoding)
        return path

    def test_rejects_nan_and_infinity(self):
        for literal in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(literal=literal):
                data, error = po._load_json(
                    self._write("nonfinite.json", '{"value": ' + literal + "}")
                )
                self.assertIsNone(data)
                self.assertIsNotNone(error)
                self.assertIn("invalid JSON", error)
                self.assertIn("non-finite", error)

    def test_rejects_duplicate_keys(self):
        data, error = po._load_json(
            self._write("dup.json", '{"schema": "a", "schema": "b"}')
        )
        self.assertIsNone(data)
        self.assertIn("duplicate key", error)

    def test_empty_and_truncated_files(self):
        for name, text in (("empty.json", ""), ("truncated.json", "{")):
            with self.subTest(name=name):
                data, error = po._load_json(self._write(name, text))
                self.assertIsNone(data)
                self.assertIn("invalid JSON", error)

    def test_missing_file_is_unreadable(self):
        data, error = po._load_json(self.tmp / "missing.json")
        self.assertIsNone(data)
        self.assertIn("unreadable", error)

    def test_utf8_bom_is_accepted(self):
        path = self.tmp / "bom.json"
        path.write_bytes(b"\xef\xbb\xbf" + b'{"ok": true}')
        data, error = po._load_json(path)
        self.assertIsNone(error)
        self.assertEqual(data, {"ok": True})


def review_envelope_problems(review):
    problems = []
    if not isinstance(review, dict):
        return ["review envelope must be a JSON object"]
    session = review.get("reviewer_session_id")
    if not isinstance(session, str) or not session.strip():
        problems.append("reviewer_session_id must be a non-empty string")
    for field in ("discover_hash", "compare_hash"):
        value = review.get(field)
        if not isinstance(value, str) or not HASH_RE.fullmatch(value):
            problems.append(f"{field} must be a 64-character lowercase sha256 hex digest")
    return problems


class CorpusRegressionTests(unittest.TestCase):
    def test_corpus_never_raises_and_records_classification(self):
        files = sorted(CORPUS_DIR.rglob("*.result.json"))
        self.assertEqual(len(files), 21, [str(path) for path in files])

        totals = {"files": 0, "legacy": 0, "invalid": 0, "valid": 0, "unreadable": 0}
        entries = []
        for path in files:
            totals["files"] += 1
            kind = "review" if path.name == "review.result.json" else "report"
            data, error = po._load_json(path)
            entry = {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "kind": kind,
                "schema": data.get("schema") if isinstance(data, dict) else None,
                "verdict": None,
                "error_count": 0,
                "errors": [],
                "envelope_error_count": 0,
                "envelope_errors": [],
            }
            if error is not None:
                entry["verdict"] = "unreadable"
                entry["error_count"] = 1
                entry["errors"] = [error]
                totals["unreadable"] += 1
                entries.append(entry)
                continue

            try:
                if kind == "review":
                    problems = po.validate_observation_review(data)
                    envelope_problems = review_envelope_problems(data)
                else:
                    problems = po.validate_observation_report(data)
                    envelope_problems = oc.validate_result_envelope(data)
            except Exception as exc:  # pragma: no cover - failure path
                self.fail(f"{entry['path']} raised {type(exc).__name__}: {exc}")

            self.assertIsInstance(problems, list, entry["path"])
            for item in problems:
                self.assertIsInstance(item, str, entry["path"])
            self.assertIsInstance(envelope_problems, list, entry["path"])

            schema = entry["schema"]
            if problems == []:
                verdict = "valid"
            elif isinstance(schema, str) and schema.endswith("/1"):
                verdict = "legacy"
            else:
                verdict = "invalid"
            entry["verdict"] = verdict
            entry["error_count"] = len(problems)
            entry["errors"] = list(problems)
            entry["envelope_error_count"] = len(envelope_problems)
            entry["envelope_errors"] = list(envelope_problems)
            totals[verdict] += 1
            entries.append(entry)

        self.assertEqual(
            totals["legacy"] + totals["invalid"] + totals["valid"] + totals["unreadable"],
            21,
        )
        summary = {
            "generated_by": "tests/test_observation_malformed.py (S03)",
            "contract": "product-observation/2",
            "corpus_dir": CORPUS_DIR.relative_to(ROOT).as_posix(),
            "note": (
                "All archived corpus files are v1; each gets the single legacy "
                "migration diagnostic from validate_observation_report/review."
            ),
            "totals": totals,
            "files": entries,
        }
        REGRESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
        REGRESSION_PATH.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        saved = json.loads(REGRESSION_PATH.read_text(encoding="utf-8"))
        self.assertEqual(saved["totals"]["files"], 21)
        print(
            (
                "S03 corpus regression: files={files} legacy={legacy} "
                "invalid={invalid} valid={valid} unreadable={unreadable} -> {path}"
            ).format(path=REGRESSION_PATH.relative_to(ROOT).as_posix(), **totals)
        )


if __name__ == "__main__":
    unittest.main()
