"""S16: offline vision adapter surface, capability status and perception records.

Covers ``adapter_status`` (four states + malformed inputs), ``host_requirements``
(env / which / unverifiable), perception record validation and claim checks,
the stdlib color probe PNG generator, and ``dispatch_mode`` routing.

Everything here is offline: no model, no browser, no network, no GUI. Real
model/desktop verification is S21 and remains BLOCKED until run there.
"""

import hashlib
import random
import shutil
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import observation_vision as ov  # noqa: E402


def fake_which(found):
    calls = []

    def which(name):
        calls.append(name)
        return "/usr/bin/" + name if name in found else None

    which.calls = calls
    return which


def png_chunks(testcase, data):
    testcase.assertEqual(data[:8], ov.PNG_SIGNATURE)
    offset = 8
    chunks = []
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        tag = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        crc = struct.unpack(">I", data[offset + 8 + length : offset + 12 + length])[0]
        testcase.assertEqual(crc, zlib.crc32(tag + payload) & 0xFFFFFFFF)
        chunks.append((tag, payload))
        offset += 12 + length
    return chunks


class ConstantsAndAdapterDataTests(unittest.TestCase):
    def test_capability_and_status_enums(self):
        self.assertEqual(
            ov.VISION_CAPABILITIES,
            ("image_read", "visual_grounding", "desktop_control"),
        )
        self.assertEqual(
            ov.STATUSES,
            ("verified", "implemented-not-verified", "unavailable", "failed"),
        )

    def test_adapter_ids_and_keys(self):
        self.assertEqual(set(ov.ADAPTERS), {"direct-multimodal", "midscene", "ui-tars"})
        for key, adapter in ov.ADAPTERS.items():
            self.assertEqual(key, adapter["id"])
            self.assertIsInstance(adapter["requires"], list)
            self.assertIsInstance(adapter["needs"], list)
            for need in adapter["needs"]:
                self.assertIn(need, ov.VISION_CAPABILITIES)

    def test_direct_multimodal_facts(self):
        self.assertEqual(
            ov.DIRECT_MULTIMODAL["requires"],
            ["observer model with image attachment support"],
        )
        self.assertEqual(ov.DIRECT_MULTIMODAL["needs"], ["image_read"])

    def test_midscene_facts(self):
        self.assertEqual(
            ov.MIDSCENE["requires"],
            [
                "@midscene/web or CLI",
                "MIDSCENE_MODEL_API_KEY",
                "MIDSCENE_MODEL_NAME",
                "MIDSCENE_MODEL_BASE_URL",
                "MIDSCENE_MODEL_FAMILY",
                "network egress to model provider",
            ],
        )
        self.assertEqual(ov.MIDSCENE["needs"], ["image_read", "visual_grounding"])

    def test_ui_tars_facts(self):
        self.assertEqual(
            ov.UI_TARS["requires"], ["UI-TARS desktop/operator", "vision-language model"]
        )
        self.assertEqual(
            ov.UI_TARS["needs"],
            ["image_read", "visual_grounding", "desktop_control"],
        )


