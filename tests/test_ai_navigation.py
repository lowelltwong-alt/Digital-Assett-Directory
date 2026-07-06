from __future__ import annotations

import json
from pathlib import Path

from digital_asset_directory.extractors import infer_semantics


ROOT = Path(__file__).resolve().parents[1]


def test_front_door_declares_single_entrypoint_and_graph_routes() -> None:
    front_door = (ROOT / "AI_FRONT_DOOR.md").read_text(encoding="utf-8")

    assert "## Concurrent Work Default" in front_door
    assert "Assume concurrent work is happening" in front_door
    assert "git fetch origin" in front_door
    assert "git worktree add -b" in front_door
    assert "origin/main" in front_door
    assert "--hub <isolated-worktree-path>" in front_door
    assert "Never overwrite, reset, merge, rebase, or clean another agent's" in front_door
    assert "## Single AI entrypoint" in front_door
    assert "## Navigation freshness" in front_door
    assert "registry/ai-navigation-registry.json" in front_door
    assert "navigation_version" in front_door
    assert "AI_TABLE_OF_CONTENTS.md branch" in front_door
    assert "docs/AI_ENTRYPOINT_AND_TOC_ROUTING_STANDARD.md" in front_door
    assert "## Knowledge graph entrypoints" in front_door
    assert "docs/KNOWLEDGE_GRAPH_MODEL.md" in front_door
    assert "registry/edge-type-registry.json" in front_door
    assert "processed/graph/graph.json" in front_door
    assert "candidate evidence" in front_door
    assert "$HOME/.dad/bin/asset-dir" in front_door
    assert "$HOME\\.dad\\bin\\asset-dir.ps1" in front_door


def test_ai_toc_has_deterministic_rows_and_tagged_graph_branch() -> None:
    toc = (ROOT / "AI_TABLE_OF_CONTENTS.md").read_text(encoding="utf-8")

    assert "| Path | What it is | Tags | Use when |" in toc
    assert "## Tag Index" in toc
    assert "`front_door`" in toc
    assert "`navigation_freshness`" in toc
    assert "`knowledge_graph`" in toc
    assert "## Knowledge Graph Entrypoints" in toc
    assert "`registry/ai-navigation-registry.json`" in toc
    assert "`docs/AI_ENTRYPOINT_AND_TOC_ROUTING_STANDARD.md`" in toc
    assert "`templates/ai-table-of-contents.template.md`" in toc
    assert "`processed/graph/graph.json`" in toc
    assert "`generated_output`" in toc
    assert "`processed/reports/exception_backfill_classifier_refresh_plan.md`" in toc


