"""Engineering design validation and small, observed delivery cycles.

Uses check.py's existing command runner, workspace binding and file lock. This
is NOT a UI driver or a semantic test oracle. Commands and observations still
need review; required UI/product-observation gates remain mandatory.
"""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PureWindowsPath

import planning_readiness


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value, empty=False):
    return isinstance(value, list) and (empty or bool(value)) and all(text(v) for v in value)


def relative(value):
    return (text(value) and not Path(value).is_absolute() and not PureWindowsPath(value).is_absolute()
            and not PureWindowsPath(value).drive and ".." not in value.replace("\\", "/").split("/"))


def default_observation_spec(ui_ids):
    if ui_ids:
        return {"required": True, "reason": "Browser/desktop journeys need independent whole-product observation"}
    return {"required": False,
            "reason": "No browser/desktop journey requires an additional observation round",
            "basis": "Engineering-plan boundary/journey mapping has no browser or desktop outcome; planned outcome checks remain required"}


def goal_problems(goal):
    if goal.get("schema_version") != 3:
        return []
    problems = []
    ref = goal.get("engineering_plan")
    if (not isinstance(ref, dict) or not relative(ref.get("path"))
            or not re.fullmatch(r"[a-f0-9]{64}", str(ref.get("sha256", "")))):
        problems.append("goal.engineering_plan requires project-relative path and sha256")
    ui = goal.get("ui")
    if not isinstance(ui, dict) or type(ui.get("required")) is not bool or not text(ui.get("reason")):
        problems.append("schema 3 requires explicit goal.ui.required and reason")
    return problems


def validate(plan, goal, engine):
    errors = []
    if not isinstance(plan, dict) or plan.get("schema") not in ("engineering-plan/1", "engineering-plan/2", "engineering-plan/3"):
        return ["engineering plan schema must be engineering-plan/1, engineering-plan/2 or engineering-plan/3"]
    layered = plan["schema"] in ("engineering-plan/2", "engineering-plan/3")
    if plan.get("goal_id") != goal["id"]:
        errors.append("engineering plan goal_id mismatch")
    for field in ("architecture", "data_flow"):
        if not text(plan.get(field)):
            errors.append(f"engineering plan needs {field}")
    groups = {}
    for name in ("components", "boundaries", "journeys", "steps"):
        items = plan.get(name)
        groups[name] = {}
        if not isinstance(items, list) or not items:
            errors.append(f"engineering plan needs nonempty {name}")
            continue
        for item in items:
            if not isinstance(item, dict) or not re.fullmatch(r"[A-Z]-\d{2,}", str(item.get("id", ""))):
                errors.append(f"{name}: invalid item/id")
                continue
            if item["id"] in groups[name]:
                errors.append(f"{name}: duplicate {item['id']}")
            groups[name][item["id"]] = item

    def fields(item, names, lists=()):
        for name in names:
            if not text(item.get(name)):
                errors.append(f"{item['id']} needs {name}")
        for name in lists:
            if not strings(item.get(name)):
                errors.append(f"{item['id']} needs nonempty {name}")
        if "files" in lists and strings(item.get("files")):
            if any(not relative(path) for path in item["files"]):
                errors.append(f"{item['id']} files must stay inside project")

    def refs(item, field, known, empty=False):
        values = item.get(field)
        if not strings(values, empty=empty):
            errors.append(f"{item['id']} needs {field}")
            return []
        if len(values) != len(set(values)) or any(v not in known for v in values):
            errors.append(f"{item['id']} {field}: duplicate or unknown reference")
        return values

    def verification(value, label, negative=False):
        if not isinstance(value, dict):
            errors.append(f"{label}: verification must be an object")
            return
        if not text(value.get("command")):
            errors.append(f"{label}: command required")
        engine.validate_assertion(value.get("assertion"), label, errors)
        timeout = value.get("timeout_seconds", 120)
        if type(timeout) is not int or not 1 <= timeout <= 3600:
            errors.append(f"{label}: timeout_seconds must be 1..3600")
        if negative and (type(value.get("expected_exit_code")) is not int
                         or not 1 <= value["expected_exit_code"] <= 255 or not text(value.get("reason"))):
            errors.append(f"{label}: negative control needs reason and expected_exit_code 1..255")
        if not negative and "expected_exit_code" in value:
            errors.append(f"{label}: only negative controls may override the successful exit code")

    for component in groups["components"].values():
        fields(component, ("responsibility",), ("files", "interfaces"))
    for boundary in groups["boundaries"].values():
        fields(boundary, ("target", "driver"))
        if boundary.get("kind") not in ("cli", "api", "browser", "desktop", "filesystem"):
            errors.append(f"{boundary['id']}: unknown boundary kind")
        if type(boundary.get("external")) is not bool:
            errors.append(f"{boundary['id']}: external must be explicit boolean")
        if boundary.get("external") is True:
            verification(boundary.get("probe"), boundary["id"] + " probe")
    outcomes = {o["id"]: o for o in goal["outcomes"]}
    covered, used_boundaries, ui_outcomes = set(), set(), set()
    for journey in groups["journeys"].values():
        fields(journey, ("entry", "preconditions", "expected"), ("actions",))
        oids = refs(journey, "outcome_ids", outcomes)
        bids = refs(journey, "boundary_ids", groups["boundaries"])
        covered.update(oids)
        used_boundaries.update(bids)
        verification(journey.get("verification"), journey["id"])
        if not layered or "negative_control" in journey:
            verification(journey.get("negative_control"), journey["id"] + " negative", negative=True)
        if any(groups["boundaries"].get(b, {}).get("kind") in ("desktop", "browser") for b in bids):
            ui_outcomes.update(oids)
    for oid, outcome in outcomes.items():
        if not any(oid in j.get("outcome_ids", []) and j.get("verification") == outcome["verification"]
                   for j in groups["journeys"].values() if isinstance(j.get("outcome_ids"), list)):
            errors.append(f"{oid}: goal verification must match a mapped public journey")
    if covered != set(outcomes):
        errors.append("journey coverage must include every outcome")
    if used_boundaries != set(groups["boundaries"]):
        errors.append("every boundary must be exercised by a journey")
    ui = goal.get("ui", {})
    if ui_outcomes and (ui.get("required") is not True or not set(ui_outcomes) <= set(ui.get("outcome_ids") or [])):
        errors.append("UI boundaries require goal.ui.required=true and all mapped outcome_ids")
    edges, used_components, used_journeys = [], set(), set()
    for step in groups["steps"].values():
        fields(step, ("context", "change", "rollback"), ("files", "bounds"))
        if text(step.get("change")) and re.search(r"\b(TODO|TBD)\b|调查后定|实现相关功能", step["change"], re.I):
            errors.append(f"{step['id']}: change contains a placeholder; resolve it or specify a bounded probe")
        deps = refs(step, "depends_on", groups["steps"], empty=True)
        edges.extend((d, step["id"]) for d in deps)
        used_components.update(refs(step, "component_ids", groups["components"]))
        used_journeys.update(refs(step, "journey_ids", groups["journeys"], empty=layered))
    engine.check_dag(list(groups["steps"]), edges, "engineering step dependencies", errors)
    if used_components != set(groups["components"]):
        errors.append("every component needs an implementation step")
    if used_journeys != set(groups["journeys"]):
        errors.append("every journey needs a verification step")
    if layered:
        validate_layered(plan, groups, fields, refs, verification, errors)
    if not errors and plan["schema"] == "engineering-plan/3":
        errors.extend(planning_readiness.validate(plan, goal, groups))
    return errors