class AdapterStatusTests(unittest.TestCase):
    def test_unavailable_reason_wins_even_with_passed_probes(self):
        evidence = {
            "probes": {"image_read": "passed", "visual_grounding": "passed"},
            "unavailable_reason": "MIDSCENE_MODEL_API_KEY is not set",
        }
        result = ov.adapter_status(ov.MIDSCENE, evidence)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["unavailable_reason"], "MIDSCENE_MODEL_API_KEY is not set")

    def test_all_needs_passed_is_verified(self):
        evidence = {"probes": {"image_read": "passed", "visual_grounding": "passed"}}
        result = ov.adapter_status(ov.MIDSCENE, evidence)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["passed"], ["image_read", "visual_grounding"])
        self.assertEqual(result["failed"], [])
        self.assertEqual(result["missing"], [])

    def test_failed_probe_beats_passed_probes(self):
        evidence = {"probes": {"image_read": "passed", "visual_grounding": "failed"}}
        result = ov.adapter_status(ov.MIDSCENE, evidence)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failed"], ["visual_grounding"])
        self.assertEqual(result["passed"], ["image_read"])

    def test_missing_probe_is_implemented_not_verified(self):
        evidence = {"probes": {"image_read": "passed", "visual_grounding": None}}
        result = ov.adapter_status(ov.MIDSCENE, evidence)
        self.assertEqual(result["status"], "implemented-not-verified")
        self.assertEqual(result["missing"], ["visual_grounding"])

    def test_absent_evidence_is_implemented_not_verified(self):
        for evidence in (None, [], "x", 42):
            result = ov.adapter_status(ov.UI_TARS, evidence)
            self.assertEqual(result["status"], "implemented-not-verified")
            self.assertEqual(
                result["missing"],
                ["image_read", "visual_grounding", "desktop_control"],
            )

    def test_probes_not_an_object(self):
        for probes in (None, [], "passed"):
            result = ov.adapter_status(ov.UI_TARS, {"probes": probes})
            self.assertEqual(result["status"], "implemented-not-verified")
            self.assertEqual(len(result["missing"]), 3)

    def test_status_hint_never_upgrades(self):
        adapter = {"id": "x", "needs": ["image_read"], "status_hint": "verified"}
        result = ov.adapter_status(adapter, None)
        self.assertEqual(result["status"], "implemented-not-verified")
        self.assertEqual(result["status_hint"], "verified")

    def test_odd_probe_values_count_as_missing(self):
        evidence = {"probes": {"image_read": True, "visual_grounding": "PASSED"}}
        result = ov.adapter_status(ov.MIDSCENE, evidence)
        self.assertEqual(result["status"], "implemented-not-verified")
        self.assertEqual(result["missing"], ["image_read", "visual_grounding"])

    def test_malformed_adapter_does_not_raise(self):
        for adapter in (None, [], "midscene", 42):
            result = ov.adapter_status(adapter, {"probes": {"image_read": "passed"}})
            self.assertEqual(result["status"], "implemented-not-verified")
            self.assertIsNone(result["id"])

    def test_malformed_needs_blocks_verified(self):
        for needs in (None, "image_read", 42, []):
            adapter = {"id": "x", "needs": needs}
            evidence = {"probes": {"image_read": "passed"}}
            result = ov.adapter_status(adapter, evidence)
            self.assertEqual(result["status"], "implemented-not-verified")
            self.assertEqual(result["needs"], [])

    def test_need_entries_filtered_and_deduped(self):
        adapter = {"id": "x", "needs": ["image_read", 7, "image_read", "  "]}
        result = ov.adapter_status(adapter, {"probes": {"image_read": "passed"}})
        self.assertEqual(result["needs"], ["image_read"])
        self.assertEqual(result["status"], "verified")

    def test_garbage_matrix_always_returns_a_status(self):
        adapters = (
            None,
            [],
            "x",
            1,
            {},
            {"id": "x", "needs": None},
            {"id": 5, "needs": [1, "image_read"]},
        )
        evidences = (
            None,
            [],
            "x",
            1,
            {},
            {"probes": None},
            {"probes": []},
            {"unavailable_reason": 5},
            {"unavailable_reason": "  "},
        )
        for adapter in adapters:
            for evidence in evidences:
                result = ov.adapter_status(adapter, evidence)
                self.assertIn(result["status"], ov.STATUSES)

    def test_result_carries_host_for_audit(self):
        result = ov.adapter_status(
            ov.DIRECT_MULTIMODAL, {"host": {"status": "passed"}, "probes": {}}
        )
        self.assertEqual(result["host"], {"status": "passed"})
        self.assertEqual(result["status"], "implemented-not-verified")


