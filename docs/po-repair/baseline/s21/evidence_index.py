#!/usr/bin/env python3
"""S21 evidence index builder (read-only over repo)."""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

FUNCS = {
    "scripts/observation_contract.py": [
        "is_blocking_finding", "semantic_finding_problems",
        "review_verdict_consistency_problems", "resolution_binding_problems",
        "validate_result_payload", "validate_review_payload",
    ],
    "scripts/product_observation.py": [
        "collect_observation_problems", "write_gate_record",
        "validate_candidate_manifest", "load_sidecar",
    ],
    "scripts/check.py": [
        "enforce_product_observation", "enforce_workspace_binding",
        "observation_state_policy_problems",
    ],
    "scripts/observation_results.py": [
        "parse_single_payload", "adopt_result", "adopt_review",
        "run_format_repair", "repair_prompt", "provenance_problems",
        "model_mismatch_problems", "file_lock", "update_sidecar",
    ],
    "scripts/runtime_state_policy.py": [
        "snapshot_excludes", "candidate_policy_alignment_problems", "load_policy",
    ],
    "scripts/observation_process.py": [
        "run_process", "run_process_capture", "kill_process_tree",
        "session_cleanup", "cleanup_directory",
    ],
    "scripts/observation_backend.py": [
        "preflight_skip_plan", "choose_backend", "agent_browser_argv", "run_step_sequence",
    ],
    "scripts/observation_vision.py": [
        "adapter_status", "host_requirements", "make_color_probe", "dispatch_mode",
        "perception_claim_problems",
    ],
    "scripts/observation_media.py": [
        "probe_media", "build_media_record", "capture_chain_verdict",
        "silence_claim_problems", "media_endpoint",
    ],
    "scripts/observation_resume.py": [
        "resume_plan", "merge_coverage", "no_progress_breaker", "lease_record",
        "lease_problems", "lease_required",
    ],
    "scripts/workflow_packets.py": ["build_observer_packet", "validate_packet"],
    "scripts/visibility_config.py": ["resolve", "load", "save", "parse"],
    "scripts/runtime_trace.py": ["verify_native_trace"],
    "scripts/observation_candidate.py": [
        "validate_runtime_state", "runtime_state_scope_problems", "undeclared_delivered_files",
    ],
    "validation/observation-calibration/driver_core.py": [
        "make_primary_mirror", "assert_single_channel", "seed_redaction_problems",
        "packet_guard", "state_reset", "server_order_plan", "adoption_result",
        "result_source_is_single",
    ],
}

print("## implementation line numbers")
for rel, names in FUNCS.items():
    path = REPO / rel
    found = {}
    if path.exists():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
                found.setdefault(node.name, node.lineno)
    print(rel, {n: found.get(n) for n in names})

print()
print("## test catalog")
TEST_FILES = [
    "tests/test_product_observation.py",
    "tests/test_observation_gate.py",
    "tests/test_observation_semantics.py",
    "tests/test_observation_candidate.py",
    "tests/test_observation_state_binding.py",
    "tests/test_observation_results.py",
    "tests/test_observation_format_repair.py",
    "tests/test_observation_backend.py",
    "tests/test_observation_vision.py",
    "tests/test_observation_media.py",
    "tests/test_observation_resume.py",
    "tests/test_observation_docs.py",
    "tests/test_visibility_config.py",
    "tests/test_install.py",
    "tests/test_observation_contract.py",
    "tests/test_observation_malformed.py",
    "tests/test_observation_permissions.py",
    "tests/test_observation_dispatch.py",
    "tests/test_calibration_driver.py",
    "tests/test_subagent_orchestration.py",
    "tests/test_observer_packets.py",
    "tests/test_observation_process.py",
    "tests/test_workflow_metrics.py",
]
for rel in TEST_FILES:
    path = REPO / rel
    if not path.exists():
        print("==", rel, "(missing)")
        continue
    tree = ast.parse(path.read_text(encoding="utf-8"))
    print("==", rel)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            names = [n.name for n in node.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
            print("  class", node.name, len(names))
            for n in names:
                print("    ", n)
        elif isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            print("  fn", node.name)