def validate_layered(plan, groups, fields, refs, verification, errors):
    """Check handoff completeness and interface/real-boundary ordering, not prose quality."""
    if not strings(plan.get("shared_context")):
        errors.append("engineering plan needs shared_context (project-wide invariants)")
    decisions = plan.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        errors.append("engineering plan needs decisions with reason and evidence")
    else:
        for d in decisions:
            if not isinstance(d, dict) or any(not text(d.get(k)) for k in ("decision", "reason", "evidence")):
                errors.append("design decision needs decision, reason and evidence")
    contracts = {}
    items = plan.get("contracts")
    if not isinstance(items, list):
        errors.append("contracts must be an array (empty only when no shared interfaces)")
        items = []
    for item in items:
        if not isinstance(item, dict) or not re.fullmatch(r"K-\d{2,}", str(item.get("id", ""))):
            errors.append("invalid interface contract")
            continue
        fields(item, ("signature", "definition", "owner"))
        if item.get("owner") not in groups["components"]:
            errors.append(f"{item['id']}: contract owner is not a component")
        if item["id"] in contracts:
            errors.append("duplicate contract " + item["id"])
        contracts[item["id"]] = item
    producers, boundary_steps, consumed = {}, {}, {}
    for step in groups["steps"].values():
        sid = step["id"]
        fields(step, (), ("implementation",))
        for key in ("read_files",):
            if not strings(step.get(key), empty=True) or any(not relative(p) for p in step.get(key, []) if isinstance(p, str)):
                errors.append(f"{sid}: {key} must be explicit project-relative paths")
        routes = step.get("failure_routes")
        if not isinstance(routes, dict) or any(not text(routes.get(k)) for k in ("implementation", "environment", "design")):
            errors.append(f"{sid}: failure_routes needs implementation/environment/design")
        consumed[sid] = refs(step, "consumes", contracts, empty=True)
        for kid in refs(step, "produces", contracts, empty=True):
            if kid in producers:
                errors.append(f"{kid}: multiple producer steps")
            producers[kid] = sid
            if contracts.get(kid, {}).get("owner") not in (step.get("component_ids") or []):
                errors.append(f"{kid}: producer step must implement its owner component")
        refs(step, "preflight_boundary_ids", groups["boundaries"], empty=True)
        checks = step.get("checks")
        if not isinstance(checks, list):
            errors.append(f"{sid}: checks must be an array")
            checks = []
        if not checks and not step.get("journey_ids"):
            errors.append(f"{sid}: step needs a component/boundary check or integration journey")
        ids = set()
        for chk in checks:
            if not isinstance(chk, dict) or not re.fullmatch(r"T-\d{2,}", str(chk.get("id", ""))):
                errors.append(f"{sid}: invalid check")
                continue
            if chk["id"] in ids:
                errors.append(f"{sid}: duplicate check id")
            ids.add(chk["id"])
            verification(chk, sid + "/" + chk["id"])
            if "negative_control" in chk:
                verification(chk["negative_control"], sid + "/" + chk["id"] + " negative", negative=True)
            if chk.get("level") not in ("component", "boundary"):
                errors.append(f"{sid}: check level must be component or boundary; use journey_ids for integration")
            bids = refs(chk, "boundary_ids", groups["boundaries"], empty=chk.get("level") == "component")
            if chk.get("level") == "boundary":
                for bid in bids:
                    boundary_steps.setdefault(bid, set()).add(sid)
            elif bids:
                errors.append(f"{sid}: component check cannot claim real-boundary coverage")
    # Iterative closure also terminates for malformed/cyclic input; base DAG validator reports cycles.
    ancestors = {sid: set() for sid in groups["steps"]}
    for _ in groups["steps"]:
        for sid, step in groups["steps"].items():
            deps = step.get("depends_on") if strings(step.get("depends_on"), empty=True) else []
            ancestors[sid].update(d for d in deps if d in ancestors)
            for d in deps:
                ancestors[sid].update(ancestors.get(d, set()))
    for kid in contracts:
        if kid not in producers:
            errors.append(f"{kid}: interface has no producer step")
    for sid, kids in consumed.items():
        for kid in kids:
            if producers.get(kid) not in ancestors[sid] | {sid}:
                errors.append(f"{sid}: consumes {kid} before its producer dependency")
    for sid, step in groups["steps"].items():
        jids = step.get("journey_ids") if strings(step.get("journey_ids"), empty=True) else []
        for jid in jids:
            journey = groups["journeys"].get(jid, {})
            bids = journey.get("boundary_ids") if strings(journey.get("boundary_ids")) else []
            for bid in bids:
                if groups["boundaries"].get(bid, {}).get("external") is True and not (boundary_steps.get(bid, set()) & ancestors[sid]):
                    errors.append(f"{sid}: external boundary {bid} needs an earlier boundary-check dependency before its integration journey")


