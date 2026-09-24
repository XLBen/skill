#!/usr/bin/env python3
"""Deterministic resolver for the workflow stage routing.

`mvp-delivery/references/stage-routing.json` is the single authority for
stage -> seat -> required capabilities. This module is the machine-readable
consumer used by `runtime_trace.py` (and available to `check.py`); it never
guesses or adds policy of its own:

  - PUA stage-card requirements are derived from the routing table, including
    its `applies_when` narrowing, instead of hard-coded role lists;
  - the Audited implementation-seat table is resolved from `seat_selection`;
  - unknown or missing rigor fails closed for guarded-or-audited cards.

Python 3.10+, stdlib only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROUTING_SCHEMA_VERSION = 3
RIGORS = ("normal", "guarded", "audited")
INTERACTIONS = ("autonomous", "checkpoints", "stepwise")
ROLE_BY_SEAT = {
    "controller": "controller",
    "worker-subagent": "worker",
    "reviewer-subagent": "reviewer",
    "test-author-subagent": "test-author",
    "step-executor-subagent": "step-executor",
    "product-observer-subagent": "product-observer",
}
KNOWN_SEATS = tuple(ROLE_BY_SEAT)
AUDITED_SEAT_TOKEN = "resolve:audited_implementation"
ENTRY_POINTS = ("work-entry", "fix-entry", "build-entry")
_APPLIES_WHEN_RIGORS = {
    "guarded": ("guarded",),
    "guarded-or-audited": ("guarded", "audited"),
    "audited": ("audited",),
}
ROUTING_FILENAME = "stage-routing.json"


class ProtocolError(Exception):
    pass


def default_routing_path() -> Path:
    """Locate the routing table in the dev repo or an installed engine tree.

    Search order: explicit env override, the repo layout used by this
    repository, then the engine copy installed next to the scripts."""

    override = os.environ.get("WORKFLOW_ROUTING")
    if override:
        return Path(override)
    here = Path(__file__).resolve().parent
    candidates = (
        here.parent / "mvp-delivery" / "references" / ROUTING_FILENAME,
        here / ROUTING_FILENAME,
        here.parent / ROUTING_FILENAME,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def load_routing(path: str | Path | None = None) -> dict[str, Any]:
    routing_path = Path(path) if path else default_routing_path()
    try:
        data = json.loads(routing_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"stage routing unreadable at {routing_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProtocolError(f"stage routing is not a JSON object: {routing_path}")
    problems = validate_routing(data)
    if problems:
        raise ProtocolError(
            "stage routing is invalid:\n- " + "\n- ".join(problems)
        )
    return data


def validate_routing(routing: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if routing.get("schema_version") != ROUTING_SCHEMA_VERSION:
        problems.append(
            f"schema_version must be {ROUTING_SCHEMA_VERSION}, got {routing.get('schema_version')!r}"
        )
    stages = routing.get("stages")
    if not isinstance(stages, list) or not stages:
        problems.append("stages must be a nonempty list")
        return problems
    rules = routing.get("responsibility_rules")
    if not isinstance(rules, dict) or not rules:
        problems.append("responsibility_rules must be a nonempty object")
    seen: set[str] = set()
    for stage in stages:
        if not isinstance(stage, dict):
            problems.append("stage entry is not an object")
            continue
        stage_id = stage.get("stage_id")
        if not isinstance(stage_id, str) or not stage_id:
            problems.append(f"stage entry missing string stage_id: {stage!r}")
            continue
        if stage_id in seen:
            problems.append(f"duplicate stage_id {stage_id}")
        seen.add(stage_id)
        if not isinstance(stage.get("entry"), str) or not stage["entry"]:
            problems.append(f"stage {stage_id}: entry must be a nonempty string")
        rigors = stage.get("rigors")
        if not isinstance(rigors, list) or not rigors or any(r not in RIGORS for r in rigors):
            problems.append(f"stage {stage_id}: rigors must be a nonempty subset of {RIGORS}")
        for entry in stage.get("required_skills") or []:
            if not isinstance(entry, dict) or not entry.get("name") or not entry.get("seat"):
                problems.append(f"stage {stage_id}: required_skills entries need name and seat")
                continue
            if entry.get("name") == "pua":
                if not _entry_roles(entry, problems, stage_id):
                    continue
                try:
                    _applies_when(entry)
                except ProtocolError as exc:
                    problems.append(f"stage {stage_id}: {exc}")
        reviewer = stage.get("reviewer")
        if not isinstance(reviewer, dict):
            problems.append(f"stage {stage_id}: reviewer must be an object")
            continue
        condition = reviewer.get("condition")
        if not isinstance(condition, dict):
            problems.append(f"stage {stage_id}: reviewer.condition must be an object")
            continue
        for field in ("dispatch", "mandatory", "blocking"):
            if not isinstance(condition.get(field), bool):
                problems.append(f"stage {stage_id}: reviewer.condition.{field} must be a bool")
        optional_rigors = condition.get("optional_rigors") or []
        if not isinstance(optional_rigors, list) or any(r not in RIGORS for r in optional_rigors):
            problems.append(f"stage {stage_id}: reviewer.condition.optional_rigors must be a rigor list")
        if condition.get("dispatch") and not isinstance(condition.get("rigors"), list):
            problems.append(f"stage {stage_id}: dispatching reviewers need a rigors list")
        elif not condition.get("dispatch") and (condition.get("rigors") or optional_rigors):
            problems.append(
                f"stage {stage_id}: non-dispatching reviewer cannot declare rigors"
            )
        for rigor in optional_rigors:
            if rigor not in (stage.get("rigors") or []):
                problems.append(
                    f"stage {stage_id}: optional rigor {rigor} not in the stage's rigors"
                )
        responsibilities = stage.get("responsibilities")
        if not isinstance(responsibilities, dict):
            problems.append(f"stage {stage_id}: responsibilities must be an object")
        else:
            _validate_responsibilities(stage_id, responsibilities, problems)
    seat_selection = routing.get("seat_selection")
    if not isinstance(seat_selection, dict) or not isinstance(
        seat_selection.get("audited_implementation"), list
    ):
        problems.append("seat_selection.audited_implementation must be a list")
    else:
        seen_pairs: set[tuple[str, str]] = set()
        for row in seat_selection["audited_implementation"]:
            if not isinstance(row, dict) or not row.get("profile") or not row.get("interaction") or not row.get("seat"):
                problems.append("seat_selection rows need profile, interaction and seat")
                continue
            if row["profile"] not in ("direct", "full", "light"):
                problems.append(f"seat_selection unknown profile {row['profile']!r}")
            if row["interaction"] not in ("any", "autonomous", "checkpoints", "stepwise"):
                problems.append(f"seat_selection unknown interaction {row['interaction']!r}")
            if row["seat"] not in ("controller", "step-executor"):
                problems.append(f"seat_selection unknown seat {row['seat']!r}")
            pair = (row["profile"], row["interaction"])
            if pair in seen_pairs:
                problems.append(f"seat_selection duplicate row {pair}")
            seen_pairs.add(pair)
    capabilities = routing.get("domain_capabilities")
    if not isinstance(capabilities, dict) or not isinstance(capabilities.get("capabilities"), list):
        problems.append("domain_capabilities.capabilities must be a list")
    else:
        capability_names: set[str] = set()
        for entry in capabilities["capabilities"]:
            if not isinstance(entry, dict) or not entry.get("name"):
                problems.append("domain capability entry needs a name")
                continue
            name = entry["name"]
            if name in capability_names:
                problems.append(f"duplicate domain capability {name}")
            capability_names.add(name)
            if not isinstance(entry.get("trigger"), str) or not entry["trigger"].strip():
                problems.append(f"domain capability {name}: trigger must be a nonempty string")
            insertion = entry.get("insertion")
            if not isinstance(insertion, list) or not insertion or any(
                not isinstance(token, str) for token in insertion
            ):
                problems.append(f"domain capability {name}: insertion must be a nonempty string list")
            else:
                for token in insertion:
                    if token not in seen and token not in ENTRY_POINTS:
                        problems.append(
                            f"domain capability {name}: unknown insertion token {token!r}"
                        )
            outputs = entry.get("outputs")
            if not isinstance(outputs, list) or not outputs or any(
                not isinstance(item, str) for item in outputs
            ):
                problems.append(f"domain capability {name}: outputs must be a nonempty string list")
    return problems


def _validate_responsibilities(
    stage_id: str, responsibilities: dict[str, Any], problems: list[str]
) -> None:
    implementation = responsibilities.get("implementation_seat")
    if implementation is not None:
        if not isinstance(implementation, dict) or not implementation:
            problems.append(f"stage {stage_id}: implementation_seat must be a nonempty object")
        else:
            for rigor, seat in implementation.items():
                if rigor not in RIGORS:
                    problems.append(
                        f"stage {stage_id}: implementation_seat unknown rigor {rigor!r}"
                    )
                    continue
                if seat != AUDITED_SEAT_TOKEN and seat not in KNOWN_SEATS:
                    problems.append(
                        f"stage {stage_id}: implementation_seat unknown seat {seat!r}"
                    )
    checks = responsibilities.get("semantic_checks")
    if not isinstance(checks, list):
        problems.append(f"stage {stage_id}: semantic_checks must be a list")
    else:
        seen_checks: set[str] = set()
        for entry in checks:
            if not isinstance(entry, dict):
                problems.append(f"stage {stage_id}: semantic check entry is not an object")
                continue
            name = entry.get("check")
            if not isinstance(name, str) or not name.strip():
                problems.append(f"stage {stage_id}: semantic check missing a string check name")
                continue
            if name in seen_checks:
                problems.append(f"stage {stage_id}: duplicate semantic check {name!r}")
            seen_checks.add(name)
            owner = entry.get("owner_seat")
            if owner not in ROLE_BY_SEAT:
                problems.append(
                    f"stage {stage_id}: check {name!r} has unknown owner seat {owner!r}"
                )
            if "kind" in entry and not isinstance(entry.get("kind"), str):
                problems.append(f"stage {stage_id}: check {name!r} kind must be a string")
    formal = responsibilities.get("formal_verification")
    if formal is not None:
        if not isinstance(formal, dict) or not formal.get("owner_seat") or not formal.get("gate"):
            problems.append(
                f"stage {stage_id}: formal_verification needs owner_seat and gate"
            )
        elif formal.get("owner_seat") != "controller":
            problems.append(
                f"stage {stage_id}: formal_verification owner must be controller"
            )


def _entry_roles(entry: dict[str, Any], problems: list[str], stage_id: str) -> list[str]:
    roles = entry.get("roles")
    if roles is not None:
        if not isinstance(roles, list) or not roles or any(not isinstance(r, str) for r in roles):
            problems.append(f"stage {stage_id}: pua entry roles must be a nonempty string list")
            return []
        return roles
    seat = entry.get("seat")
    role = ROLE_BY_SEAT.get(seat)
    if role is None:
        problems.append(
            f"stage {stage_id}: pua seat {seat!r} needs an explicit roles list"
        )
        return []
    return [role]


def _applies_when(entry: dict[str, Any]) -> str:
    condition = entry.get("applies_when")
    if condition is None:
        return "always"
    if condition not in _APPLIES_WHEN_RIGORS:
        raise ProtocolError(f"unknown applies_when value {condition!r}")
    return condition


def stage_definition(routing: dict[str, Any], stage_id: str) -> dict[str, Any]:
    for stage in routing["stages"]:
        if stage["stage_id"] == stage_id:
            return stage
    raise ProtocolError(f"unknown stage_id {stage_id!r}")


def required_skills_for_stage(
    routing: dict[str, Any], stage_id: str, rigor: str | None
) -> list[dict[str, Any]]:
    """Return the stage's required skills that apply at this rigor.

    A rigor outside the stage's own rigors yields no PUA card (the stage does
    not run there); PUA cards with `applies_when` are filtered by rigor, and
    unknown rigor keeps them (fail closed)."""

    stage = stage_definition(routing, stage_id)
    stage_rigors = stage.get("rigors") or []
    known = rigor in RIGORS
    stage_applies = rigor is None or not known or rigor in stage_rigors
    required = []
    for entry in stage.get("required_skills") or []:
        if entry.get("name") == "pua":
            if not stage_applies:
                continue
            if not pua_applies(entry, rigor):
                continue
        required.append(entry)
    return required


def pua_applies(entry: dict[str, Any], rigor: str | None) -> bool:
    """True when a PUA entry applies at this rigor.

    Missing or unrecognized rigor fails closed for narrowed cards rather than
    silently exempting the seat."""

    condition = _applies_when(entry)
    if condition == "always":
        return True
    if rigor is None or rigor not in RIGORS:
        return True
    return rigor in _APPLIES_WHEN_RIGORS[condition]


def pua_stage_cards(
    routing: dict[str, Any], stage_id: str, rigor: str | None, role: str | None = None
) -> list[str]:
    """Stage cards that apply at this rigor, optionally narrowed to one role.

    Some stages carry two cards (reviewer and controller); callers that know
    the executing seat must pass `role` instead of assuming the first match."""

    cards = []
    stage = stage_definition(routing, stage_id)
    stage_rigors = stage.get("rigors") or []
    if rigor in RIGORS and rigor not in stage_rigors:
        return cards
    for entry in stage.get("required_skills") or []:
        if entry.get("name") != "pua":
            continue
        if role is not None and role not in _entry_roles(entry, [], stage_id):
            continue
        if pua_applies(entry, rigor):
            card = entry.get("stage_card")
            if card and card not in cards:
                cards.append(card)
    return cards


def pua_stage_card(
    routing: dict[str, Any], stage_id: str, rigor: str | None, role: str | None = None
) -> str | None:
    cards = pua_stage_cards(routing, stage_id, rigor, role)
    return cards[0] if cards else None


def pua_required_for_role(
    routing: dict[str, Any], role: str, rigor: str | None
) -> bool:
    """True when any routing entry obliges this role to load a PUA card.

    A stage only applies at its own rigors; within an applying stage, a PUA
    entry narrowed by `applies_when` is skipped outside those rigors. Unknown
    rigor fails closed; `normal` stays exempt from guarded-or-audited cards."""

    for stage in routing["stages"]:
        stage_rigors = stage.get("rigors") or []
        if rigor is not None and rigor in RIGORS and rigor not in stage_rigors:
            continue
        for entry in stage.get("required_skills") or []:
            if entry.get("name") != "pua":
                continue
            if role not in _entry_roles(entry, [], stage["stage_id"]):
                continue
            if pua_applies(entry, rigor):
                return True
    return False


def reviewer_condition(
    routing: dict[str, Any], stage_id: str, rigor: str | None
) -> dict[str, Any]:
    stage = stage_definition(routing, stage_id)
    condition = dict(stage.get("reviewer", {}).get("condition") or {})
    mandatory_rigors = condition.get("rigors") or []
    optional_rigors = condition.get("optional_rigors") or []
    required = rigor in mandatory_rigors
    optional = rigor in optional_rigors
    applies = bool(condition.get("dispatch")) and (required or optional)
    result = {
        "dispatch": applies,
        "mandatory": bool(condition.get("mandatory")) and required,
        "blocking": bool(condition.get("blocking")) and required,
    }
    if optional and rigor == "normal" and condition.get("normal_trigger"):
        result["normal_trigger"] = condition["normal_trigger"]
    if applies and condition.get("gate"):
        result["gate"] = condition["gate"]
    return result


def normalized_interaction(interaction: str) -> str:
    if interaction in ("checkpoints/stepwise", "checkpoints-stepwise"):
        return "checkpoints"
    return interaction


def execution_seat(
    profile: str, interaction: str, routing: dict[str, Any] | None = None
) -> str:
    """Resolve the Audited implementation seat; the table is authoritative."""

    if profile not in ("direct", "full", "light"):
        raise ProtocolError(f"unknown profile {profile!r}")
    interaction = normalized_interaction(interaction)
    if interaction not in INTERACTIONS:
        raise ProtocolError(f"unknown interaction {interaction!r}")
    table = (routing or load_routing())["seat_selection"]["audited_implementation"]
    for row in table:
        if row["profile"] == profile and row["interaction"] in ("any", interaction):
            return row["seat"]
    raise ProtocolError(f"no seat for profile {profile!r} interaction {interaction!r}")


def _implementation_seat_rules(routing: dict[str, Any]) -> dict[str, str]:
    rules: dict[str, str] = {}
    for stage_id in ("slice-implementation", "step-verification"):
        stage = stage_definition(routing, stage_id)
        stage_rules = (stage.get("responsibilities") or {}).get("implementation_seat") or {}
        rules.update(stage_rules)
    return rules


def implementation_seat(
    routing: dict[str, Any],
    rigor: str,
    profile: str | None = None,
    interaction: str | None = None,
) -> str:
    """Resolve the implementation seat for a rigor.

    Normal -> controller, Guarded -> worker-subagent, Audited -> the seat
    table (controller or step-executor; never worker). Unknown rigor fails
    closed instead of guessing a lazier seat."""

    if rigor not in RIGORS:
        raise ProtocolError(f"unknown rigor {rigor!r} for implementation seat resolution")
    seat = _implementation_seat_rules(routing).get(rigor)
    if seat is None:
        raise ProtocolError(f"no implementation seat rule for rigor {rigor!r}")
    if seat == AUDITED_SEAT_TOKEN:
        if profile is None or interaction is None:
            raise ProtocolError("audited implementation seat needs profile and interaction")
        return execution_seat(profile, interaction, routing)
    return seat


def semantic_checks(routing: dict[str, Any], stage_id: str) -> list[dict[str, Any]]:
    """Named semantic checks for a stage, each with exactly one owner seat."""

    stage = stage_definition(routing, stage_id)
    checks = (stage.get("responsibilities") or {}).get("semantic_checks") or []
    return [dict(entry) for entry in checks]


def semantic_check_owner(
    routing: dict[str, Any], stage_id: str, check_id: str
) -> str | None:
    for entry in semantic_checks(routing, stage_id):
        if entry.get("check") == check_id:
            return entry.get("owner_seat")
    return None


def formal_verification(
    routing: dict[str, Any], stage_id: str
) -> dict[str, Any] | None:
    """The controller-owned engine gate for a stage, when one exists."""

    stage = stage_definition(routing, stage_id)
    formal = (stage.get("responsibilities") or {}).get("formal_verification")
    return dict(formal) if isinstance(formal, dict) else None


def domain_capabilities(
    routing: dict[str, Any], insertion: str | None = None
) -> list[dict[str, Any]]:
    """Registered conditional domain skills, optionally filtered by insertion."""

    block = routing.get("domain_capabilities") or {}
    entries = [dict(entry) for entry in (block.get("capabilities") or [])]
    if insertion is None:
        return entries
    return [entry for entry in entries if insertion in (entry.get("insertion") or [])]
