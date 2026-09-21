#!/usr/bin/env python3
"""S16 offline vision surface: adapters, capability status and perception claims.

This module is deliberately offline: it inspects no model, starts no browser
and touches no network. It provides the pure/data surface the observation
controller needs before real probing lands in S21:

- ``VISION_CAPABILITIES`` / ``STATUSES`` and ``adapter_status`` turn probe
  evidence into one of four honest statuses. A declared ``status_hint`` or an
  existing requirement never upgrades an adapter to ``verified``; only probe
  evidence does.
- ``ADAPTERS`` holds the direct-multimodal / midscene / ui-tars adapter facts.
- ``host_requirements`` checks env vars and executables with an injected
  ``which``; prose requirements (network egress, model attachment support)
  stay ``unverifiable`` and are never guessed as satisfied.
- ``build_perception_record`` / ``validate_perception_record`` /
  ``perception_claim_problems``: a record is only a claim; the claim check
  requires the described image to exist inside the evidence root with a
  matching sha256. Writing a file alone proves nothing.
- ``make_color_probe`` writes a stdlib-generated solid-color PNG plus the
  expected color name, so S21 can ask the dispatched model which color it saw.
- ``dispatch_mode`` routes structured / direct-multimodal / hybrid / blocked
  from observer capabilities, product channels and available engine adapters.

Real model/browser verification is S21 and remains BLOCKED until run there.
"""

import hashlib
import os
import random
import re
import shutil
import struct
import zlib
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

VISION_CAPABILITIES = ("image_read", "visual_grounding", "desktop_control")
STATUSES = ("verified", "implemented-not-verified", "unavailable", "failed")

PERCEPTION_SCHEMA = "perception-probe/1"
PROBE_COLORS = ("red", "green", "blue", "yellow", "cyan", "magenta")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DEFAULT_PROBE_SIZE = 48

_ENGINE_ADAPTERS = ("midscene", "ui-tars")

_COLOR_RGB = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
}

_HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_ENV_PREFIX = "MIDSCENE_"
_PACKAGE_NAME_RE = re.compile(r"^[A-Za-z0-9@][A-Za-z0-9@._+-]*$")

DIRECT_MULTIMODAL = {
    "id": "direct-multimodal",
    "requires": ["observer model with image attachment support"],
    "needs": ["image_read"],
    "status_hint": "implemented-not-verified",
}

MIDSCENE = {
    "id": "midscene",
    "requires": [
        "@midscene/web or CLI",
        "MIDSCENE_MODEL_API_KEY",
        "MIDSCENE_MODEL_NAME",
        "MIDSCENE_MODEL_BASE_URL",
        "MIDSCENE_MODEL_FAMILY",
        "network egress to model provider",
    ],
    "needs": ["image_read", "visual_grounding"],
    "status_hint": "implemented-not-verified",
}

UI_TARS = {
    "id": "ui-tars",
    "requires": ["UI-TARS desktop/operator", "vision-language model"],
    "needs": ["image_read", "visual_grounding", "desktop_control"],
    "status_hint": "implemented-not-verified",
}

ADAPTERS = {
    "direct-multimodal": DIRECT_MULTIMODAL,
    "midscene": MIDSCENE,
    "ui-tars": UI_TARS,
}

_STRUCTURED_CHANNELS = (
    "structured",
    "text",
    "dom",
    "console",
    "api",
    "json",
    "html",
    "cli",
)
_S17_CHANNELS = ("audio", "video")
_CHANNEL_NEEDS = {
    "visual": ("image_read",),
    "canvas": ("image_read",),
    "desktop": ("image_read", "visual_grounding", "desktop_control"),
}


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, os.PathLike):
        try:
            return os.fsdecode(os.fspath(value))
        except TypeError:
            return ""
    return str(value)


def _dedupe(values) -> list:
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def _adapter_status_result() -> dict:
    return {
        "id": None,
        "status": "implemented-not-verified",
        "needs": [],
        "passed": [],
        "failed": [],
        "missing": [],
        "unavailable_reason": None,
        "status_hint": None,
        "host": None,
        "reason": "",
    }


