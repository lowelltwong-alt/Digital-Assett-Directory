from __future__ import annotations

import json
import os
import shutil
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema.exceptions import ValidationError
from jsonschema.validators import validator_for
from typer.testing import CliRunner

from digital_asset_directory import global_personal_skills as gps
from digital_asset_directory.cli import app
from digital_asset_directory.global_personal_skills import (
    archive_root,
    build_graph,
    export_portable,
    inventory,
    list_archive,
    query_archive,
    snapshot,
    status,
)
from digital_asset_directory.journal import _iter_data_plane_files
from digital_asset_directory.transport import (
    LOCAL_ONLY_DATA_PATHS,
    apply_data_migration,
    init_data_root,
    plan_data_migration,
)

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = [
    "personal-skill-source-manifest.schema.json",
    "personal-skill-revision.schema.json",
    "personal-skill-run.schema.json",
    "personal-skill-portable-export.schema.json",
]


def _manifest(skills: list[tuple[str, str]]) -> dict:
    return {
        "schema_version": "dad.personal-skills.v1",
        "manifest_id": "global-personal-skills-gpt",
        "source_runtime": "codex",
        "source_root_kind": "codex_home_skills",
        "source_root_relative": "skills",
        "deny_skill_names": [".system", "third-party"],
        "deny_path_parts": ["cache", "vendor"],
        "text_extensions": [".json", ".md", ".py", ".txt", ".yaml", ".yml"],
        "max_file_bytes": 100000,
        "max_skill_bytes": 500000,
        "authority_boundary": "Fixture allowlist; live root remains authority.",
        "skills": [
            {
                "skill_id": f"personal-skill:{skill_id}",
                "name": skill_id,
                "source_path": path,
                "origin": "personal",
                "status": "active",
            }
            for skill_id, path in skills
        ],
    }


def _hub(
    tmp_path: Path, skills: list[tuple[str, str]] = [("alpha", "alpha")]
) -> tuple[Path, Path, Path, dict[str, str]]:
    hub = tmp_path / "hub"
    source = tmp_path / "codex" / "skills"
    data = tmp_path / "data"
    (hub / "registry").mkdir(parents=True)
    (hub / "schemas").mkdir()
    (hub / "config").mkdir()
    source.mkdir(parents=True)
    schema_registry = {"schemas": {}}
    for name in SCHEMAS:
        shutil.copy2(ROOT / "schemas" / name, hub / "schemas" / name)
        schema_registry["schemas"][name.removesuffix(".schema.json").replace("-", "_")] = (
            f"schemas/{name}"
        )
    (hub / "registry/schema-registry.json").write_text(
        json.dumps(schema_registry), encoding="utf-8"
    )
    (hub / "registry/agent-skill-library.json").write_text('{"skills": []}', encoding="utf-8")
    (hub / "config/global-personal-skills.json").write_text(
        json.dumps(_manifest(skills)), encoding="utf-8"
    )
    init_data_root(data, hub_root=hub)
    return hub, source, data, {"DAD_DATA_ROOT": str(data)}


def _skill(
    source: Path,
    name: str,
    body: str = "# Skill\n\nPortable procedure.\n",
    *,
    adapter: bool = False,
) -> Path:
    root = source / name
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text(body, encoding="utf-8")
    if adapter:
        (root / "agents").mkdir()
        (root / "agents/openai.yaml").write_text(
            "interface:\n  display_name: Fixture\n", encoding="utf-8"
        )
    return root


def test_source_manifest_is_registered_and_conforms() -> None:
    registry = json.loads((ROOT / "registry/schema-registry.json").read_text(encoding="utf-8"))[
        "schemas"
    ]
    payload = json.loads((ROOT / "config/global-personal-skills.json").read_text(encoding="utf-8"))
    schema = json.loads(
        (ROOT / registry["personal_skill_source_manifest"]).read_text(encoding="utf-8")
    )
    cls = validator_for(schema)
    cls.check_schema(schema)
    cls(schema).validate(payload)
    assert len(payload["skills"]) == 20
    assert {".system", "codex-primary-runtime"} <= set(payload["deny_skill_names"])
    assert LOCAL_ONLY_DATA_PATHS["personal_skill_archives"] == "private/personal-skills"