def test_manifest_exposes_navigation_and_graph_entrypoints() -> None:
    manifest = json.loads((ROOT / "MACHINE_NAVIGATION_MANIFEST.json").read_text())

    assert manifest["navigation_standards"]["single_ai_entrypoint"] == "AI_FRONT_DOOR.md"
    assert manifest["navigation_standards"]["navigation_registry"] == (
        "registry/ai-navigation-registry.json"
    )
    assert manifest["navigation_standards"]["navigation_version"] == "2026.07.06.5"
    assert manifest["navigation_standards"]["routing_standard"] == (
        "docs/AI_ENTRYPOINT_AND_TOC_ROUTING_STANDARD.md"
    )
    assert "AI_TABLE_OF_CONTENTS.md" in manifest["start_files"]
    assert "docs/KNOWLEDGE_GRAPH_MODEL.md" in manifest["knowledge_graph_entrypoints"]
    assert "registry/asset-pattern-registry.json" in manifest["knowledge_graph_entrypoints"]
    assert "processed/graph/graph.json" in manifest["knowledge_graph_entrypoints"]
    assert (
        "processed/reports/exception_backfill_classifier_refresh_plan.md"
        in manifest["knowledge_graph_entrypoints"]
    )
    assert "docs/LESSON_LIFECYCLE_GOVERNANCE.md" in manifest["knowledge_graph_entrypoints"]
    assert (
        "docs/DAD_MAIL_STORM_AND_DIRTY_STATE_RUNBOOK.md" in manifest["knowledge_graph_entrypoints"]
    )
    assert "docs/PR_BRANCH_LIFECYCLE_GOVERNANCE.md" in manifest["knowledge_graph_entrypoints"]
    assert "docs/DAD_EVENT_PIPELINE.md" in manifest["knowledge_graph_entrypoints"]
    assert "tools/dad_scan_core/src/event_log.rs" in manifest["knowledge_graph_entrypoints"]
    assert "processed/events/" in manifest["knowledge_graph_entrypoints"]
    assert (
        "processed/events/reports/event_pipeline.md"
        in manifest["knowledge_graph_entrypoints"]
    )
    assert (
        "docs/rust/RUST_ROLLOUT_LESSON_CAPTURE_PROTOCOL.md"
        in manifest["knowledge_graph_entrypoints"]
    )
    assert (
        "assets/coding-harnesses/repo-enrollment-mail-governance-safety/"
        in manifest["knowledge_graph_entrypoints"]
    )
    assert (
        "roadmap/evidence/phase-10-mail-end-to-end-trial.md"
        in manifest["knowledge_graph_entrypoints"]
    )
    assert (
        "roadmap/evidence/phase-8-dad-local-deployment.human-review-packet.json"
        in manifest["knowledge_graph_entrypoints"]
    )
    assert (
        "processed/fable5/deep-dives/2026-07-06-dad-deployment-rust-handoff/fable5-master-prompt.md"
        in manifest["knowledge_graph_entrypoints"]
    )
    assert manifest["registries"]["ai_navigation"] == "registry/ai-navigation-registry.json"
    assert manifest["registries"]["ai_navigation_registry_schema"] == (
        "schemas/ai-navigation-registry.schema.json"
    )
    assert manifest["registries"]["rust_rollout_lesson_schema"] == (
        "schemas/rust-rollout-lesson.schema.json"
    )
    assert manifest["registries"]["dad_pipeline_event_schema"] == (
        "schemas/dad-pipeline-event.schema.json"
    )


def test_navigation_registry_keeps_front_door_singular_and_fresh() -> None:
    registry = json.loads((ROOT / "registry" / "ai-navigation-registry.json").read_text())

    assert registry["singular_entrypoint"]["path"] == "AI_FRONT_DOOR.md"
    assert registry["navigation_version"] == "2026.07.06.5"
    assert registry["updated_at"]
    assert "memory" in registry["entrypoint_policy"]["memory_rule"].lower()
    assert registry["freshness_policy"]["recent_changes_limit"] <= 20
    assert (
        "Do not add date/version columns to every TOC row"
        in (registry["branch_depth_policy"]["anti_bloat_rule"])
    )

    branches = {branch["path"]: branch for branch in registry["branch_map"]}
    assert "AI_FRONT_DOOR.md" in branches
    assert "AI_TABLE_OF_CONTENTS.md" in branches
    assert "MACHINE_NAVIGATION_MANIFEST.json" in branches
    assert "registry/ai-navigation-registry.json" in branches
    assert "registry/dad-offerings-registry.json" in branches
    assert "docs/MAIL_CENTER.md" in branches
    assert "docs/DAD_EVENT_PIPELINE.md" in branches
    assert "docs/DAD_MAIL_STORM_AND_DIRTY_STATE_RUNBOOK.md" in branches
    assert "docs/PR_BRANCH_LIFECYCLE_GOVERNANCE.md" in branches
    assert "docs/rust/RUST_ROLLOUT_LESSON_CAPTURE_PROTOCOL.md" in branches
    assert "assets/coding-harnesses/repo-enrollment-mail-governance-safety/" in branches
    assert (
        "roadmap/evidence/dad-deployment-and-all-repo-verification-roadmap.md"
        in branches
    )
    deployment_branch = branches[
        "roadmap/evidence/dad-deployment-and-all-repo-verification-roadmap.md"
    ]
    assert (
        "roadmap/evidence/phase-8-dad-local-deployment.human-review-packet.json"
        in deployment_branch["route_after"]
    )
    assert (
        "roadmap/evidence/phase-10a-mailbox-event-pipeline.md"
        in deployment_branch["route_after"]
    )
    assert (
        "processed/fable5/deep-dives/2026-07-06-dad-deployment-rust-handoff/fable5-master-prompt.md"
        in deployment_branch["route_after"]
    )
    assert "docs/HARNESS_VS_DETERMINISTIC_ENFORCEMENT.md" in branches
    assert "docs/CLAUDE_ARCHITECTURAL_ROOT_CAUSE_REVIEW.md" in branches
    assert "docs/LESSON_LIFECYCLE_GOVERNANCE.md" in branches

    change_paths = {path for change in registry["recent_changes"] for path in change["paths"]}
    assert "registry/ai-navigation-registry.json" in change_paths
    assert "docs/DAD_ADDRESS_MODEL.md" in change_paths
    assert "docs/HARNESS_VS_DETERMINISTIC_ENFORCEMENT.md" in change_paths
    assert "docs/CLAUDE_ARCHITECTURAL_ROOT_CAUSE_REVIEW.md" in change_paths
    assert (
        "roadmap/evidence/phase-8-dad-local-deployment.human-review-packet.json"
        in change_paths
    )
    assert "docs/DAD_EVENT_PIPELINE.md" in change_paths
    assert (
        "processed/fable5/deep-dives/2026-07-06-dad-deployment-rust-handoff/fable5-master-prompt.md"
        in change_paths
    )
    assert "schemas/dad-pipeline-event.schema.json" in change_paths
    assert "docs/LESSON_LIFECYCLE_GOVERNANCE.md" in change_paths
    assert "docs/DAD_MAIL_STORM_AND_DIRTY_STATE_RUNBOOK.md" in change_paths
    assert "docs/PR_BRANCH_LIFECYCLE_GOVERNANCE.md" in change_paths
    assert "docs/rust/RUST_ROLLOUT_LESSON_CAPTURE_PROTOCOL.md" in change_paths
    assert "schemas/rust-rollout-lesson.schema.json" in change_paths
    assert "assets/coding-harnesses/repo-enrollment-mail-governance-safety/" in change_paths


