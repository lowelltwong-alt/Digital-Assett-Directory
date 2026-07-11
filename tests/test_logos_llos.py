from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import yaml

from digital_asset_directory.logos_llos import LOGOS_LLOS_SURFACES, audit_logos_llos


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _repo(tmp_path: Path, repo_id: str) -> SimpleNamespace:
    root = tmp_path / "control" / repo_id
    live_root = tmp_path / "live" / repo_id
    live_root.mkdir(parents=True)
    payloads = {
        "logos-governance-architecture": [
            {
                "schema_version": "logos.llos.standard.v1",
                "standard_id": "LLOS-v1",
                "surface_version": "1.0.0",
                "dad_bridge": {
                    "write_inside_logos_repo": False,
                    "deliver_to_logos_inbox": False,
                    "mutate_logos_contract": False,
                    "mutate_logos_index": False,
                },
                "communication": {
                    "dad_push_to_logos_allowed": False,
                    "dad_direct_logos_inbox_write_allowed": False,
                    "candidate_return_authorizes_local_change": False,
                },
            },
            {
                "schema_version": "logos.llos.routes.v1",
                "surface_version": "1.0.0",
                "routes": {key: {} for key in ("governance", "scripture", "boundary", "doctrine", "dad_candidate")},
            },
        ],
        "logos-scripture-graph": [
            {
                "object_type": "scripture_llos_v1_adapter",
                "upstream_governance": {
                    "repository": "logos-governance-architecture",
                    "path": "governance/LOGOS_LEARNING_LOOP_OPERATING_STANDARD.yaml",
                    "surface_version": "1.0.0",
                },
                "asymmetric_transport_boundary": {"dad_central": {"may_push_or_write_any_file_into_logos": False, "may_write_logos_inbox": False}},
                "authority": {"authorizes_dad_write_to_logos": False, "authorizes_scripture_data_change": False},
            }
        ],
        "logos-boundary-literature": [
            {
                "object_type": "llos_standard_mirror",
                "upstream_standard": {"repo": "logos-governance-architecture", "path": "governance/LOGOS_LEARNING_LOOP_OPERATING_STANDARD.yaml", "surface_version": "1.0.0"},
                "dad_bridge": {"dad_may_write_inside_logos_repo": False, "dad_may_deliver_to_logos_inbox": False},
                "authority": {"authorizes_source_import": False, "authorizes_canonical_authority": False, "authorizes_cross_repo_override": False},
            },
            {"object_type": "llos_lesson_index", "lessons": []},
        ],
        "logos-doctrine-genealogy": [
            {
                "object_type": "llos_v1_adapter",
                "upstream_standard": {"repository": "logos-governance-architecture", "path": "governance/LOGOS_LEARNING_LOOP_OPERATING_STANDARD.yaml", "surface_version": "1.0.0"},
                "dad_bridge": {"may_write_doctrine_files": False, "may_push_or_write_logos_inbox": False},
                "authority": {"authorizes_runtime_adapters": False, "authorizes_data_authority": False, "authorizes_theology_authority": False},
            },
            {"object_type": "llos_v1_lesson_index", "lessons": []},
        ],
    }
    for relative, payload in zip(LOGOS_LLOS_SURFACES[repo_id], payloads[repo_id], strict=True):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    marker = root / ".digital-asset/dad-write-policy.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps(
            {
                "schema_version": "dad.logos.write-policy.v1",
                "repo_id": repo_id,
                "dad_write_allowed": False,
                "approval_mode": "fresh_explicit_owner_approval",
                "approved_explicit_approval_ids": [],
                "logos_local_outbox_write_allowed": True,
                "logos_local_dad_central_read_allowed": True,
                "dad_read_approved_metadata_allowed": True,
                "dad_push_or_inbox_write_allowed": False,
                "rollout_approval_is_standing_write_permission": False,
            }
        ),
        encoding="utf-8",
    )
    return SimpleNamespace(
        id=repo_id,
        path=live_root,
        llos_control_path=root,
        mail_enabled=True,
    )