def test_local_only_archive_migrates_but_is_never_journaled(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    archive_file = hub / "private/personal-skills/revisions/example/revision.json"
    archive_file.parent.mkdir(parents=True)
    archive_file.write_text('{"inert": true}', encoding="utf-8")
    target = tmp_path / "data"

    plan = plan_data_migration(hub, target)
    surface = next(
        row for row in plan["surfaces"] if row["logical_name"] == "personal_skill_archives"
    )
    assert surface["file_count"] == 1

    applied = apply_data_migration(hub, target)
    assert applied["activated"] is True
    assert applied["copied"] == 1
    assert (
        target / "private/personal-skills/revisions/example/revision.json"
    ).read_text(encoding="utf-8") == '{"inert": true}'
    assert not any(
        "private/personal-skills" in relative.as_posix()
        for _source, relative in _iter_data_plane_files(hub)
    )


def test_local_only_migration_rejects_linked_archive_source(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    outside = tmp_path / "outside.txt"
    outside.write_text("must not migrate", encoding="utf-8")
    link = hub / "private/personal-skills/linked.txt"
    link.parent.mkdir(parents=True)
    try:
        os.symlink(outside, link)
    except OSError:
        pytest.skip("file symlink creation unavailable")

    with pytest.raises(RuntimeError, match="link or reparse"):
        plan_data_migration(hub, tmp_path / "data")


def test_local_only_migration_rejects_redirected_destination(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    archive_file = hub / "private/personal-skills/revisions/example/revision.json"
    archive_file.parent.mkdir(parents=True)
    archive_file.write_text('{"inert": true}', encoding="utf-8")
    target = tmp_path / "data"
    target.mkdir()
    live_source = tmp_path / "live-source"
    live_source.mkdir()
    try:
        os.symlink(live_source, target / "private", target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation unavailable")

    with pytest.raises(RuntimeError, match="link or reparse|resolved outside"):
        apply_data_migration(hub, target)
    assert not (live_source / "personal-skills").exists()



def test_local_only_migration_rejects_redirected_source_ancestor(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    redirected_parent = tmp_path / "redirected-private"
    redirected_parent.mkdir()
    archive_file = redirected_parent / "personal-skills/revision.json"
    archive_file.parent.mkdir()
    archive_file.write_text('{"inert": true}', encoding="utf-8")
    try:
        os.symlink(redirected_parent, hub / "private", target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation unavailable")

    with pytest.raises(RuntimeError, match="link or reparse|resolved outside"):
        plan_data_migration(hub, tmp_path / "data")


def test_data_root_init_rejects_redirected_target(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    live_source = tmp_path / "live-source"
    live_source.mkdir()
    target = tmp_path / "data"
    try:
        os.symlink(live_source, target, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation unavailable")

    with pytest.raises(RuntimeError, match="link or reparse|resolved outside"):
        init_data_root(target, hub_root=hub)
    assert not (live_source / ".dad-data-root.json").exists()


def test_allowlist_deny_and_unknown_origin_are_deterministic(tmp_path: Path) -> None:

    hub, source, _data, env = _hub(tmp_path)
    skill = _skill(source, "alpha")
    _skill(source, "unknown", "api_key=not-read-because-unknown\n")
    _skill(source, ".system")
    _skill(source, "third-party")
    result = inventory(hub, source_root=source, env=env)
    assert result["active_skill_count"] == 1
    assert result["unsafe_skill_count"] == 0
    assert result["unknown_origins"] == [
        {
            "source_relative_path": "unknown",
            "status": "unknown_origin",
            "reason": "not_in_explicit_personal_skill_allowlist",
        }
    ]
    (skill / "SKILL.md").write_text("api_key=not-read-because-denied\n", encoding="utf-8")
    manifest_path = hub / "config/global-personal-skills.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["deny_skill_names"].append("alpha")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    denied = inventory(hub, source_root=source, env=env)
    assert denied["skills"][0]["status"] == "unsafe"
    assert denied["skills"][0]["issues"] == [{"path": "alpha", "reason": "explicit_deny_wins"}]


def test_source_path_traversal_is_rejected_by_manifest_schema(tmp_path: Path) -> None:
    hub, source, _data, env = _hub(tmp_path)
    _skill(source, "alpha")
    manifest_path = hub / "config/global-personal-skills.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["skills"][0]["source_path"] = "../outside"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValidationError, match="does not match"):
        inventory(hub, source_root=source, env=env)
    manifest["skills"][0]["source_path"] = "alpha"
    manifest["source_runtime"] = "../../escape"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValidationError, match="does not match"):
        inventory(hub, source_root=source, env=env)


def test_dedupe_revision_creation_and_disappearance_preserve_history(tmp_path: Path) -> None:
    hub, source, _data, env = _hub(tmp_path)
    skill = _skill(source, "alpha")
    first = snapshot(hub, source_root=source, env=env, observed_at="2026-07-13T00:00:00+00:00")
    second = snapshot(hub, source_root=source, env=env, observed_at="2026-07-13T01:00:00+00:00")
    assert first["entries"][0]["event_type"] == "created"
    assert second["entries"][0]["event_type"] == "unchanged"
    assert first["entries"][0]["revision_id"] == second["entries"][0]["revision_id"]
    assert len(list(archive_root(hub, env=env).glob("revisions/*/*/revision.json"))) == 1
    (skill / "SKILL.md").write_text("# Skill\n\nChanged.\n", encoding="utf-8")
    third = snapshot(hub, source_root=source, env=env, observed_at="2026-07-13T02:00:00+00:00")
    assert third["entries"][0]["event_type"] == "revised"
    assert len(list(archive_root(hub, env=env).glob("revisions/*/*/revision.json"))) == 2
    (skill / "SKILL.md").write_text("# Skill\n\nChanged again.\n", encoding="utf-8")
    fourth = snapshot(hub, source_root=source, env=env, observed_at="2026-07-13T02:00:00+00:00")
    assert third["run_id"] != fourth["run_id"]
    assert len(list(archive_root(hub, env=env).glob("revisions/*/*/revision.json"))) == 3
    shutil.rmtree(skill)
    missing = snapshot(hub, source_root=source, env=env, observed_at="2026-07-13T03:00:00+00:00")
    assert missing["entries"][0]["event_type"] == "missing"
    assert len(list_archive(hub, env=env)["archived_revisions"]) == 3


def test_unsafe_secret_and_sensitive_path_archive_no_bytes(tmp_path: Path) -> None:
    hub, source, _data, env = _hub(tmp_path)
    skill = _skill(source, "alpha", "api_key=syntheticplaceholder\n")
    secret_result = snapshot(hub, source_root=source, env=env)
    assert secret_result["entries"][0]["event_type"] == "unsafe"
    assert any(
        issue["reason"] == "secret_like_content"
        for issue in secret_result["entries"][0]["issues"]
    )

    (skill / "SKILL.md").write_text("# Safe fixture\n", encoding="utf-8")
    (skill / "secrets").mkdir()
    (skill / "secrets/value.txt").write_text(
        "synthetic fixture content", encoding="utf-8"
    )
    result = snapshot(hub, source_root=source, env=env)
    assert result["entries"][0]["event_type"] == "unsafe"
    assert any(
        issue["reason"] == "private_or_sensitive_path"
        for issue in result["entries"][0]["issues"]
    )
    assert result["status"] == "needs_review"
    assert not list(archive_root(hub, env=env).glob("blobs/sha256/*/*"))
    assert not list(archive_root(hub, env=env).glob("revisions/*/*/revision.json"))

    unsafe = query_archive(hub, health="unsafe", env=env)["results"]
    assert len(unsafe) == 1 and unsafe[0]["artifact_role"] == "active_personal_source"


def test_unknown_origin_query_and_local_only_journal_exclusion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub, source, _data, env = _hub(tmp_path)
    _skill(source, "alpha")
    _skill(source, "unknown")
    monkeypatch.setenv("DAD_DATA_ROOT", str(_data))
    snapshot(hub, source_root=source, env=env)
    unknown = query_archive(hub, health="unknown_origin", env=env)["results"]
    assert unknown == [
        {
            "source_relative_path": "unknown",
            "status": "unknown_origin",
            "reason": "not_in_explicit_personal_skill_allowlist",
            "skill_id": "",
            "revision_id": "",
            "artifact_role": "unknown_source_observation",
            "health": "unknown_origin",
            "health_flags": ["unknown_origin"],
            "pointer_status": "unknown_origin",
        }
    ]
    archive_file = archive_root(hub, env=env) / "private-proof.txt"
    archive_file.write_text("not journaled", encoding="utf-8")
    assert archive_file not in {
        source_path for source_path, _relative in _iter_data_plane_files(hub)
    }


def test_link_or_junction_is_rejected_when_supported(tmp_path: Path) -> None:
    hub, source, _data, env = _hub(tmp_path)
    skill = _skill(source, "alpha")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    try:
        os.symlink(outside, skill / "linked.txt")
    except OSError:
        pytest.skip("symlink creation unavailable")
    result = inventory(hub, source_root=source, env=env)
    assert result["skills"][0]["status"] == "unsafe"
    assert any(issue["reason"] == "link_or_junction" for issue in result["skills"][0]["issues"])



def test_archive_pointer_symlink_cannot_redirect_write_into_live_source(
    tmp_path: Path,
) -> None:
    hub, source, _data, env = _hub(tmp_path)
    skill = _skill(source, "alpha")
    snapshot(
        hub,
        source_root=source,
        env=env,
        observed_at="2026-07-13T00:00:00+00:00",
    )
    pointer_directory = next((archive_root(hub, env=env) / "skills").iterdir())
    (pointer_directory / "current.json").unlink()
    pointer_directory.rmdir()
    try:
        os.symlink(skill, pointer_directory, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation unavailable")

    (skill / "SKILL.md").write_text("# Changed live source\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="link or reparse|resolved outside"):
        snapshot(hub, source_root=source, env=env)
    assert not (skill / "current.json").exists()

def test_snapshot_fails_closed_without_initialized_data_root(tmp_path: Path) -> None:
    hub, source, _data, _env = _hub(tmp_path)
    _skill(source, "alpha")
    ghost = {"DAD_DATA_ROOT": str(tmp_path / "ghost")}
    assert status(hub, source_root=source, env=ghost)["data_root_mode"] == "legacy"
    with pytest.raises(RuntimeError, match="initialized DAD_DATA_ROOT"):
        snapshot(hub, source_root=source, env=ghost)


def test_portable_export_is_deterministic_redacted_and_adapter_separated(tmp_path: Path) -> None:
    hub, source, _data, env = _hub(tmp_path)
    _skill(source, "alpha", f"# Skill\n\nRead {source} only when local.\n", adapter=True)
    run = snapshot(hub, source_root=source, env=env, observed_at="2026-07-13T00:00:00+00:00")
    revision = run["entries"][0]["revision_id"]
    first = export_portable(
        hub,
        skill_id="personal-skill:alpha",
        revision_id=revision,
        target_runtime="frontier-x",
        reviewed_by="Lowell",
        approval_id="APPROVED-1",
        env=env,
    )
    second = export_portable(
        hub,
        skill_id="personal-skill:alpha",
        revision_id=revision,
        target_runtime="frontier-x",
        reviewed_by="Lowell",
        approval_id="APPROVED-1",
        env=env,
    )
    assert first["bundle_sha256"] == second["bundle_sha256"]
    bundle = Path(first["bundle_path_private_hint"])
    assert first["exported_at"] == second["exported_at"]
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        combined = b"".join(archive.read(name) for name in names)
    assert "procedure/SKILL.md" in names
    assert "adapters/codex/agents/openai.yaml" not in names
    assert str(source).encode() not in combined
    assert b"${LOCAL_SOURCE_ROOT}" in combined


def test_portable_export_rejects_unrecognized_absolute_paths(tmp_path: Path) -> None:
    hub, source, _data, env = _hub(tmp_path)
    _skill(source, "alpha", "# Skill\n\nRead D:/Elsewhere/private.txt.\n")
    run = snapshot(hub, source_root=source, env=env)
    with pytest.raises(ValueError, match="absolute local path"):
        export_portable(
            hub,
            skill_id="personal-skill:alpha",
            revision_id=run["entries"][0]["revision_id"],
            target_runtime="frontier-x",
            reviewed_by="Lowell",
            approval_id="APPROVED-2",
            env=env,
        )


def test_graph_distinguishes_identity_roles_and_exact_duplicates(tmp_path: Path) -> None:
    hub, source, _data, env = _hub(tmp_path, [("alpha", "alpha"), ("beta", "beta")])
    _skill(source, "alpha")
    _skill(source, "beta")
    snapshot(hub, source_root=source, env=env, observed_at="2026-07-13T00:00:00+00:00")
    graph = build_graph(hub, env=env)
    node_types = {node["node_type"] for node in graph["nodes"]}
    edge_types = {edge["edge_type"] for edge in graph["edges"]}
    assert {
        "personal_skill",
        "active_personal_source",
        "archived_revision",
        "runtime",
    } <= node_types
    assert {"snapshot_of", "revision_of", "loaded_by", "duplicate_content_of"} <= edge_types
    node_ids = {node["node_id"] for node in graph["nodes"]}
    assert {"personal-skill:alpha", "personal-skill:beta"} <= node_ids
    assert not any(
        node_id.startswith("personal-skill:personal-skill:")
        for node_id in node_ids
    )
    assert all(
        not edge["target"].startswith("personal-skill:personal-skill:")
        for edge in graph["edges"]
    )
    assert graph["local_paths_included"] is False
    assert str(tmp_path) not in json.dumps(graph)


def test_sensitive_filename_forms_are_blocked_without_archiving(tmp_path: Path) -> None:
    hub, source, _data, env = _hub(tmp_path)
    skill = _skill(source, "alpha")
    (skill / "conversation.md").write_text("private payload", encoding="utf-8")
    result = snapshot(hub, source_root=source, env=env)
    assert result["entries"][0]["event_type"] == "unsafe"
    assert {issue["reason"] for issue in result["entries"][0]["issues"]} == {
        "private_or_sensitive_path"
    }
    assert not list(archive_root(hub, env=env).glob("blobs/sha256/*/*"))


def test_dotenv_is_blocking_and_never_partially_archived(tmp_path: Path) -> None:
    hub, source, _data, env = _hub(tmp_path)
    skill = _skill(source, "alpha")
    (skill / ".env").write_text("SYNTHETIC_ONLY=true\n", encoding="utf-8")
    result = snapshot(hub, source_root=source, env=env)
    assert result["entries"][0]["event_type"] == "unsafe"
    assert {issue["reason"] for issue in result["entries"][0]["issues"]} == {
        "private_or_sensitive_path"
    }
    assert not list(archive_root(hub, env=env).glob("blobs/sha256/*/*"))
    assert not list(archive_root(hub, env=env).glob("revisions/*/*/revision.json"))



def test_paused_and_deny_rows_are_metadata_only(tmp_path: Path) -> None:
    hub, source, _data, env = _hub(tmp_path)
    skill = _skill(source, "alpha", "api_key=not-read-because-paused\n")
    manifest_path = hub / "config/global-personal-skills.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["skills"][0]["status"] = "paused"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    observed = inventory(hub, source_root=source, env=env)
    assert observed["skills"][0]["status"] == "paused"
    assert observed["skills"][0]["issues"] == []
    run = snapshot(hub, source_root=source, env=env)
    assert run["entries"][0]["event_type"] == "paused"
    assert not list(archive_root(hub, env=env).glob("blobs/sha256/*/*"))
    assert skill.exists()


def test_manifest_rejects_duplicate_stable_ids_and_casefolded_paths(tmp_path: Path) -> None:
    hub, source, _data, env = _hub(tmp_path)
    _skill(source, "alpha")
    manifest_path = hub / "config/global-personal-skills.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    duplicate = dict(manifest["skills"][0])
    duplicate["source_path"] = "ALPHA"
    manifest["skills"].append(duplicate)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate skill_id"):
        inventory(hub, source_root=source, env=env)
    manifest["skills"][1]["skill_id"] = "personal-skill:beta"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate case-insensitive source_path"):
        inventory(hub, source_root=source, env=env)


def test_snapshot_prevalidates_entire_transaction_before_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub, source, _data, env = _hub(tmp_path)
    _skill(source, "alpha")
    original = gps._validate

    def fail_run(target_hub: Path, schema_name: str, payload: dict) -> None:
        if schema_name == "personal_skill_run":
            raise ValueError("synthetic run schema failure")
        original(target_hub, schema_name, payload)

    monkeypatch.setattr(gps, "_validate", fail_run)
    with pytest.raises(ValueError, match="synthetic run schema failure"):
        snapshot(hub, source_root=source, env=env)
    root = archive_root(hub, env=env)
    assert not list(root.glob("blobs/sha256/*/*"))
    assert not list(root.glob("revisions/*/*/revision.json"))
    assert not list(root.glob("skills/*/current.json"))
    assert not list(root.glob("runs/*.json"))
    assert not (root / "runs.jsonl").exists()
    assert not (root / "events.jsonl").exists()


def test_archive_root_must_be_disjoint_from_active_source(tmp_path: Path) -> None:
    hub, source, _data, _env = _hub(tmp_path)
    _skill(source, "alpha")
    init_data_root(source, hub_root=hub)
    env = {"DAD_DATA_ROOT": str(source)}
    with pytest.raises(RuntimeError, match="must be disjoint"):
        snapshot(hub, source_root=source, env=env)
    assert not (source / "private/personal-skills").exists()


def test_same_content_rename_dedupes_and_allowlist_removal_closes_pointer(
    tmp_path: Path,
) -> None:
    hub, source, _data, env = _hub(tmp_path, [("alpha", "alpha"), ("gamma", "gamma")])
    alpha = _skill(source, "alpha")
    _skill(source, "gamma", "# Gamma\n")
    first = snapshot(hub, source_root=source, env=env)
    first_revision = next(
        row["revision_id"] for row in first["entries"] if row["skill_id"] == "personal-skill:alpha"
    )
    alpha.rename(source / "beta")
    manifest_path = hub / "config/global-personal-skills.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["skills"][0]["source_path"] = "beta"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    renamed = snapshot(hub, source_root=source, env=env)
    renamed_event = next(
        row for row in renamed["entries"] if row["skill_id"] == "personal-skill:alpha"
    )
    assert renamed_event["revision_id"] == first_revision
    assert renamed_event["source_relative_path"] == "beta"
    manifest["skills"] = [manifest["skills"][1]]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    shutil.rmtree(source / "beta")
    pending = status(hub, source_root=source, env=env)
    pending_alpha = next(
        row for row in pending["changes"] if row["skill_id"] == "personal-skill:alpha"
    )
    assert pending_alpha["change"] == "not_allowlisted"
    assert pending["unknown_origins"] == []
    removed = snapshot(hub, source_root=source, env=env)
    removed_event = next(
        row for row in removed["entries"] if row["skill_id"] == "personal-skill:alpha"
    )
    assert removed_event["event_type"] == "not_allowlisted"
    pointer = next(
        row
        for row in list_archive(hub, env=env)["active_sources"]
        if row["skill_id"] == "personal-skill:alpha"
    )
    assert pointer["status"] == "not_allowlisted"
    assert pointer["current_revision_id"] == first_revision


def test_export_binds_skill_revision_and_rejects_path_like_metadata(tmp_path: Path) -> None:
    hub, source, _data, env = _hub(tmp_path, [("alpha", "alpha"), ("beta", "beta")])
    _skill(source, "alpha")
    _skill(source, "beta", "# Beta\n")
    run = snapshot(hub, source_root=source, env=env)
    alpha_revision = next(
        row["revision_id"] for row in run["entries"] if row["skill_id"] == "personal-skill:alpha"
    )
    with pytest.raises(ValueError, match="does not own"):
        export_portable(
            hub,
            skill_id="personal-skill:beta",
            revision_id=alpha_revision,
            target_runtime="frontier-x",
            reviewed_by="Lowell",
            approval_id="APPROVED-3",
            env=env,
        )
    with pytest.raises(ValueError, match="revision ID"):
        export_portable(
            hub,
            skill_id="personal-skill:alpha",
            revision_id="../../escape",
            target_runtime="frontier-x",
            reviewed_by="Lowell",
            approval_id="APPROVED-3",
            env=env,
        )
    with pytest.raises(ValueError, match="path-like"):
        export_portable(
            hub,
            skill_id="personal-skill:alpha",
            revision_id=alpha_revision,
            target_runtime="frontier-x",
            reviewed_by="C:\\Users\\name",
            approval_id="APPROVED-3",
            env=env,
        )


def test_export_revalidates_stored_blob_and_rejects_any_posix_absolute_path(
    tmp_path: Path,
) -> None:
    hub, source, _data, env = _hub(tmp_path)
    _skill(source, "alpha", "# Skill\n\nRead /etc/private-client-payload.\n")
    run = snapshot(hub, source_root=source, env=env)
    revision_id = run["entries"][0]["revision_id"]
    with pytest.raises(ValueError, match="absolute local path"):
        export_portable(
            hub,
            skill_id="personal-skill:alpha",
            revision_id=revision_id,
            target_runtime="frontier-x",
            reviewed_by="Lowell",
            approval_id="APPROVED-4",
            env=env,
        )
    revision = list_archive(hub, env=env)["archived_revisions"][0]
    blob = gps._blob(archive_root(hub, env=env), revision["files"][0]["blob_sha256"])
    blob.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity validation"):
        export_portable(
            hub,
            skill_id="personal-skill:alpha",
            revision_id=revision_id,
            target_runtime="frontier-x",
            reviewed_by="Lowell",
            approval_id="APPROVED-4",
            env=env,
        )


def test_query_distinguishes_historical_unvalidated_adaptations_and_duplicates(
    tmp_path: Path,
) -> None:
    hub, source, _data, env = _hub(tmp_path, [("alpha", "alpha"), ("beta", "beta")])
    alpha = _skill(source, "alpha")
    _skill(source, "beta")
    registry = {
        "skills": [
            {
                "skill_id": "skill:alpha-adaptation",
                "name": "Alpha Adaptation",
                "review_status": "candidate",
                "source_evidence": ["personal-skill-source:alpha"],
            }
        ]
    }
    (hub / "registry/agent-skill-library.json").write_text(json.dumps(registry), encoding="utf-8")
    snapshot(hub, source_root=source, env=env, observed_at="2026-07-13T00:00:00+00:00")
    duplicate_rows = query_archive(
        hub, artifact_role="duplicate_content_relation", skill_id="personal-skill:alpha", env=env
    )["results"]
    assert duplicate_rows and duplicate_rows[0]["relation"] == "duplicate_content_of"
    adaptation_rows = query_archive(
        hub, artifact_role="dad_adaptation", skill_id="personal-skill:alpha", env=env
    )["results"]
    assert adaptation_rows and adaptation_rows[0]["adaptation_skill_id"] == "skill:alpha-adaptation"
    (alpha / "SKILL.md").write_text("# Skill\n\nChanged.\n", encoding="utf-8")
    snapshot(hub, source_root=source, env=env, observed_at="2026-07-13T01:00:00+00:00")
    revisions = query_archive(
        hub, artifact_role="source_snapshot", skill_id="personal-skill:alpha", env=env
    )["results"]
    assert len(revisions) == 2
    assert "historical" in revisions[0]["health_flags"]
    assert "historical" not in revisions[1]["health_flags"]
    assert all("unvalidated" in row["health_flags"] for row in revisions)


def test_graph_edges_include_candidate_provenance_and_real_checkouts_only(tmp_path: Path) -> None:
    hub, source, _data, env = _hub(tmp_path)
    _skill(source, "alpha")
    snapshot(hub, source_root=source, env=env)
    graph = build_graph(hub, env=env)
    assert all(edge["confidence"] for edge in graph["edges"])
    assert all(
        edge["scan_provenance"]["source"] == "global-personal-skills-gpt" for edge in graph["edges"]
    )
    assert not any(node["node_type"] == "checkout_pointer" for node in graph["nodes"])
    assert not any(
        node.get("node_type") == "active_personal_source" and node.get("active") is False
        for node in graph["nodes"]
    )


def test_stored_revision_member_traversal_is_rejected(tmp_path: Path) -> None:
    hub, source, _data, env = _hub(tmp_path)
    _skill(source, "alpha")
    run = snapshot(hub, source_root=source, env=env)
    revision_id = run["entries"][0]["revision_id"]
    root = archive_root(hub, env=env)
    revision_path = gps._revision(root, revision_id)
    record = json.loads(revision_path.read_text(encoding="utf-8"))
    record["files"][0]["relative_path"] = "../escape.md"
    revision_path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsafe portable bundle member"):
        export_portable(
            hub,
            skill_id="personal-skill:alpha",
            revision_id=revision_id,
            target_runtime="frontier-x",
            reviewed_by="Lowell",
            approval_id="APPROVED-5",
            env=env,
        )


def test_final_path_metadata_change_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill = tmp_path / "skill"
    skill.mkdir()
    path = skill / "SKILL.md"
    path.write_text("stable bytes", encoding="utf-8")
    original_lstat = Path.lstat
    calls = 0

    def changed_final_lstat(candidate: Path):
        nonlocal calls
        observed = original_lstat(candidate)
        if candidate == path:
            calls += 1
            if calls == 2:
                return SimpleNamespace(
                    st_dev=observed.st_dev,
                    st_ino=observed.st_ino,
                    st_mode=observed.st_mode,
                    st_size=observed.st_size,
                    st_mtime_ns=observed.st_mtime_ns + 1,
                )
        return observed

    monkeypatch.setattr(Path, "lstat", changed_final_lstat)
    data, reason = gps._read_regular_file(path, skill, 1000)
    assert data == b""
    assert reason == "changed_during_read"


def test_graph_legacy_fallback_never_writes_repo_state(tmp_path: Path) -> None:
    hub, _source, _data, _env = _hub(tmp_path)
    ghost = {"DAD_DATA_ROOT": str(tmp_path / "uninitialized")}
    graph = build_graph(
        hub,
        env=ghost,
        manifest=_manifest([("alpha", "alpha")]),
        observations=[],
    )
    assert graph["schema_version"] == "dad.personal-skills.v1"
    assert not (hub / "private/personal-skills/graph.json").exists()


def test_personal_skills_cli_has_no_unreviewed_source_or_manifest_override() -> None:
    runner = CliRunner()
    for command in ("inventory", "status", "diff", "snapshot", "daily"):
        result = runner.invoke(app, ["personal-skills", command, "--help"])
        assert result.exit_code == 0
        assert "--source-root" not in result.stdout
        assert "--manifest" not in result.stdout