def test_mail_storm_runbook_distinguishes_spool_and_worktree_dirt() -> None:
    runbook = (ROOT / "docs" / "DAD_MAIL_STORM_AND_DIRTY_STATE_RUNBOOK.md").read_text(
        encoding="utf-8"
    )
    front_door = (ROOT / "AI_FRONT_DOOR.md").read_text(encoding="utf-8")
    toc = (ROOT / "AI_TABLE_OF_CONTENTS.md").read_text(encoding="utf-8")
    harness_readme = (
        ROOT
        / "assets"
        / "coding-harnesses"
        / "repo-enrollment-mail-governance-safety"
        / "README.md"
    ).read_text(encoding="utf-8")

    assert "mail storm-gate" in runbook
    assert "mail doctor --repo all --summary-only --fail-on-dirty --fail-on-coverage-gap" in runbook
    assert "`dirty` and `spool_dirty`" in runbook
    assert "`worktree_dirty`" in runbook
    assert "safe_for_mail_storm_operations" in runbook
    assert "safe_for_ingest_operations" in runbook
    assert "safe_for_delivery_operations" in runbook
    assert "--operation ingest" in runbook
    assert "--operation delivery" in runbook
    assert "safe_to_collect" in runbook
    assert "dirty_state_fingerprint" in runbook
    assert "--dirty-state-fingerprint" in runbook
    assert ".digital-asset/mail/outbox.jsonl" in runbook
    assert "processed/mail/inbox/*.jsonl" in runbook
    assert "mail/outbox/rust_rollout/" in runbook
    assert "not proof that mail is corrupt" in runbook
    assert "DAD_MAIL_STORM_AND_DIRTY_STATE_RUNBOOK.md" in toc
    assert "assets/coding-harnesses/repo-enrollment-mail-governance-safety/" in front_door
    assert "assets/coding-harnesses/repo-enrollment-mail-governance-safety/" in toc
    assert "mail storm-gate" in harness_readme
    assert "safe_for_mail_storm_operations" in harness_readme
    assert "safe_for_ingest_operations" in harness_readme
    assert "safe_for_delivery_operations" in harness_readme
    assert "--operation ingest" in harness_readme
    assert "--operation delivery" in harness_readme
    assert "safe_to_collect" in harness_readme
    assert "--dirty-state-fingerprint" in harness_readme