def adapter_status(adapter: Any, evidence: Any) -> dict:
    """Summarize an adapter against its probe evidence.

    ``adapter`` is ``{"id", "requires", "needs", "status_hint"}`` and
    ``evidence`` is ``{"host", "probes", "unavailable_reason"}``. Rules, in
    order: a non-empty ``unavailable_reason`` wins -> ``unavailable``; every
    ``needs`` probe exactly ``"passed"`` -> ``verified``; any probe exactly
    ``"failed"`` -> ``failed``; otherwise ``implemented-not-verified``.
    Missing or malformed inputs never raise and never claim ``verified``.
    """
    result = _adapter_status_result()
    if not isinstance(adapter, dict):
        result["reason"] = "adapter is not an object"
        return result

    adapter_id = adapter.get("id")
    if isinstance(adapter_id, str) and adapter_id.strip():
        result["id"] = adapter_id
    hint = adapter.get("status_hint")
    if isinstance(hint, str) and hint.strip():
        result["status_hint"] = hint

    raw_needs = adapter.get("needs")
    needs = []
    needs_ok = isinstance(raw_needs, (list, tuple))
    if needs_ok:
        needs = [
            need.strip()
            for need in raw_needs
            if isinstance(need, str) and need.strip()
        ]
    result["needs"] = _dedupe(needs)

    probes = None
    unavailable_reason = None
    if isinstance(evidence, dict):
        result["host"] = evidence.get("host")
        raw_probes = evidence.get("probes")
        if isinstance(raw_probes, dict):
            probes = raw_probes
        reason = evidence.get("unavailable_reason")
        if isinstance(reason, str) and reason.strip():
            unavailable_reason = reason.strip()
    result["unavailable_reason"] = unavailable_reason

    if unavailable_reason is not None:
        result["status"] = "unavailable"
        result["reason"] = "evidence reports the adapter unavailable: " + unavailable_reason
        return result

    if probes is None:
        result["missing"] = list(result["needs"])
        result["reason"] = "no probe evidence for the required capabilities"
        return result

    passed, failed, missing = [], [], []
    for need in result["needs"]:
        value = probes.get(need)
        if value == "passed":
            passed.append(need)
        elif value == "failed":
            failed.append(need)
        else:
            missing.append(need)
    result["passed"] = passed
    result["failed"] = failed
    result["missing"] = missing

    if not needs_ok or not result["needs"]:
        result["reason"] = "adapter does not declare probeable needs"
        return result
    if failed:
        result["status"] = "failed"
        result["reason"] = "failed capability probe(s): " + ", ".join(failed)
        return result
    if missing:
        result["reason"] = "no probe result yet for: " + ", ".join(missing)
        return result

    result["status"] = "verified"
    result["reason"] = "all required capability probes passed"
    return result


def _requirement_kind(requirement: str) -> str:
    if requirement.startswith(_ENV_PREFIX):
        return "env"
    if "/" in requirement:
        return "command"
    if _PACKAGE_NAME_RE.fullmatch(requirement.strip()):
        return "command"
    return "unverifiable"


def _command_candidates(requirement: str) -> list:
    text = requirement.strip()
    head = text.split("/", 1)[0].strip() if "/" in text else text
    pieces = head.split()
    token = pieces[0] if pieces else ""
    candidates = []
    for candidate in (token, token.lstrip("@"), token.lower(), token.lstrip("@").lower()):
        candidate = candidate.strip().strip("\"'")
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def host_requirements(
    adapter: Any,
    env: Any = None,
    which: Optional[Callable[[str], Optional[str]]] = None,
) -> dict:
    """Check an adapter's host requirements without inventing a pass.

    ``MIDSCENE_*`` requirements are looked up in ``env`` (non-empty strings
    only); requirements containing ``/`` or shaped like a package name are
    resolved with ``which`` (production ``shutil.which``, tests inject a
    fake). Everything else is a prose requirement and lands in
    ``unverifiable``; it is never guessed as satisfied. ``satisfied`` is true
    only when nothing is missing and nothing is unverifiable.
    """
    if not isinstance(adapter, dict):
        return {"satisfied": False, "missing": [], "present": [], "unverifiable": []}

    raw_requires = adapter.get("requires")
    requires_ok = isinstance(raw_requires, (list, tuple))
    items = []
    if requires_ok:
        items = [
            item.strip()
            for item in raw_requires
            if isinstance(item, str) and item.strip()
        ]
    env_map = env if isinstance(env, dict) else {}
    if which is None:
        which_fn = shutil.which
    elif callable(which):
        which_fn = which
    else:
        which_fn = lambda name: None

    present, missing, unverifiable = [], [], []
    for item in items:
        kind = _requirement_kind(item)
        if kind == "env":
            value = env_map.get(item)
            if isinstance(value, str) and value.strip():
                present.append(item)
            else:
                missing.append(item)
        elif kind == "command":
            found = False
            for candidate in _command_candidates(item):
                try:
                    if which_fn(candidate):
                        found = True
                        break
                except Exception:
                    continue
            (present if found else missing).append(item)
        else:
            unverifiable.append(item)

    return {
        "satisfied": requires_ok and not missing and not unverifiable,
        "missing": missing,
        "present": present,
        "unverifiable": unverifiable,
    }


