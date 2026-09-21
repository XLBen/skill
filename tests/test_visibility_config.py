"""S11: project visibility settings -- catalog parsing, request disambiguation,
atomic persistence, capability marking, and the /visibility CLI.

The fixture catalog is the real `opencode models` output recorded in
`docs/po-repair/baseline/s01/models-list.txt` (S01), including duplicates,
blank lines and non-model noise, so matching is tested against the host's
actual catalog instead of invented model ids.
"""

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import visibility_config as vc  # noqa: E402

CATALOG_TEXT = """\
opencode/big-pickle
opencode/ling-3.0-flash-fin-free
opencode/mimo-v2.5-free
opencode/muse-spark-1.2-contributor-free
opencode/muse-spark-1.3-contributor-free
opencode/nemotron-3-ultra-free
opencode/nemotron-3.5-lightning-free
deepseek/deepseek-flash
deepseek/deepseek-v4-flash
deepseek/deepseek-v4-flash-vision-exp
deepseek/deepseek-v4-pro
openai/gpt-5.3-codex-spark
openai/gpt-5.4
openai/gpt-5.4-fast
openai/gpt-5.4-mini
openai/gpt-5.4-mini-fast
openai/gpt-5.5
openai/gpt-5.5-fast
openai/gpt-5.6-luna
openai/gpt-5.6-luna-fast
openai/gpt-5.6-sol
openai/gpt-5.6-sol-fast
openai/gpt-5.6-terra
openai/gpt-5.6-terra-fast
zhipuai-coding-plan/glm-4.6v
zhipuai-coding-plan/glm-5.3
zhipuai-coding-plan/glm-5.3-flash
zhipuai-coding-plan/glm-5.3-highspeed
"""


def catalog():
    return vc.parse_catalog(CATALOG_TEXT)


def sample_document(request="gpt 5.6 luna"):
    return {
        "schema": vc.VISIBILITY_SCHEMA,
        "updated_at": "2026-09-21T00:00:00Z",
        "selection": {
            "requested_name": request,
            "provider_id": "openai",
            "model_id": "gpt-5.6-luna",
            "status": "selected",
            "capabilities": dict(vc.DEFAULT_CAPABILITIES),
        },
    }


class TemporaryProjectCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = self.tmp / "project"
        (self.project / ".opencode" / "mvp").mkdir(parents=True)
        self.path = vc.visibility_path(self.project)

    def write_catalog_file(self, text=CATALOG_TEXT, name="models.txt", encoding="utf-8-sig"):
        target = self.tmp / name
        target.write_text(text, encoding=encoding)
        return target

    def run_cli(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = vc.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()


class ParseCatalogTests(unittest.TestCase):
    def test_parses_real_catalog_with_fields(self):
        entries = catalog()
        self.assertEqual(len(entries), 28)
        self.assertEqual(
            entries[0],
            {
                "provider_id": "opencode",
                "model_id": "big-pickle",
                "full": "opencode/big-pickle",
            },
        )

    def test_ignores_blank_and_junk_lines(self):
        text = "openai/gpt-5.6-luna\n\nnot a model\nwarning: something\n/model\nopenai/\n"
        entries = vc.parse_catalog(text)
        self.assertEqual([entry["full"] for entry in entries], ["openai/gpt-5.6-luna"])

    def test_deduplicates_repeated_lines(self):
        text = "a/one\na/one\na/two\n"
        entries = vc.parse_catalog(text)
        self.assertEqual([entry["full"] for entry in entries], ["a/one", "a/two"])

    def test_handles_crlf_and_bom(self):
        entries = vc.parse_catalog("\ufeffa/one\r\n\r\nb/two\r\n")
        self.assertEqual([entry["full"] for entry in entries], ["a/one", "b/two"])

    def test_non_string_is_empty(self):
        self.assertEqual(vc.parse_catalog(None), [])
        self.assertEqual(vc.parse_catalog(b"a/b"), [])


class NormalizeKeyTests(unittest.TestCase):
    def test_lowercases_and_collapses_separators(self):
        self.assertEqual(vc.normalize_key(" GPT_5.6  Luna "), "gpt-5.6-luna")
        self.assertEqual(vc.normalize_key("DeepSeek\tV4"), "deepseek-v4")

    def test_strips_outer_hyphens(self):
        self.assertEqual(vc.normalize_key("--luna--"), "luna")

    def test_non_string_is_empty(self):
        self.assertEqual(vc.normalize_key(None), "")
        self.assertEqual(vc.normalize_key(7), "")


class MatchModelsTests(unittest.TestCase):
    def test_default_request_resolves_to_the_real_luna(self):
        result = vc.match_models(vc.DEFAULT_REQUEST, catalog())
        self.assertEqual(result["query"], vc.DEFAULT_REQUEST)
        self.assertEqual(
            [entry["full"] for entry in result["matches"]],
            ["openai/gpt-5.6-luna"],
        )
        self.assertEqual(result["mode"], "unique")

    def test_full_id_is_exact(self):
        result = vc.match_models("openai/gpt-5.6-luna", catalog())
        self.assertEqual(result["mode"], "exact")
        self.assertEqual([entry["full"] for entry in result["matches"]], ["openai/gpt-5.6-luna"])

    def test_case_and_space_variant_of_full_is_exact(self):
        result = vc.match_models("OpenAI/GPT 5.6 Luna", catalog())
        self.assertEqual(result["mode"], "exact")
        self.assertEqual([entry["full"] for entry in result["matches"]], ["openai/gpt-5.6-luna"])

    def test_bare_model_id_is_unique(self):
        result = vc.match_models("deepseek-v4-flash-vision-exp", catalog())
        self.assertEqual(result["mode"], "unique")
        self.assertEqual(
            [entry["full"] for entry in result["matches"]],
            ["deepseek/deepseek-v4-flash-vision-exp"],
        )

    def test_provider_only_is_ambiguous_with_four_deepseek_models(self):
        result = vc.match_models("deepseek", catalog())
        self.assertEqual(result["mode"], "ambiguous")
        self.assertEqual(
            [entry["full"] for entry in result["matches"]],
            [
                "deepseek/deepseek-flash",
                "deepseek/deepseek-v4-flash",
                "deepseek/deepseek-v4-flash-vision-exp",
                "deepseek/deepseek-v4-pro",
            ],
        )

    def test_token_subset_can_be_unique(self):
        result = vc.match_models("vision exp", catalog())
        self.assertEqual(result["mode"], "unique")
        self.assertEqual(
            [entry["full"] for entry in result["matches"]],
            ["deepseek/deepseek-v4-flash-vision-exp"],
        )

    def test_token_subset_with_several_hits_is_ambiguous(self):
        glm = vc.match_models("glm", catalog())
        self.assertEqual(glm["mode"], "ambiguous")
        self.assertEqual(len(glm["matches"]), 4)
        luna = vc.match_models("gpt luna", catalog())
        self.assertEqual(luna["mode"], "ambiguous")
        self.assertEqual(
            [entry["full"] for entry in luna["matches"]],
            ["openai/gpt-5.6-luna", "openai/gpt-5.6-luna-fast"],
        )

    def test_unknown_request_is_none_and_never_fabricated(self):
        result = vc.match_models("gpt 7 omega", catalog())
        self.assertEqual(result["mode"], "none")
        self.assertEqual(result["matches"], [])

    def test_empty_query_is_none(self):
        self.assertEqual(vc.match_models("", catalog())["mode"], "none")
        self.assertEqual(vc.match_models(None, catalog())["mode"], "none")
        self.assertEqual(vc.match_models("   ", catalog())["mode"], "none")

    def test_malformed_catalog_entries_are_ignored(self):
        result = vc.match_models(
            "gpt 5.6 luna",
            [
                "not a dict",
                {"full": "openai/gpt-5.6-luna", "provider_id": "openai", "model_id": "gpt-5.6-luna"},
                {"full": "bad", "provider_id": "", "model_id": "x"},
                None,
            ],
        )
        self.assertEqual(result["mode"], "unique")
        self.assertEqual(len(result["matches"]), 1)


class ResolveRequestTests(TemporaryProjectCase):
    def test_unique_request_persists_selection(self):
        result = vc.resolve_request(self.path, "gpt 5.6 luna", catalog())
        self.assertEqual(result["status"], "selected")
        selection = result["selection"]
        self.assertEqual(selection["requested_name"], "gpt 5.6 luna")
        self.assertEqual(selection["provider_id"], "openai")
        self.assertEqual(selection["model_id"], "gpt-5.6-luna")
        self.assertEqual(selection["status"], "selected")
        self.assertEqual(selection["capabilities"], dict(vc.DEFAULT_CAPABILITIES))
        data, problems = vc.load_visibility(self.path)
        self.assertEqual(problems, [])
        self.assertEqual(data["schema"], vc.VISIBILITY_SCHEMA)
        self.assertTrue(data["updated_at"])

    def test_default_request_persists_luna(self):
        result = vc.resolve_request(self.path, vc.DEFAULT_REQUEST, catalog())
        self.assertEqual(result["status"], "selected")
        self.assertEqual(result["selection"]["model_id"], "gpt-5.6-luna")

    def test_exact_full_request_persists(self):
        result = vc.resolve_request(self.path, "zhipuai-coding-plan/glm-4.6v", catalog())
        self.assertEqual(result["status"], "selected")
        self.assertEqual(result["selection"]["provider_id"], "zhipuai-coding-plan")
        self.assertEqual(result["selection"]["model_id"], "glm-4.6v")

    def test_ambiguous_request_does_not_write(self):
        result = vc.resolve_request(self.path, "deepseek", catalog())
        self.assertEqual(result["status"], "needs-selection")
        self.assertEqual(len(result["candidates"]), 4)
        self.assertIn("deepseek/deepseek-v4-pro", result["candidates"])
        self.assertFalse(self.path.exists())

    def test_not_found_request_does_not_write(self):
        result = vc.resolve_request(self.path, "nothing-like-this", catalog())
        self.assertEqual(result, {"status": "not-found"})
        self.assertFalse(self.path.exists())

    def test_repeat_resolution_preserves_capabilities(self):
        vc.resolve_request(self.path, "gpt 5.6 luna", catalog())
        data, problems = vc.mark_capability(
            self.path, "image", "verified", "baseline/s16/red.png"
        )
        self.assertEqual(problems, [])
        self.assertEqual(data["selection"]["capabilities"]["image"], "verified")
        again = vc.resolve_request(self.path, "gpt 5.6 luna", catalog())
        self.assertEqual(again["status"], "selected")
        self.assertEqual(again["selection"]["capabilities"]["image"], "verified")
        self.assertEqual(again["selection"]["capabilities"]["video"], "unverified")
        self.assertEqual(again["selection"]["capabilities"]["audio"], "unverified")

    def test_default_capabilities_are_not_mutated(self):
        result = vc.resolve_request(self.path, "gpt 5.6 luna", catalog())
        result["selection"]["capabilities"]["image"] = "verified"
        self.assertEqual(
            vc.DEFAULT_CAPABILITIES["image"],
            "unverified",
        )
        self.assertEqual(
            vc.DEFAULT_CAPABILITIES,
            {"image": "unverified", "video": "unverified", "audio": "unverified"},
        )

    def test_save_failure_is_reported_without_crashing(self):
        shutil.rmtree(self.project / ".opencode")
        result = vc.resolve_request(self.path, "gpt 5.6 luna", catalog())
        self.assertEqual(result["status"], "error")
        self.assertTrue(result["problems"])


class SelectModelTests(TemporaryProjectCase):
    def test_valid_full_id_is_persisted(self):
        data, problems = vc.select_model(self.path, "openai/gpt-5.6-luna")
        self.assertEqual(problems, [])
        self.assertEqual(data["selection"]["requested_name"], "openai/gpt-5.6-luna")
        self.assertEqual(data["selection"]["model_id"], "gpt-5.6-luna")
        loaded, load_problems = vc.load_visibility(self.path)
        self.assertEqual(load_problems, [])
        self.assertEqual(loaded["selection"], data["selection"])

    def test_invalid_full_id_keeps_existing_file(self):
        vc.select_model(self.path, "openai/gpt-5.6-luna")
        before = self.path.read_bytes()
        data, problems = vc.select_model(self.path, "gpt-5.6-luna")
        self.assertIsNone(data)
        self.assertTrue(problems)
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_forms_are_rejected(self):
        for bad in ("nope", "", "/luna", "openai/", "a/b/c", "open ai/luna", 7):
            data, problems = vc.select_model(self.path, bad)
            self.assertIsNone(data, bad)
            self.assertTrue(problems, bad)
        self.assertFalse(self.path.exists())


class MarkCapabilityTests(TemporaryProjectCase):
    def setUp(self):
        super().setUp()
        vc.select_model(self.path, "openai/gpt-5.6-luna")

    def test_verified_without_evidence_is_refused_and_file_unchanged(self):
        before = self.path.read_bytes()
        data, problems = vc.mark_capability(self.path, "image", "verified")
        self.assertIsNone(data)
        self.assertTrue(any("evidence" in problem for problem in problems))
        self.assertEqual(self.path.read_bytes(), before)

    def test_verified_with_evidence_updates_only_that_capability(self):
        data, problems = vc.mark_capability(
            self.path, "image", "verified", "docs/evidence/red.png"
        )
        self.assertEqual(problems, [])
        selection = data["selection"]
        self.assertEqual(selection["capabilities"]["image"], "verified")
        self.assertEqual(selection["capabilities"]["video"], "unverified")
        self.assertEqual(selection["capabilities"]["audio"], "unverified")
        self.assertEqual(
            selection["capability_evidence"], {"image": "docs/evidence/red.png"}
        )
        self.assertEqual(selection["model_id"], "gpt-5.6-luna")
        loaded, load_problems = vc.load_visibility(self.path)
        self.assertEqual(load_problems, [])
        self.assertEqual(loaded["selection"]["capabilities"]["image"], "verified")

    def test_unavailable_needs_no_evidence(self):
        data, problems = vc.mark_capability(self.path, "audio", "unavailable")
        self.assertEqual(problems, [])
        self.assertEqual(data["selection"]["capabilities"]["audio"], "unavailable")
        self.assertNotIn("capability_evidence", data["selection"])

    def test_invalid_capability_or_status_is_rejected(self):
        for capability in ("vision", None):
            data, problems = vc.mark_capability(self.path, capability, "verified", "x")
            self.assertIsNone(data)
            self.assertTrue(problems)
        for status in ("partial", None):
            data, problems = vc.mark_capability(self.path, "image", status, "x")
            self.assertIsNone(data)
            self.assertTrue(problems)

    def test_missing_file_fails_closed(self):
        self.path.unlink()
        data, problems = vc.mark_capability(self.path, "image", "verified", "ref")
        self.assertIsNone(data)
        self.assertTrue(any("select a model" in problem for problem in problems))


class LoadSaveTests(TemporaryProjectCase):
    def test_missing_file_is_none_and_empty(self):
        self.assertEqual(vc.load_visibility(self.path), (None, []))

    def test_roundtrip(self):
        document = sample_document()
        self.assertEqual(vc.save_visibility(self.path, document), [])
        loaded, problems = vc.load_visibility(self.path)
        self.assertEqual(problems, [])
        self.assertEqual(loaded, document)

    def test_bom_and_capability_evidence_load(self):
        document = sample_document()
        document["selection"]["capability_evidence"] = {"image": "ref.png"}
        self.path.write_text(
            json.dumps(document, ensure_ascii=False), encoding="utf-8-sig"
        )
        loaded, problems = vc.load_visibility(self.path)
        self.assertEqual(problems, [])
        self.assertEqual(loaded["selection"]["capability_evidence"], {"image": "ref.png"})

    def test_invalid_json_is_rejected(self):
        self.path.write_text("{not json}", encoding="utf-8")
        loaded, problems = vc.load_visibility(self.path)
        self.assertIsNone(loaded)
        self.assertTrue(any("not valid JSON" in problem for problem in problems))

    def test_duplicate_keys_are_rejected(self):
        self.path.write_text(
            '{"schema": "workflow-visibility/1", "schema": "workflow-visibility/1"}',
            encoding="utf-8",
        )
        loaded, problems = vc.load_visibility(self.path)
        self.assertIsNone(loaded)
        self.assertTrue(problems)

    def test_structural_problems_are_rejected(self):
        cases = {
            "non-object": [],
            "wrong-schema": dict(sample_document(), schema="workflow-visibility/2"),
            "no-updated-at": {
                key: value
                for key, value in sample_document().items()
                if key != "updated_at"
            },
            "unknown-field": dict(sample_document(), note="x"),
            "bad-capability": {
                **sample_document(),
                "selection": {
                    **sample_document()["selection"],
                    "capabilities": {
                        "image": "maybe",
                        "video": "unverified",
                        "audio": "unverified",
                    },
                },
            },
            "missing-tag": {
                **sample_document(),
                "selection": {
                    **sample_document()["selection"],
                    "capabilities": {"image": "unverified", "video": "unverified"},
                },
            },
            "unknown-selection-field": {
                **sample_document(),
                "selection": {**sample_document()["selection"], "extra": 1},
            },
            "bad-evidence-key": {
                **sample_document(),
                "selection": {
                    **sample_document()["selection"],
                    "capability_evidence": {"sound": "x"},
                },
            },
        }
        for label, document in cases.items():
            with self.subTest(label=label):
                problems = vc.validate_visibility(document)
                self.assertTrue(problems, label)
                self.assertFalse(self.path.exists(), label)
                self.assertTrue(vc.save_visibility(self.path, document), label)
                self.assertFalse(self.path.exists(), label)

    def test_invalid_save_keeps_existing_bytes(self):
        self.assertEqual(vc.save_visibility(self.path, sample_document()), [])
        before = self.path.read_bytes()
        self.assertTrue(vc.save_visibility(self.path, {"schema": "nope"}))
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_parent_directory_is_not_created(self):
        target = self.tmp / "missing" / "visibility.json"
        problems = vc.save_visibility(target, sample_document())
        self.assertTrue(any("does not exist" in problem for problem in problems))
        self.assertFalse(target.parent.exists())

    def test_replace_failure_is_atomic(self):
        self.assertEqual(vc.save_visibility(self.path, sample_document()), [])
        before = self.path.read_bytes()
        with mock.patch.object(vc.os, "replace", side_effect=OSError("boom")):
            problems = vc.save_visibility(self.path, sample_document("deepseek-v4-pro"))
        self.assertTrue(problems)
        self.assertEqual(self.path.read_bytes(), before)
        leftovers = sorted(p.name for p in self.path.parent.glob("visibility.json.*.tmp"))
        self.assertEqual(leftovers, [])


class ShowTests(TemporaryProjectCase):
    def test_unconfigured(self):
        result = vc.show(self.path)
        self.assertEqual(result["status"], "unconfigured")
        self.assertIsNone(result["selection"])
        self.assertEqual(result["default_request"], vc.DEFAULT_REQUEST)

    def test_selected(self):
        vc.select_model(self.path, "openai/gpt-5.6-luna")
        result = vc.show(self.path)
        self.assertEqual(result["status"], "selected")
        self.assertEqual(result["selection"]["model_id"], "gpt-5.6-luna")

    def test_invalid_file(self):
        self.path.write_text("{not json}", encoding="utf-8")
        result = vc.show(self.path)
        self.assertEqual(result["status"], "invalid")
        self.assertTrue(result["problems"])


class VisibilityPathTests(unittest.TestCase):
    def test_frozen_project_layout(self):
        self.assertEqual(
            vc.visibility_path("proj"),
            Path("proj") / ".opencode" / "mvp" / "visibility.json",
        )
        self.assertEqual(vc.VISIBILITY_SCHEMA, "workflow-visibility/1")
        self.assertEqual(vc.DEFAULT_REQUEST, "gpt 5.6 luna")


class CliTests(TemporaryProjectCase):
    def setUp(self):
        super().setUp()
        self.catalog_file = self.write_catalog_file()

    def set_argv(self, *extra):
        return [
            "set",
            "--project",
            str(self.project),
            "--catalog-file",
            str(self.catalog_file),
            *extra,
        ]

    def test_set_default_request_selects_luna(self):
        code, stdout, stderr = self.run_cli(self.set_argv())
        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["status"], "selected")
        self.assertEqual(payload["selection"]["requested_name"], vc.DEFAULT_REQUEST)
        self.assertEqual(payload["selection"]["model_id"], "gpt-5.6-luna")
        self.assertTrue(self.path.is_file())

    def test_set_with_explicit_request(self):
        code, stdout, stderr = self.run_cli(self.set_argv("--request", "OpenAI/GPT 5.6 Luna"))
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["selection"]["provider_id"], "openai")

    def test_set_ambiguous_returns_3(self):
        code, stdout, stderr = self.run_cli(self.set_argv("--request", "deepseek"))
        self.assertEqual(code, 3, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["status"], "needs-selection")
        self.assertEqual(len(payload["candidates"]), 4)
        self.assertFalse(self.path.exists())

    def test_set_not_found_returns_4(self):
        code, stdout, _ = self.run_cli(self.set_argv("--request", "nothing-like-this"))
        self.assertEqual(code, 4)
        self.assertEqual(json.loads(stdout), {"status": "not-found"})
        self.assertFalse(self.path.exists())

    def test_set_catalog_error_returns_2(self):
        code, stdout, stderr = self.run_cli(
            [
                "set",
                "--project",
                str(self.project),
                "--catalog-file",
                str(self.tmp / "no-such-file.txt"),
                "--request",
                "gpt 5.6 luna",
            ]
        )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("cannot read catalog file", stderr)

    def test_set_ignores_junk_catalog_lines(self):
        noisy = self.write_catalog_file(
            "warning: stale cache\n\n" + CATALOG_TEXT + "not/a model\n", name="noisy.txt"
        )
        code, stdout, stderr = self.run_cli(
            [
                "set",
                "--project",
                str(self.project),
                "--catalog-file",
                str(noisy),
                "--request",
                "gpt 5.6 luna",
            ]
        )
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["status"], "selected")

    def test_select_then_show(self):
        code, stdout, stderr = self.run_cli(
            [
                "select",
                "--project",
                str(self.project),
                "--model",
                "deepseek/deepseek-v4-flash-vision-exp",
            ]
        )
        self.assertEqual(code, 0, stderr)
        self.assertEqual(
            json.loads(stdout)["selection"]["model_id"], "deepseek-v4-flash-vision-exp"
        )
        code, stdout, stderr = self.run_cli(["show", "--project", str(self.project)])
        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["status"], "selected")
        self.assertEqual(
            payload["selection"]["provider_id"], "deepseek"
        )

    def test_select_invalid_returns_2(self):
        code, stdout, stderr = self.run_cli(
            ["select", "--project", str(self.project), "--model", "no-slash"]
        )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("provider/model", stderr)
        self.assertFalse(self.path.exists())

    def test_show_unconfigured_returns_0(self):
        code, stdout, stderr = self.run_cli(["show", "--project", str(self.project)])
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["status"], "unconfigured")

    def test_show_invalid_returns_2(self):
        self.path.write_text("{not json}", encoding="utf-8")
        code, stdout, stderr = self.run_cli(["show", "--project", str(self.project)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout)["status"], "invalid")
        self.assertIn("-", stderr)

    def test_mark_cli_requires_evidence_and_records_it(self):
        self.run_cli(
            [
                "select",
                "--project",
                str(self.project),
                "--model",
                "openai/gpt-5.6-luna",
            ]
        )
        code, stdout, stderr = self.run_cli(
            [
                "mark",
                "--project",
                str(self.project),
                "--capability",
                "image",
                "--status",
                "verified",
            ]
        )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("evidence", stderr)

        code, stdout, stderr = self.run_cli(
            [
                "mark",
                "--project",
                str(self.project),
                "--capability",
                "image",
                "--status",
                "verified",
                "--evidence",
                "docs/evidence/red.png",
            ]
        )
        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["status"], "marked")
        self.assertEqual(payload["value"], "verified")
        loaded, problems = vc.load_visibility(self.path)
        self.assertEqual(problems, [])
        self.assertEqual(
            loaded["selection"]["capability_evidence"]["image"], "docs/evidence/red.png"
        )

    def test_cli_never_touches_a_global_path(self):
        self.run_cli(self.set_argv())
        created = sorted(
            p.relative_to(self.project).as_posix()
            for p in self.project.rglob("*")
            if p.is_file()
        )
        self.assertEqual(created, [".opencode/mvp/visibility.json"])


if __name__ == "__main__":
    unittest.main()