def test_synthetic_family_audit_is_current_and_never_writes_sources(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    policies = [_repo(tmp_path, repo_id) for repo_id in LOGOS_LLOS_SURFACES]
    before_live = {row.id: _tree_hash(row.path) for row in policies}
    before_control = {row.id: _tree_hash(row.llos_control_path) for row in policies}

    result = audit_logos_llos(hub, policies)

    assert result["current_count"] == 4
    assert result["upgrade_required_count"] == 0
    assert result["source_write_count"] == 0
    assert {row.id: _tree_hash(row.path) for row in policies} == before_live
    assert {row.id: _tree_hash(row.llos_control_path) for row in policies} == before_control
    assert Path(result["report_path"]).is_file()


def test_control_mirror_is_independent_from_live_communication_root(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    mirror_policy = _repo(tmp_path / "mirrors", "logos-scripture-graph")
    live_root = tmp_path / "live" / "logos-scripture-graph"
    outbox = live_root / ".digital-asset/mail/outbox.jsonl"
    outbox.parent.mkdir(parents=True)
    outbox.write_text('{"candidate":"local"}\n', encoding="utf-8")
    policy = SimpleNamespace(
        id="logos-scripture-graph",
        path=live_root,
        llos_control_path=mirror_policy.llos_control_path,
        mail_enabled=True,
    )
    before_live = _tree_hash(live_root)
    before_mirror = _tree_hash(mirror_policy.llos_control_path)

    result = audit_logos_llos(hub, [policy])

    scripture = next(row for row in result["repos"] if row["repo_id"] == policy.id)
    assert scripture["status"] == "current"
    assert scripture["control_root_source"] == "llos_control_path"
    assert _tree_hash(live_root) == before_live
    assert _tree_hash(mirror_policy.llos_control_path) == before_mirror


def test_missing_blank_or_overlapping_control_root_fails_closed(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    controls = (None, "", tmp_path / "live", tmp_path / "live/nested")

    for index, control_root in enumerate(controls):
        live_root = tmp_path / "live" if index >= 2 else tmp_path / f"live-{index}"
        policy = SimpleNamespace(
            id="logos-scripture-graph",
            path=live_root,
            mail_enabled=True,
        )
        if control_root is not None:
            policy.llos_control_path = control_root
        result = audit_logos_llos(hub, [policy])
        scripture = next(
            row for row in result["repos"] if row["repo_id"] == "logos-scripture-graph"
        )
        assert scripture["status"] == "upgrade_required"
        assert scripture["dad_write_policy"] == "missing_or_unsafe"
        assert scripture["control_root_source"] in {
            "unconfigured",
            "invalid_llos_control_path",
        }


def test_malformed_yaml_replaces_stale_current_report(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    policy = _repo(tmp_path, "logos-scripture-graph")
    first = audit_logos_llos(hub, [policy])
    assert first["current_count"] == 1
    adapter = policy.llos_control_path / ".ai/control/llos_v1_adapter.yaml"
    adapter.write_text("invalid: [unterminated\n", encoding="utf-8")

    second = audit_logos_llos(hub, [policy])

    scripture = next(row for row in second["repos"] if row["repo_id"] == policy.id)
    persisted = json.loads(Path(second["report_path"]).read_text(encoding="utf-8"))
    assert scripture["status"] == "upgrade_required"
    assert scripture["files"][0]["status"] == "invalid"
    assert persisted["current_count"] == 0
    assert persisted["upgrade_required_count"] == 4


def test_missing_marker_or_surface_fails_closed_as_upgrade_required(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    policy = _repo(tmp_path, "logos-scripture-graph")
    (policy.llos_control_path / ".digital-asset/dad-write-policy.json").unlink()
    (policy.llos_control_path / ".ai/control/llos_v1_adapter.yaml").unlink()

    result = audit_logos_llos(hub, [policy])
    scripture = next(row for row in result["repos"] if row["repo_id"] == "logos-scripture-graph")
    assert scripture["status"] == "upgrade_required"
    assert scripture["dad_write_policy"] == "missing_or_unsafe"


def test_mismatched_marker_identity_and_unsafe_adapter_fail_closed(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    policy = _repo(tmp_path, "logos-boundary-literature")
    marker = policy.llos_control_path / ".digital-asset/dad-write-policy.json"
    value = json.loads(marker.read_text(encoding="utf-8"))
    value["repo_id"] = "logos-scripture-graph"
    marker.write_text(json.dumps(value), encoding="utf-8")
    adapter = policy.llos_control_path / "governance/LLOS_STANDARD_MIRROR.yaml"
    payload = yaml.safe_load(adapter.read_text(encoding="utf-8"))
    payload["upstream_standard"]["path"] = "wrong/path.yaml"
    payload["dad_bridge"]["dad_may_write_inside_logos_repo"] = True
    adapter.write_text(yaml.safe_dump(payload), encoding="utf-8")

    result = audit_logos_llos(hub, [policy])
    boundary = next(row for row in result["repos"] if row["repo_id"] == "logos-boundary-literature")
    assert boundary["status"] == "upgrade_required"
    assert boundary["dad_write_policy"] == "missing_or_unsafe"
    assert any("upstream identity" in error or "unsafe" in error for error in boundary["semantic_errors"])


def test_route_registry_must_be_a_mapping_not_just_matching_names(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    policy = _repo(tmp_path, "logos-governance-architecture")
    routes = policy.llos_control_path / "governance/registry/LLOS_ROUTE_REGISTRY.yaml"
    routes.write_text(
        yaml.safe_dump(
            {
                "schema_version": "logos.llos.routes.v1",
                "surface_version": "1.0.0",
                "routes": ["governance", "scripture", "boundary", "doctrine", "dad_candidate"],
            }
        ),
        encoding="utf-8",
    )
    result = audit_logos_llos(hub, [policy])
    governance = next(row for row in result["repos"] if row["repo_id"] == "logos-governance-architecture")
    assert governance["status"] == "upgrade_required"
    assert any("route registry" in error for error in governance["semantic_errors"])


def test_governed_yaml_accepts_frontmatter_and_multi_document_styles(tmp_path: Path) -> None:
    from digital_asset_directory.logos_llos import _governed_yaml

    one_document = tmp_path / "one.yaml"
    one_document.write_text("---\nsurface_version: 1.0.0\n", encoding="utf-8")
    two_documents = tmp_path / "two.yaml"
    two_documents.write_text(
        "object_type: metadata\n---\nsurface_version: 1.0.0\n",
        encoding="utf-8",
    )
    frontmatter = tmp_path / "frontmatter.yaml"
    frontmatter.write_text(
        "---\nobject_type: metadata\n---\nsurface_version: 1.0.0\n",
        encoding="utf-8",
    )

    for path in (one_document, two_documents, frontmatter):
        assert _governed_yaml(path)["surface_version"] == "1.0.0"


def test_surface_version_accepts_governance_and_standard_adapter_shapes() -> None:
    from digital_asset_directory.logos_llos import _surface_version

    assert _surface_version({"upstream_governance": {"surface_version": "1.0.0"}}) == "1.0.0"
    assert _surface_version({"upstream_standard": {"surface_version": "1.0.0"}}) == "1.0.0"
