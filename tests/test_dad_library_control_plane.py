from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from jsonschema.validators import validator_for
import pytest

from digital_asset_directory.config import EnrollmentRepoPolicy, MailRepoPolicy
from digital_asset_directory.dad_library import (
    build_dad_cadence_plan,
    discover_harness_opportunities,
    load_asset_recognition_methodology,
    load_harness_discovery_methodology,
    load_harnesses,
    load_needs,
    load_offerings,
    load_usefulness_methodology,
    match_repo_offerings,
    recommend_harnesses,
    reconcile_repo_inventory,
    record_usage,
    scout_asset_candidates,
    usage_upgrades,
)

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def _schema(name: str) -> dict:
    registry = json.loads((ROOT / "registry" / "schema-registry.json").read_text())
    return json.loads((ROOT / registry["schemas"][name]).read_text())


def _validate(schema_name: str, payload: dict) -> None:
    schema = _schema(schema_name)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


def _context_repo(tmp_path: Path, *, public_facing: bool = False) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    context = {
        "schema_version": "0.1.0",
        "repo_id": "repo",
        "repo_alias": "repo",
        "repo_ref": str(repo),
        "dad_hub_ref": str(ROOT),
        "context_dimensions": {
            "languages": ["python", "rust"],
            "repo_type": "application",
            "domains": ["software_engineering", "test_performance"],
            "visibility": "public" if public_facing else "internal",
            "public_facing": public_facing,
            "context_tags": ["pytest", "test_parity", "rust_shadow", "performance"],
        },
        "routes": [],
        "authority_boundary": "test fixture",
    }
    path = repo / ".digital-asset" / "context-map.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(context), encoding="utf-8")
    return repo


def test_dad_library_registries_validate_against_schemas():
    _validate("dad_need_registry", load_needs(ROOT))
    _validate("dad_offering_registry", load_offerings(ROOT))
    _validate("dad_usefulness_methodology", load_usefulness_methodology(ROOT))
    _validate("asset_recognition_methodology", load_asset_recognition_methodology(ROOT))
    _validate("harness_discovery_methodology", load_harness_discovery_methodology(ROOT))
    harness_schema = _schema("coding_harness")
    validator_cls = validator_for(harness_schema)
    validator_cls.check_schema(harness_schema)
    validator = validator_cls(harness_schema)
    harnesses = load_harnesses(ROOT)["harnesses"]

    assert len(harnesses) >= 6
    assert len({item["harness_id"] for item in harnesses}) == len(harnesses)
    for harness in harnesses:
        validator.validate(harness)
        harness_path = ROOT / harness["path"]
        validator.validate(json.loads((harness_path / "harness.json").read_text()))
        assert (harness_path / "README.md").exists()
        assert (harness_path / "VERSION").exists()
        assert (harness_path / "prompts" / "README.md").exists()
        assert (harness_path / "scripts" / "README.md").exists()
        assert (harness_path / "tests-or-evals" / "README.md").exists()
        assert (harness_path / "examples" / "README.md").exists()
        assert any(
            item.name != "README.md" for item in (harness_path / "scripts").iterdir()
        )
        assert any(
            item.name != "README.md" for item in (harness_path / "tests-or-evals").iterdir()
        )
        assert any(
            item.name != "README.md" for item in (harness_path / "examples").iterdir()
        )


def test_dad_match_recommends_rust_parity_for_slow_python_test_task(tmp_path: Path):
    repo = _context_repo(tmp_path)

    result = match_repo_offerings(
        ROOT,
        repo,
        task="slow pytest battery rust shadow parity timing",
        limit=5,
    )

    ids = [item["offering_id"] for item in result["matches"]]
    assert "dad:offering:rust-shadow-parity-harness" in ids
    match = next(
        item
        for item in result["matches"]
        if item["offering_id"] == "dad:offering:rust-shadow-parity-harness"
    )
    assert match["decision"] in {"save_for_future", "needs_human_review", "use_now"}
    assert match["methodology_id"] == "dad-usefulness-methodology-v0.1"
    assert "component_scores" in match


def test_harness_recommend_routes_to_rust_shadow_harness(tmp_path: Path):
    repo = _context_repo(tmp_path)

    result = recommend_harnesses(
        ROOT,
        repo,
        task="compare Rust shadow tests with Python pytest parity",
        limit=3,
    )

    ids = [item["harness_id"] for item in result["recommendations"]]
    assert "dad:harness:rust-shadow-parity" in ids


