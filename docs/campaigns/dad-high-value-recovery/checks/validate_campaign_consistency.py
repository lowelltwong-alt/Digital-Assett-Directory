#!/usr/bin/env python3
"""Validate campaign-to-packet, digest, CI, pilot, mesh, and receipt consistency.

This is a static fail-closed specification check. It does not launch work,
evaluate evidence truth, or authorize any repository/external effect.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any


CAMPAIGN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CAMPAIGN_ROOT.parents[2]
MANIFEST_PATH = CAMPAIGN_ROOT / "campaign.json"
MESH_PATH = CAMPAIGN_ROOT / "mesh" / "agent-mesh.plan.v1.json"
RECEIPT_TEMPLATE = CAMPAIGN_ROOT / "checks" / "evidence-receipt.template.json"
PACKET_ID = re.compile(r"^(J-[0-9]{3})_")
LEASE_LINE = re.compile(
    r"^- Lease: ([0-9]+) minutes; heartbeat every ([0-9]+) minutes$",
    re.MULTILINE,
)
OPERATIONAL_BASELINE = (
    "processed/reports/dad-high-value-recovery/"
    "operational-eligibility-baseline.json"
)
RECEIPT_BOUND_DIGEST = "receipt-bound-output-digest:"
EXPECTED_REVISION = "7-atomic-terminal-navigation-candidate-20260826"
EXPECTED_ADAPTER_REVISION = "dad-campaign-codex-shell-adapter:0.3.0-prelaunch"
ATOMIC_SLOT_SCHEMA = "dad.campaign.atomic_case_slots.v2"
CASE_BINDING_TABLE_SCHEMA = "dad.campaign.atomic_case_binding_table.v2"
COHORT_CLOSURES = {
    "J-510": "processed/reports/dad-high-value-recovery/pilot-shadow-10-closure.json",
    "J-520": "processed/reports/dad-high-value-recovery/pilot-comparison-20-closure.json",
    "J-530": "processed/reports/dad-high-value-recovery/pilot-value-gate-40-closure.json",
}
CASE_ENVELOPE_TEMPLATE = (
    "processed/reports/dad-high-value-recovery/pilot-case-envelopes/{job_id}.json"
)
TERMINAL_ROUTE_IDS = {
    "p5a-valid-terminal",
    "p5a-inconclusive",
    "p5b-valid-terminal",
    "p5b-inconclusive",
    "p5c-pass",
    "p5c-valid-terminal",
    "p5c-inconclusive",
}
NAVIGATION_RECEIPT_TEMPLATE = (
    "docs/campaigns/dad-high-value-recovery/checks/evidence/navigation/"
    "{route_id}.json"
)
NAVIGATION_POST_RECEIPT_TEMPLATE = (
    "docs/campaigns/dad-high-value-recovery/checks/evidence/navigation/"
    "{route_id}-post-j600.json"
)
NAVIGATION_PROTECTED_PATHS = {
    "docs/campaigns/dad-high-value-recovery/07_EVIDENCE_INDEX.md",
    "docs/campaigns/dad-high-value-recovery/handoff.md",
    "docs/campaigns/dad-high-value-recovery/08_SUPERSESSION_AND_ARCHIVE_MAP.md",
    "docs/campaigns/dad-high-value-recovery/checks/evidence/navigation/",
}
EXPECTED_TERMINAL_ROUTES = {
    "p5c-pass": {
        "predecessor_job_id": "J-530",
        "result": ["pass"],
        "state": ["complete"],
        "coverage": ["complete"],
        "trigger_class": ["value-gate-pass"],
        "closure_path": COHORT_CLOSURES["J-530"],
        "permitted_decisions": ["scale", "narrow", "retire", "re-audit"],
    },
    "p5a-valid-terminal": {
        "predecessor_job_id": "J-510",
        "result": ["fail_terminal"],
        "state": ["failed"],
        "coverage": ["complete"],
        "trigger_class": ["privacy", "source-authority", "harmful", "material-safety"],
        "closure_path": COHORT_CLOSURES["J-510"],
        "permitted_decisions": ["narrow", "retire"],
    },
    "p5a-inconclusive": {
        "predecessor_job_id": "J-510",
        "result": ["inconclusive", "blocked_human"],
        "state": ["blocked"],
        "coverage": ["partial", "coverage_unavailable"],
        "trigger_class": [
            "missing",
            "stale",
            "unjoinable",
            "metric-corruption",
            "checker-integrity",
        ],
        "closure_path": COHORT_CLOSURES["J-510"],
        "permitted_decisions": ["re-audit"],
    },
    "p5b-valid-terminal": {
        "predecessor_job_id": "J-520",
        "result": ["fail_terminal"],
        "state": ["failed"],
        "coverage": ["complete"],
        "trigger_class": ["frozen-benefit-failure", "safety", "authority"],
        "closure_path": COHORT_CLOSURES["J-520"],
        "permitted_decisions": ["narrow", "retire"],
    },
    "p5b-inconclusive": {
        "predecessor_job_id": "J-520",
        "result": ["inconclusive", "blocked_human"],
        "state": ["blocked"],
        "coverage": ["partial", "coverage_unavailable"],
        "trigger_class": [
            "missing",
            "stale",
            "unjoinable",
            "metric-corruption",
            "checker-integrity",
        ],
        "closure_path": COHORT_CLOSURES["J-520"],
        "permitted_decisions": ["re-audit"],
    },
    "p5c-valid-terminal": {
        "predecessor_job_id": "J-530",
        "result": ["fail_terminal"],
        "state": ["failed"],
        "coverage": ["complete"],
        "trigger_class": [
            "frozen-benefit-failure",
            "guardrail-failure",
            "safety",
            "authority",
        ],
        "closure_path": COHORT_CLOSURES["J-530"],
        "permitted_decisions": ["narrow", "retire"],
    },
    "p5c-inconclusive": {
        "predecessor_job_id": "J-530",
        "result": ["inconclusive", "blocked_human"],
        "state": ["blocked"],
        "coverage": ["partial", "coverage_unavailable"],
        "trigger_class": [
            "missing",
            "stale",
            "unjoinable",
            "metric-corruption",
            "checker-integrity",
        ],
        "closure_path": COHORT_CLOSURES["J-530"],
        "permitted_decisions": ["re-audit"],
    },
}


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _jobs(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        job["id"]: job
        for phase in manifest["phases"]
        for wave in phase["waves"]
        for subwave in wave["subwaves"]
        for job in subwave["jobs"]
    }


def _phase(manifest: dict[str, Any], phase_id: str) -> dict[str, Any]:
    return next(phase for phase in manifest["phases"] if phase["id"] == phase_id)


def _load_receipt_checker() -> Any:
    path = CAMPAIGN_ROOT / "checks" / "verify_receipt_durability.py"
    spec = importlib.util.spec_from_file_location("receipt_checker", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def validate() -> list[str]:
    errors: list[str] = []
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    jobs = _jobs(manifest)
    if manifest.get("revision") != EXPECTED_REVISION:
        errors.append("campaign revision is not the frozen revision-7 candidate")
    adapter = manifest.get("execution", {}).get("adapter", {})
    if adapter.get("revision") != EXPECTED_ADAPTER_REVISION:
        errors.append("campaign adapter revision is not the frozen 0.3 candidate")
    if (
        manifest.get("execution", {}).get("mode") != "specification_only"
        or manifest.get("execution", {}).get("execution_authorized") is not False
        or manifest.get("execution", {}).get("launch_command") != "not-authorized"
    ):
        errors.append("revision-7 campaign must remain specification-only and inert")

    packet_ids = set()
    packets: dict[str, Path] = {}
    for packet in (CAMPAIGN_ROOT / "jobs").glob("J-*.md"):
        match = PACKET_ID.match(packet.name)
        if match:
            packet_ids.add(match.group(1))
            packets[match.group(1)] = packet
    if packet_ids != set(jobs):
        errors.append(
            "job packet/manifest IDs differ: "
            f"packets_only={sorted(packet_ids - set(jobs))}; "
            f"manifest_only={sorted(set(jobs) - packet_ids)}"
        )

    for job_id, packet in packets.items():
        match = LEASE_LINE.search(packet.read_text(encoding="utf-8"))
        if match and (
            jobs[job_id].get("lease_minutes") != int(match.group(1))
            or jobs[job_id].get("heartbeat_minutes") != int(match.group(2))
        ):
            errors.append(f"{job_id} packet/manifest lease or heartbeat differs")

    for source in manifest["source_authority"]:
        path = REPO_ROOT / source["path"]
        if not path.is_file():
            errors.append(f"missing source_authority file: {source['path']}")
        elif source["digest"] != _sha256(path):
            errors.append(f"stale source_authority digest: {source['path']}")

    for job_id, job in jobs.items():
        if set(job["inputs"]) != set(job["input_digests"]):
            errors.append(f"{job_id} input/input_digests keys differ")
            continue
        dependency_outputs = {
            output
            for dependency_id in job["depends_on"]
            for output in jobs.get(dependency_id, {}).get("outputs", [])
        }
        execution = job.get("case_execution", {})
        binding_source_outputs: set[str] = set()
        if isinstance(execution, dict):
            binding_job = jobs.get(str(execution.get("binding_job", "")), {})
            binding_table = execution.get("binding_table")
            if (
                isinstance(binding_table, str)
                and binding_table in binding_job.get("outputs", [])
            ):
                binding_source_outputs.add(binding_table)
        for relative, expected in job["input_digests"].items():
            path = REPO_ROOT / relative
            if expected.startswith(RECEIPT_BOUND_DIGEST):
                if (
                    relative not in dependency_outputs
                    and relative not in binding_source_outputs
                ):
                    errors.append(
                        f"{job_id} symbolic digest is not a direct dependency output "
                        "or accepted binding-source output: "
                        f"{relative}"
                    )
                elif path.is_file():
                    errors.append(
                        f"{job_id} must rebind materialized dependency output digest: "
                        f"{relative}"
                    )
                continue
            if not path.is_file():
                errors.append(f"{job_id} missing input: {relative}")
            elif expected != _sha256(path):
                errors.append(f"{job_id} stale input digest: {relative}")

    j100 = jobs.get("J-100", {})
    j400 = jobs.get("J-400", {})
    if OPERATIONAL_BASELINE not in j100.get("outputs", []):
        errors.append("J-100 must output the operational eligibility baseline")
    if OPERATIONAL_BASELINE not in j100.get("allowed_paths", []):
        errors.append("J-100 must be allowed to write the operational eligibility baseline")
    if OPERATIONAL_BASELINE not in j100.get("acceptance", [{}])[0].get("inputs", []):
        errors.append("J-100 acceptance must inspect the operational eligibility baseline")
    if "J-100" not in j400.get("depends_on", []):
        errors.append("J-400 must directly depend on accepted J-100")
    if OPERATIONAL_BASELINE not in j400.get("inputs", []):
        errors.append("J-400 must consume the exact operational eligibility baseline path")
    if OPERATIONAL_BASELINE not in j400.get("acceptance", [{}])[0].get("inputs", []):
        errors.append("J-400 acceptance must inspect the operational eligibility baseline")
    if j400.get("input_digests", {}).get(OPERATIONAL_BASELINE) != (
        "receipt-bound-output-digest:resolve-from-accepted-J-100"
    ):
        errors.append("J-400 must bind its operational baseline to J-100 acceptance")
    baseline_rubric = j100.get("acceptance", [{}])[0].get("rubric", "").casefold()
    for term in ("cutoff", "reason-code", "reconciliation"):
        if term not in baseline_rubric:
            errors.append(f"J-100 acceptance rubric is missing {term}")

    if "J-215" not in jobs:
        errors.append("J-215 scheduled stability job is missing")
    else:
        if jobs["J-215"]["depends_on"] != ["J-210"]:
            errors.append("J-215 must depend only on accepted J-210")
        observation = jobs["J-215"].get("observation_execution", {})
        slots = observation.get("slots", [])
        if len(slots) != 4 or observation.get("controller_max_concurrency") != 1:
            errors.append("J-215 must define four serial natural-schedule observation slots")
        if observation.get("manual_substitution_allowed") is not False:
            errors.append("J-215 manual scheduled-run substitution must be false")
    if "four scheduled" in jobs["J-210"]["acceptance"][0]["rubric"].casefold():
        errors.append("J-210 immediate gate still requires four scheduled runs")
    if "four consecutive" not in jobs["J-215"]["acceptance"][0]["rubric"].casefold():
        errors.append("J-215 acceptance does not require four consecutive runs")

    p3 = _phase(manifest, "P3")
    if p3["depends_on"] != ["J-210"]:
        errors.append("P3 must be released by immediate J-210, not calendar-complete P2")
    p5 = _phase(manifest, "P5")
    for label, dependencies in (
        ("P5", p5["depends_on"]),
        ("P5-W1", p5["waves"][0]["depends_on"]),
        ("P5-W1-S1", p5["waves"][0]["subwaves"][0]["depends_on"]),
    ):
        if "J-215" not in dependencies:
            errors.append(f"{label} must wait for J-215")
    if set(jobs["J-500"]["depends_on"]) != {"J-410", "J-215"}:
        errors.append("J-500 must wait for both J-410 and J-215")

    metric = jobs["J-500"].get("pilot_metric_contract", {})
    required_metric_fields = {
        "metric_id",
        "direction",
        "estimator",
        "analysis_population",
        "denominator",
        "missing_data_rule",
        "P5B_threshold",
        "P5C_threshold",
        "uncertainty_method",
    }
    if set(metric.get("required_frozen_fields", [])) != required_metric_fields:
        errors.append("J-500 does not freeze the complete primary metric contract")
    expected_metrics = {
        "cycle_time",
        "rework",
        "review_iterations",
        "defects_prevented",
        "operator_attention",
    }
    if set(metric.get("default_thresholds", {})) != expected_metrics:
        errors.append("J-500 threshold schedule does not cover every H-005 choice")
    binding_path = (
        "processed/reports/dad-high-value-recovery/pilot-case-bindings.json"
    )
    if binding_path not in jobs["J-500"]["outputs"]:
        errors.append("J-500 does not output the case binding table")

    all_child_ids: set[str] = set()
    all_checkpoints: set[str] = set()
    all_receipts: set[str] = set()
    all_envelopes: set[str] = set()
    child_attempts = 0
    child_cost = 0
    child_output = 0
    for stage, count, first_dependency in (
        ("J-510", 10, "J-500"),
        ("J-520", 20, "J-510"),
        ("J-530", 40, "J-520"),
    ):
        execution = jobs[stage].get("case_execution", {})
        slots = execution.get("slots", [])
        if execution.get("schema_version") != ATOMIC_SLOT_SCHEMA:
            errors.append(f"{stage} atomic child schema is not v2")
        if execution.get("parent_semantics") != "cohort-reconciliation-gate-only":
            errors.append(f"{stage} parent must be reconciliation-only")
        if execution.get("parent_action") != "validate":
            errors.append(f"{stage} parent action must be validate")
        if execution.get("controller_max_concurrency") != 1:
            errors.append(f"{stage} child concurrency must be one")
        if execution.get("binding_table_schema") != CASE_BINDING_TABLE_SCHEMA:
            errors.append(f"{stage} binding table schema is invalid")
        if execution.get("case_envelope_path_template") != CASE_ENVELOPE_TEMPLATE:
            errors.append(f"{stage} case envelope template is invalid")
        if execution.get("closure_path") != COHORT_CLOSURES[stage]:
            errors.append(f"{stage} closure path is invalid")
        if execution.get("closure_path") not in jobs[stage].get("outputs", []):
            errors.append(f"{stage} closure is not a declared parent output")
        if execution.get("closure_path") not in jobs[stage].get(
            "allowed_paths", []
        ):
            errors.append(f"{stage} closure is outside parent allowed_paths")
        if execution.get("materialization_mode") != (
            "in-memory-case-digest-substitution-only"
        ):
            errors.append(f"{stage} child materialization is not in-memory only")
        if execution.get("binding_table_digest_required_in") != [
            "child-packet",
            "lease",
            "dispatch-projection",
            "checkpoint",
            "receipt",
        ]:
            errors.append(f"{stage} binding-table digest propagation is incomplete")
        forbidden_classes = set(execution.get("child_forbidden_output_classes", []))
        if forbidden_classes != {
            "parent-aggregate",
            "parent-closure",
            "navigation-metadata",
            "checker-record",
        }:
            errors.append(f"{stage} child forbidden output classes are incomplete")
        closure_contract = execution.get("closure_contract", {})
        if not isinstance(closure_contract, dict) or not closure_contract or not all(
            value is True for value in closure_contract.values()
        ):
            errors.append(f"{stage} closure contract must fail closed on every invariant")
        child_gate = execution.get("child_acceptance", {})
        if (
            child_gate.get("revision") != "2"
            or "{job_id}" not in child_gate.get("evidence_path_template", "")
            or not child_gate.get("revalidation_triggers")
            or child_gate.get("producer_attempt_digest_required") is not True
            or child_gate.get("checker_record_digest_required") is not True
        ):
            errors.append(f"{stage} child acceptance template is incomplete")
        if len(slots) != count:
            errors.append(f"{stage} must enumerate exactly {count} child slots")
            continue
        for index, slot in enumerate(slots, start=1):
            expected_id = f"{stage}-C{index:02d}"
            expected_dependency = (
                first_dependency if index == 1 else f"{stage}-C{index - 1:02d}"
            )
            if slot.get("job_id") != expected_id:
                errors.append(f"{stage} slot {index} has wrong job_id")
            if slot.get("depends_on") != [expected_dependency]:
                errors.append(f"{expected_id} is not serially dependent")
            if slot.get("case_binding") != (
                "unbound-until-accepted-J-500-binding-table"
            ):
                errors.append(f"{expected_id} has an unsafe pre-bound case value")
            if expected_id not in slot.get("idempotency_key", ""):
                errors.append(f"{expected_id} idempotency key is not slot-specific")
            if slot.get("idempotency_key", "").count("{case_digest}") != 1:
                errors.append(f"{expected_id} does not have one case digest placeholder")
            envelope = CASE_ENVELOPE_TEMPLATE.replace("{job_id}", expected_id)
            if envelope in all_envelopes:
                errors.append(f"{expected_id} case envelope path is duplicated")
            all_envelopes.add(envelope)
            if envelope in jobs[stage].get("outputs", []):
                errors.append(f"{expected_id} envelope leaked into parent aggregate outputs")
            for collection, field in (
                (all_child_ids, "job_id"),
                (all_checkpoints, "checkpoint"),
                (all_receipts, "receipt"),
            ):
                value = slot.get(field)
                if not isinstance(value, str) or value in collection:
                    errors.append(f"{expected_id} duplicate or missing {field}")
                else:
                    collection.add(value)
        child_attempts += count * execution.get("max_attempts_per_child", 0)
        child_cost += count * execution.get("cost_ceiling_per_child", 0)
        child_output += count * execution.get("output_ceiling_mb_per_child", 0)

    outer_attempts = sum(job["max_attempts"] for job in jobs.values())
    outer_cost = sum(job["cost_ceiling"] for job in jobs.values())
    outer_output = sum(job["output_ceiling_mb"] for job in jobs.values())
    budgets = manifest["budgets"]
    if outer_attempts + child_attempts > budgets["max_attempts_total"]:
        errors.append("outer plus child attempts exceed campaign budget")
    if outer_cost + child_cost > budgets["cost_units"]:
        errors.append("outer plus child cost exceeds campaign budget")
    if outer_output + child_output > budgets["max_storage_mb"]:
        errors.append("outer plus child output ceilings exceed storage budget")
    if budgets["max_parallel_jobs"] != 1:
        errors.append("campaign must keep max_parallel_jobs at one")

    navigation = manifest.get("terminal_navigation", {})
    if not isinstance(navigation, dict):
        errors.append("terminal_navigation must be an object")
        navigation = {}
    if navigation.get("schema_version") != "dad.campaign.terminal_navigation.v1":
        errors.append("terminal navigation schema is invalid")
    if (
        navigation.get("controller_mode") != "projection_only"
        or navigation.get("dispatch_allowed") is not False
    ):
        errors.append("terminal navigation controller must remain inert")
    if (
        navigation.get("writer_role") != "campaign-navigation-writer"
        or navigation.get("checker_role") != "independent-checker"
        or navigation.get("writer_checker_distinct") is not True
    ):
        errors.append("terminal navigation writer/checker separation is invalid")
    if navigation.get("receipt_path_template") != NAVIGATION_RECEIPT_TEMPLATE:
        errors.append("terminal navigation receipt path template is invalid")
    if (
        navigation.get("post_j600_receipt_path_template")
        != NAVIGATION_POST_RECEIPT_TEMPLATE
    ):
        errors.append("terminal navigation post-J600 receipt path template is invalid")
    expected_receipt_contract = {
        "immutable_stage_specific_receipts": True,
        "pre_j600_stage": "accepted-terminal-route",
        "post_j600_stage": "post-j600-signed-decision",
        "required_projection_bindings": [
            "projection_digest",
            "navigation_stage",
            "navigation_paths",
            "output_digests",
            "dependency_route_id",
            "predecessor_receipt_digest",
            "closure_digest",
        ],
        "post_j600_additional_bindings": [
            "navigation_receipt_digest",
            "j600_receipt_digest",
        ],
        "overwrite_or_cross_stage_reuse_forbidden": True,
    }
    if navigation.get("receipt_contract") != expected_receipt_contract:
        errors.append("terminal navigation stage-specific receipt contract is invalid")
    if set(navigation.get("protected_paths", [])) != NAVIGATION_PROTECTED_PATHS:
        errors.append("terminal navigation protected path set is incomplete")
    if navigation.get("post_j600_only_paths") != [
        "docs/campaigns/dad-high-value-recovery/08_SUPERSESSION_AND_ARCHIVE_MAP.md"
    ]:
        errors.append("terminal navigation post-J600 path set is invalid")
    if navigation.get("j600_dependency_projection") != (
        "exactly-one-selected-predecessor"
    ):
        errors.append("J-600 dependency projection is not exactly one predecessor")
    if navigation.get("new_job_or_command_created") is not False:
        errors.append("terminal navigation must not create a job or command")
    routes = navigation.get("routes", [])
    route_rows = [row for row in routes if isinstance(row, dict)] if isinstance(
        routes, list
    ) else []
    if len(route_rows) != len(routes) if isinstance(routes, list) else True:
        errors.append("terminal navigation routes contain a non-object row")
    route_map = {
        row.get("route_id"): {
            key: value for key, value in row.items() if key != "route_id"
        }
        for row in route_rows
        if isinstance(row.get("route_id"), str)
    }
    if set(route_map) != TERMINAL_ROUTE_IDS or len(route_map) != len(route_rows):
        errors.append("terminal navigation route identities are incomplete or duplicated")
    for route_id, expected in EXPECTED_TERMINAL_ROUTES.items():
        if route_map.get(route_id) != expected:
            errors.append(f"terminal navigation route contract differs: {route_id}")
    if jobs.get("J-600", {}).get("depends_on") != []:
        errors.append("J-600 manifest dependencies must be empty until route materialization")
    for job_id, job in jobs.items():
        if set(job.get("allowed_paths", [])) & NAVIGATION_PROTECTED_PATHS:
            errors.append(f"ordinary job claims navigation-writer path: {job_id}")

    checker = _load_receipt_checker()
    expected_producer_digest_exclusions = {
        "producer_attempt_digest",
        "checker_role",
        "checker_identity",
        "independence_basis",
        "checker_record_path",
        "checker_record_digest",
    }
    if checker.PRODUCER_DIGEST_EXCLUDED_FIELDS != expected_producer_digest_exclusions:
        errors.append("producer-attempt digest exclusion contract differs")
    if checker.CHECKER_RECEIPT_DIGEST_SEMANTICS != "checker-file-bytes":
        errors.append("receipt checker digest is not bound to checker file bytes")
    template = json.loads(RECEIPT_TEMPLATE.read_text(encoding="utf-8"))
    if set(template) != checker.REQUIRED_FIELDS:
        errors.append("receipt template fields differ from fail-closed validator")
    flattened_jobs = checker._manifest_jobs(manifest)
    if set(flattened_jobs) != set(jobs) | all_child_ids:
        errors.append("receipt checker job/atomic-child inventory is incomplete")
    mesh = json.loads(MESH_PATH.read_text(encoding="utf-8"))
    mesh_roles = {
        row.get("role_id"): row
        for row in mesh.get("roles", [])
        if isinstance(row, dict) and isinstance(row.get("role_id"), str)
    }
    if not {"campaign-navigation-writer", "independent-checker"}.issubset(
        mesh_roles
    ):
        errors.append("mesh lacks terminal navigation writer/checker roles")
    navigation_role_text = json.dumps(
        mesh_roles.get("campaign-navigation-writer", {}), sort_keys=True
    )
    if not NAVIGATION_PROTECTED_PATHS.issubset(
        {
            path
            for path in NAVIGATION_PROTECTED_PATHS
            if path in navigation_role_text
        }
    ):
        errors.append("mesh navigation writer does not name every protected path")
    if mesh["source_snapshot_digest"] != _sha256(MANIFEST_PATH):
        errors.append("mesh source_snapshot_digest does not match campaign.json")
    return errors


def main() -> int:
    try:
        errors = validate()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors = [f"validator failed closed: {type(exc).__name__}: {exc}"]
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"INVALID: {len(errors)} consistency error(s)")
        return 1
    print(
        "VALID: campaign packets, digests, CI split, atomic pilot slots, "
        "budgets, receipt contract, and mesh snapshot are consistent "
        "(static specification only; no execution authorization)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
