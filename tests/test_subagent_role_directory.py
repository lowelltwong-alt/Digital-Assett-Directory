from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from digital_asset_directory.portfolio_attention import LIFECYCLE_STATES
from digital_asset_directory.subagent_evaluations import (
    build_graph,
    build_role_directory_projection,
    ingest_packet,
    load_registered_role_catalog,
    role_directory_freshness,
    search_role_directory,
    write_role_directory_projection,
)


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "examples/subagent-evaluations/logos-t475-and-dad-graph-v1"


def _hub(tmp_path: Path, *, evaluation_support: bool = False) -> Path:
    hub = tmp_path / "hub"
    files = [
        "registry/schema-registry.json",
        "registry/agent-skill-library.json",
        "registry/subagent-capability-registry.json",
        "registry/subagent-evaluation-methodology.json",
        "registry/subagent-evaluation-methodologies/0.1.0.json",
        "schemas/agent-skill-library.schema.json",
        "schemas/subagent-pack.schema.json",
        "schemas/subagent-role-directory.schema.json",
        "schemas/subagent-evaluation-methodology.schema.json",
    ]
    if evaluation_support:
        files.extend(
            [
                "registry/graph-edge-registry.json",
                "registry/edge-type-registry.json",
                "schemas/subagent-role-profile-revision.schema.json",
                "schemas/subagent-execution-attempt.schema.json",
                "schemas/subagent-attempt-evaluation.schema.json",
                "schemas/subagent-capability-graph.schema.json",
                "schemas/subagent-action-recommendation.schema.json",
                "schemas/subagent-unrated-inventory.schema.json",
            ]
        )
    for relative in files:
        target = hub / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    for skill_name in (
        "personal-project-management-ops",
        "dad-trigger-pattern-radar",
        "subagent-continuous-improvement",
    ):
        source = ROOT / "assets/agent-skills" / skill_name
        target = hub / "assets/agent-skills" / skill_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
    if evaluation_support:
        source = PACKET / "evidence"
        target = hub / PACKET.relative_to(ROOT) / "evidence"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
    return hub


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_yaml(path: Path, value: dict) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def test_catalog_builds_without_attempts_and_keeps_grades_insufficient(tmp_path: Path):
    hub = _hub(tmp_path)

    projection = build_role_directory_projection(hub)

    assert projection["role_count"] == 15
    assert {row["skill_id"] for row in projection["roles"]} == {
        "skill:personal-project-management-ops",
        "skill:dad-trigger-pattern-radar",
        "skill:subagent-continuous-improvement",
    }
    assert all(row["evaluation_status"] == "insufficient_evidence" for row in projection["roles"])
    assert all(row["evaluated_revisions"] == [] for row in projection["roles"])
    assert all("profile_score" not in row for row in projection["roles"])


def test_search_is_read_only_and_uses_categorical_match_contract(tmp_path: Path):
    hub = _hub(tmp_path)
    before = sorted(path.relative_to(hub).as_posix() for path in hub.rglob("*"))

    result = search_role_directory(hub, query="neglected dirty worktree")

    after = sorted(path.relative_to(hub).as_posix() for path in hub.rglob("*"))
    assert before == after
    assert result["coverage"]["returned_role_count"] == 1
    match = result["matches"][0]
    assert match["role_id"] == "neglected-worktree-triage-manager"
    assert match["match_basis"] == "all_query_tokens"
    assert "quality_rank" not in json.dumps(result)
    assert "recommended" not in json.dumps(result).casefold()

    capability_result = search_role_directory(
        hub,
        capability="dependency_frontier_analysis",
    )
    assert {row["match_basis"] for row in capability_result["matches"]} == {"exact_declared_match"}
    assert all(row["matched_fields"] == ["capabilities"] for row in capability_result["matches"])