class HostRequirementsTests(unittest.TestCase):
    def test_midscene_all_checkable_present_but_network_unverifiable(self):
        env = {
            "MIDSCENE_MODEL_API_KEY": "key",
            "MIDSCENE_MODEL_NAME": "gpt-5.6-luna",
            "MIDSCENE_MODEL_BASE_URL": "https://example.invalid/v1",
            "MIDSCENE_MODEL_FAMILY": "openai",
        }
        which = fake_which({"midscene"})
        result = ov.host_requirements(ov.MIDSCENE, env, which)
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["unverifiable"], ["network egress to model provider"])
        self.assertIn("@midscene/web or CLI", result["present"])
        self.assertIn("MIDSCENE_MODEL_FAMILY", result["present"])
        self.assertFalse(result["satisfied"])
        self.assertIn("midscene", which.calls)

    def test_missing_env_key_is_missing(self):
        env = {
            "MIDSCENE_MODEL_API_KEY": "key",
            "MIDSCENE_MODEL_NAME": "name",
            "MIDSCENE_MODEL_BASE_URL": "url",
        }
        result = ov.host_requirements(ov.MIDSCENE, env, fake_which({"midscene"}))
        self.assertEqual(result["missing"], ["MIDSCENE_MODEL_FAMILY"])
        self.assertFalse(result["satisfied"])

    def test_empty_or_nonstring_env_values_are_missing(self):
        env = {
            "MIDSCENE_MODEL_API_KEY": "",
            "MIDSCENE_MODEL_NAME": "   ",
            "MIDSCENE_MODEL_BASE_URL": None,
            "MIDSCENE_MODEL_FAMILY": 7,
        }
        result = ov.host_requirements(ov.MIDSCENE, env, fake_which({"midscene"}))
        self.assertEqual(
            sorted(result["missing"]),
            [
                "MIDSCENE_MODEL_API_KEY",
                "MIDSCENE_MODEL_BASE_URL",
                "MIDSCENE_MODEL_FAMILY",
                "MIDSCENE_MODEL_NAME",
            ],
        )

    def test_env_not_a_dict_means_every_env_var_missing(self):
        result = ov.host_requirements(ov.MIDSCENE, ["MIDSCENE_MODEL_API_KEY"], None)
        self.assertEqual(len(result["missing"]), 5)

    def test_which_none_marks_package_missing(self):
        env = {
            "MIDSCENE_MODEL_API_KEY": "key",
            "MIDSCENE_MODEL_NAME": "name",
            "MIDSCENE_MODEL_BASE_URL": "url",
            "MIDSCENE_MODEL_FAMILY": "openai",
        }
        result = ov.host_requirements(ov.MIDSCENE, env, fake_which(set()))
        self.assertIn("@midscene/web or CLI", result["missing"])
        self.assertFalse(result["satisfied"])

    def test_ui_tars_command_and_prose_classification(self):
        which = fake_which({"ui-tars"})
        result = ov.host_requirements(ov.UI_TARS, {}, which)
        self.assertEqual(result["present"], ["UI-TARS desktop/operator"])
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["unverifiable"], ["vision-language model"])
        self.assertFalse(result["satisfied"])
        self.assertIn("ui-tars", which.calls)

    def test_direct_multimodal_is_unverifiable_only(self):
        result = ov.host_requirements(ov.DIRECT_MULTIMODAL, {}, fake_which({"anything"}))
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["present"], [])
        self.assertEqual(
            result["unverifiable"],
            ["observer model with image attachment support"],
        )
        self.assertFalse(result["satisfied"])

    def test_satisfied_only_when_all_items_checkable_and_present(self):
        adapter = {
            "id": "custom",
            "requires": ["midscene", "MIDSCENE_MODEL_API_KEY"],
            "needs": ["image_read"],
        }
        result = ov.host_requirements(
            adapter, {"MIDSCENE_MODEL_API_KEY": "key"}, fake_which({"midscene"})
        )
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["unverifiable"], [])
        self.assertTrue(result["satisfied"])

    def test_which_exception_is_treated_as_missing(self):
        def broken(name):
            raise OSError("which exploded")

        result = ov.host_requirements(ov.UI_TARS, {}, broken)
        self.assertIn("UI-TARS desktop/operator", result["missing"])
        self.assertEqual(result["unverifiable"], ["vision-language model"])

    def test_non_callable_which_fails_closed(self):
        result = ov.host_requirements(ov.UI_TARS, {}, "not-callable")
        self.assertIn("UI-TARS desktop/operator", result["missing"])

    def test_malformed_adapter_does_not_raise(self):
        for adapter in (None, [], "x", 42, {"requires": None}, {"requires": "midscene"}):
            result = ov.host_requirements(adapter, {}, fake_which({"midscene"}))
            self.assertEqual(
                set(result), {"satisfied", "missing", "present", "unverifiable"}
            )
            self.assertFalse(result["satisfied"])

    def test_prose_requirement_is_never_guessed(self):
        adapter = {"id": "custom", "requires": ["network egress to provider"]}
        result = ov.host_requirements(adapter, {}, fake_which({"network"}))
        self.assertEqual(result["unverifiable"], ["network egress to provider"])
        self.assertEqual(result["present"], [])
        self.assertFalse(result["satisfied"])


