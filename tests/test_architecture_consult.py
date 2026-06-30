from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.architecture_consult import (
    build_architecture_consult,
    parse_architecture_intent,
    write_architecture_consult_outputs,
)

pytestmark = pytest.mark.integration

TIMESTAMP = "2026-01-01T00:00:00+00:00"
SCAN_ID = "dad:scan:test"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def seed_consult_inputs(root: Path) -> None:
    write_jsonl(
        root / "processed" / "learning" / "reference_architecture_candidates.jsonl",
        [
            {
                "reference_architecture_id": "dad:reference-architecture:governance",
                "architecture_label": "Governed AI workflow control plane",
                "architecture_type": "governance_control_plane",
                "reference_score": 86.0,
                "component_roles": {
                    "agent_navigation": ["dad:asset:front"],
                    "rules_governance": ["dad:asset:authority"],
                    "schemas_contracts": ["dad:asset:schema"],
                    "validators_tests": ["dad:asset:test"],
                    "learning_loops": ["dad:asset:learning"],
                },
                "detected_patterns": [
                    "AI navigation",
                    "schema contracts",
                    "human gates",
                    "learning loop",
                ],
                "why_it_is_good_reference": [
                    "Combines AI navigation, governance, schemas, validators, and learning loops."
                ],
                "reuse_guidance": ["Reuse the component order, not source-owned facts."],
                "human_gates": ["Human review before installing governance."],
                "scan_id": SCAN_ID,
            },
            {
                "reference_architecture_id": "dad:reference-architecture:data",
                "architecture_label": "Public data processing reference",
                "architecture_type": "data_pipeline",
                "reference_score": 55.0,
                "component_roles": {
                    "dataflow_normalization": ["dad:asset:dataflow"],
                    "quality_eval": ["dad:asset:eval"],
                },
                "detected_patterns": ["normalization", "quality evaluation"],
                "why_it_is_good_reference": ["Good for low-risk public data flows."],
                "reuse_guidance": ["Reuse normalization checklist only."],
                "human_gates": [],
                "scan_id": SCAN_ID,
            },
        ],
    )
    write_json(
        root / "registry" / "template-registry.json",
        {
            "registry_version": "0.1.0",
            "templates": [
                {
                    "template_id": "template:ai-table-of-contents",
                    "template_name": "AI table of contents",
                    "template_type": "ai_navigation",
                    "purpose": "Future agents can route by tagged AI TOC rows.",
                    "applies_when": ["AI navigation is needed."],
                    "depends_on_template_ids": [],
                    "dependent_template_ids": ["template:load-bearing-decision-review"],
                    "depends_on_contracts": ["docs/AI_ENTRYPOINT_AND_TOC_ROUTING_STANDARD.md"],
                    "validation_commands": ["python -m pytest tests/test_ai_navigation.py"],
                    "authority_boundary": "Template guidance only.",
                },
                {
                    "template_id": "template:load-bearing-decision-review",
                    "template_name": "Load-bearing decision review",
                    "template_type": "review_gate",
                    "purpose": "Red-team and premortem high-risk defaults.",
                    "applies_when": ["A high risk repo needs human gate review."],
                    "depends_on_template_ids": ["template:software-repo-checklist-tree"],
                    "dependent_template_ids": [],
                    "depends_on_contracts": ["docs/LOAD_BEARING_DECISION_REVIEW.md"],
                    "validation_commands": ["python -m digital_asset_directory.cli validate"],
                    "authority_boundary": "Does not self-approve high-risk decisions.",
                },
            ],
        },
    )
    write_json(
        root / "processed" / "workflow_parts" / "workflow_part_usage_guidance.json",
        {
            "review_use_candidates": [
                {
                    "part_id": "dad:workflow-part:validator",
                    "part_type": "validator",
                    "asset_pattern_id": "evaluation_contract_system",
                    "representative_path": "repo/tests/test_contract.py",
                    "decision": "accept_for_review_use",
                    "action": "reuse shape only",
                    "safety": "safe",
                    "dataflow_completeness": "adequate_for_now",
                    "note": "Schema contract validator workflow part.",
                }
            ],
            "human_gated_candidates": [],
        },
    )
    write_json(
        root / "registry" / "learning-rule-registry.json",
        {
            "rules": [
                {
                    "rule_id": "learning-rule:load-bearing-decisions-need-risk-tier-review",
                    "title": "Load-bearing decisions need risk tier review",
                    "summary": "High-risk software defaults need red-team and premortem.",
                    "trigger_terms": ["risk", "software", "governance"],
                    "applies_when": ["A decision affects downstream agents."],
                    "required_actions": ["Run fresh-eyes review."],
                    "enforcement_level": "require_ack",
                    "danger_if_ignored": "Bad defaults can cascade.",
                }
            ]
        },
    )
    write_json(
        root / "processed" / "reports" / "governance_map_adoption_scope.json",
        {
            "repo_candidates": [
                {
                    "repo_key": "git-projects/example",
                    "repo_label": "example",
                    "priority_score": 71.0,
                    "proposed_role": "child_repo",
                    "missing_surface_ids": ["governance_dependency_map"],
                    "human_gate_required": True,
                }
            ]
        },
    )
    write_jsonl(
        root / "processed" / "learning" / "background_connection_candidates.jsonl",
        [
            {
                "connection_candidate_id": "dad:connection-candidate:test",
                "connection_type": "learning_loop_to_governance",
                "connectivity_score": 0.81,
                "why_might_matter_now": "Learning loop could strengthen governance seed repos.",
                "why_might_be_false": "Signals are generated candidates.",
                "reuse_first_edge_mapping": ["composes_with"],
            }
        ],
    )


