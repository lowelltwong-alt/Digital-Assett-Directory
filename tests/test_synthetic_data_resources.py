from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from digital_asset_directory import validation
from digital_asset_directory.synthetic_data_resources import (
    load_synthetic_resources,
    synthetic_catalog,
    synthetic_route,
)


ROOT = Path(__file__).resolve().parents[1]


def test_registry_is_valid_unique_and_pointer_only() -> None:
    registry = load_synthetic_resources(ROOT)
    ids = [row["resource_id"] for row in registry["resources"]]
    assert len(ids) >= 35
    assert len(ids) == len(set(ids))
    assert registry["ai_agnostic"] is True
    assert registry["research_contract"]["auto_schedule"] is True
    assert registry["research_contract"]["auto_promote"] is False
    assert registry["research_contract"]["runtime_route"] == {
        "capability_alias": "luna",
        "reasoning_effort": "low",
        "adapter_revision_id": "portability-card-revision:runtime-adapter-codex-gpt-5-6-luna-low-weekly-research:0.1.1",
        "retirement_rule": registry["research_contract"]["runtime_route"]["retirement_rule"],
        "escalation_rule": registry["research_contract"]["runtime_route"]["escalation_rule"],
    }
    assert registry["research_contract"]["candidate_limits"] == {
        "max_candidates": 10,
        "max_immediate_decisions": 3,
        "max_read_only_scouts": 2,
    }
    assert registry["research_contract"]["external_content_security"]
    assert any("untrusted data" in row for row in registry["research_contract"]["external_content_security"])
    assert all(row["primary_sources"] for row in registry["resources"])
    assert all("prompt" not in row for row in registry["resources"])


def test_weekly_research_has_distinct_workflow_and_expiring_adapter() -> None:
    family = json.loads((ROOT / "registry/ml-agent-family-registry.json").read_text(encoding="utf-8"))
    workflows = {row["workflow_id"]: row for row in family["workflow_cards"]}
    assert workflows["workflow:ml-frontier-research-refresh"]["cadence"] == "P14D"
    assert workflows["workflow:ml-synthetic-helper-research-refresh"]["cadence"] == "P7D"
    registry = load_synthetic_resources(ROOT)
    contract = registry["research_contract"]
    helper = workflows["workflow:ml-synthetic-helper-research-refresh"]
    assert helper["activation_status"] == contract["activation_status"] == "human_activated"
    assert contract["auto_schedule"] is True
    assert contract["automation_binding"]["automation_id"] == "weekly-dad-external-asset-scout"
    portability = json.loads((ROOT / "registry/portable-capability-registry.json").read_text(encoding="utf-8"))
    cards = {row["artifact_id"]: row for row in portability["cards"]}
    core = cards["workflow:ml-synthetic-helper-research-refresh"]
    adapter = cards["runtime-adapter:codex-gpt-5-6-luna-low-weekly-research"]
    assert adapter["core_revision_id"] == core["revision_id"]
    assert adapter["target_capability_predicate"]["capability_alias"] == "luna"
    assert adapter["target_capability_predicate"]["reasoning_effort"] == "low"
    assert adapter["fresh_until"] < core["fresh_until"]


def test_clinocr_and_induocr_are_not_conflated() -> None:
    registry = load_synthetic_resources(ROOT)
    clin = next(row for row in registry["resources"] if row["resource_id"] == "synthetic-resource:clinocr-bench")
    indu = next(row for row in registry["resources"] if row["resource_id"] == "synthetic-resource:induocrbench")
    assert clin["synthetic_scope"] == "fully_synthetic"
    assert indu["synthetic_scope"] != "fully_synthetic"
    assert "real holdout" in " ".join(indu["use_when"]).lower()


def test_catalog_searches_use_cases_and_domains() -> None:
    result = synthetic_catalog(ROOT, query="clinical scanned", domain="document_ai")
    assert any(row["resource_id"] == "synthetic-resource:clinocr-bench" for row in result["resources"])
    assert result["candidate_only"] is True


def test_route_requires_positive_signal_and_blocks_known_risks() -> None:
    insufficient = synthetic_route(ROOT, objective="Improve OCR", modality="document_image")
    assert insufficient["disposition"] == "insufficient_evidence"
    assert insufficient["candidates"] == []
    blocked = synthetic_route(
        ROOT,
        objective="Improve OCR",
        modality="document_image",
        signals="scarce_labels,source_terms_unknown",
    )
    assert blocked["disposition"] == "blocked"
    assert blocked["dispatch_authorized"] is False


