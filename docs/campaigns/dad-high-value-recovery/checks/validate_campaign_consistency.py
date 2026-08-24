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
        for relative, expected in job["input_digests"].items():
            path = REPO_ROOT / relative
            if expected.startswith(RECEIPT_BOUND_DIGEST):
                if relative not in dependency_outputs:
                    errors.append(
                        f"{job_id} symbolic digest is not a direct dependency output: "
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
        if execution.get("parent_semantics") != "cohort-reconciliation-gate-only":
            errors.append(f"{stage} parent must be reconciliation-only")
        if execution.get("controller_max_concurrency") != 1:
            errors.append(f"{stage} child concurrency must be one")
        child_gate = execution.get("child_acceptance", {})
        if (
            child_gate.get("revision") != "1"
            or "{job_id}" not in child_gate.get("evidence_path_template", "")
            or not child_gate.get("revalidation_triggers")
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

    checker = _load_receipt_checker()
    template = json.loads(RECEIPT_TEMPLATE.read_text(encoding="utf-8"))
    if set(template) != checker.REQUIRED_FIELDS:
        errors.append("receipt template fields differ from fail-closed validator")
    flattened_jobs = checker._manifest_jobs(manifest)
    if set(flattened_jobs) != set(jobs) | all_child_ids:
        errors.append("receipt checker job/atomic-child inventory is incomplete")
    mesh = json.loads(MESH_PATH.read_text(encoding="utf-8"))
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