class PerceptionRecordTests(unittest.TestCase):
    def valid_record(self, **overrides):
        record = ov.build_perception_record(
            "images/probe.png",
            hashlib.sha256(b"bytes").hexdigest(),
            "gpt-5.6-luna",
            "a solid red square",
            "sess-1",
            "2026-09-21T00:00:00Z",
        )
        record.update(overrides)
        return record

    def test_build_shape_and_values(self):
        record = self.valid_record()
        self.assertEqual(
            set(record),
            {
                "schema",
                "image",
                "described_by",
                "description",
                "session_id",
                "created_at",
            },
        )
        self.assertEqual(record["schema"], "perception-probe/1")
        self.assertEqual(record["image"]["path"], "images/probe.png")
        self.assertEqual(set(record["image"]), {"path", "sha256"})

    def test_build_accepts_path_objects_without_raising(self):
        record = ov.build_perception_record(
            Path("a") / "b.png", None, None, None, None, None
        )
        self.assertEqual(record["image"]["path"], str(Path("a") / "b.png"))
        self.assertEqual(record["image"]["sha256"], "")
        self.assertEqual(record["description"], "")

    def test_valid_record_has_no_problems(self):
        self.assertEqual(ov.validate_perception_record(self.valid_record()), [])

    def test_missing_or_wrong_fields_are_reported(self):
        cases = (
            {"schema": "other/1"},
            {"described_by": ""},
            {"description": "   "},
            {"session_id": None},
            {"created_at": 5},
            {"image": None},
            {"image": {"path": "", "sha256": hashlib.sha256(b"bytes").hexdigest()}},
            {"image": {"path": "p.png", "sha256": "abc"}},
            {"image": {"path": "p.png", "sha256": "z" * 64}},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertTrue(
                    ov.validate_perception_record(self.valid_record(**overrides))
                )

    def test_non_object_record(self):
        for record in (None, [], "x", 42):
            problems = ov.validate_perception_record(record)
            self.assertEqual(problems, ["perception record must be a JSON object"])

    def test_uppercase_hex_is_accepted(self):
        record = self.valid_record()
        record["image"]["sha256"] = record["image"]["sha256"].upper()
        self.assertEqual(ov.validate_perception_record(record), [])

    def test_file_existence_is_not_part_of_record_validation(self):
        record = self.valid_record()
        record["image"]["path"] = "does/not/exist.png"
        self.assertEqual(ov.validate_perception_record(record), [])


class PerceptionClaimTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ov-claim-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.evidence = self.tmp / "evidence"
        self.evidence.mkdir()
        self.data = b"probe-image-bytes"
        self.image = self.evidence / "probe.png"
        self.image.write_bytes(self.data)

    def record(self, path="probe.png", sha=None, **overrides):
        record = ov.build_perception_record(
            path,
            sha if sha is not None else hashlib.sha256(self.data).hexdigest(),
            "gpt-5.6-luna",
            "solid red square",
            "sess-1",
            "2026-09-21T00:00:00Z",
        )
        record.update(overrides)
        return record

    def test_matching_claim_passes(self):
        self.assertEqual(ov.perception_claim_problems(self.record(), self.evidence), [])

    def test_absolute_path_inside_root_passes(self):
        record = self.record(path=str(self.image.resolve()))
        self.assertEqual(ov.perception_claim_problems(record, self.evidence), [])

    def test_missing_image_is_reported(self):
        problems = ov.perception_claim_problems(self.record(path="other.png"), self.evidence)
        self.assertEqual(len(problems), 1)
        self.assertIn("not found", problems[0])

    def test_sha_mismatch_is_reported(self):
        wrong = hashlib.sha256(b"different-bytes").hexdigest()
        problems = ov.perception_claim_problems(self.record(sha=wrong), self.evidence)
        self.assertEqual(len(problems), 1)
        self.assertIn("sha256 does not match", problems[0])

    def test_path_escaping_root_is_reported(self):
        outside = self.tmp / "outside.png"
        outside.write_bytes(self.data)
        record = self.record(path="../outside.png")
        problems = ov.perception_claim_problems(record, self.evidence)
        self.assertEqual(len(problems), 1)
        self.assertIn("escapes the evidence root", problems[0])

    def test_absolute_path_outside_root_is_reported(self):
        outside = self.tmp / "outside.png"
        outside.write_bytes(self.data)
        record = self.record(path=str(outside.resolve()))
        problems = ov.perception_claim_problems(record, self.evidence)
        self.assertEqual(len(problems), 1)
        self.assertIn("escapes the evidence root", problems[0])

    def test_malformed_record_returns_structural_problems(self):
        problems = ov.perception_claim_problems({"schema": "wrong"}, self.evidence)
        self.assertTrue(problems)
        self.assertIn("schema must be perception-probe/1", problems)

    def test_unusable_evidence_root_does_not_raise(self):
        for root in (None, 5, ["x"]):
            problems = ov.perception_claim_problems(self.record(), root)
            self.assertTrue(problems)
            self.assertIn("evidence root", problems[0])

    def test_file_without_record_is_not_a_claim(self):
        self.assertTrue(self.image.is_file())
        problems = ov.perception_claim_problems(
            self.record(path="missing.png"), self.evidence
        )
        self.assertEqual(len(problems), 1)


class ColorProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ov-color-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_png_signature_chunks_and_dimensions(self):
        result = ov.make_color_probe(self.tmp / "probe.png", color="red")
        data = Path(result["path"]).read_bytes()
        chunks = png_chunks(self, data)
        self.assertEqual([tag for tag, _ in chunks], [b"IHDR", b"IDAT", b"IEND"])
        width, height = struct.unpack(">II", chunks[0][1][:8])
        self.assertEqual((width, height), (48, 48))
        self.assertEqual(chunks[0][1][8], 8)
        self.assertEqual(chunks[0][1][9], 2)
        raw = zlib.decompress(chunks[1][1])
        self.assertEqual(len(raw), 48 * (1 + 48 * 3))
        self.assertEqual(raw[:4], b"\x00\xff\x00\x00")

    def test_sha256_matches_file_bytes(self):
        result = ov.make_color_probe(self.tmp / "probe.png", color="blue")
        data = Path(result["path"]).read_bytes()
        self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest())

    def test_returned_fields(self):
        result = ov.make_color_probe(self.tmp / "probe.png", color="magenta")
        self.assertEqual(set(result), {"path", "color", "sha256", "size"})
        self.assertEqual(result["color"], "magenta")
        self.assertEqual(result["size"], 48)

    def test_same_color_is_deterministic(self):
        first = ov.make_color_probe(self.tmp / "a.png", color="cyan")
        second = ov.make_color_probe(self.tmp / "b.png", color="cyan")
        self.assertEqual(first["sha256"], second["sha256"])

    def test_rng_choice_is_reproducible(self):
        first = ov.make_color_probe(self.tmp / "a.png", rng=random.Random(7))
        second = ov.make_color_probe(self.tmp / "b.png", rng=random.Random(7))
        self.assertEqual(first["color"], second["color"])
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertIn(first["color"], ov.PROBE_COLORS)

    def test_random_choices_stay_in_allowed_set(self):
        for seed in range(20):
            result = ov.make_color_probe(self.tmp / f"p{seed}.png", rng=random.Random(seed))
            self.assertIn(result["color"], ov.PROBE_COLORS)

    def test_invalid_color_raises(self):
        with self.assertRaises(ValueError):
            ov.make_color_probe(self.tmp / "probe.png", color="chartreuse")

    def test_invalid_rng_raises(self):
        with self.assertRaises(ValueError):
            ov.make_color_probe(self.tmp / "probe.png", rng=object())

    def test_invalid_size_raises(self):
        for size in (0, -3, "48", True):
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    ov.make_color_probe(self.tmp / "probe.png", color="red", size=size)

    def test_parent_directories_created(self):
        result = ov.make_color_probe(self.tmp / "nested" / "deep" / "probe.png")
        self.assertTrue(Path(result["path"]).is_file())


