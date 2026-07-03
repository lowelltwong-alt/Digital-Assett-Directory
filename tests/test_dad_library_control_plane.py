from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from jsonschema.validators import validator_for
import pytest

from digital_asset_directory.config import EnrollmentRepoPolicy, MailRepoPolicy
from digital_asset_directory.dad_library import (
    build_dad_cadence_plan,
    calibration_report,
    check_offering_novelty,
    compile_context_pack,
    discover_harness_opportunities,
    harness_evaluate,
    load_asset_patterns,
    load_asset_recognition_methodology,
    load_harness_discovery_methodology,
    load_harnesses,
    load_needs,
    load_offerings,
    load_usefulness_methodology,
    match_asset_patterns,
    match_repo_offerings,
    recommend_harnesses,
    reconcile_repo_inventory,
    record_usage,
    record_trace_outcomes,
    scout_asset_candidates,
    score_offering,
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


def test_best_case_usefulness_score_can_reach_use_now(tmp_path: Path):
    repo = _context_repo(tmp_path)
    context = json.loads((repo / ".digital-asset" / "context-map.json").read_text())[
        "context_dimensions"
    ]
    methodology = load_usefulness_methodology(ROOT)
    offering = {
        "offering_id": "dad:offering:test",
        "name": "Perfect test harness",
        "offering_type": "harness",
        "path": "assets/coding-harnesses/python-test-performance-orchestration",
        "languages": ["python", "rust"],
        "repo_types": ["application", "library", "control_plane"],
        "domains": ["software_engineering", "test_performance"],
        "context_tags": ["pytest", "test_parity", "rust_shadow", "performance"],
        "task_types": ["slow", "pytest", "rust", "shadow", "parity", "timing"],
        "capabilities": ["slow", "pytest", "rust", "shadow", "parity", "timing"],
        "public_safe": True,
        "review_status": "reviewed",
    }

    result = score_offering(context, offering, methodology, task="slow pytest rust shadow parity timing")

    assert result["decision"] == "use_now"
    assert result["usefulness_score"] >= methodology["thresholds"]["use_now"]


def test_adding_declared_repo_type_does_not_lower_score(tmp_path: Path):
    repo = _context_repo(tmp_path)
    context = json.loads((repo / ".digital-asset" / "context-map.json").read_text())[
        "context_dimensions"
    ]
    methodology = load_usefulness_methodology(ROOT)
    base = {
        "offering_id": "dad:offering:test",
        "name": "Directional coverage test",
        "offering_type": "asset",
        "path": "assets/ai-engineering-preflight",
        "languages": ["python"],
        "repo_types": ["application"],
        "domains": ["software_engineering"],
        "context_tags": ["pytest"],
        "task_types": ["testing"],
        "capabilities": ["testing"],
        "public_safe": True,
        "review_status": "reviewed",
    }
    broader = {**base, "repo_types": ["application", "library", "template_repo"]}

    base_score = score_offering(context, base, methodology, task="testing")["usefulness_score"]
    broader_score = score_offering(context, broader, methodology, task="testing")[
        "usefulness_score"
    ]

    assert broader_score >= base_score


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


def test_usage_upgrades_match_stable_repo_id_after_repo_move(tmp_path: Path):
    hub = tmp_path / "hub"
    old_repo = tmp_path / "old" / "repo"
    new_repo = tmp_path / "new" / "renamed-repo"
    hub.mkdir()
    old_repo.mkdir(parents=True)
    new_repo.mkdir(parents=True)
    for rel in ("registry/dad-offerings-registry.json",):
        target = hub / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    old_policy = MailRepoPolicy(id="stable-repo", path=old_repo, alias="repo")
    new_policy = MailRepoPolicy(id="stable-repo", path=new_repo, alias="renamed-repo")
    record_usage(
        hub,
        old_repo,
        asset_id="dad:offering:rust-shadow-parity-harness",
        status="watching",
        recorded_by="unit-test",
        mail_policies=[old_policy],
    )

    upgrades = usage_upgrades(hub, new_repo, mail_policies=[new_policy])

    assert upgrades["upgrade_count"] == 1


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


def test_asset_scout_importance_tier_is_independent_of_task_wording(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    hub.mkdir()
    (hub / "registry").mkdir()
    (hub / "registry" / "asset-recognition-methodology.json").write_text(
        (ROOT / "registry" / "asset-recognition-methodology.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "utils.py").write_text("VALUE = 1\n", encoding="utf-8")

    quiet = scout_asset_candidates(hub, repo, task="quiet task", max_files=10)
    noisy = scout_asset_candidates(
        hub,
        repo,
        task="source truth governance agent skill preflight harness prompt review test eval parity performance validation",
        max_files=10,
    )

    quiet_by_path = {item["path"]: item for item in quiet["asset_candidates"]["candidates"]}
    noisy_by_path = {item["path"]: item for item in noisy["asset_candidates"]["candidates"]}
    for path in quiet_by_path.keys() & noisy_by_path.keys():
        assert noisy_by_path[path]["file_importance"] == quiet_by_path[path]["file_importance"]
        assert noisy_by_path[path]["importance_tier"] == quiet_by_path[path]["importance_tier"]
    assert noisy["asset_candidates"]["methodology_hash"].startswith("sha256:")


def test_readme_only_harness_note_stays_below_candidate_cutoff(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    hub.mkdir()
    (hub / "registry").mkdir()
    (hub / "registry" / "asset-recognition-methodology.json").write_text(
        (ROOT / "registry" / "asset-recognition-methodology.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    path = repo / "assets" / "coding-harnesses" / "demo" / "tests-or-evals"
    path.mkdir(parents=True)
    (path / "README.md").write_text("notes", encoding="utf-8")

    result = scout_asset_candidates(hub, repo, task="harness tests eval performance", max_files=10)

    assert not any(
        item["path"].endswith("tests-or-evals/README.md")
        for item in result["asset_candidates"]["candidates"]
    )


def test_context_pack_trace_and_calibration_round_trip(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = _context_repo(tmp_path)
    hub.mkdir(exist_ok=True)
    for rel in (
        "registry/non-negotiables.json",
        "registry/dad-offerings-registry.json",
        "registry/dad-usefulness-methodology.json",
    ):
        target = hub / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")

    pack = compile_context_pack(
        hub,
        repo,
        session_id="dad:session:test",
        task="slow pytest rust parity",
        mail_digest_status={"stale": False},
    )
    record_trace_outcomes(
        hub,
        trace_id=pack["trace_id"],
        session_id="dad:session:test",
        outcomes={"used": [pack["assets"][0]["asset_id"]], "ignored": [], "attempted_failed": [], "harmful": []},
        summary="used recommendation",
    )
    report = calibration_report(hub)

    assert len(pack["non_negotiables"]) <= 10
    assert len(pack["assets"]) <= 5
    assert (hub / "processed" / "usage" / "decision-traces.jsonl").exists()
    assert report["outcome_count"] == 1
    assert report["decision_rows"][0]["percentages_available"] is False


def test_context_pack_delivers_matched_asset_patterns(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = _context_repo(tmp_path)
    hub.mkdir(exist_ok=True)
    for rel in (
        "registry/non-negotiables.json",
        "registry/dad-offerings-registry.json",
        "registry/dad-usefulness-methodology.json",
        "registry/asset-pattern-registry.json",
    ):
        target = hub / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")

    pack = compile_context_pack(
        hub,
        repo,
        session_id="dad:session:test-patterns",
        task="build knowledge graph retrieval and context pack indexes for agents",
        mail_digest_status={"stale": False},
    )
    _validate("context_pack", pack)

    registry_version = load_asset_patterns(hub)["registry_version"]
    assert pack["pattern_library_version"] == registry_version
    assert "asset_pattern_registry" in pack["registry_hashes"]
    assert 1 <= len(pack["asset_patterns"]) <= 3
    for item in pack["asset_patterns"]:
        assert item["report_via"] == "dad:need:asset-pattern-sightings"
        assert item["matched_terms"]
        assert len(item["watch_for"]) <= 4
    trace_rows = [
        json.loads(line)
        for line in (hub / "processed" / "usage" / "decision-traces.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    pattern_trace = next(
        row for row in trace_rows if row.get("session_id") == "dad:session:test-patterns"
    )
    assert pattern_trace["recommended_patterns"] == [
        item["pattern_id"] for item in pack["asset_patterns"]
    ]


def test_match_asset_patterns_is_deterministic_and_fails_soft(tmp_path: Path):
    repo = _context_repo(tmp_path)
    first = match_asset_patterns(
        ROOT, task="governed learning loop lessons and handoffs", repo=repo
    )
    second = match_asset_patterns(
        ROOT, task="governed learning loop lessons and handoffs", repo=repo
    )
    assert first["matches"] == second["matches"]
    assert first["match_basis"]
    assert [item["pattern_id"] for item in first["matches"]][0] == "governed_learning_loop_system"

    empty_repo = tmp_path / "empty-repo"
    empty_repo.mkdir()
    no_context = match_asset_patterns(ROOT, task="", repo=empty_repo)
    assert no_context["matches"] == []
    assert no_context["pattern_count"] >= 1

    missing_hub = tmp_path / "missing-hub"
    missing_hub.mkdir()
    pack = compile_context_pack(
        missing_hub,
        repo,
        session_id="dad:session:test-missing-patterns",
        task="anything",
        mail_digest_status={"stale": False},
    )
    assert pack["asset_patterns"] == []
    assert any("asset pattern registry unavailable" in warning for warning in pack["warnings"])


def test_prepopulated_coding_assets_are_wellformed_and_surface_in_matching(tmp_path: Path):
    idioms = json.loads((ROOT / "assets" / "python-underused-idioms" / "idioms.json").read_text(encoding="utf-8"))
    idiom_ids = [item["id"] for group in idioms["groups"] for item in group["idioms"]]
    assert len(idiom_ids) == len(set(idiom_ids))
    assert len(idiom_ids) >= 30
    for group in idioms["groups"]:
        for item in group["idioms"]:
            for field in ("construct", "min_python", "what", "use_when", "avoid_when", "ai_note", "example"):
                assert item[field], f"{item['id']} missing {field}"
    python_frontier_sources = {item["source_id"] for item in idioms["frontier_research_sources"]}
    assert {"python-core", "python-packaging", "astral", "pyo3"} <= python_frontier_sources

    rust = json.loads((ROOT / "assets" / "rust-buildout-guide" / "rust-buildout.json").read_text(encoding="utf-8"))
    stages = [stage["stage"] for stage in rust["python_to_rust_migration_path"]["stages"]]
    assert stages == sorted(stages)
    assert {"profile", "parity_gate", "pyo3_extension"} <= {
        stage["name"] for stage in rust["python_to_rust_migration_path"]["stages"]
    }
    rust_idiom_ids = [item["id"] for item in rust["rust_idioms_for_ai_legibility"]]
    assert len(rust_idiom_ids) == len(set(rust_idiom_ids))
    rust_frontier_sources = {item["source_id"] for item in rust["frontier_research_sources"]}
    assert {"rust-lang", "rust-community-frontier", "rust-security", "pyo3"} <= rust_frontier_sources

    repo = _context_repo(tmp_path)
    python_result = match_repo_offerings(
        ROOT, repo, task="refactor python code readability idioms review", limit=10
    )
    python_match = next(
        item
        for item in python_result["matches"]
        if item["offering_id"] == "dad:offering:python-underused-idioms"
    )
    assert python_match["needs_human_review"] is False
    assert python_match["decision"] in {"use_now", "save_for_future", "defer"}

    rust_result = match_repo_offerings(
        ROOT, repo, task="rust performance migration for a profiled python hot path", limit=10
    )
    rust_match = next(
        item
        for item in rust_result["matches"]
        if item["offering_id"] == "dad:offering:rust-buildout-guide"
    )
    assert rust_match["needs_human_review"] is False
    assert rust_match["decision"] in {"use_now", "save_for_future", "defer"}


def test_check_offering_novelty_classifies_duplicate_upgrade_and_new():
    same_path_same_version = check_offering_novelty(
        ROOT,
        name="Python Underused Idioms AI Coding Card",
        path="assets/python-underused-idioms",
        version="0.1.0",
    )
    assert same_path_same_version["verdict"] == "duplicate"

    same_path_new_version = check_offering_novelty(
        ROOT,
        name="Python Underused Idioms AI Coding Card v2",
        path="assets/python-underused-idioms",
        version="0.2.0",
    )
    assert same_path_new_version["verdict"] == "upgrade_candidate"

    similar_name_same_caps = check_offering_novelty(
        ROOT,
        name="Underused Python Idioms Coding Card",
        capabilities=["idiom_card", "underused_stdlib_guidance"],
    )
    assert similar_name_same_caps["verdict"] == "possible_duplicate"

    similar_name_new_caps = check_offering_novelty(
        ROOT,
        name="Python Underused Idioms AI Coding Card",
        capabilities=["idiom_card", "notebook_linting"],
    )
    assert similar_name_new_caps["verdict"] == "possible_upgrade"
    assert "notebook" in similar_name_new_caps["matches"][0]["new_capabilities"]

    novel = check_offering_novelty(
        ROOT,
        name="Completely Unrelated Terraform Module Vault",
        capabilities=["terraform_modules"],
    )
    assert novel["verdict"] == "new"
    assert novel["matches"] == []
    for result in (same_path_same_version, similar_name_new_caps, novel):
        assert result["check_basis"]
        assert result["next_steps"]


def test_context_pack_caps_and_reports_deferred_mail(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = _context_repo(tmp_path)
    hub.mkdir(exist_ok=True)
    for rel in (
        "registry/non-negotiables.json",
        "registry/dad-offerings-registry.json",
        "registry/dad-usefulness-methodology.json",
        "registry/asset-pattern-registry.json",
    ):
        target = hub / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    deferred_items = [
        {
            "mail_id": f"dad:mail:test-{index}",
            "message_type": "asset_suggestion",
            "summary": "deferred suggestion",
            "intake_decision": "save_for_future",
            "matched_terms": ["parity"],
            "repo_watches_asset": False,
            "source_asset_refs": [],
            "why_now": "previously deferred mail matches the current task context",
        }
        for index in range(5)
    ]
    pack = compile_context_pack(
        hub,
        repo,
        session_id="dad:session:test-deferred",
        task="rust parity",
        mail_digest_status={"stale": False},
        deferred_mail={"items": deferred_items, "match_basis": "test basis", "deferred_total": 7},
    )
    _validate("context_pack", pack)
    assert len(pack["deferred_mail"]) == 3
    assert pack["deferred_backlog_count"] == 7
    assert pack["deferred_mail_basis"] == "test basis"
    assert any("deferred mail" in warning for warning in pack["warnings"])
    trace_rows = [
        json.loads(line)
        for line in (hub / "processed" / "usage" / "decision-traces.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    trace = next(row for row in trace_rows if row.get("session_id") == "dad:session:test-deferred")
    assert trace["resurfaced_mail"] == [item["mail_id"] for item in pack["deferred_mail"]]


def test_harness_evaluate_executes_commands_and_records_failure(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()
    harness_dir = hub / "assets" / "coding-harnesses" / "failing"
    harness_dir.mkdir(parents=True)
    registry = {
        "schema_version": "0.1.0",
        "harnesses": [
            {
                "harness_id": "dad:harness:failing",
                "name": "Failing Harness",
                "version": "0.1.0",
                "family": "test",
                "path": "assets/coding-harnesses/failing",
                "languages": ["python"],
                "repo_types": ["application"],
                "domains": ["software_engineering"],
                "context_tags": ["test"],
                "task_types": ["test"],
                "capabilities": ["test"],
                "validation_commands": ["python -c \"import sys; sys.exit(7)\""],
                "review_status": "candidate",
                "public_safe": True,
                "research_questions": [],
                "source_evidence": [],
                "authority_boundary": "test",
            }
        ],
    }
    for rel in (
        "registry/dad-usefulness-methodology.json",
        "registry/dad-offerings-registry.json",
    ):
        target = hub / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    (hub / "registry" / "coding-harness-registry.json").write_text(
        json.dumps(registry),
        encoding="utf-8",
    )

    result = harness_evaluate(hub, "dad:harness:failing", repo)

    assert result["evaluation"]["evaluation_status"] == "failed"
    assert result["evaluation"]["command_results"][0]["exit_code"] == 7
    rows = (hub / "processed" / "usage" / "harness-outcomes.jsonl").read_text(encoding="utf-8")
    assert "candidate_only" not in rows


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