def test_pr_branch_lifecycle_governance_route_is_discoverable() -> None:
    front_door = (ROOT / "AI_FRONT_DOOR.md").read_text(encoding="utf-8")
    toc = (ROOT / "AI_TABLE_OF_CONTENTS.md").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "MACHINE_NAVIGATION_MANIFEST.json").read_text())
    registry = json.loads((ROOT / "registry" / "ai-navigation-registry.json").read_text())
    needs = json.loads((ROOT / "registry" / "dad-needs-registry.json").read_text())
    runbook = (ROOT / "docs" / "PR_BRANCH_LIFECYCLE_GOVERNANCE.md").read_text(
        encoding="utf-8"
    )

    route = "docs/PR_BRANCH_LIFECYCLE_GOVERNANCE.md"

    assert route in front_door
    assert route in toc
    assert route in manifest["knowledge_graph_entrypoints"]
    assert "owner, next action" in front_door
    assert "branch_lifecycle" in toc
    assert "escalation clock" in runbook
    assert "gh pr list --state open" in runbook
    assert "git cherry -v" in runbook
    assert "metadata-only" in runbook
    assert "Do not send source blobs" in runbook

    branch = next(
        row
        for row in registry["branch_map"]
        if row["branch_id"] == "pr_branch_lifecycle_governance"
    )
    assert branch["path"] == route
    assert "registry/dad-needs-registry.json" in branch["route_after"]

    need_ids = {need["need_id"] for need in needs["needs"]}
    assert "dad:need:pr-branch-lifecycle-escalation" in need_ids


def test_rust_rollout_lesson_capture_route_is_discoverable() -> None:
    front_door = (ROOT / "AI_FRONT_DOOR.md").read_text(encoding="utf-8")
    toc = (ROOT / "AI_TABLE_OF_CONTENTS.md").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "MACHINE_NAVIGATION_MANIFEST.json").read_text())
    registry = json.loads((ROOT / "registry" / "ai-navigation-registry.json").read_text())

    protocol = "docs/rust/RUST_ROLLOUT_LESSON_CAPTURE_PROTOCOL.md"
    schema = "schemas/rust-rollout-lesson.schema.json"

    assert protocol in front_door
    assert protocol in toc
    assert protocol in manifest["knowledge_graph_entrypoints"]
    assert "--dirty-state-fingerprint" in (ROOT / protocol).read_text(encoding="utf-8")
    assert manifest["registries"]["rust_rollout_lesson_schema"] == schema

    branch = next(
        row for row in registry["branch_map"] if row["branch_id"] == "rust_rollout_lesson_capture"
    )
    assert branch["path"] == protocol
    assert schema in branch["route_after"]
    assert "outbox" in (ROOT / protocol).read_text(encoding="utf-8")


def test_dad_rust_route_is_explicit_and_ordered() -> None:
    front_door = (ROOT / "AI_FRONT_DOOR.md").read_text(encoding="utf-8")
    toc = (ROOT / "AI_TABLE_OF_CONTENTS.md").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "MACHINE_NAVIGATION_MANIFEST.json").read_text())
    registry = json.loads((ROOT / "registry" / "ai-navigation-registry.json").read_text())

    rust_route = [
        "assets/dad-rust-upgrade-starter-pack/README.md",
        "docs/rust/RUST_ADOPTION_PLAN.md",
        "tools/dad_scan_core/",
        "src/digital_asset_directory/rust_bridge/",
    ]

    for surface in (front_door, toc):
        positions = [surface.index(path) for path in rust_route]
        assert positions == sorted(positions)

    for path in rust_route:
        assert path in manifest["knowledge_graph_entrypoints"]
    assert "tools/dad_scan_core/src/event_log.rs" in manifest["knowledge_graph_entrypoints"]

    rust_branch = next(
        branch for branch in registry["branch_map"] if branch["branch_id"] == "dad_rust_system"
    )
    assert rust_branch["path"] == rust_route[0]
    for path in rust_route[1:]:
        assert path in rust_branch["route_after"]
    assert "tools/dad_scan_core/src/event_log.rs" in rust_branch["route_after"]
    assert "asset-dir rust event-log-check" in rust_branch["route_after"]
    assert "starter-pack README" in rust_branch["freshness_hint"]


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