def build_perception_record(
    image_path: Any,
    sha256: Any,
    described_by: Any,
    description: Any,
    session_id: Any,
    created_at: Any,
) -> dict:
    """Build a ``perception-probe/1`` claim. Values are copied, never probed."""
    return {
        "schema": PERCEPTION_SCHEMA,
        "image": {"path": _text(image_path), "sha256": _text(sha256)},
        "described_by": _text(described_by),
        "description": _text(description),
        "session_id": _text(session_id),
        "created_at": _text(created_at),
    }


def validate_perception_record(record: Any) -> list:
    """Check record completeness only: fields, 64-hex sha256, non-empty text.

    The image file existing does not make the record true and is not checked
    here; that distinction belongs to ``perception_claim_problems``. This
    validator only answers "is this a well-formed claim".
    """
    problems = []
    if not isinstance(record, dict):
        return ["perception record must be a JSON object"]
    if record.get("schema") != PERCEPTION_SCHEMA:
        problems.append("schema must be " + PERCEPTION_SCHEMA)
    image = record.get("image")
    if not isinstance(image, dict):
        problems.append("image must be an object with path and sha256")
    else:
        path = image.get("path")
        if not isinstance(path, str) or not path.strip():
            problems.append("image.path must be a non-empty string")
        digest = image.get("sha256")
        if not isinstance(digest, str) or not _HASH_RE.match(digest):
            problems.append("image.sha256 must be a 64-character hex digest")
    for field in ("described_by", "description", "session_id", "created_at"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(field + " must be a non-empty string")
    return problems


def _resolved_root(evidence_root: Any) -> Optional[Path]:
    if evidence_root is None:
        return None
    try:
        return Path(evidence_root).resolve()
    except (TypeError, ValueError, OSError):
        return None


def perception_claim_problems(record: Any, evidence_root: Any) -> list:
    """Verify that a well-formed perception claim points at a real image.

    The image path must resolve inside ``evidence_root`` (absolute paths are
    allowed only when already inside), the file must exist, and its sha256
    must equal the recorded digest. Wrong or malformed records return the
    structural problems instead of raising.
    """
    problems = validate_perception_record(record)
    if problems:
        return problems

    root = _resolved_root(evidence_root)
    if root is None:
        return ["evidence root is not a usable directory path"]

    raw_path = record["image"]["path"]
    try:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        target = candidate.resolve()
    except (OSError, ValueError):
        return ["perception image path is not usable: " + raw_path]

    if not target.is_relative_to(root):
        return ["perception image escapes the evidence root: " + raw_path]
    if not target.is_file():
        return ["perception image not found: " + raw_path]
    try:
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
    except OSError as exc:
        return ["perception image cannot be read: " + raw_path + " (" + str(exc) + ")"]
    if digest != record["image"]["sha256"].lower():
        return ["perception image sha256 does not match: " + raw_path]
    return []


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _solid_rgb_png(size: int, rgb: Sequence[int]) -> bytes:
    row = b"\x00" + bytes(rgb) * size
    raw = row * size
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(raw, 9))
        + _png_chunk(b"IEND", b"")
    )