VIEW_HEADER = "<!-- generated engineering plan view; edit the source design instead -->\n"


def readable_plan(source, plan):
    """Render one authoritative index into human task cards; the planner never maintains two specs."""
    def code(value):
        fence = "`" * max(3, max((len(m) + 1 for m in re.findall(r"`+", value)), default=3))
        return f"\n{fence}text\n{value}\n{fence}\n"

    def checks(spec, label):
        expected = json.dumps(spec["assertion"], ensure_ascii=False)
        return f"\n**{label}**\n" + code(spec["command"]) + f"预期断言：`{expected}`；退出码：{spec.get('expected_exit_code', 0)}。\n"

    sections = ["## 核心设计\n", plan["architecture"] + "\n", "数据/控制流：" + plan["data_flow"] + "\n",
                "\n**全局约定**\n"]
    sections += ["- " + item + "\n" for item in plan.get("shared_context", [])]
    for decision in plan.get("decisions", []):
        sections.append(f"\n技术决定：{decision['decision']}\n\n理由：{decision['reason']}\n\n依据：{decision['evidence']}\n")
        if "evidence_level" in decision:
            sections.append(f"\n证据级别：{decision['evidence_level']}；范围：{decision['scope']}；证伪条件：{decision['invalidated_by']}\n")
    if plan.get("conditions"):
        sections.append("\n## 待决条件（未满足前不等于可施工）\n")
        for condition in plan["conditions"]:
            sections.append(f"\n- {condition['id']} / {condition['kind']}：{condition['claim']}\n"
                            f"  解除标准：{condition['criterion']}；影响：{', '.join(condition['affects'])} 及后继任务。\n")
    if "design_review" in plan:
        review = plan["design_review"]
        sections.append(f"\n设计审查方式：{review['mode']}；理由：{review['reason']}；这不是已完成审查的声明。\n")
    sections.append("\n## 组件与真实边界\n")
    for component in plan["components"]:
        sections.append(f"\n- {component['id']}：{component['responsibility']}；文件：" + ", ".join(component["files"]) +
                        "；接口：" + ", ".join(component["interfaces"]) + "\n")
    for boundary in plan["boundaries"]:
        sections.append(f"\n- {boundary['id']}（{boundary['kind']}）：{boundary['target']}；通过 {boundary['driver']}\n")
    sections.append("\n## 共享接口（唯一合同定义）\n")
    for contract in plan.get("contracts", []):
        sections += [f"### {contract['id']} — {contract['signature']}\n", code(contract["definition"])]
    sections.append("## 全部实施任务\n")
    journeys = {j["id"]: j for j in plan["journeys"]}
    boundaries = {b["id"]: b for b in plan["boundaries"]}
    for step in plan["steps"]:
        sections += [f"### {step['id']} — {step['context']}\n",
                     "依赖：" + ", ".join(step["depends_on"]) + "\n",
                     "必读：" + ", ".join(step.get("read_files", [])) + "\n",
                     "改动文件：" + ", ".join(step["files"]) + "\n",
                     "消费合同：" + ", ".join(step.get("consumes", [])) + "；产出合同：" + ", ".join(step.get("produces", [])) + "\n",
                     "\n**实现顺序**\n"]
        sections += [f"{i}. {action}\n" for i, action in enumerate(step.get("implementation", []), 1)]
        sections += ["\n**关键代码 / 算法**\n", code(step["change"]), "\n**边界行为**\n"]
        sections += ["- " + item + "\n" for item in step["bounds"]]
        for bid in step.get("preflight_boundary_ids", []):
            if boundaries[bid]["external"]:
                sections.append(checks(boundaries[bid]["probe"], "前提探测 " + bid))
        for chk in step.get("checks", []):
            sections.append(checks(chk, chk["level"] + " " + chk["id"]))
            if "negative_control" in chk:
                sections.append(checks(chk["negative_control"], "负向对照"))
        for jid in step["journey_ids"]:
            j = journeys[jid]
            sections += [f"\n**集成旅程 {jid}**\n\n前提：{j['preconditions']}\n\n动作：" + " → ".join(j["actions"]) + "\n",
                         "结果：" + j["expected"] + "\n", checks(j["verification"], "经交付入口验证")]
            if "negative_control" in j:
                sections.append(checks(j["negative_control"], "负向对照"))
        sections.append("\n**失败处理**\n")
        sections += [f"- {kind}：{route}\n" for kind, route in step.get("failure_routes", {}).items()]
        sections.append("\n回退：" + step["rollback"] + "\n")
    return VIEW_HEADER + re.sub(r"```json\s+engineering-plan\s*\n.*?\n```", lambda _: "\n".join(sections), source, count=1, flags=re.S)


