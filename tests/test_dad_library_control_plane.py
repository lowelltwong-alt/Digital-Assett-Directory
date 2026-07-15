from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from jsonschema.validators import validator_for
import pytest
from typer.testing import CliRunner

from digital_asset_directory.cli import app
from digital_asset_directory.config import EnrollmentRepoPolicy, MailRepoPolicy, load_config
from digital_asset_directory.dad_library import (
    build_dad_cadence_plan,
    calibration_report,
    check_offering_novelty,
    collect_repo_local_assets,
    compile_context_pack,
    discover_harness_opportunities,
    harness_evaluate,
    load_address_model_registry,
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
    repo_local_asset_surface_standard,
    scout_asset_candidates,
    score_offering,
    usage_upgrades,
    write_repo_inventory_rust_probe_parity,
)

RUNNER = CliRunner()

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def _write_minimal_hub_markers(hub: Path) -> None:
    (hub / "registry").mkdir(parents=True, exist_ok=True)
    (hub / "registry" / "source-of-truth.json").write_text("{}\n", encoding="utf-8")
    (hub / "src" / "digital_asset_directory").mkdir(parents=True, exist_ok=True)
    (hub / "src" / "digital_asset_directory" / "cli.py").write_text("", encoding="utf-8")
    (hub / "AI_FRONT_DOOR.md").write_text("# AI Front Door\n", encoding="utf-8")
    (hub / "MACHINE_NAVIGATION_MANIFEST.json").write_text(
        '{"manifest_version":"test"}\n', encoding="utf-8"
    )
    (hub / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "digital-asset-directory"',
                'version = "0.1.0"',
                "[project.scripts]",
                'asset-dir = "digital_asset_directory.cli:app"',
                "",
            ]
        ),
        encoding="utf-8",
    )


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
    _validate("dad_address_model_registry", load_address_model_registry(ROOT))
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


def test_every_offering_declares_validation_owner_and_adoption_contract():
    offerings = load_offerings(ROOT)["offerings"]

    assert len(offerings) == 17
    for offering in offerings:
        assert offering["validation_refs"]
        assert all((ROOT / ref).exists() for ref in offering["validation_refs"])
        assert offering["owner_authority"].strip()
        assert offering["adoption_semantics"].strip()
        assert any(
            term in offering["adoption_semantics"].lower()
            for term in ("candidate", "pointer", "requires", "cannot", "no ")
        )


def test_harness_vs_enforcement_decision_model_is_cataloged():
    offerings = load_offerings(ROOT)["offerings"]
    needs = load_needs(ROOT)["needs"]

    offering = next(
        item
        for item in offerings
        if item["offering_id"] == "dad:offering:harness-vs-deterministic-enforcement"
    )
    need = next(
        item
        for item in needs
        if item["need_id"] == "dad:need:harness-enforcement-tradeoff-feedback"
    )

    assert offering["path"] == "docs/HARNESS_VS_DETERMINISTIC_ENFORCEMENT.md"
    assert offering["review_status"] == "reviewed"
    assert "harness_first_decision_model" in offering["capabilities"]
    assert "red_amber_green_data_sensitivity_routing" in offering["capabilities"]
    assert need["priority"] == "critical"
    assert "coding_harnesses" in need["target_control_planes"]


def test_claude_architectural_root_cause_review_is_cataloged():
    offerings = load_offerings(ROOT)["offerings"]
    needs = load_needs(ROOT)["needs"]

    offering = next(
        item
        for item in offerings
        if item["offering_id"] == "dad:offering:claude-architectural-root-cause-review"
    )
    need = next(
        item
        for item in needs
        if item["need_id"] == "dad:need:integration-implementation-root-cause-patterns"
    )

    assert offering["path"] == "docs/CLAUDE_ARCHITECTURAL_ROOT_CAUSE_REVIEW.md"
    assert offering["review_status"] == "reviewed"
    assert "claude_review_packet" in offering["capabilities"]
    assert "architectural_root_cause_questions" in offering["capabilities"]
    assert need["priority"] == "critical"
    assert "architecture_references" in need["target_control_planes"]


def test_address_model_is_compact_nine_layer_learning_model():
    registry = load_address_model_registry(ROOT)
    standard = repo_local_asset_surface_standard()

    assert registry["adopted_layer_count"] == 9
    assert registry["layers"][8]["name"] == "learning_adaptation"
    assert registry["layers"][8]["status"] == "dad_adopted"
    assert registry["compact_encoding"]["max_inline_summary_chars"] <= 400
    assert "workflow_card_fields" in registry["workflow_encoding_policy"]
    assert "full prompts" in registry["workflow_encoding_policy"]["do_not_inline"]
    assert registry["evolution_policy"]["status"] == "evolving"
    assert "frontier ai" in " ".join(registry["frontier_review_policy"]["who_to_ask"]).lower()
    assert standard["adopted_layer_count"] == 9
    assert standard["dad_layer_9"]["name"] == "learning_adaptation"
    assert standard["address_model_ref"] == "registry/dad-address-model-registry.json"


def test_repo_local_asset_record_schema_allows_compact_refs():
    payload = {
        "schema_version": "0.1.0",
        "asset_id": "repo:asset:nine-layer-address",
        "asset_type": "architecture_reference",
        "title": "Nine-layer address card",
        "summary": "Compact address-model pointer for repo-local asset memory.",
        "source_paths": ["docs/address-model.md"],
        "tags": ["address_model"],
        "context_tags": ["learning_loop", "repo_local_asset_memory"],
        "graph_tags": ["nine_layer_address", "learning_adaptation"],
        "applies_when": ["A future agent needs compact placement."],
        "does_not_apply_when": ["A one-off note has no reuse value."],
        "novelty_claim": "Keeps learning outcomes separate from object identity.",
        "usefulness_context": "Useful for DAD lookup, validation, and upgrade routing.",
        "workflow_ref": "workflow:address-card-fill",
        "learning_ref": "learning:address-model-delta",
        "fractal_address": {
            "layer": 9,
            "layer_name": "learning_adaptation",
            "optional_layer_9_variant": "learning_adaptation",
            "address_ref": "local/source/layer/domain/module/object/id/v0.1",
        },
        "validation_commands": ["python -m digital_asset_directory.cli dad address-model"],
        "source_refs": ["registry/dad-address-model-registry.json"],
        "sensitivity": "internal",
        "review_status": "candidate",
        "authority_boundary": "Source repo candidate metadata only.",
    }

    _validate("repo_local_digital_asset_record", payload)


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


@pytest.mark.parametrize(
    ("task", "expected_first"),
    [
        (
            "coding preflight profile test plan",
            "dad:offering:ai-engineering-preflight",
        ),
        (
            "governance review deterministic enforcement risk authority",
            "dad:offering:harness-vs-deterministic-enforcement",
        ),
        (
            "mail delivery protected repository dirty spool safety",
            "dad:offering:repo-enrollment-mail-governance-safety-harness",
        ),
        (
            "Rust performance migration profiling parity",
            "dad:offering:rust-buildout-guide",
        ),
        (
            "repository enrollment protected repo mail governance",
            "dad:offering:repo-enrollment-mail-governance-safety-harness",
        ),
    ],
)
def test_golden_task_routes_specific_guidance_before_generic_rust(
    tmp_path: Path, task: str, expected_first: str
):
    repo = _context_repo(tmp_path)

    result = match_repo_offerings(ROOT, repo, task=task, limit=5)

    assert result["matches"][0]["offering_id"] == expected_first
    assert result["matches"][0]["route_specificity"] > 0
    assert "not proof" in result["routing_basis"]


