from __future__ import annotations

import json
from pathlib import Path

from digital_asset_directory.extractors import infer_semantics


ROOT = Path(__file__).resolve().parents[1]


def test_front_door_declares_single_entrypoint_and_graph_routes() -> None:
    front_door = (ROOT / "AI_FRONT_DOOR.md").read_text(encoding="utf-8")

    assert "## Single AI entrypoint" in front_door
    assert "AI_TABLE_OF_CONTENTS.md branch" in front_door
    assert "docs/AI_ENTRYPOINT_AND_TOC_ROUTING_STANDARD.md" in front_door
    assert "## Knowledge graph entrypoints" in front_door
    assert "docs/KNOWLEDGE_GRAPH_MODEL.md" in front_door
    assert "registry/edge-type-registry.json" in front_door
    assert "processed/graph/graph.json" in front_door
    assert "candidate evidence" in front_door


def test_ai_toc_has_deterministic_rows_and_tagged_graph_branch() -> None:
    toc = (ROOT / "AI_TABLE_OF_CONTENTS.md").read_text(encoding="utf-8")

    assert "| Path | What it is | Tags | Use when |" in toc
    assert "## Tag Index" in toc
    assert "`front_door`" in toc
    assert "`knowledge_graph`" in toc
    assert "## Knowledge Graph Entrypoints" in toc
    assert "`docs/AI_ENTRYPOINT_AND_TOC_ROUTING_STANDARD.md`" in toc
    assert "`templates/ai-table-of-contents.template.md`" in toc
    assert "`processed/graph/graph.json`" in toc
    assert "`generated_output`" in toc


def test_manifest_exposes_navigation_and_graph_entrypoints() -> None:
    manifest = json.loads((ROOT / "MACHINE_NAVIGATION_MANIFEST.json").read_text())

    assert manifest["navigation_standards"]["single_ai_entrypoint"] == "AI_FRONT_DOOR.md"
    assert manifest["navigation_standards"]["routing_standard"] == (
        "docs/AI_ENTRYPOINT_AND_TOC_ROUTING_STANDARD.md"
    )
    assert "AI_TABLE_OF_CONTENTS.md" in manifest["start_files"]
    assert "docs/KNOWLEDGE_GRAPH_MODEL.md" in manifest["knowledge_graph_entrypoints"]
    assert "registry/asset-pattern-registry.json" in manifest["knowledge_graph_entrypoints"]
    assert "processed/graph/graph.json" in manifest["knowledge_graph_entrypoints"]


def test_ai_navigation_rule_and_pattern_are_registered() -> None:
    rules = json.loads((ROOT / "registry" / "learning-rule-registry.json").read_text())
    patterns = json.loads((ROOT / "registry" / "asset-pattern-registry.json").read_text())
    context_tags = json.loads((ROOT / "registry" / "context-tag-registry.json").read_text())

    rule_ids = {rule["rule_id"] for rule in rules["rules"]}
    pattern_ids = {pattern["id"] for pattern in patterns["patterns"]}
    tag_ids = {tag["context_tag_id"] for tag in context_tags["tags"]}

    assert "learning-rule:ai-entrypoint-toc-routing-required" in rule_ids
    assert "ai_entrypoint_toc_routing_system" in pattern_ids
    assert "ai_navigation" in tag_ids


def test_ai_navigation_asset_pattern_is_detectable() -> None:
    semantic = infer_semantics(
        "AI_FRONT_DOOR.md",
        (
            "Single AI entrypoint with AI_TABLE_OF_CONTENTS branches, "
            "knowledge graph entrypoint rows, routing tags, and use when triggers."
        ),
    )

    assert "ai-navigation" in semantic["tags"]
    assert "ai_entrypoint_toc_routing_system" in semantic["asset_patterns"]


def test_background_connection_radar_pattern_is_detectable() -> None:
    semantic = infer_semantics(
        "docs/BACKGROUND_CONNECTION_RADAR.md",
        (
            "Background Connection Radar uses attention seeds, cold storage, "
            "a background scout, escalation packet, high-intensity verifier, "
            "candidate connection records, and multi-hop expansion."
        ),
    )

    assert "connection-radar" in semantic["tags"]
    assert "background_connection_radar_system" in semantic["asset_patterns"]


def test_background_connection_radar_keeps_reuse_first_graph_boundary() -> None:
    radar = (ROOT / "docs" / "BACKGROUND_CONNECTION_RADAR.md").read_text(encoding="utf-8")
    synthesis = (
        ROOT / "roadmap" / "evidence" / "background-connection-radar-synthesis.md"
    ).read_text(encoding="utf-8")

    assert "These labels are review-packet types, not automatically new edge IDs." in radar
    assert "reuse existing edge types before proposing new ones" in radar
    assert "WorkflowPartRecord" in radar
    assert "Leave inputs, outputs, preconditions, side effects" in synthesis
    assert "Re-confirm the edge registry at implementation time" in synthesis


def test_background_connection_radar_has_gate_before_score_hardening() -> None:
    radar = (ROOT / "docs" / "BACKGROUND_CONNECTION_RADAR.md").read_text(encoding="utf-8")
    synthesis = (
        ROOT / "roadmap" / "evidence" / "background-connection-radar-synthesis.md"
    ).read_text(encoding="utf-8")

    assert "Use gate-before-score escalation" in radar
    assert "background-connection-connectivity-v1" in radar
    assert "0.30 * attention_relevance" in radar
    assert "Default escalation threshold: `connectivity_score >= 0.70`." in radar
    assert "Do not persist raw user messages" in radar
    assert "hot set cap: `200` attention seeds" in radar
    assert "Family dedup happens before budget allocation." in radar
    assert "Dedupe by connection type and endpoint family" in synthesis
    assert "Let verified connections affect ceiling or edge-candidacy review" in synthesis