def test_usage_record_writes_local_and_central_ledgers_and_reports_upgrades(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    for rel in (
        "registry/dad-offerings-registry.json",
        "registry/dad-usefulness-methodology.json",
        "registry/dad-needs-registry.json",
        "registry/coding-harness-registry.json",
    ):
        source = ROOT / rel
        target = hub / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    repo = _context_repo(tmp_path)

    policy = MailRepoPolicy(
        id="repo",
        path=repo,
        alias="repo",
        visibility="internal",
        mail_enabled=True,
        delivery_allowed=True,
    )

    result = record_usage(
        hub,
        repo,
        asset_id="dad:offering:rust-shadow-parity-harness",
        status="watching",
        recorded_by="unit-test",
        source_ref="registry/dad-offerings-registry.json",
        reason="Need to track Rust parity upgrades.",
        mail_policies=[policy],
    )
    upgrades = usage_upgrades(hub, repo, mail_policies=[policy])

    assert result["central_appended"] is True
    assert result["local_appended"] is True
    assert (repo / ".digital-asset" / "dad-usage.jsonl").exists()
    assert upgrades["upgrade_count"] == 1
    assert upgrades["upgrades"][0]["asset_id"] == "dad:offering:rust-shadow-parity-harness"


def test_usage_record_without_reviewed_policy_is_central_only(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()

    result = record_usage(
        hub,
        repo,
        asset_id="dad:offering:ai-engineering-preflight",
        status="watching",
        recorded_by="unit-test",
    )

    assert result["central_only"] is True
    assert result["local_appended"] is False
    assert "no reviewed DAD repo policy" in result["usage"]["central_only_reason"]
    assert not (repo / ".digital-asset" / "dad-usage.jsonl").exists()


def test_protected_logos_usage_record_is_central_only(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "logos"
    hub.mkdir()
    repo.mkdir()
    policy = MailRepoPolicy(
        id="logos-scripture-graph",
        path=repo,
        alias="logos-scripture-graph",
        visibility="public",
        public_facing=True,
        write_protected=True,
        write_protection_reason="explicit local-write approval required",
    )

    result = record_usage(
        hub,
        repo,
        asset_id="dad:offering:ai-engineering-preflight",
        status="watching",
        recorded_by="unit-test",
        mail_policies=[policy],
    )

    assert result["central_only"] is True
    assert result["local_appended"] is False
    assert not (repo / ".digital-asset" / "dad-usage.jsonl").exists()


def test_active_hold_enrollment_policy_is_central_only_for_usage(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "logos-governance"
    hub.mkdir()
    repo.mkdir()
    policy = EnrollmentRepoPolicy(
        id="logos-governance-architecture",
        path=repo,
        alias="logos-governance",
        visibility="public",
        public_facing=True,
        enrollment_enabled=True,
        active_hold=True,
        active_hold_reason="explicit local-write approval required",
    )

    result = record_usage(
        hub,
        repo,
        asset_id="dad:offering:repo-enrollment-mail-governance-safety-harness",
        status="watching",
        recorded_by="unit-test",
        enrollment_policies=[policy],
    )

    assert result["central_only"] is True
    assert "explicit local-write approval" in result["usage"]["central_only_reason"]


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / ".git").mkdir()
    return path


def test_inventory_reconciliation_is_central_only_and_classifies_special_repos(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    hub.mkdir()
    workspace.mkdir()
    logos = _git_repo(workspace / "logos-scripture-graph")
    mocktrial = _git_repo(workspace / "Albert-Trial-Simulation-System")
    intake = _git_repo(workspace / "LawFirm-os-intake")
    duplicate = _git_repo(workspace / "repos" / "DuplicateRepo")
    local_source = SimpleNamespace(
        id="workspace",
        path=workspace,
        enabled=True,
        follow_symlinks=False,
    )

    result = reconcile_repo_inventory(
        hub,
        local_sources=[local_source],
        max_depth=4,
    )
    records = {
        record["repo_name"]: record
        for record in result["inventory"]["records"]
    }

    assert records[logos.name]["classification"] == "protected-central-only"
    assert "Logos repo marker" in "; ".join(records[logos.name]["classification_reasons"])
    assert records[mocktrial.name]["classification"] == "needs-human-classification"
    assert "not Logos-protected" in "; ".join(records[mocktrial.name]["classification_reasons"])
    assert records[intake.name]["classification"] == "side-project"
    assert records[duplicate.name]["classification"] == "duplicate-ignore"
    assert Path(result["json_path"]) == hub / "processed" / "repo_inventory" / "reconciled_inventory.json"
    assert Path(result["markdown_path"]).is_file()
    for repo in [logos, mocktrial, intake, duplicate]:
        assert not (repo / ".digital-asset").exists()


def test_inventory_public_policy_uses_public_safe_repo_ref(tmp_path: Path):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    public_repo = _git_repo(workspace / "Public Repo With Spaces")
    hub.mkdir()
    policy = MailRepoPolicy(
        id="public-repo",
        path=public_repo,
        alias="public-repo",
        visibility="public",
        public_facing=True,
    )

    result = reconcile_repo_inventory(hub, mail_policies=[policy], max_depth=1)
    record = result["inventory"]["records"][0]

    assert record["classification"] == "enroll"
    assert record["path_ref"] == "dad://repo/public-repo"
    assert record["path_public_safe"] == "dad://repo/public-repo"
    assert str(public_repo) not in json.dumps(record)


def test_mocktrial_policy_can_classify_as_normal_enrollment(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = _git_repo(tmp_path / "MockTrial4.26")
    hub.mkdir()
    policy = EnrollmentRepoPolicy(
        id="mocktrial-426",
        path=repo,
        alias="mocktrial",
        visibility="private",
        enrollment_enabled=True,
    )

    result = reconcile_repo_inventory(hub, enrollment_policies=[policy], max_depth=1)
    record = result["inventory"]["records"][0]

    assert record["classification"] == "enroll"
    assert record["write_boundary"] == "reviewed_policy_required"
    assert "Logos" not in "; ".join(record["classification_reasons"])


def test_cadence_plan_documents_mailbox_only_recurring_boundary(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    hub.mkdir()
    policy = MailRepoPolicy(id="repo", path=repo, alias="repo")

    result = build_dad_cadence_plan(hub, mail_policies=[policy])
    cadence = result["cadence"]

    assert cadence["daily"]["write_boundary"] == ".digital-asset/mail/**"
    assert "no normal recurring source edits" in cadence["blocked_operations"]
    assert Path(result["json_path"]) == hub / "processed" / "cadence" / "dad_cadence_plan.json"
    assert not repo.exists()


def test_asset_scout_is_path_metadata_only_and_writes_central_report(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    hub.mkdir()
    for rel in (
        "registry/asset-recognition-methodology.json",
    ):
        source = ROOT / rel
        target = hub / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    (repo / "schemas").mkdir(parents=True)
    (repo / "schemas" / "asset.schema.json").write_text('{"secret":"do-not-copy"}', encoding="utf-8")
    (repo / ".env").write_text("AWS_SECRET_ACCESS_KEY=do-not-copy", encoding="utf-8")

    result = scout_asset_candidates(hub, repo, task="schema registry asset recognition")
    payload = result["asset_candidates"]

    assert payload["candidate_count"] >= 1
    assert payload["candidates"][0]["source_policy"].startswith("path-and-metadata-only")
    assert "do-not-copy" not in json.dumps(payload)
    assert all(".env" not in item["path"] for item in payload["candidates"])
    assert Path(result["path"]).parent == hub / "processed" / "reports"
    assert Path(result["path"]).name.startswith("asset-recognition-repo-")
    assert not (repo / "processed").exists()


def test_asset_scout_report_paths_do_not_collide_for_same_basename(tmp_path: Path):
    hub = tmp_path / "hub"
    repo_a = tmp_path / "a" / "repo"
    repo_b = tmp_path / "b" / "repo"
    hub.mkdir()
    for rel in ("registry/asset-recognition-methodology.json",):
        source = ROOT / rel
        target = hub / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    for repo in (repo_a, repo_b):
        repo.mkdir(parents=True)
        (repo / "AGENTS.md").write_text("rules", encoding="utf-8")

    first = scout_asset_candidates(hub, repo_a)
    second = scout_asset_candidates(hub, repo_b)

    assert first["path"] != second["path"]
    assert Path(first["path"]).is_file()
    assert Path(second["path"]).is_file()


def test_harness_discovery_is_candidate_only_and_recommends_existing_harness(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    repo = _context_repo(tmp_path)
    hub.mkdir()
    for rel in (
        "registry/harness-discovery-methodology.json",
        "registry/coding-harness-registry.json",
    ):
        source = ROOT / rel
        target = hub / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    result = discover_harness_opportunities(
        hub,
        repo,
        task="slow pytest rust shadow parity and governance safety",
    )
    discovery = result["discovery"]

    assert discovery["opportunity_count"] >= 1
    assert discovery["authority_boundary"].startswith("This DAD report is central candidate")
    assert any(
        item["recommended_action"] == "evaluate_existing_harness"
        for item in discovery["opportunities"]
    )
    assert all(item["review_status"] == "candidate" for item in discovery["opportunities"])
    assert Path(result["path"]).parent == hub / "processed" / "harnesses"
    assert Path(result["path"]).name.startswith("discovery-repo-")
    assert not (repo / "processed").exists()