class DispatchModeTests(unittest.TestCase):
    def test_structured_only(self):
        self.assertEqual(
            ov.dispatch_mode({}, ["structured"]),
            {"mode": "structured", "needs": [], "gaps": []},
        )

    def test_no_channels_is_structured(self):
        result = ov.dispatch_mode({"image_read": True}, [])
        self.assertEqual(result["mode"], "structured")
        self.assertEqual(result["needs"], [])
        self.assertEqual(result["gaps"], [])

    def test_visual_with_image_read_is_direct(self):
        result = ov.dispatch_mode({"image_read": True}, ["visual"])
        self.assertEqual(result["mode"], "direct-multimodal")
        self.assertEqual(result["needs"], ["image_read"])
        self.assertEqual(result["gaps"], [])

    def test_canvas_with_image_read_is_direct(self):
        result = ov.dispatch_mode({"image_read": True}, ["canvas"])
        self.assertEqual(result["mode"], "direct-multimodal")

    def test_visual_missing_image_read_hybrid_with_midscene(self):
        result = ov.dispatch_mode({}, ["visual"], ["midscene"])
        self.assertEqual(result["mode"], "hybrid")
        self.assertEqual(result["needs"], ["image_read"])
        self.assertEqual(result["gaps"], [])

    def test_hybrid_accepts_adapter_status_dict(self):
        available = {"midscene": {"status": "verified"}}
        result = ov.dispatch_mode({}, ["visual"], available)
        self.assertEqual(result["mode"], "hybrid")

    def test_unverified_adapter_does_not_unlock_hybrid(self):
        for available in (
            {"midscene": {"status": "implemented-not-verified"}},
            {"midscene": False},
            {"midscene": "failed"},
            [],
        ):
            with self.subTest(available=available):
                result = ov.dispatch_mode({}, ["visual"], available)
                self.assertEqual(result["mode"], "blocked")
                self.assertTrue(any("image_read" in gap for gap in result["gaps"]))

    def test_direct_multimodal_is_not_an_engine_adapter(self):
        result = ov.dispatch_mode({}, ["visual"], ["direct-multimodal"])
        self.assertEqual(result["mode"], "blocked")

    def test_unknown_adapter_ids_are_ignored(self):
        result = ov.dispatch_mode({}, ["visual"], {"mystery": True})
        self.assertEqual(result["mode"], "blocked")

    def test_visual_without_any_coverage_is_blocked(self):
        result = ov.dispatch_mode({"image_read": False}, ["visual"])
        self.assertEqual(result["mode"], "blocked")
        self.assertTrue(any("image_read" in gap for gap in result["gaps"]))

    def test_desktop_direct_needs_all_three_capabilities(self):
        caps = {"image_read": True, "visual_grounding": True, "desktop_control": True}
        result = ov.dispatch_mode(caps, ["desktop"])
        self.assertEqual(result["mode"], "direct-multimodal")
        self.assertEqual(
            result["needs"], ["image_read", "visual_grounding", "desktop_control"]
        )

    def test_desktop_hybrid_with_ui_tars(self):
        result = ov.dispatch_mode({}, ["desktop"], ["ui-tars"])
        self.assertEqual(result["mode"], "hybrid")
        self.assertEqual(result["gaps"], [])

    def test_desktop_midscene_misses_desktop_control(self):
        result = ov.dispatch_mode({}, ["desktop"], ["midscene"])
        self.assertEqual(result["mode"], "blocked")
        self.assertTrue(any("desktop_control" in gap for gap in result["gaps"]))

    def test_audio_and_video_go_to_s17(self):
        for channel in ("audio", "video"):
            with self.subTest(channel=channel):
                result = ov.dispatch_mode({}, [channel])
                self.assertEqual(result["mode"], "blocked")
                self.assertTrue(any("S17" in gap for gap in result["gaps"]))

    def test_covered_visual_plus_audio_is_still_blocked_for_s17(self):
        result = ov.dispatch_mode({"image_read": True}, ["visual", "audio"])
        self.assertEqual(result["mode"], "blocked")
        self.assertEqual(result["needs"], ["image_read"])
        self.assertEqual(len(result["gaps"]), 1)
        self.assertIn("S17", result["gaps"][0])

    def test_unknown_channel_is_blocked_and_named(self):
        result = ov.dispatch_mode({}, ["hologram"])
        self.assertEqual(result["mode"], "blocked")
        self.assertTrue(any("hologram" in gap for gap in result["gaps"]))

    def test_observer_capability_must_be_true(self):
        for caps in ({"image_read": 1}, {"image_read": "yes"}, {"image_read": None}):
            with self.subTest(caps=caps):
                result = ov.dispatch_mode(caps, ["visual"])
                self.assertEqual(result["mode"], "blocked")

    def test_single_string_channel_is_accepted(self):
        result = ov.dispatch_mode({"image_read": True}, "visual")
        self.assertEqual(result["mode"], "direct-multimodal")

    def test_malformed_inputs_do_not_raise(self):
        for caps in (None, "x", 1, []):
            for channels in (None, 42, {"visual": True}):
                with self.subTest(caps=caps, channels=channels):
                    result = ov.dispatch_mode(caps, channels)
                    self.assertIn(
                        result["mode"],
                        ("structured", "direct-multimodal", "hybrid", "blocked"),
                    )
                    self.assertIsInstance(result["needs"], list)
                    self.assertIsInstance(result["gaps"], list)

    def test_malformed_channels_are_blocked_not_structured(self):
        result = ov.dispatch_mode({}, {"visual": True})
        self.assertEqual(result["mode"], "blocked")
        self.assertTrue(any("malformed" in gap for gap in result["gaps"]))


if __name__ == "__main__":
    unittest.main()