def prepare(goal_path, plan_path, engine):
    """Publish the planner's artifact; derive bookkeeping instead of asking a worker to edit hashes/UI flags."""
    _, goal = engine.read_artifact(goal_path, "goal")
    if goal.get("status") == "complete":
        raise engine.ValidationError("cannot replace a completed goal's plan")
    root = engine.goal_project_root(goal_path)
    if not isinstance(goal.get("id"), str) or not engine.GOAL_ID_RE.fullmatch(goal["id"]):
        raise engine.ValidationError("invalid goal id")
    planning_readiness.publication_guard(root, goal_path, goal, engine)
    if not relative(plan_path):
        raise engine.ValidationError("plan path must be project-relative")
    path = (root / plan_path).resolve()
    try:
        path.relative_to(root)
        raw = path.read_bytes()
        plan = engine.parse_block(raw.decode("utf-8-sig"), "engineering-plan")
        if not isinstance(plan, dict):
            raise ValueError("plan must be an object")
        boundaries = {b["id"]: b for b in plan.get("boundaries", []) if isinstance(b, dict) and text(b.get("id"))}
        ui_ids = set()
        for j in plan.get("journeys", []):
            if not isinstance(j, dict):
                continue
            bids, oids = j.get("boundary_ids"), j.get("outcome_ids")
            if strings(bids) and strings(oids) and any(boundaries.get(b, {}).get("kind") in ("browser", "desktop") for b in bids):
                ui_ids.update(oids)
        updated = json.loads(json.dumps(goal))
        updated.update(schema_version=3, engineering_plan={"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(raw).hexdigest()},
                       ui={"required": bool(ui_ids), "reason": "Derived from engineering-plan boundary/journey mapping", "outcome_ids": sorted(ui_ids)})
        updated.setdefault("product_observation", default_observation_spec(ui_ids))
        changed = engine.goal_definition_hash(updated) != engine.goal_definition_hash(goal)
        if changed:
            updated["status"] = "active"
            for outcome in updated.get("outcomes", []):
                outcome["status"] = "pending"
                outcome.pop("evidence", None)
                outcome.pop("blocker", None)
        # Validate through the real artifact path rules BEFORE replacing the card.
        temp = None
        view_temp = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".md", dir=Path(goal_path).parent, delete=False) as f:
                temp = Path(f.name)
                f.write(engine.render_goal(updated))
            _, _, errors = engine.validate_goal_artifact(temp)
            if errors:
                raise engine.ValidationError("; ".join(errors))
            view = path.with_name(path.stem + ".readable.md").resolve()
            view.relative_to(root)
            if view == Path(goal_path).resolve():
                raise engine.ValidationError("readable plan would overwrite the goal card")
            old_view = view.read_bytes() if view.exists() else None
            if old_view is not None and old_view.decode("utf-8-sig").splitlines()[:1] != [VIEW_HEADER.strip()]:
                raise engine.ValidationError("refusing to overwrite unowned readable plan: " + str(view))
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=view.parent, delete=False) as f:
                view_temp = Path(f.name)
                f.write(readable_plan(raw.decode("utf-8-sig"), plan))
            os.replace(view_temp, view)
            if changed:
                try:
                    os.replace(temp, goal_path)
                except OSError:
                    if old_view is None:
                        view.unlink()
                    else:
                        view.write_bytes(old_view)
                    raise
            return {"plan": str(path), "readable_plan": str(view), "changed": changed, "next": "next-step", "note": "Structural validation only; planner must complete the design walkthrough"}
        finally:
            if temp and temp.exists():
                temp.unlink()
            if view_temp and view_temp.exists():
                view_temp.unlink()
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise engine.ValidationError(f"prepare-plan: {exc}") from exc