def write_intent(path: Path, *, secret: bool = False) -> None:
    secret_line = "\napi_key: SECRET_VALUE_12345" if secret else ""
    path.write_text(
        "\n".join(
            [
                "Purpose: Seed a governed AI workflow repo.",
                "Domain: AI governance",
                "Risk level: high risk",
                "Data sensitivity: internal data",
                "Expected users/agents: Codex, Claude, human maintainer",
                "Workflows needed: AI navigation, schema contracts, learning loop",
                "Validation needs: pytest, schema validation, privacy review",
                secret_line,
            ]
        ),
        encoding="utf-8",
    )


def test_parse_architecture_intent_normalizes_labels_and_redacts_secrets(tmp_path: Path):
    intent_file = tmp_path / "new-repo-intent.md"
    write_intent(intent_file, secret=True)

    parsed = parse_architecture_intent(intent_file)

    assert parsed["risk_level"] == "high"
    assert parsed["data_sensitivity"] == "internal"
    assert parsed["redaction_count"] == 1
    assert "SECRET_VALUE_12345" not in parsed["raw_text_redacted"]
    assert "schema contracts" in parsed["workflows_needed"]


def test_build_architecture_consult_uses_generated_inputs_without_promotion(tmp_path: Path):
    seed_consult_inputs(tmp_path)
    intent_file = tmp_path / "new-repo-intent.md"
    write_intent(intent_file)

    record = build_architecture_consult(
        tmp_path,
        intent_file,
        limit=5,
        generated_at=TIMESTAMP,
    )

    assert record.review_status == "generated_candidate"
    assert record.scan_id == SCAN_ID
    assert record.matched_reference_architectures[0]["architecture_label"] == (
        "Governed AI workflow control plane"
    )
    assert record.gates["no_source_mutation_gate"] is True
    assert record.gates["no_external_call_gate"] is True
    assert any("LOAD_BEARING" in item for item in record.starter_repo_structure)
    assert any("Human review" in gate for gate in record.required_human_gates)
    assert any("python -m pytest" in item for item in record.validation_checklist)


def test_write_architecture_consult_outputs_are_generated_and_deterministic(tmp_path: Path):
    seed_consult_inputs(tmp_path)
    intent_file = tmp_path / "new-repo-intent.md"
    write_intent(intent_file)

    first = write_architecture_consult_outputs(
        tmp_path,
        intent_file,
        limit=5,
        generated_at=TIMESTAMP,
    )
    second = write_architecture_consult_outputs(
        tmp_path,
        intent_file,
        limit=5,
        generated_at=TIMESTAMP,
    )

    assert first == second
    for key in ("report", "payload", "seed_prompt"):
        path = Path(first[key])
        assert path.exists()
        assert path.is_relative_to(tmp_path / "processed")
    payload = json.loads(Path(first["payload"]).read_text(encoding="utf-8"))
    assert payload["review_status"] == "generated_candidate"
    assert "consult-and-compose" in payload["authority_boundary"].lower()
    assert "new repository retains its own canon" in payload["authority_boundary"]
    seed_prompt = Path(first["seed_prompt"]).read_text(encoding="utf-8")
    assert "Reuse architecture shapes" in seed_prompt


def test_missing_generated_inputs_degrade_to_warnings(tmp_path: Path):
    intent_file = tmp_path / "new-repo-intent.md"
    write_intent(intent_file)

    record = build_architecture_consult(
        tmp_path,
        intent_file,
        limit=5,
        generated_at=TIMESTAMP,
    )

    assert record.review_status == "generated_candidate"
    assert record.matched_reference_architectures == []
    assert record.warnings
    assert record.scan_id == "catalog-without-scan"
    assert record.validation_checklist
