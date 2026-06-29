from __future__ import annotations

import json
from pathlib import Path

from digital_asset_directory.extractors import infer_semantics
from digital_asset_directory.template_library import validate_template_registry

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "templates" / "cross-repo-governance-dependency-map"


def test_cross_repo_governance_pattern_and_template_are_registered() -> None:
    patterns = json.loads((ROOT / "registry" / "asset-pattern-registry.json").read_text())
    templates = json.loads((ROOT / "registry" / "template-registry.json").read_text())

    pattern_ids = {pattern["id"] for pattern in patterns["patterns"]}
    template_by_id = {record["template_id"]: record for record in templates["templates"]}

    assert "cross_repo_governance_dependency_map_pattern" in pattern_ids
    template = template_by_id["template:cross-repo-governance-dependency-map"]
    assert template["path"] == "templates/cross-repo-governance-dependency-map"
    assert template["template_type"] == "governance"
    assert "template:ai-table-of-contents" in template["depends_on_template_ids"]
    assert "template:load-bearing-decision-review" in template["depends_on_template_ids"]
    assert "child repos cannot override upstream governance" in template["authority_boundary"]


def test_cross_repo_governance_template_files_exist_and_are_generic() -> None:
    expected = {
        "GOVERNANCE_DEPENDENCY_MAP.yaml",
        "governance_dependency_map_mirror.yaml",
        "AI_FRONT_DOOR.section.md",
        "AI_TABLE_OF_CONTENTS.section.md",
        "repo-contract.section.md",
        "PR_DESCRIPTION_REQUIRED_SECTIONS.md",
        "validate_governance_dependency_map.stub.py",
        "test_governance_dependency_map.stub.py",
        "HANDOFF_CHECKLIST.md",
        "ADOPTION_CHECKLIST.md",
    }

    for filename in expected:
        assert (TEMPLATE_DIR / filename).exists(), filename

    blob = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(TEMPLATE_DIR.iterdir())
        if path.is_file()
    )
    forbidden_domain_terms = ("Bible", "Scripture", "theology", "Logos")
    assert not any(term in blob for term in forbidden_domain_terms)
    assert "{{UPSTREAM_GOVERNANCE_REPO}}" in blob
    assert "local_repo_may_override_upstream_dependency_map: false" in blob


def test_cross_repo_governance_template_registry_validates_reverse_deps() -> None:
    result = validate_template_registry(ROOT)

    assert result["valid"] is True
    assert "template:cross-repo-governance-dependency-map" in result["reverse_dependencies"][
        "template:ai-table-of-contents"
    ]
    assert "template:cross-repo-governance-dependency-map" in result["reverse_dependencies"][
        "template:load-bearing-decision-review"
    ]


def test_cross_repo_governance_template_is_detectable_by_semantics() -> None:
    inferred = infer_semantics(
        "templates/cross-repo-governance-dependency-map/governance_dependency_map_mirror.yaml",
        (TEMPLATE_DIR / "governance_dependency_map_mirror.yaml").read_text(encoding="utf-8"),
    )

    assert "cross_repo_governance_dependency_map_pattern" in inferred["asset_patterns"]
    assert "governance-map" in inferred["tags"]