def load(goal_path, goal, engine):
    root = engine.goal_project_root(goal_path)
    ref = goal["engineering_plan"]
    path = (root / ref["path"]).resolve()
    try:
        path.relative_to(root)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
            raise ValueError("engineering_plan.sha256 mismatch; revise the goal binding and invalidate evidence")
        plan = engine.parse_block(raw.decode("utf-8-sig"), "engineering-plan")
        errors = validate(plan, goal, engine)
        if errors:
            raise ValueError("; ".join(errors))
        return plan
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise engine.ValidationError(f"engineering plan: {exc}") from exc


class Cycles:
    def __init__(self, goal_path, goal, engine):
        self.e, self.goal, self.path = engine, goal, Path(goal_path)
        self.root = engine.goal_project_root(goal_path)
        self.plan = load(goal_path, goal, engine)
        self.definition = engine.goal_definition_hash(goal)
        self.policy, errors = engine._load_state_policy(goal_path, goal["id"])
        if errors:
            raise engine.ValidationError("; ".join(errors))
        self.excludes = engine._state_policy_excludes(self.root, self.policy)
        self.identity = {"goal_definition_hash": self.definition, "runtime_state_policy": self.policy}
        self.home = self.path.parent / "cycles" / goal["id"] / engine.digest(self.identity, "delivery-cycles")
        self.steps = {s["id"]: s for s in self.plan["steps"]}
        self.journeys = {j["id"]: j for j in self.plan["journeys"]}
        self.boundaries = {b["id"]: b for b in self.plan["boundaries"]}
        self.readiness = planning_readiness.Readiness(self)

    def fail(self, message):
        raise self.e.ValidationError(message)

    def snapshot(self):
        return self.e.workspace_snapshot(self.root, self.excludes, self.goal.get("snapshot_include") or [])[0]

    def read(self, path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("expected object")
            return data
        except (OSError, ValueError) as exc:
            self.fail(f"cycle record unreadable {path}: {exc}")

    def write(self, path, value):
        # Create-only records: retries get a new attempt, never relabel old runs.
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        except FileExistsError:
            self.fail(f"cycle record already exists: {path}; observe it before retrying")

    def run(self, folder, name, spec):
        path = folder / (name + ".json")
        metadata = dict(self.identity, kind="delivery-cycle", assertion=spec["assertion"])
        payload, sha = self.e.run_command_evidence(
            spec["command"], self.root, path, metadata, spec.get("timeout_seconds", 120),
            snapshot_include=self.goal.get("snapshot_include") or [], state_excludes=self.excludes)
        return {"file": path.name, "sha256": sha}, self.receipt_ok(payload, spec)

    def receipt_ok(self, payload, spec):
        return (all(payload.get(k) == v for k, v in self.identity.items())
                and payload.get("kind") == "delivery-cycle"
                and payload.get("command") == spec["command"] and payload.get("cwd") == str(self.root)
                and payload.get("timeout_seconds") == spec.get("timeout_seconds", 120)
                and type(payload.get("exit_code")) is int
                and payload["exit_code"] == spec.get("expected_exit_code", 0)
                and payload.get("timed_out") is False and payload.get("workspace_changed") is False
                and payload.get("assertion") == spec["assertion"]
                and self.e.evaluate_assertion(payload.get("stdout"), spec["assertion"]))

    def specs(self, step, probe=False):
        layered = self.plan["schema"] in ("engineering-plan/2", "engineering-plan/3")
        if probe:
            bids = step["preflight_boundary_ids"] if layered else {b for j in step["journey_ids"] for b in self.journeys[j]["boundary_ids"]}
            return [(b + "-probe", self.boundaries[b]["probe"]) for b in sorted(bids) if self.boundaries[b]["external"]]
        specs = []
        for chk in step.get("checks", []) if layered else []:
            if "negative_control" in chk:
                specs.append((chk["id"] + "-negative_control", chk["negative_control"]))
            specs.append((chk["id"] + "-" + chk["level"], chk))
        for jid in step["journey_ids"]:
            for kind in ("negative_control", "verification"):
                if kind in self.journeys[jid]:
                    specs.append((jid + "-" + kind, self.journeys[jid][kind]))
        return specs

    def verify_record(self, folder, name, step, probe=False):
        record = self.read(folder / name)
        expected = self.specs(step, probe)
        receipts = record.get("receipts")
        if not isinstance(receipts, list) or len(receipts) != len(expected):
            self.fail("cycle receipts do not cover its declared commands")
        passed = True
        for ref, (label, spec) in zip(receipts, expected):
            if not isinstance(ref, dict) or ref.get("file") != label + ".json":
                self.fail("cycle receipt command identity mismatch")
            path = folder / ref["file"]
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != ref.get("sha256"):
                self.fail("cycle receipt sha256 mismatch")
            payload = self.read(path)
            passed = passed and self.receipt_ok(payload, spec)
            if payload.get("workspace_before") != record.get("workspace") or payload.get("workspace_after") != record.get("workspace"):
                passed = False
        if record.get("passed") is not passed:
            self.fail("cycle result disagrees with its execution receipts")
        return record

    def history(self):
        folders = sorted(p for p in self.home.glob("[0-9]*") if p.is_dir())
        completed = set()
        for index, folder in enumerate(folders):
            start = self.read(folder / "start.json")
            if any(start.get(k) != v for k, v in self.identity.items()) or start.get("step") not in self.steps:
                self.fail("cycle start identity mismatch")
            step = self.steps[start["step"]]
            if not set(step["depends_on"]) <= completed:
                self.fail("cycle dependency has no observed passing result")
            # Re-running a step invalidates that step and every downstream step.
            affected = {step["id"]}
            while True:
                expanded = affected | {s["id"] for s in self.steps.values() if set(s["depends_on"]) & affected}
                if expanded == affected:
                    break
                affected = expanded
            completed -= affected
            observation_path = folder / "observation.json"
            if not observation_path.exists():
                if index != len(folders) - 1:
                    self.fail("unobserved cycle precedes another attempt")
                return folders, completed, folder
            obs = self.read(observation_path)
            for field in ("actual", "interpretation", "next_action"):
                if not text(obs.get(field)):
                    self.fail("cycle observation lacks " + field)
            if obs.get("decision") not in ("advance", "retry", "blocked", "replan"):
                self.fail("invalid cycle observation decision")
            binding = self.e._sha256_file(folder / "result.json") if (folder / "result.json").exists() else None
            if obs.get("result_sha256") != binding:
                self.fail("cycle observation/result binding changed")
            if obs["decision"] == "advance":
                preflight = self.verify_record(folder, "preflight.json", step, probe=True)
                result = self.verify_record(folder, "result.json", step)
                if not preflight["passed"] or not result["passed"]:
                    self.fail("cannot advance from a failed cycle")
                completed.add(step["id"])
        return folders, completed, None

    def readbacks(self, folder):
        outputs = []
        step = self.steps[self.read(folder / "start.json")["step"]]
        for name, _ in self.specs(step, probe=True) + self.specs(step):
            path = folder / (name + ".json")
            if path.is_file():
                p = self.read(path)
                outputs.append({"path": str(path), "command": p.get("command"), "exit_code": p.get("exit_code"),
                                "stdout": str(p.get("stdout", ""))[:6000], "stderr": str(p.get("stderr", ""))[:6000],
                                "timed_out": p.get("timed_out"),
                                "truncated": len(str(p.get("stdout", ""))) > 6000 or len(str(p.get("stderr", ""))) > 6000})
        return outputs

    def next_packet(self):
        folders, completed, active = self.history()
        hold = self.readiness.hold()
        if hold:
            return dict(hold, goal=self.goal["goal"], plan=self.goal["engineering_plan"]["path"],
                        active_cycle=str(active) if active else None,
                        instructions=["Resolve the actual owner decision; no success is implied and no cycle history is rewritten."])
        if active:
            sid = self.read(active / "start.json")["step"]
            action = "observe" if (active / "result.json").exists() else "implement"
            if not (active / "preflight.json").exists() or not self.read(active / "preflight.json").get("passed"):
                action = "blocked"
            elif action == "implement" and any((active / (name + suffix)).exists()
                                                for name, _ in self.specs(self.steps[sid])
                                                for suffix in (".json", ".json.tmp")):
                action = "blocked"  # incomplete verification; inspect effects, then observe retry
        elif folders and self.read(folders[-1] / "observation.json")["decision"] != "advance":
            sid = self.read(folders[-1] / "start.json")["step"]
            decision = self.read(folders[-1] / "observation.json")["decision"]
            action = "replan" if decision == "replan" else "retry" if decision == "retry" else "blocked"
        else:
            ready = [s for s in self.plan["steps"] if s["id"] not in completed and set(s["depends_on"]) <= completed]
            unblocked = [s for s in ready if not self.readiness.pending(s["id"], completed) and not self.readiness.missing_files(s["id"])]
            if unblocked:
                ready = unblocked
            if not ready:
                pending_steps = [s for s in self.plan["steps"] if self.readiness.pending(s["id"], completed)]
                if pending_steps:
                    sid, action = pending_steps[0]["id"], "blocked"
                elif folders and self.read(folders[-1] / "result.json")["workspace"] != self.snapshot():
                    sid, action = self.read(folders[-1] / "start.json")["step"], "revalidate"
                else:
                    return {"action": "final-acceptance", "completed": sorted(completed),
                            "instructions": ["Run final outcomes, required UI/product observation and finish-goal; steps passing is not delivery acceptance."]}
            else:
                sid, action = ready[0]["id"], "begin-cycle"
        step = self.steps[sid]
        pending_conditions = self.readiness.pending(sid, completed)
        missing_files = self.readiness.missing_files(sid)
        if pending_conditions or missing_files:
            action = "blocked"
        kids = set(step.get("consumes", []) + step.get("produces", []))
        packet = {"schema": "implementation-packet/1", "action": action, "goal": self.goal["goal"],
                  "plan": self.goal["engineering_plan"]["path"], "architecture": self.plan["architecture"],
                  "shared_context": self.plan.get("shared_context", self.goal["constraints"]),
                  "step": step, "contracts": [c for c in self.plan.get("contracts", []) if c["id"] in kids],
                  "completed_dependencies": [d for d in step["depends_on"] if d in completed],
                  "pending_conditions": pending_conditions, "missing_preflight_files": missing_files,
                  "instructions": ["Read only read_files and current step's relevant sources. Implement no later step.",
                                   "If existing code already satisfies the task, verify it; do not rewrite working code just because the plan binding changed.",
                                   "Use exact shared contracts. Local implementation failures: repair; missing environment: blocked; interface/architecture conflict: replan.",
                                   "Run this step's checks, inspect actual output, then observe before continuing. Component PASS is not real-boundary or journey PASS."]}
        if step["journey_ids"]:
            packet["journeys"] = [self.journeys[j] for j in step["journey_ids"]]
        bids = set(step.get("preflight_boundary_ids", []))
        for c in step.get("checks", []):
            bids.update(c.get("boundary_ids", []))
        for j in step["journey_ids"]:
            bids.update(self.journeys[j]["boundary_ids"])
        if bids:
            packet["boundaries"] = [self.boundaries[b] for b in sorted(bids)]
        if active:
            packet["observed"] = self.readbacks(active)
        elif folders and action in ("replan", "retry", "blocked"):
            packet["feedback"] = self.read(folders[-1] / "observation.json")
        return packet

    def begin(self, step_id):
        self.readiness.guard()
        folders, completed, active = self.history()
        if active:
            self.fail("previous cycle needs execution and observation before the next cycle")
        step = self.steps.get(step_id)
        if step is None or not set(step["depends_on"]) <= completed:
            self.fail("unknown step or dependency not yet observed")
        pending = self.readiness.pending(step_id, completed)
        missing = self.readiness.missing_files(step_id)
        if pending or missing:
            self.fail("step not ready: " + json.dumps({"conditions": pending, "preflight_files": missing}, ensure_ascii=False))
        if folders and self.read(folders[-1] / "observation.json")["decision"] != "advance":
            if self.read(folders[-1] / "observation.json")["decision"] == "replan":
                self.fail("design conflict requires a revised planner artifact before implementation resumes")
            if self.read(folders[-1] / "start.json")["step"] != step_id:
                self.fail("retry the blocked step before expanding implementation")
        folder = self.home / f"{len(folders) + 1:04d}"
        self.write(folder / "start.json", dict(self.identity, step=step_id, started_at=self.e._now_iso()))
        passed, receipts, snapshot = True, [], self.snapshot()
        for name, spec in self.specs(step, probe=True):
            ref, ok = self.run(folder, name, spec)
            receipts.append(ref)
            passed = passed and ok
        passed = passed and snapshot == self.snapshot()
        self.write(folder / "preflight.json", {"passed": passed, "receipts": receipts, "workspace": snapshot})
        return {"cycle": str(folder), "passed": passed, "observed": self.readbacks(folder),
                "next": "implement one step" if passed else "observe blocker; do not implement"}

    def verify(self):
        self.readiness.guard()
        _, completed, folder = self.history()
        if folder is None:
            self.fail("begin-cycle required before verification")
        step = self.steps[self.read(folder / "start.json")["step"]]
        if self.readiness.pending(step["id"], completed):
            self.fail("step has unresolved planning conditions")
        if not self.verify_record(folder, "preflight.json", step, probe=True)["passed"]:
            self.fail("external preflight failed; observe and retry before implementation")
        if (folder / "result.json").exists():
            self.fail("cycle already tested; observation required before another run")
        passed, receipts, snapshot = True, [], self.snapshot()
        for name, spec in self.specs(step):
            ref, ok = self.run(folder, name, spec)
            receipts.append(ref)
            passed = passed and ok
        passed = passed and snapshot == self.snapshot()
        result = {"passed": passed, "receipts": receipts, "workspace": snapshot}
        self.write(folder / "result.json", result)
        return dict(result, cycle=str(folder), observed=self.readbacks(folder), next="inspect observed output then observe-cycle")

    def observe(self, source):
        self.readiness.guard()
        _, completed, folder = self.history()
        if folder is None:
            self.fail("no unobserved cycle")
        obs = dict(source) if isinstance(source, dict) else self.read(Path(source))
        if isinstance(source, dict):
            obs["actual"] = json.dumps(self.readbacks(folder), ensure_ascii=False)
            obs.setdefault("next_action", "next-step selects the dependency-ready task or returns to planner")
        if any(not text(obs.get(f)) for f in ("actual", "interpretation", "next_action")):
            self.fail("observation needs actual, interpretation and next_action")
        if obs.get("decision") not in ("advance", "retry", "blocked", "replan"):
            self.fail("observation decision must be advance, retry, blocked or replan")
        if obs["decision"] == "advance":
            step = self.steps[self.read(folder / "start.json")["step"]]
            if self.readiness.pending(step["id"], completed):
                self.fail("cannot advance with unresolved planning conditions")
            preflight = self.verify_record(folder, "preflight.json", step, probe=True)
            result = self.verify_record(folder, "result.json", step)
            if not preflight["passed"] or not result["passed"] or result["workspace"] != self.snapshot():
                self.fail("failed or stale cycle cannot advance; inspect evidence and retry")
        # An interrupted run may only be retried/blocked, never accepted.
        record = {f: obs[f] for f in ("actual", "interpretation", "decision", "next_action")}
        record.update(observed_at=self.e._now_iso(), result_sha256=(
            self.e._sha256_file(folder / "result.json") if (folder / "result.json").exists() else None))
        self.write(folder / "observation.json", record)
        return record

    def gate(self):
        self.readiness.guard()
        folders, completed, active = self.history()
        if active:
            self.fail("cycle observation missing; inspect the actual results before proceeding")
        if set(self.steps) != completed:
            self.fail("engineering steps lack observed real verification: " + ", ".join(sorted(set(self.steps) - completed)))
        for sid in self.steps:
            if self.readiness.pending(sid, completed):
                self.fail("unresolved planning conditions for " + sid)
        last = self.read(folders[-1] / "result.json")
        if last["workspace"] != self.snapshot():
            self.fail("cycle evidence is stale after product changes; begin a new verification cycle")
        return {"passed": True, "steps": sorted(completed)}