def test_high_consequence_requires_real_holdout() -> None:
    result = synthetic_route(
        ROOT,
        objective="Clinical scanned document OCR",
        modality="document_image",
        domain="document_ai healthcare",
        signals="scarce_labels,rare_cases,controllable_ground_truth",
        consequence="high",
    )
    assert result["disposition"] == "real_holdout_required"
    assert result["candidates"] == []
    permitted = synthetic_route(
        ROOT,
        objective="Clinical scanned document OCR",
        modality="document_image",
        domain="document_ai healthcare",
        signals="scarce_labels,rare_cases,controllable_ground_truth",
        real_holdout_available=True,
        consequence="high",
        limit=20,
    )
    assert permitted["disposition"] == "candidate_synthetic_path"
    assert permitted["dispatch_authorized"] is False
    assert permitted["candidates"][0]["resource_id"] == "synthetic-resource:clinocr-bench"
    assert permitted["candidates"][0]["candidate_role"] == "generator_or_dataset_candidate"
    real_holdout = next(row for row in permitted["candidates"] if row["resource_id"] == "synthetic-resource:induocrbench")
    assert real_holdout["candidate_role"] == "real_holdout_candidate"
    assert real_holdout["synthetic_scope"] == "real_validation_benchmark"
    assert real_holdout["terms_review_required"] is True


def test_retired_resources_never_route(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = load_synthetic_resources(ROOT)
    retired = dict(registry["resources"][0])
    retired["resource_id"] = "synthetic-resource:retired-fixture"
    retired["name"] = "Retired clinical OCR fixture"
    retired["status"] = "retired"
    registry = {**registry, "resources": [retired, *registry["resources"]]}
    monkeypatch.setattr(
        "digital_asset_directory.synthetic_data_resources.load_synthetic_resources",
        lambda _root: registry,
    )
    result = synthetic_route(
        ROOT,
        objective="Clinical OCR fixture",
        modality="document_image",
        domain="document_ai healthcare",
        signals="rare_cases",
        real_holdout_available=True,
    )
    assert all(row["resource_id"] != retired["resource_id"] for row in result["candidates"])


def test_route_is_deterministic_and_rejects_unknown_signal() -> None:
    kwargs = {
        "objective": "Generate rare industrial table layouts for OCR",
        "modality": "document_image",
        "domain": "document_ai",
        "signals": "rare_cases,controllable_ground_truth",
        "real_holdout_available": True,
    }
    assert synthetic_route(ROOT, **kwargs) == synthetic_route(ROOT, **kwargs)
    with pytest.raises(ValueError, match="unknown synthetic-data signals"):
        synthetic_route(ROOT, objective="x", signals="magic")


def test_route_requires_requested_modality_and_domain_compatibility() -> None:
    result = synthetic_route(
        ROOT,
        objective="Generate rare hardware examples",
        modality="quantum_state",
        domain="quantum_hardware",
        signals="rare_cases,controllable_ground_truth",
        real_holdout_available=True,
    )
    assert result["disposition"] == "insufficient_evidence"
    assert result["candidates"] == []


def test_repo_validation_includes_synthetic_resource_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str] = []
    original = validation._validate_payload

    def recording_validator(repo_root: Path, registry: dict, schema_name: str, payload: object) -> None:
        observed.append(schema_name)
        original(repo_root, registry, schema_name, payload)

    monkeypatch.setattr(validation, "_validate_payload", recording_validator)
    result = validation.validate_repo(ROOT)
    assert result["valid"], result["errors"]
    assert "synthetic_data_resource_registry" in observed


def test_nonstandard_portal_and_conflicting_terms_are_review_required() -> None:
    result = synthetic_route(
        ROOT,
        objective="Invoice table structure extraction",
        modality="document_image",
        domain="document_ai business_documents",
        signals="scarce_labels,controllable_ground_truth",
        real_holdout_available=True,
        limit=20,
    )
    by_id = {row["resource_id"]: row for row in result["candidates"]}
    assert by_id["synthetic-resource:docile-synthetic"]["terms_review_required"] is True
    assert by_id["synthetic-resource:tablebank"]["terms_review_required"] is True


@pytest.mark.parametrize("command", [
    ["synthetic-catalog", "--query", "ocr"],
    ["synthetic-route", "--objective", "OCR rare cases", "--modality", "document_image", "--signals", "rare_cases", "--real-holdout-available"],
])
def test_cli_is_read_only_and_succeeds(command: list[str]) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(part for part in (str(ROOT / "src"), env.get("PYTHONPATH", "")) if part)
    result = subprocess.run(
        [sys.executable, "-m", "digital_asset_directory.cli", "ml", *command, "--hub", str(ROOT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["candidate_only"] is True
