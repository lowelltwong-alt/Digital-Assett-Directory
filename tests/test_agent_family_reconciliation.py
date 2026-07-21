from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO = ROOT / "registry" / "agent-family-portfolio-registry.json"
ML = ROOT / "registry" / "ml-agent-family-registry.json"
RECON = ROOT / "docs" / "AGENT_FAMILY_RECONCILIATION.md"
TECH = ROOT / "registry" / "technical-product-company-os-registry.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_ml_workflow_is_sole_ml_family_authority() -> None:
    portfolio = _load(PORTFOLIO)
    ml = _load(ML)
    family_ids = {row["family_id"] for row in portfolio["families"]}
    assert "family:ml-workflow" in family_ids
    assert "family:machine-learning" not in family_ids
    assert "machine-learning-family" not in json.dumps(portfolio)
    assert "machine-learning-family" not in json.dumps(ml)
    ml_family = next(row for row in portfolio["families"] if row["family_id"] == "family:ml-workflow")
    assert ml_family["skill_ref"] == "skill:ml-workflow-agent-family"
    assert (ROOT / "assets/agent-skills/ml-workflow-agent-family/SKILL.md").is_file()


def test_dad_pilot_covers_implemented_core_families() -> None:
    portfolio = _load(PORTFOLIO)
    pilots = {row["pilot_id"]: row for row in portfolio["pilots"]}
    assert set(pilots) >= {
        "pilot:dad-agent-family-portfolio",
        "pilot:mock-trial-agent-family-portfolio",
        "pilot:lawfirm-os-security-overlay",
    }
    pilot = pilots["pilot:dad-agent-family-portfolio"]
    assert pilot["repo_id"] == "repo:dad"
    assert "family:ml-workflow" in pilot["family_ids"]
    assert "family:platform-cloud-sre" in pilot["family_ids"]
    assert "family:full-stack-engineering" in pilot["family_ids"]
    assert pilots["pilot:mock-trial-agent-family-portfolio"]["repo_id"] == "repo:mock-trial"


def test_full_stack_specialist_packs_are_real_pack_ids() -> None:
    portfolio = _load(PORTFOLIO)
    family = next(row for row in portfolio["families"] if row["family_id"] == "family:full-stack-engineering")
    assert family["specialist_packs"] == ["pack:developer-platform-devex-specialist-pack"]
    assert "migration_modernization" not in family["specialist_packs"]


def test_reconciliation_doc_and_thin_composition_exist() -> None:
    text = RECON.read_text(encoding="utf-8")
    assert "machine-learning-family" in text
    assert "skill:technical-product-company-os" in text
    assert "Do **not** create" in text
    tech = _load(TECH)
    assert tech["registry_id"] == "technical-product-company-os-registry"
    portfolio = _load(PORTFOLIO)
    edges = portfolio["graph_contract"]["dependency_edges"]
    composition = {
        (edge["source"], edge["target"])
        for edge in edges
        if edge["source"] == "skill:technical-product-company-os" and edge["edge_type"] == "depends_on"
    }
    assert ("skill:technical-product-company-os", "family:ml-workflow") in composition
    assert ("skill:technical-product-company-os", "family:full-stack-engineering") in composition
    assert ("skill:technical-product-company-os", "family:platform-cloud-sre") in composition


def test_no_subagent_role_directory_required_yet() -> None:
    assert not (ROOT / "processed/agents/subagent-role-directory.json").is_file()
    assert "subagent-role-directory.json" in RECON.read_text(encoding="utf-8")