def test_usage_can_explicitly_record_dependency_without_inferring_it(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    repo = _context_repo(tmp_path)
    policy = MailRepoPolicy(id="repo", path=repo, alias="repo")

    result = record_usage(
        hub,
        repo,
        asset_id="dad:offering:ai-engineering-preflight",
        status="depends_on",
        dependency_basis="explicit_repo_record",
        recorded_by="unit-test",
        source_ref="repo://repo/.digital-asset/dad-usage.jsonl",
        mail_policies=[policy],
    )

    _validate("repo_asset_usage", result["usage"])
    assert result["usage"]["status"] == "depends_on"
    assert result["usage"]["dependency_basis"] == "explicit_repo_record"

    candidate = record_usage(
        hub,
        repo,
        asset_id="dad:offering:ai-engineering-preflight",
        status="dependency_candidate",
        dependency_basis="imported_candidate",
        recorded_by="unit-test",
        mail_policies=[policy],
    )
    _validate("repo_asset_usage", candidate["usage"])
    assert candidate["usage"]["status"] == "dependency_candidate"
    assert candidate["usage"]["usage_id"] != result["usage"]["usage_id"]


def test_usage_dependency_requires_explicit_basis(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    repo = _context_repo(tmp_path)

    with pytest.raises(ValueError, match="requires dependency_basis"):
        record_usage(
            hub,
            repo,
            asset_id="dad:offering:ai-engineering-preflight",
            status="depends_on",
            recorded_by="unit-test",
        )


def test_usage_record_cli_forwards_confirmed_dependency_basis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()
    monkeypatch.setattr(
        "digital_asset_directory.cli._cfg",
        lambda hub=None: SimpleNamespace(repo_root=hub, mail_repos=[], enrollment_repos=[]),
    )

    result = RUNNER.invoke(
        app,
        [
            "usage",
            "record",
            "--hub",
            str(hub),
            "--repo",
            str(repo),
            "--asset",
            "dad:offering:ai-engineering-preflight",
            "--status",
            "depends_on",
            "--dependency-basis",
            "human_reviewed",
            "--recorded-by",
            "Lowell",
            "--adoption-id",
            "review:phase-11-test",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["usage"]["status"] == "depends_on"
    assert payload["usage"]["dependency_basis"] == "human_reviewed"


def test_usage_record_cli_fails_closed_without_dependency_basis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()
    monkeypatch.setattr(
        "digital_asset_directory.cli._cfg",
        lambda hub=None: SimpleNamespace(repo_root=hub, mail_repos=[], enrollment_repos=[]),
    )

    result = RUNNER.invoke(
        app,
        [
            "usage",
            "record",
            "--hub",
            str(hub),
            "--repo",
            str(repo),
            "--asset",
            "dad:offering:ai-engineering-preflight",
            "--status",
            "depends_on",
        ],
    )

    assert result.exit_code == 2
    assert "requires dependency_basis" in result.output


def test_confirmed_dependency_bases_require_authority_evidence(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()

    with pytest.raises(ValueError, match="nonempty source_ref"):
        record_usage(
            hub,
            repo,
            asset_id="dad:offering:ai-engineering-preflight",
            status="depends_on",
            dependency_basis="explicit_repo_record",
            recorded_by="unit-test",
        )
    with pytest.raises(ValueError, match="named non-generic reviewer"):
        record_usage(
            hub,
            repo,
            asset_id="dad:offering:ai-engineering-preflight",
            status="depends_on",
            dependency_basis="human_reviewed",
            recorded_by="unknown",
            adoption_id="review:test",
        )
    with pytest.raises(ValueError, match="named non-generic reviewer"):
        record_usage(
            hub,
            repo,
            asset_id="dad:offering:ai-engineering-preflight",
            status="depends_on",
            dependency_basis="human_reviewed",
            recorded_by="human",
            adoption_id="review:test",
        )
    with pytest.raises(ValueError, match="adoption_id or source_ref"):
        record_usage(
            hub,
            repo,
            asset_id="dad:offering:ai-engineering-preflight",
            status="depends_on",
            dependency_basis="human_reviewed",
            recorded_by="Lowell",
        )


def test_distinct_human_dependency_review_pointers_have_distinct_usage_ids(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()

    first = record_usage(
        hub,
        repo,
        asset_id="dad:offering:ai-engineering-preflight",
        status="depends_on",
        dependency_basis="human_reviewed",
        recorded_by="Lowell",
        adoption_id="review:first",
    )
    second = record_usage(
        hub,
        repo,
        asset_id="dad:offering:ai-engineering-preflight",
        status="depends_on",
        dependency_basis="human_reviewed",
        recorded_by="Lowell",
        adoption_id="review:second",
    )

    assert first["usage"]["usage_id"] != second["usage"]["usage_id"]


def test_usage_record_cli_rejects_unbound_human_review_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()
    monkeypatch.setattr(
        "digital_asset_directory.cli._cfg",
        lambda hub=None: SimpleNamespace(repo_root=hub, mail_repos=[], enrollment_repos=[]),
    )

    result = RUNNER.invoke(
        app,
        [
            "usage",
            "record",
            "--hub",
            str(hub),
            "--repo",
            str(repo),
            "--asset",
            "dad:offering:ai-engineering-preflight",
            "--status",
            "depends_on",
            "--dependency-basis",
            "human_reviewed",
        ],
    )

    assert result.exit_code == 2
    assert "named non-generic reviewer" in result.output


@pytest.mark.parametrize(
    ("task", "expected_first"),
    [
        (
            "review our enrollment rules before adding this repository",
            "dad:offering:repo-enrollment-mail-governance-safety-harness",
        ),
        (
            "design authority and governance controls",
            "dad:offering:harness-vs-deterministic-enforcement",
        ),
        (
            "profile slow Python parser before considering Rust",
            "dad:offering:rust-buildout-guide",
        ),
        (
            "write Python feature and tests",
            "dad:offering:ai-engineering-preflight",
        ),
    ],
)
def test_task_family_routing_handles_paraphrases_and_negative_case(
    tmp_path: Path, task: str, expected_first: str
):
    repo = _context_repo(tmp_path)

    result = match_repo_offerings(ROOT, repo, task=task, limit=5)

    assert result["matches"][0]["offering_id"] == expected_first
    assert result["matches"][0]["route_intent_matches"]


def test_declared_multi_intent_precedence_prefers_enrollment_safety(tmp_path: Path):
    repo = _context_repo(tmp_path)

    result = match_repo_offerings(
        ROOT,
        repo,
        task="code governance mail controls for repository enrollment",
        limit=5,
    )

    assert load_usefulness_methodology(ROOT)["intent_priority"] == [
        "enrollment",
        "mail",
        "rust",
        "governance",
        "coding",
    ]
    assert (
        result["matches"][0]["offering_id"]
        == "dad:offering:repo-enrollment-mail-governance-safety-harness"
    )
    assert "['enrollment', 'mail', 'rust', 'governance', 'coding']" in result["routing_basis"]


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


def test_harness_recommend_routes_language_frontier_research(tmp_path: Path):
    repo = _context_repo(tmp_path)

    result = recommend_harnesses(
        ROOT,
        repo,
        task="python rust language frontier underused compiler typing fuzz tooling research",
        limit=5,
    )

    ids = [item["harness_id"] for item in result["recommendations"]]
    assert "dad:harness:language-frontier-research" in ids
    match = next(
        item
        for item in result["recommendations"]
        if item["harness_id"] == "dad:harness:language-frontier-research"
    )
    assert match["decision"] in {"save_for_future", "needs_human_review", "use_now"}
    assert match["methodology_id"] == "dad-usefulness-methodology-v0.1"


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


def _rust_repo_probe_summary(
    repos: list[dict[str, object]],
    *,
    root_alias: str = "dad-local-source/workspace",
    skipped_dirs: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    skipped_dirs = skipped_dirs or []
    repos = [_rust_repo_probe_record_with_defaults(repo) for repo in repos]
    return {
        "schema_version": "dad_repo_inventory_probe.v0_2",
        "root_count": 1,
        "repo_count": len(repos),
        "skipped_dir_count": len(skipped_dirs),
        "roots": [
            {
                "root_alias": root_alias,
                "status": "checked",
                "repo_count": len(repos),
                "skipped_dir_count": len(skipped_dirs),
            }
        ],
        "repos": repos,
        "skipped_dirs": skipped_dirs,
        "no_mutation_performed": True,
        "authority_boundary": "Rust repo-inventory probing is read-only structural evidence.",
    }


def _rust_repo_probe_record_with_defaults(record: dict[str, object]) -> dict[str, object]:
    if "contract_present" not in record:
        return record
    contract_present = bool(record["contract_present"])
    contract_structural_pass = bool(record.get("contract_structural_pass", False))
    if contract_structural_pass:
        default_issue_codes: list[str] = []
    elif contract_present:
        default_issue_codes = ["contract_missing_schema_version"]
    else:
        default_issue_codes = ["contract_missing"]
    defaults: dict[str, object] = {
        "contract_parse_status": "present_parseable" if contract_present else "missing",
        "contract_schema_version_present": contract_structural_pass,
        "contract_repo_id_present": contract_structural_pass,
        "contract_capture_surface_version_present": contract_structural_pass,
        "contract_cli_fallback_present": contract_structural_pass,
        "contract_stable_user_shim_present": contract_structural_pass,
        "contract_windows_user_shim_present": contract_structural_pass,
        "contract_raw_checkout_fallback_present": contract_structural_pass,
        "contract_stable_shim_before_raw_checkout": contract_structural_pass,
        "contract_structural_pass": contract_structural_pass,
        "contract_issue_codes": default_issue_codes,
    }
    return {**defaults, **record}


def _real_git_repo(path: Path, *, branch: str = "main") -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-b", branch], cwd=path, check=True, capture_output=True)
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
    assert "input_hashes" in result["inventory"]
    assert (
        "src/digital_asset_directory/dad_library.py"
        in result["inventory"]["input_hashes"]
        or result["inventory"]["input_hashes"] == {}
    )
    for repo in [logos, mocktrial, intake, duplicate]:
        assert not (repo / ".digital-asset").exists()


def test_inventory_duplicate_markers_ignore_ancestor_temp_container(tmp_path: Path):
    hub = tmp_path / "hub"
    workspace = tmp_path / "temp-harness-root" / "workspace"
    repo = _git_repo(workspace / "ordinary-repo")
    duplicate = _git_repo(workspace / "repos" / "copy")
    hub.mkdir()
    source = SimpleNamespace(
        id="workspace",
        path=workspace,
        enabled=True,
        follow_symlinks=False,
    )

    result = reconcile_repo_inventory(hub, local_sources=[source], max_depth=3)
    records = {record["repo_name"]: record for record in result["inventory"]["records"]}

    assert records[repo.name]["classification"] == "needs-human-classification"
    assert records[duplicate.name]["classification"] == "duplicate-ignore"


def test_inventory_report_id_changes_for_same_count_content_change(tmp_path: Path):
    hub = tmp_path / "hub"
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    hub.mkdir()
    workspace_a.mkdir()
    workspace_b.mkdir()
    _git_repo(workspace_a / "alpha-repo")
    _git_repo(workspace_b / "beta-repo")
    source_a = SimpleNamespace(
        id="workspace-a",
        path=workspace_a,
        enabled=True,
        follow_symlinks=False,
    )
    source_b = SimpleNamespace(
        id="workspace-b",
        path=workspace_b,
        enabled=True,
        follow_symlinks=False,
    )

    first = reconcile_repo_inventory(hub, local_sources=[source_a], max_depth=2)["inventory"]
    second = reconcile_repo_inventory(hub, local_sources=[source_b], max_depth=2)["inventory"]

    assert first["repo_count"] == second["repo_count"] == 1
    assert first["records"][0]["repo_name"] == "alpha-repo"
    assert second["records"][0]["repo_name"] == "beta-repo"
    assert first["content_fingerprint"].startswith("sha256:")
    assert second["content_fingerprint"].startswith("sha256:")
    assert first["content_fingerprint"] != second["content_fingerprint"]
    assert first["report_id"] != second["report_id"]


def test_inventory_active_hold_is_active_no_write_but_logos_stays_protected(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    held = _git_repo(tmp_path / "active-repo")
    logos = _git_repo(tmp_path / "logos-scripture-graph")
    hub.mkdir()
    held_policy = EnrollmentRepoPolicy(
        id="active-repo",
        path=held,
        alias="active",
        visibility="internal",
        enrollment_enabled=True,
        active_hold=True,
        active_hold_reason="actively being worked on",
    )
    logos_policy = EnrollmentRepoPolicy(
        id="logos-scripture-graph",
        path=logos,
        alias="logos",
        visibility="public",
        public_facing=True,
        enrollment_enabled=True,
        active_hold=True,
    )

    result = reconcile_repo_inventory(
        hub,
        enrollment_policies=[held_policy, logos_policy],
        max_depth=1,
    )
    records = {record["repo_name"]: record for record in result["inventory"]["records"]}

    assert records[held.name]["classification"] == "active-no-write"
    assert records[held.name]["write_boundary"] == "central_only"
    assert "active_hold" in "; ".join(records[held.name]["classification_reasons"])
    assert records[logos.name]["classification"] == "protected-central-only"


def test_inventory_enrollment_hold_wins_when_mail_policy_also_matches(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = _git_repo(tmp_path / "active-repo")
    hub.mkdir()
    mail_policy = MailRepoPolicy(
        id="active-mail",
        path=repo,
        alias="active",
        visibility="internal",
    )
    enrollment_policy = EnrollmentRepoPolicy(
        id="active-enrollment",
        path=repo,
        alias="active",
        visibility="internal",
        enrollment_enabled=True,
        active_hold=True,
        active_hold_reason="actively being worked on",
    )

    result = reconcile_repo_inventory(
        hub,
        mail_policies=[mail_policy],
        enrollment_policies=[enrollment_policy],
        max_depth=1,
    )
    record = result["inventory"]["records"][0]

    assert record["repo_id"] == "active-enrollment"
    assert record["classification"] == "active-no-write"
    assert "active_hold" in "; ".join(record["classification_reasons"])
    assert record["mail_policy_present"] is True
    assert record["enrollment_policy_present"] is True


def test_inventory_dirty_or_non_main_policy_repo_is_active_no_write(tmp_path: Path):
    hub = tmp_path / "hub"
    dirty = _real_git_repo(tmp_path / "dirty-repo")
    feature = _real_git_repo(tmp_path / "feature-repo", branch="feature/inventory")
    hub.mkdir()
    (dirty / "untracked.txt").write_text("work in progress", encoding="utf-8")
    policies = [
        EnrollmentRepoPolicy(
            id="dirty-repo",
            path=dirty,
            alias="dirty",
            visibility="internal",
            enrollment_enabled=True,
        ),
        EnrollmentRepoPolicy(
            id="feature-repo",
            path=feature,
            alias="feature",
            visibility="internal",
            enrollment_enabled=True,
        ),
    ]

    result = reconcile_repo_inventory(hub, enrollment_policies=policies, max_depth=1)
    records = {record["repo_name"]: record for record in result["inventory"]["records"]}

    assert records[dirty.name]["classification"] == "active-no-write"
    assert "dirty_worktree" in "; ".join(records[dirty.name]["classification_reasons"])
    assert records[dirty.name]["git_state"]["is_dirty"] is True
    assert records[feature.name]["classification"] == "active-no-write"
    assert "non_main_branch" in "; ".join(records[feature.name]["classification_reasons"])
    assert records[feature.name]["git_state"]["branch_status"] == "non_main"


def test_inventory_duplicate_contract_lineage_is_not_enrolled_by_default(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    first = _git_repo(workspace / "renamed-a")
    second = _git_repo(workspace / "copied-b")
    hub.mkdir()
    for repo in (first, second):
        contract_path = repo / ".digital-asset" / "dad-integration.json"
        contract_path.parent.mkdir(parents=True)
        contract_path.write_text(
            json.dumps({"repo_id": "stable-repo-id", "repo_alias": repo.name}),
            encoding="utf-8",
        )
    local_source = SimpleNamespace(
        id="workspace",
        path=workspace,
        enabled=True,
        follow_symlinks=False,
    )

    result = reconcile_repo_inventory(hub, local_sources=[local_source], max_depth=2)
    records = {record["repo_name"]: record for record in result["inventory"]["records"]}

    assert records[first.name]["repo_id"] == "stable-repo-id"
    assert records[second.name]["repo_id"] == "stable-repo-id"
    assert records[first.name]["repo_id_source"] == "contract"
    assert records[first.name]["classification"] == "duplicate-ignore"
    assert records[second.name]["classification"] == "duplicate-ignore"
    assert records[first.name]["duplicate_lineage"] is True
    assert not (first / "processed").exists()
    assert not (second / "processed").exists()


def test_inventory_github_rows_are_central_records_without_local_writes(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    local = _git_repo(tmp_path / "workspace" / "local-repo")
    hub.mkdir()
    source = SimpleNamespace(
        id="github-lowelltwong-alt",
        owner="lowelltwong-alt",
        enabled=True,
        include_private=True,
        repositories=[
            {"name": "local-repo", "full_name": "lowelltwong-alt/local-repo", "visibility": "public"},
            {"name": "remote-only", "full_name": "lowelltwong-alt/remote-only", "private": True},
            {"name": "old-archive", "full_name": "lowelltwong-alt/old-archive", "archived": True},
        ],
    )
    local_source = SimpleNamespace(
        id="workspace",
        path=local.parent,
        enabled=True,
        follow_symlinks=False,
    )

    result = reconcile_repo_inventory(
        hub,
        local_sources=[local_source],
        github_sources=[source],
        max_depth=2,
    )
    records = {record["repo_name"]: record for record in result["inventory"]["records"]}
    github_source = result["inventory"]["github_sources"][0]

    assert github_source["inventory_status"] == "imported_repo_list"
    assert github_source["repo_count"] == 3
    assert len([record for record in result["inventory"]["records"] if record["repo_name"] == "local-repo"]) == 2
    assert records["remote-only"]["path_ref"] == "dad://github/lowelltwong-alt/remote-only"
    assert records["remote-only"]["classification"] == "needs-human-classification"
    assert records["old-archive"]["classification"] == "archive-ignore"
    assert not (local / ".digital-asset").exists()


def test_inventory_github_only_protected_logos_repo_stays_protected(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    source = SimpleNamespace(
        id="github-lowelltwong-alt",
        owner="lowelltwong-alt",
        enabled=True,
        include_private=True,
        repositories=[
            {
                "name": "logos-governance-architecture",
                "full_name": "lowelltwong-alt/logos-governance-architecture",
                "visibility": "private",
            },
        ],
    )

    result = reconcile_repo_inventory(hub, github_sources=[source], max_depth=1)
    record = result["inventory"]["records"][0]

    assert record["classification"] == "protected-central-only"
    assert record["write_boundary"] == "central_only"
    assert "protected Logos" in "; ".join(record["classification_reasons"])
    assert record["path_ref"] == "dad://github/lowelltwong-alt/logos-governance-architecture"


def test_inventory_github_remote_origin_match_can_attach_to_local_record(tmp_path: Path):
    hub = tmp_path / "hub"
    local = _real_git_repo(tmp_path / "workspace" / "local-repo")
    hub.mkdir()
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/lowelltwong-alt/local-repo.git"],
        cwd=local,
        check=True,
        capture_output=True,
    )
    source = SimpleNamespace(
        id="github-lowelltwong-alt",
        owner="lowelltwong-alt",
        enabled=True,
        include_private=True,
        repositories=[
            {"name": "local-repo", "full_name": "lowelltwong-alt/local-repo", "visibility": "public"},
        ],
    )
    local_source = SimpleNamespace(
        id="workspace",
        path=local.parent,
        enabled=True,
        follow_symlinks=False,
    )

    result = reconcile_repo_inventory(
        hub,
        local_sources=[local_source],
        github_sources=[source],
        max_depth=2,
    )
    records = [record for record in result["inventory"]["records"] if record["repo_name"] == "local-repo"]

    assert len(records) == 1
    assert records[0]["github_inventory_status"] == "matched_by_remote_origin"
    assert "github_source:github-lowelltwong-alt" in records[0]["source_signals"]


def test_inventory_enabled_github_source_without_rows_is_incomplete(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    source = SimpleNamespace(
        id="github-lowelltwong-alt",
        owner="lowelltwong-alt",
        enabled=True,
        include_private=True,
    )

    result = reconcile_repo_inventory(hub, github_sources=[source], max_depth=1)
    inventory = result["inventory"]

    assert inventory["github_coverage_status"] == "incomplete_import_required"
    assert inventory["github_coverage_complete"] is False
    assert any("GitHub source lacks imported repo rows" in warning for warning in inventory["source_warnings"])


def test_load_config_preserves_reviewed_github_repo_rows_for_inventory(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    hub.mkdir()
    _write_minimal_hub_markers(hub)
    config_dir = hub / "config"
    config_dir.mkdir()
    config_path = config_dir / "sources.example.yaml"
    config_path.write_text(
        "\n".join(
            [
                "project:",
                "  database: state/catalog.sqlite3",
                "sources:",
                "  local: []",
                "  github:",
                "    - id: github-lowelltwong-alt",
                "      owner: lowelltwong-alt",
                "      enabled: true",
                "      include_private: true",
                "      include_archived: true",
                "      repositories:",
                "        - name: remote-only",
                "          full_name: lowelltwong-alt/remote-only",
                "          visibility: private",
                "          archived: false",
                "        - name: public-archive",
                "          full_name: lowelltwong-alt/public-archive",
                "          visibility: public",
                "          archived: true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_config(repo_root=hub)
    result = reconcile_repo_inventory(
        hub,
        github_sources=cfg.github_sources,
        max_depth=1,
    )
    inventory = result["inventory"]
    records = {record["repo_name"]: record for record in inventory["records"]}

    assert cfg.github_sources[0].repositories[0]["full_name"] == "lowelltwong-alt/remote-only"
    assert inventory["github_coverage_status"] == "imported_repo_list"
    assert inventory["github_coverage_complete"] is True
    assert records["remote-only"]["path_ref"] == "dad://github/lowelltwong-alt/remote-only"
    assert records["remote-only"]["classification"] == "needs-human-classification"
    assert records["public-archive"]["classification"] == "archive-ignore"
    assert not (tmp_path / "remote-only").exists()


def test_load_config_preserves_reviewed_github_repo_rows_from_file_for_inventory(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    hub.mkdir()
    _write_minimal_hub_markers(hub)
    repo_file = hub / "processed" / "repo_inventory" / "github_repos.json"
    repo_file.parent.mkdir(parents=True)
    repo_file.write_text(
        json.dumps(
            [
                {
                    "name": "remote-only",
                    "nameWithOwner": "lowelltwong-alt/remote-only",
                    "visibility": "PRIVATE",
                    "isArchived": False,
                },
                {
                    "name": "logos-governance-architecture",
                    "nameWithOwner": "lowelltwong-alt/logos-governance-architecture",
                    "visibility": "PUBLIC",
                    "isArchived": False,
                },
            ]
        ),
        encoding="utf-8-sig",
    )
    config_dir = hub / "config"
    config_dir.mkdir()
    (config_dir / "sources.example.yaml").write_text(
        "\n".join(
            [
                "project:",
                "  database: state/catalog.sqlite3",
                "sources:",
                "  local: []",
                "  github:",
                "    - id: github-lowelltwong-alt",
                "      owner: lowelltwong-alt",
                "      enabled: true",
                "      include_private: true",
                "      include_archived: true",
                "      repositories_file: processed/repo_inventory/github_repos.json",
                "",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_config(repo_root=hub)
    result = reconcile_repo_inventory(hub, github_sources=cfg.github_sources, max_depth=1)
    inventory = result["inventory"]
    records = {record["repo_name"]: record for record in inventory["records"]}
    source = inventory["github_sources"][0]

    assert cfg.github_sources[0].repositories_file == repo_file
    assert len(cfg.github_sources[0].repositories) == 2
    assert inventory["github_coverage_status"] == "imported_repo_list"
    assert inventory["github_coverage_complete"] is True
    assert source["metadata_source"] == "repositories_file"
    assert source["repositories_file_ref"] == "processed/repo_inventory/github_repos.json"
    assert source["repositories_file_sha256"].startswith("sha256:")
    assert inventory["input_hashes"]["processed/repo_inventory/github_repos.json"] == source[
        "repositories_file_sha256"
    ]
    assert records["remote-only"]["path_ref"] == "dad://github/lowelltwong-alt/remote-only"
    assert records["logos-governance-architecture"]["classification"] == "protected-central-only"
    assert not (tmp_path / "remote-only").exists()


def test_load_config_resolves_separate_llos_control_path(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    _write_minimal_hub_markers(hub)
    config_dir = hub / "config"
    config_dir.mkdir()
    (config_dir / "sources.example.yaml").write_text(
        "\n".join(
            [
                "project:",
                "  database: state/catalog.sqlite3",
                "sources:",
                "  local: []",
                "  github: []",
                "mail:",
                "  repos:",
                "    - id: logos-scripture-graph",
                "      path: live/scripture",
                "      llos_control_path: control-mirrors/scripture",
                "      transport_audit_path: transport-mirrors/scripture",
                "    - id: blank-audit-root",
                "      path: live/blank",
                "      transport_audit_path: ''",
                "    - id: omitted-audit-root",
                "      path: live/omitted",
                "",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_config(repo_root=hub)

    policy = cfg.mail_repos[0]
    assert policy.path == hub / "live/scripture"
    assert policy.llos_control_path == hub / "control-mirrors/scripture"
    assert policy.transport_audit_path == hub / "transport-mirrors/scripture"
    assert cfg.mail_repos[1].transport_audit_path is None
    assert cfg.mail_repos[2].transport_audit_path is None


def test_load_config_preserves_absolute_llos_control_path(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    _write_minimal_hub_markers(hub)
    mirror = (tmp_path / "absolute-control-mirror").resolve()
    config_dir = hub / "config"
    config_dir.mkdir()
    (config_dir / "sources.example.yaml").write_text(
        "\n".join(
            [
                "project:",
                "  database: state/catalog.sqlite3",
                "sources:",
                "  local: []",
                "  github: []",
                "mail:",
                "  repos:",
                "    - id: logos-scripture-graph",
                "      path: live/scripture",
                f"      llos_control_path: '{mirror}'",
                f"      transport_audit_path: '{mirror}'",
                "",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_config(repo_root=hub)

    assert cfg.mail_repos[0].llos_control_path == mirror
    assert cfg.mail_repos[0].transport_audit_path == mirror


def test_dad_inventory_cli_can_use_reviewed_github_repository_file(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    hub.mkdir()
    _write_minimal_hub_markers(hub)
    repo_file = hub / "processed" / "repo_inventory" / "github_repos.json"
    repo_file.parent.mkdir(parents=True)
    repo_file.write_text(
        json.dumps(
            [
                {
                    "name": "remote-only",
                    "full_name": "lowelltwong-alt/remote-only",
                    "visibility": "private",
                    "archived": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    config_dir = hub / "config"
    config_dir.mkdir()
    (config_dir / "sources.example.yaml").write_text(
        "\n".join(
            [
                "project:",
                "  database: state/catalog.sqlite3",
                "sources:",
                "  local: []",
                "  github:",
                "    - id: github-lowelltwong-alt",
                "      owner: lowelltwong-alt",
                "      enabled: false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = RUNNER.invoke(
        app,
        [
            "dad",
            "inventory",
            "--hub",
            str(hub),
            "--github-repositories-file",
            "processed/repo_inventory/github_repos.json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    inventory = payload["inventory"]
    source = inventory["github_sources"][0]
    assert inventory["github_coverage_status"] == "imported_repo_list"
    assert source["source_id"] == "github-lowelltwong-alt"
    assert source["metadata_source"] == "repositories_file"
    assert source["repositories_file_ref"] == "processed/repo_inventory/github_repos.json"
    assert source["repo_count"] == 1
    assert not (tmp_path / "remote-only").exists()


def test_inventory_mail_policy_is_public_safe_but_not_enrollment(tmp_path: Path):
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

    assert record["classification"] == "needs-human-classification"
    assert "mail policy" in "; ".join(record["classification_reasons"])
    assert record["path_ref"] == "dad://repo/public-repo"
    assert record["path_public_safe"] == "dad://repo/public-repo"
    assert str(public_repo) not in json.dumps(record)


def test_inventory_remote_matched_public_github_repo_redacts_local_path(tmp_path: Path):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    public_repo = _real_git_repo(workspace / "Sensitive Local Clone")
    hub.mkdir()
    subprocess.run(
        [
            "git",
            "remote",
            "add",
            "origin",
            "https://github.com/lowelltwong-alt/public-repo.git",
        ],
        cwd=public_repo,
        check=True,
        capture_output=True,
    )
    local_source = SimpleNamespace(
        id="workspace",
        path=workspace,
        enabled=True,
        follow_symlinks=False,
    )
    github_source = SimpleNamespace(
        id="github-lowelltwong-alt",
        owner="lowelltwong-alt",
        enabled=True,
        include_private=True,
        repositories=[
            {
                "name": "public-repo",
                "full_name": "lowelltwong-alt/public-repo",
                "visibility": "public",
                "archived": False,
            }
        ],
    )

    result = reconcile_repo_inventory(
        hub,
        local_sources=[local_source],
        github_sources=[github_source],
        max_depth=2,
    )
    record = result["inventory"]["records"][0]
    serialized = json.dumps(record)

    assert record["github_inventory_status"] == "matched_by_remote_origin"
    assert record["github_visibility"] == "public"
    assert record["public_facing"] is True
    assert record["visibility"] == "public"
    assert record["path_ref"] == "dad://github/lowelltwong-alt/public-repo"
    assert record["path_public_safe"] == "dad://github/lowelltwong-alt/public-repo"
    assert record["git_state"]["remote_origin"] == "redacted-public-facing"
    assert str(public_repo) not in serialized
    assert "Sensitive Local Clone" not in serialized


def test_inventory_remote_matched_github_protected_repo_overrides_local_classification(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    local_clone = _real_git_repo(workspace / "renamed-local-clone")
    hub.mkdir()
    subprocess.run(
        [
            "git",
            "remote",
            "add",
            "origin",
            "https://github.com/lowelltwong-alt/logos-governance-architecture.git",
        ],
        cwd=local_clone,
        check=True,
        capture_output=True,
    )
    local_source = SimpleNamespace(
        id="workspace",
        path=workspace,
        enabled=True,
        follow_symlinks=False,
    )
    github_source = SimpleNamespace(
        id="github-lowelltwong-alt",
        owner="lowelltwong-alt",
        enabled=True,
        include_private=True,
        repositories=[
            {
                "name": "logos-governance-architecture",
                "full_name": "lowelltwong-alt/logos-governance-architecture",
                "visibility": "public",
                "archived": False,
            }
        ],
    )

    result = reconcile_repo_inventory(
        hub,
        local_sources=[local_source],
        github_sources=[github_source],
        max_depth=2,
    )
    record = result["inventory"]["records"][0]
    serialized = json.dumps(record)

    assert record["github_inventory_status"] == "matched_by_remote_origin"
    assert record["classification"] == "protected-central-only"
    assert record["write_boundary"] == "central_only"
    assert "GitHub remote-origin match" in "; ".join(record["classification_reasons"])
    assert record["path_ref"] == "dad://github/lowelltwong-alt/logos-governance-architecture"
    assert str(local_clone) not in serialized
    assert "renamed-local-clone" not in serialized


def test_inventory_remote_matched_github_archived_repo_overrides_unreviewed_local_clone(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    local_clone = _real_git_repo(workspace / "old-local-tool")
    hub.mkdir()
    subprocess.run(
        [
            "git",
            "remote",
            "add",
            "origin",
            "https://github.com/lowelltwong-alt/archived-tool.git",
        ],
        cwd=local_clone,
        check=True,
        capture_output=True,
    )
    local_source = SimpleNamespace(
        id="workspace",
        path=workspace,
        enabled=True,
        follow_symlinks=False,
    )
    github_source = SimpleNamespace(
        id="github-lowelltwong-alt",
        owner="lowelltwong-alt",
        enabled=True,
        include_private=True,
        repositories=[
            {
                "name": "archived-tool",
                "full_name": "lowelltwong-alt/archived-tool",
                "visibility": "private",
                "archived": True,
            }
        ],
    )

    result = reconcile_repo_inventory(
        hub,
        local_sources=[local_source],
        github_sources=[github_source],
        max_depth=2,
    )
    record = result["inventory"]["records"][0]

    assert record["github_inventory_status"] == "matched_by_remote_origin"
    assert record["github_archived"] is True
    assert record["classification"] == "archive-ignore"
    assert record["write_boundary"] == "central_only"
    assert "GitHub remote-origin match" in "; ".join(record["classification_reasons"])


def test_inventory_mail_policy_does_not_promote_archive_path(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = _git_repo(tmp_path / "archive" / "repo")
    hub.mkdir()
    policy = MailRepoPolicy(
        id="repo-mail",
        path=repo,
        alias="repo",
        visibility="internal",
    )

    result = reconcile_repo_inventory(hub, mail_policies=[policy], max_depth=2)
    record = result["inventory"]["records"][0]

    assert record["classification"] == "archive-ignore"
    assert record["mail_policy_present"] is True
    assert record["enrollment_policy_present"] is False


def test_inventory_prefers_enrollment_policy_when_mail_policy_also_matches(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    repo = _git_repo(tmp_path / "repo")
    hub.mkdir()
    mail_policy = MailRepoPolicy(
        id="repo-mail",
        path=repo,
        alias="repo",
        visibility="internal",
    )
    enrollment_policy = EnrollmentRepoPolicy(
        id="repo-enrollment",
        path=repo,
        alias="repo",
        visibility="internal",
        enrollment_enabled=True,
        local_paths_allowed=True,
    )

    result = reconcile_repo_inventory(
        hub,
        mail_policies=[mail_policy],
        enrollment_policies=[enrollment_policy],
        max_depth=1,
    )
    record = result["inventory"]["records"][0]

    assert record["repo_id"] == "repo-enrollment"
    assert record["repo_id_source"] == "policy"
    assert record["local_paths_allowed"] is True
    assert record["mail_policy_present"] is True
    assert record["enrollment_policy_present"] is True


def test_inventory_public_contract_without_policy_redacts_local_path(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = _git_repo(tmp_path / "Public Contract Repo")
    hub.mkdir()
    contract = repo / ".digital-asset" / "dad-integration.json"
    contract.parent.mkdir(parents=True)
    contract.write_text(
        json.dumps(
            {
                "repo_id": "public-contract",
                "repo_alias": "public-contract",
                "visibility": "public",
                "public_facing": True,
            }
        ),
        encoding="utf-8",
    )

    result = reconcile_repo_inventory(
        hub,
        local_sources=[
            SimpleNamespace(id="workspace", path=repo.parent, enabled=True, follow_symlinks=False)
        ],
        max_depth=1,
    )
    record = result["inventory"]["records"][0]
    serialized = json.dumps(record)

    assert record["public_facing"] is True
    assert record["repo_id"] == "public-contract"
    assert record["repo_id_source"] == "contract"
    assert record["path_ref"] == "dad://repo/public-contract"
    assert str(repo) not in serialized


def test_inventory_public_facing_git_state_redacts_branch_and_head(tmp_path: Path):
    hub = tmp_path / "hub"
    public_repo = _real_git_repo(tmp_path / "Public Repo", branch="feature/private-branch")
    hub.mkdir()
    policy = EnrollmentRepoPolicy(
        id="public-repo",
        path=public_repo,
        alias="public-repo",
        visibility="public",
        public_facing=True,
        enrollment_enabled=True,
        allow_non_main_branch=True,
        local_paths_allowed=False,
    )

    result = reconcile_repo_inventory(hub, enrollment_policies=[policy], max_depth=1)
    record = result["inventory"]["records"][0]
    serialized = json.dumps(record)

    assert record["classification"] == "enroll"
    assert record["git_state"]["branch_status"] == "non_main"
    assert record["git_state"]["branch"] == "redacted-public-facing"
    assert "feature/private-branch" not in serialized
    assert str(public_repo) not in serialized


def test_inventory_unborn_repo_has_deterministic_explicit_head_identity(tmp_path: Path):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    hub.mkdir()
    unborn = _real_git_repo(workspace / "unborn")
    source = SimpleNamespace(
        id="workspace",
        path=workspace,
        enabled=True,
        follow_symlinks=False,
    )

    first = reconcile_repo_inventory(hub, local_sources=[source], max_depth=1)["inventory"]
    second = reconcile_repo_inventory(hub, local_sources=[source], max_depth=1)["inventory"]
    first_record = first["records"][0]
    second_record = second["records"][0]

    assert first_record["git_state"]["git_detected"] is True
    assert first_record["git_state"]["head"] == "UNBORN"
    assert second_record["git_state"]["head"] == "UNBORN"
    assert first["content_fingerprint"] == second["content_fingerprint"]
    assert unborn.exists()


def test_inventory_born_head_identity_is_unchanged_and_public_unborn_is_redacted(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    hub.mkdir()
    born = _real_git_repo(tmp_path / "born")
    (born / "README.md").write_text("born\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=born, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=DAD Test",
            "-c",
            "user.email=dad-test@example.invalid",
            "commit",
            "-m",
            "initial",
        ],
        cwd=born,
        check=True,
        capture_output=True,
    )
    expected_head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=born,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    born_policy = EnrollmentRepoPolicy(
        id="born",
        path=born,
        alias="born",
        visibility="internal",
        public_facing=False,
        enrollment_enabled=True,
    )

    born_record = reconcile_repo_inventory(
        hub, enrollment_policies=[born_policy], max_depth=1
    )["inventory"]["records"][0]
    assert born_record["git_state"]["head"] == expected_head

    public_unborn = _real_git_repo(tmp_path / "public-unborn")
    public_policy = EnrollmentRepoPolicy(
        id="public-unborn",
        path=public_unborn,
        alias="public-unborn",
        visibility="public",
        public_facing=True,
        enrollment_enabled=True,
        local_paths_allowed=False,
    )
    public_record = reconcile_repo_inventory(
        hub, enrollment_policies=[public_policy], max_depth=1
    )["inventory"]["records"][0]
    assert public_record["git_state"]["head"] == "redacted-public-facing"
    assert "UNBORN" not in json.dumps(public_record)


def test_inventory_nested_git_root_is_reported_duplicate_ignore(tmp_path: Path):
    hub = tmp_path / "hub"
    parent = _git_repo(tmp_path / "workspace" / "parent")
    _git_repo(parent / "vendor" / "child")
    hub.mkdir()
    source = SimpleNamespace(
        id="workspace",
        path=parent.parent,
        enabled=True,
        follow_symlinks=False,
    )

    result = reconcile_repo_inventory(hub, local_sources=[source], max_depth=4)
    records = {record["repo_name"]: record for record in result["inventory"]["records"]}

    assert "child" in records
    assert records["child"]["nested_repo"] is True
    assert records["child"]["classification"] == "duplicate-ignore"
    assert records["child"]["addressing_status"] == "nested_repo"


def test_inventory_workspace_root_git_metadata_does_not_make_children_nested(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    workspace = _git_repo(tmp_path / "git-projects")
    child = _git_repo(workspace / "child")
    hub.mkdir()
    source = SimpleNamespace(
        id="workspace",
        path=workspace,
        enabled=True,
        follow_symlinks=False,
    )

    result = reconcile_repo_inventory(hub, local_sources=[source], max_depth=2)
    records = {record["repo_name"]: record for record in result["inventory"]["records"]}

    assert records[workspace.name]["classification"] == "duplicate-ignore"
    assert records[child.name]["nested_repo"] is False
    assert records[child.name]["classification"] == "needs-human-classification"


def test_inventory_nested_bare_name_does_not_match_unrelated_policy(tmp_path: Path):
    hub = tmp_path / "hub"
    policy_repo = _git_repo(tmp_path / "workspace" / "dad")
    parent = _git_repo(tmp_path / "workspace" / "parent")
    nested = _git_repo(parent / "vendor" / "dad")
    hub.mkdir()
    policy = EnrollmentRepoPolicy(
        id="dad-policy",
        path=policy_repo,
        alias="dad",
        visibility="internal",
        enrollment_enabled=True,
    )
    source = SimpleNamespace(
        id="workspace",
        path=tmp_path / "workspace",
        enabled=True,
        follow_symlinks=False,
    )

    result = reconcile_repo_inventory(
        hub,
        local_sources=[source],
        enrollment_policies=[policy],
        max_depth=4,
    )
    nested_record = next(
        record
        for record in result["inventory"]["records"]
        if record["path_ref"].endswith("parent/vendor/dad")
    )

    assert nested_record["repo_name"] == nested.name
    assert nested_record["repo_id"] == ""
    assert nested_record["classification"] == "duplicate-ignore"
    assert nested_record["enrollment_policy_present"] is False


def test_inventory_skips_pytest_temp_workspaces(tmp_path: Path):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    _git_repo(workspace / "pytest_tmp_dirty_mail" / "repo")
    _git_repo(workspace / "keep-me")
    hub.mkdir()
    source = SimpleNamespace(
        id="workspace",
        path=workspace,
        enabled=True,
        follow_symlinks=False,
    )

    result = reconcile_repo_inventory(hub, local_sources=[source], max_depth=3)
    names = {record["repo_name"] for record in result["inventory"]["records"]}

    assert "repo" not in names
    assert "keep-me" in names


def test_inventory_skips_dad_tmp_workspaces(tmp_path: Path):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    _git_repo(workspace / ".tmp" / "exception-learning-check" / "synthetic-public-clean")
    _git_repo(workspace / "keep-me")
    hub.mkdir()
    source = SimpleNamespace(
        id="workspace",
        path=workspace,
        enabled=True,
        follow_symlinks=False,
    )

    result = reconcile_repo_inventory(hub, local_sources=[source], max_depth=4)
    names = {record["repo_name"] for record in result["inventory"]["records"]}

    assert "synthetic-public-clean" not in names
    assert "keep-me" in names


def test_inventory_skips_rust_target_build_roots(tmp_path: Path):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    _git_repo(workspace / "target" / "generated")
    _git_repo(workspace / "keep-me")
    hub.mkdir()
    source = SimpleNamespace(
        id="workspace",
        path=workspace,
        enabled=True,
        follow_symlinks=False,
    )

    result = reconcile_repo_inventory(hub, local_sources=[source], max_depth=3)
    names = {record["repo_name"] for record in result["inventory"]["records"]}

    assert "generated" not in names
    assert "keep-me" in names


def test_inventory_does_not_descend_symlinked_repo_without_followlinks(tmp_path: Path):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    outside = _git_repo(tmp_path / "outside-repo")
    workspace.mkdir()
    hub.mkdir()
    link = workspace / "linked-repo"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    source = SimpleNamespace(
        id="workspace",
        path=workspace,
        enabled=True,
        follow_symlinks=False,
    )

    result = reconcile_repo_inventory(hub, local_sources=[source], max_depth=3)
    names = {record["repo_name"] for record in result["inventory"]["records"]}

    assert "linked-repo" not in names
    assert "outside-repo" not in names


def test_repo_inventory_rust_probe_parity_is_candidate_only(tmp_path: Path):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    repo = _git_repo(workspace / "repo")
    _git_repo(workspace / "pytest_tmp_dirty_mail" / "hidden")
    hub.mkdir()
    rust_summary = _rust_repo_probe_summary(
        [
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/repo",
                "depth": 1,
                "git_marker_type": "directory",
                "contract_present": False,
                "no_mutation_performed": True,
            }
        ],
        skipped_dirs=[
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/pytest_tmp_dirty_mail",
                "reason": "pytest temp workspace",
            },
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/repo/.git",
                "reason": "repo discovery skip directory",
            },
        ],
    )

    result = write_repo_inventory_rust_probe_parity(
        hub,
        roots=[workspace],
        root_aliases=["dad-local-source/workspace"],
        rust_summary=rust_summary,
        max_depth=3,
    )
    parity = result["parity"]

    assert parity["parity_status"] == "matched"
    assert parity["python_repo_count"] == 1
    assert parity["rust_repo_count"] == 1
    assert parity["duplicate_logical_path_count"] == 0
    assert parity["contract_present_mismatch_count"] == 0
    assert parity["rust_unknown_contract_field_count"] == 0
    assert parity["rust_contract_structural_pass_count"] == 0
    assert parity["rust_contract_structural_fail_count"] == 1
    assert parity["rust_contract_issue_code_count"] == 1
    assert parity["rust_contract_parse_status_counts"] == {"missing": 1}
    assert "deployment-doctor inputs only" in parity["contract_structural_scope"]
    assert parity["duplicate_logical_paths"] == []
    assert parity["contract_present_mismatches"] == []
    assert parity["rust_unknown_contract_fields"] == []
    assert parity["python_records"][0]["logical_path"] == "dad-local-source/workspace/repo"
    assert "input_hashes" in parity
    assert "candidate machine evidence only" in parity["authority_boundary"]
    assert not (repo / "processed").exists()
    assert Path(result["json_path"]) == hub / "processed" / "repo_inventory" / "rust_probe_shadow_parity.json"


def test_repo_inventory_rust_probe_parity_normalizes_public_safe_logical_paths(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    _git_repo(workspace / "Mock Trial4.26 (active)")
    hub.mkdir()
    rust_summary = _rust_repo_probe_summary(
        [
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/mock-trial4.26-active",
                "depth": 1,
                "git_marker_type": "directory",
                "contract_present": False,
                "no_mutation_performed": True,
            }
        ],
        skipped_dirs=[
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/mock-trial4.26-active/.git",
                "reason": "repo discovery skip directory",
            }
        ],
    )

    result = write_repo_inventory_rust_probe_parity(
        hub,
        roots=[workspace],
        root_aliases=["dad-local-source/workspace"],
        rust_summary=rust_summary,
        max_depth=3,
    )
    parity = result["parity"]

    assert parity["parity_status"] == "matched"
    assert parity["python_records"][0]["logical_path"] == (
        "dad-local-source/workspace/mock-trial4.26-active"
    )
    assert parity["only_python_logical_paths"] == []
    assert parity["only_rust_logical_paths"] == []


def test_repo_inventory_rust_probe_parity_rejects_duplicate_root_aliases(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    other = tmp_path / "other-workspace"
    _git_repo(workspace / "repo")
    _git_repo(other / "repo")
    hub.mkdir()
    rust_summary = _rust_repo_probe_summary([])

    with pytest.raises(ValueError, match="root_alias values must be unique"):
        write_repo_inventory_rust_probe_parity(
            hub,
            roots=[workspace, other],
            root_aliases=["dad-local-source/workspace", "dad-local-source/workspace"],
            rust_summary=rust_summary,
            max_depth=3,
        )


def test_repo_inventory_rust_probe_parity_flags_skipped_dir_policy_drift(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    repo = _git_repo(workspace / "repo")
    fs_target = repo / "target" / "generated"
    fs_target.mkdir(parents=True)
    (fs_target / ".git").mkdir()
    hub.mkdir()
    rust_summary = _rust_repo_probe_summary(
        [
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/repo",
                "depth": 1,
                "git_marker_type": "directory",
                "contract_present": False,
                "no_mutation_performed": True,
            }
        ],
        skipped_dirs=[
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/repo/.git",
                "reason": "repo discovery skip directory",
            }
        ],
    )

    result = write_repo_inventory_rust_probe_parity(
        hub,
        roots=[workspace],
        root_aliases=["dad-local-source/workspace"],
        rust_summary=rust_summary,
        max_depth=3,
    )
    parity = result["parity"]

    assert parity["parity_status"] == "mismatch_candidate"
    assert parity["skip_policy_mismatch_count"] == 1
    assert parity["only_python_skipped_dirs"] == [
        {
            "logical_path": "dad-local-source/workspace/repo/target",
            "reason": "repo discovery skip directory",
            "source": "python_inventory_discovery",
        }
    ]


def test_repo_inventory_rust_probe_parity_flags_contract_presence_drift(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    repo = _git_repo(workspace / "repo")
    contract_path = repo / ".digital-asset" / "dad-integration.json"
    contract_path.parent.mkdir(parents=True)
    contract_path.write_text('{"repo_id":"repo"}', encoding="utf-8")
    hub.mkdir()
    rust_summary = _rust_repo_probe_summary(
        [
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/repo",
                "depth": 1,
                "git_marker_type": "directory",
                "contract_present": False,
                "no_mutation_performed": True,
            }
        ]
    )

    result = write_repo_inventory_rust_probe_parity(
        hub,
        roots=[workspace],
        root_aliases=["dad-local-source/workspace"],
        rust_summary=rust_summary,
        max_depth=3,
    )
    parity = result["parity"]

    assert parity["parity_status"] == "mismatch_candidate"
    assert parity["only_python_logical_paths"] == []
    assert parity["only_rust_logical_paths"] == []
    assert parity["contract_present_mismatch_count"] == 1
    assert parity["contract_present_mismatches"] == [
        {
            "logical_path": "dad-local-source/workspace/repo",
            "python_contract_present": True,
            "rust_contract_present": False,
        }
    ]
    assert "candidate machine evidence only" in Path(result["markdown_path"]).read_text(
        encoding="utf-8"
    )


def test_repo_inventory_rust_probe_parity_flags_reverse_contract_presence_drift(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    _git_repo(workspace / "repo")
    hub.mkdir()
    rust_summary = _rust_repo_probe_summary(
        [
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/repo",
                "depth": 1,
                "git_marker_type": "directory",
                "contract_present": True,
                "no_mutation_performed": True,
            }
        ]
    )

    result = write_repo_inventory_rust_probe_parity(
        hub,
        roots=[workspace],
        root_aliases=["dad-local-source/workspace"],
        rust_summary=rust_summary,
        max_depth=3,
    )
    parity = result["parity"]

    assert parity["parity_status"] == "mismatch_candidate"
    assert parity["contract_present_mismatch_count"] == 1
    assert parity["contract_present_mismatches"] == [
        {
            "logical_path": "dad-local-source/workspace/repo",
            "python_contract_present": False,
            "rust_contract_present": True,
        }
    ]


def test_repo_inventory_rust_probe_parity_flags_missing_contract_probe_field(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    _git_repo(workspace / "repo")
    hub.mkdir()
    rust_summary = _rust_repo_probe_summary(
        [
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/repo",
                "depth": 1,
                "git_marker_type": "directory",
                "no_mutation_performed": True,
            }
        ]
    )

    result = write_repo_inventory_rust_probe_parity(
        hub,
        roots=[workspace],
        root_aliases=["dad-local-source/workspace"],
        rust_summary=rust_summary,
        max_depth=3,
    )
    parity = result["parity"]

    assert parity["parity_status"] == "mismatch_candidate"
    assert parity["contract_present_mismatch_count"] == 0
    assert parity["rust_unknown_contract_field_count"] == 1
    assert parity["rust_unknown_contract_fields"] == [
        {
            "logical_path": "dad-local-source/workspace/repo",
            "root_alias": "dad-local-source/workspace",
            "field_status": "missing",
        }
    ]
    assert parity["rust_records"][0]["contract_present"] is None
    assert parity["rust_records"][0]["contract_present_field_status"] == "missing"


def test_repo_inventory_rust_probe_parity_flags_invalid_probe_summary(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    _git_repo(workspace / "repo")
    hub.mkdir()
    rust_summary = {
        "schema_version": "old_probe",
        "repo_count": 1,
        "repos": [
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/repo",
                "contract_present": False,
            }
        ],
    }

    result = write_repo_inventory_rust_probe_parity(
        hub,
        roots=[workspace],
        root_aliases=["dad-local-source/workspace"],
        rust_summary=rust_summary,
        max_depth=3,
    )
    parity = result["parity"]

    assert parity["parity_status"] == "mismatch_candidate"
    assert parity["rust_summary_valid"] is False
    assert any("schema_version" in issue for issue in parity["rust_summary_validation_errors"])


def test_repo_inventory_rust_probe_parity_flags_duplicate_logical_paths(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    _git_repo(workspace / "repo")
    hub.mkdir()
    rust_summary = _rust_repo_probe_summary(
        [
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/repo",
                "depth": 1,
                "git_marker_type": "directory",
                "contract_present": False,
                "no_mutation_performed": True,
            },
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/repo",
                "depth": 1,
                "git_marker_type": "directory",
                "contract_present": False,
                "no_mutation_performed": True,
            },
        ]
    )

    result = write_repo_inventory_rust_probe_parity(
        hub,
        roots=[workspace],
        root_aliases=["dad-local-source/workspace"],
        rust_summary=rust_summary,
        max_depth=3,
    )
    parity = result["parity"]

    assert parity["parity_status"] == "mismatch_candidate"
    assert parity["python_repo_count"] == 1
    assert parity["rust_repo_count"] == 2
    assert parity["duplicate_logical_path_count"] == 1
    assert parity["duplicate_logical_paths"] == [
        {
            "source": "rust_repo_inventory_probe",
            "logical_path": "dad-local-source/workspace/repo",
            "count": 2,
        }
    ]


def test_repo_inventory_rust_probe_parity_reports_mismatch_without_classifying(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    workspace = tmp_path / "workspace"
    _git_repo(workspace / "repo")
    hub.mkdir()
    rust_summary = _rust_repo_probe_summary(
        [
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/other",
                "depth": 1,
                "git_marker_type": "directory",
                "contract_present": False,
                "no_mutation_performed": True,
            }
        ]
    )

    result = write_repo_inventory_rust_probe_parity(
        hub,
        roots=[workspace],
        root_aliases=["dad-local-source/workspace"],
        rust_summary=rust_summary,
        max_depth=3,
    )
    parity = result["parity"]

    assert parity["parity_status"] == "mismatch_candidate"
    assert parity["only_python_logical_paths"] == ["dad-local-source/workspace/repo"]
    assert parity["only_rust_logical_paths"] == ["dad-local-source/workspace/other"]
    assert "does not classify repos" in parity["authority_boundary"]


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


def test_collect_repo_local_assets_reads_canonical_and_legacy_metadata_only(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    hub.mkdir()
    (hub / "registry").mkdir()
    (hub / "registry" / "asset-recognition-methodology.json").write_text(
        (ROOT / "registry" / "asset-recognition-methodology.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    asset_dir = repo / ".digital-asset" / "assets"
    ingest_dir = repo / ".digital-asset" / "dad-ingest"
    asset_dir.mkdir(parents=True)
    ingest_dir.mkdir(parents=True)
    (asset_dir / "index.jsonl").write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "asset_id": "repo:asset:address",
                "asset_type": "architecture_reference",
                "title": "Address model",
                "summary": "Metadata-only address model pointer.",
                "source_paths": ["docs/address.md"],
                "sensitivity": "internal",
                "review_status": "candidate",
                "fractal_address": {"layer": 9, "layer_name": "learning_adaptation"},
                "graph_tags": ["address_model"],
                "raw_blob": "do-not-copy",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ingest_dir / "asset_manifest.json").write_text(
        json.dumps(
            {
                "manifest_id": "legacy",
                "assets": [
                    {
                        "asset_id": "legacy:asset:workflow",
                        "asset_type": "workflow",
                        "title": "Legacy workflow",
                        "summary": "Legacy workflow pointer.",
                        "path": "docs/workflow.md",
                        "sensitivity": "internal",
                        "review_status": "candidate",
                        "large_private_rows": "do-not-copy",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (repo / "docs").mkdir()
    (repo / "docs" / "address.md").write_text("secret=do-not-copy", encoding="utf-8")

    result = collect_repo_local_assets(hub, repo, task="address workflow asset", limit=10)
    payload = result["repo_assets"]

    assert payload["declared_assets"]["record_count"] == 2
    assert payload["standard"]["adopted_layer_count"] == 9
    assert payload["declared_assets"]["records"][0]["fractal_address"]["layer"] == 9
    assert "raw_blob" in payload["declared_assets"]["records"][0]["dropped_fields"]
    assert "large_private_rows" in payload["declared_assets"]["records"][1]["dropped_fields"]
    assert "do-not-copy" not in json.dumps(payload)
    assert Path(result["path"]).parent == hub / "processed" / "reports" / "repo_local_assets"
    assert not (repo / "processed").exists()


def test_collect_repo_local_assets_tolerates_malformed_index_row(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    hub.mkdir()
    (hub / "registry").mkdir()
    (hub / "registry" / "asset-recognition-methodology.json").write_text(
        (ROOT / "registry" / "asset-recognition-methodology.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    asset_dir = repo / ".digital-asset" / "assets"
    asset_dir.mkdir(parents=True)
    (asset_dir / "index.jsonl").write_text(
        '{"asset_id":"good","asset_type":"note","title":"Good","summary":"ok","source_paths":["a"],"sensitivity":"internal","review_status":"candidate"}\n'
        "{not-json}\n",
        encoding="utf-8",
    )

    result = collect_repo_local_assets(hub, repo, task="asset", limit=5)
    canonical = result["repo_assets"]["declared_assets"]["canonical_index"]

    assert canonical["record_count"] == 1
    assert canonical["malformed_count"] == 1
    assert result["repo_assets"]["declared_assets"]["record_count"] == 1


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