def test_projection_freshness_detects_pack_change(tmp_path: Path):
    hub = _hub(tmp_path)
    write_role_directory_projection(hub)
    assert role_directory_freshness(hub) == {"state": "fresh", "reasons": []}

    pack = hub / "assets/agent-skills/dad-trigger-pattern-radar/subagents.yaml"
    pack.write_text(pack.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    assert role_directory_freshness(hub) == {
        "state": "stale",
        "reasons": ["source_hashes_changed"],
    }


def test_unknown_capability_fails_closed(tmp_path: Path):
    hub = _hub(tmp_path)
    path = hub / "assets/agent-skills/dad-trigger-pattern-radar/subagents.yaml"
    pack = _load_yaml(path)
    pack["roles"][0]["capability_ids"].append("unregistered_magic")
    _write_yaml(path, pack)

    with pytest.raises(ValueError, match="unknown capabilities"):
        load_registered_role_catalog(hub)


def test_pack_path_must_be_explicit_and_inside_registered_skill(tmp_path: Path):
    hub = _hub(tmp_path)
    path = hub / "registry/agent-skill-library.json"
    library = json.loads(path.read_text(encoding="utf-8"))
    skill = next(
        row for row in library["skills"] if row["skill_id"] == "skill:dad-trigger-pattern-radar"
    )
    skill["subagent_pack"] = "assets/agent-skills/../private/subagents.yaml"
    path.write_text(json.dumps(library), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid agent skill library|Unsafe"):
        load_registered_role_catalog(hub)


def test_same_role_name_in_distinct_packs_keeps_distinct_identity(tmp_path: Path):
    hub = _hub(tmp_path)
    trigger_path = hub / "assets/agent-skills/dad-trigger-pattern-radar/subagents.yaml"
    personal_path = hub / "assets/agent-skills/personal-project-management-ops/subagents.yaml"
    trigger = _load_yaml(trigger_path)
    personal = _load_yaml(personal_path)
    duplicate_name = dict(trigger["roles"][0])
    duplicate_name["profile_role_id"] = "personal_luna_trigger_observer"
    personal["roles"].append(duplicate_name)
    _write_yaml(personal_path, personal)

    catalog = load_registered_role_catalog(hub)
    same_names = [row for row in catalog if row["role_id"] == "luna-trigger-observer"]

    assert len(same_names) == 2
    assert len({row["role_ref"] for row in same_names}) == 2
    assert len({row["role_profile_id"] for row in same_names}) == 2


def test_evaluation_link_requires_exact_declared_revision_and_identity(tmp_path: Path):
    hub = _hub(tmp_path, evaluation_support=True)
    personal_path = hub / "assets/agent-skills/personal-project-management-ops/subagents.yaml"
    personal = _load_yaml(personal_path)
    role = personal["roles"][0]
    role["profile_role_id"] = "terra_integration_specialist"
    role["evaluated_role_revision_ids"] = [
        "dad:role-profile-revision:terra-integration-specialist:v1"
    ]
    _write_yaml(personal_path, personal)

    ingest_packet(hub, PACKET)
    build_graph(hub)
    projection = build_role_directory_projection(hub)
    linked = next(
        row
        for row in projection["roles"]
        if row["role_ref"].endswith("#workstream-intake-identity-steward")
    )

    assert linked["evaluation_status"] == "attempt_evidence_only"
    assert [row["revision_id"] for row in linked["evaluated_revisions"]] == [
        "dad:role-profile-revision:terra-integration-specialist:v1"
    ]

    role["profile_role_id"] = "wrong_identity"
    _write_yaml(personal_path, personal)
    with pytest.raises(ValueError, match="crosses role identity"):
        build_role_directory_projection(hub)


def test_registered_pm_kernel_vocabulary_matches_implemented_contract():
    library = json.loads((ROOT / "registry/agent-skill-library.json").read_text(encoding="utf-8"))
    pm = next(
        row
        for row in library["skills"]
        if row["skill_id"] == "skill:personal-project-management-ops"
    )

    assert set(pm["kernel_compatibility"]["durable_lifecycle_states"]) == set(LIFECYCLE_STATES)
    assert "focus-window" in pm["kernel_compatibility"]["overlay_terms"]
    unsupported_claims = set(pm["kernel_compatibility"]["unsupported_claims"])
    assert (
        "bare approval identifiers never authorize; typed event-digest attestations "
        "require an external trusted verifier"
    ) in unsupported_claims
    assert "the kernel does not dispatch agents or mutate Git" in unsupported_claims