def make_color_probe(
    path: Any,
    color: Any = None,
    rng: Any = None,
    size: int = DEFAULT_PROBE_SIZE,
) -> dict:
    """Write a solid-color PNG and record the expected color name.

    The PNG is assembled with ``struct`` + ``zlib`` only (8-bit RGB, one
    IDAT). ``color`` must be one of ``PROBE_COLORS``; when omitted, ``rng``
    (or ``random``) chooses from that set, so injecting ``random.Random(n)``
    makes the probe reproducible. Returns ``{"path", "color", "sha256",
    "size"}``. S21 asks the dispatched model which color it saw.
    """
    if color is None:
        chooser = rng if rng is not None else random
        choice = getattr(chooser, "choice", None)
        if not callable(choice):
            raise ValueError("rng must provide a callable choice()")
        color = choice(list(PROBE_COLORS))
    if not isinstance(color, str) or color not in _COLOR_RGB:
        raise ValueError(f"unsupported probe color: {color!r}")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ValueError("size must be a positive integer")

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    png = _solid_rgb_png(size, _COLOR_RGB[color])
    target.write_bytes(png)
    return {
        "path": str(target),
        "color": color,
        "sha256": hashlib.sha256(png).hexdigest(),
        "size": size,
    }


def _normalized_capabilities(value: Any) -> dict:
    return {
        capability: (value.get(capability) is True if isinstance(value, dict) else False)
        for capability in VISION_CAPABILITIES
    }


def _adapter_available(value: Any) -> bool:
    if value is True or value == "verified":
        return True
    if isinstance(value, dict):
        return value.get("status") == "verified"
    return False


def _adapter_capabilities(available: Any) -> set:
    covered = set()
    entries = []
    if isinstance(available, (list, tuple, set, frozenset)):
        entries = [(item, True) for item in available if isinstance(item, str)]
    elif isinstance(available, dict):
        entries = list(available.items())
    for adapter_id, value in entries:
        if not isinstance(adapter_id, str) or adapter_id not in _ENGINE_ADAPTERS:
            continue
        adapter = ADAPTERS.get(adapter_id)
        if not isinstance(adapter, dict):
            continue
        if _adapter_available(value):
            covered.update(adapter["needs"])
    return covered


def dispatch_mode(
    observer_capabilities: Any,
    product_channels: Any,
    available_adapters: Any = None,
) -> dict:
    """Route an observation dispatch to one of four modes.

    Structured-only products use ``structured``; products needing visual or
    canvas perception with ``image_read`` on the observer use
    ``direct-multimodal``; when the observer cannot see but a known engine
    adapter (midscene / ui-tars, supplied as verified in
    ``available_adapters``) can, the mode is ``hybrid``. Audio/video channels
    belong to S17 and are reported in ``gaps``; anything neither the observer
    nor an adapter covers makes the mode ``blocked`` with explicit gaps.
    A ``status_hint`` or declared capability is never taken as verified: only
    boolean ``True`` observer capabilities and verified adapters count.
    """
    caps = _normalized_capabilities(observer_capabilities)
    adapter_caps = _adapter_capabilities(available_adapters)

    channels = []
    malformed_channels = False
    if product_channels is None:
        channels = []
    elif isinstance(product_channels, str):
        if product_channels.strip():
            channels = [product_channels]
    elif isinstance(product_channels, (list, tuple, set, frozenset)):
        channels = [
            channel.strip()
            for channel in product_channels
            if isinstance(channel, str) and channel.strip()
        ]
    else:
        malformed_channels = True

    needs, gaps, unknown = [], [], []
    s17 = []
    for channel in channels:
        key = channel.lower()
        if key in _CHANNEL_NEEDS:
            for need in _CHANNEL_NEEDS[key]:
                if need not in needs:
                    needs.append(need)
        elif key in _S17_CHANNELS:
            s17.append(key)
        elif key in _STRUCTURED_CHANNELS:
            continue
        else:
            unknown.append(channel)
            gaps.append("unknown product channel: " + channel)

    if malformed_channels:
        gaps.append("product channels are malformed")
    for channel in _dedupe(s17):
        gaps.append(
            "product channel '" + channel + "' requires audio/video perception (S17)"
        )
    for need in needs:
        if caps.get(need) or need in adapter_caps:
            continue
        gaps.append("no observer capability or engine adapter covers: " + need)

    blocked = bool(unknown or malformed_channels or s17 or gaps)
    if blocked:
        mode = "blocked"
    elif not needs:
        mode = "structured"
    elif all(caps.get(need) for need in needs):
        mode = "direct-multimodal"
    else:
        mode = "hybrid"

    return {"mode": mode, "needs": needs, "gaps": gaps}
