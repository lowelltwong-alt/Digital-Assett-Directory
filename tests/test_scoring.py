import pytest

from digital_asset_directory.models import AssetRecord
from digital_asset_directory.scoring import DEFAULT_WEIGHTS, score_asset

pytestmark = pytest.mark.unit

SCORING = {"weights": DEFAULT_WEIGHTS}


def _asset(aid: str, **overrides) -> AssetRecord:
    base = dict(
        asset_id=aid,
        revision_id="r",
        source_id="s",
        source_kind="local",
        asset_type="document",
        title=aid,
        logical_path=f"{aid}.md",
        content_hash="h",
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        lifecycle_state="active",
        freshness_status="current",
        trust_zone="source_owned",
        value_score=0,
        value_components={},
    )
    base.update(overrides)
    return AssetRecord(**base)


def test_provenance_rewards_real_content_hash_over_metadata_only():
    read = _asset("read", content_sha256="abc123", source_provenance={"observed_by": "local_scan"})
    metadata_only = _asset(
        "meta", content_sha256=None, source_provenance={"observed_by": "local_scan"}
    )
    score_asset(read, SCORING)
    score_asset(metadata_only, SCORING)
    # Previously provenance was a constant 0.95 for every asset; now it discriminates.
    assert read.value_components["provenance"] == 95.0
    assert metadata_only.value_components["provenance"] == 55.0


def test_uniqueness_drops_with_duplicate_cluster_size():
    solo = _asset("solo")
    dup = _asset("dup")
    score_asset(solo, SCORING)
    score_asset(dup, SCORING, duplicate_counts={"dup": 4})
    # Previously uniqueness was a hardcoded 0.55 (55.0) for every asset.
    assert solo.value_components["uniqueness"] == 100.0
    assert dup.value_components["uniqueness"] < solo.value_components["uniqueness"]


def test_dead_constants_removed_scores_vary_across_a_mix():
    assets = [
        _asset("a", asset_type="test", content_sha256="x", capabilities=["validate_contracts"]),
        _asset("b", asset_type="document", content_sha256=None),
        _asset("c", asset_type="schema", content_sha256="y", outcomes=["repeatable_quality"]),
    ]
    for asset in assets:
        score_asset(asset, SCORING)
    scores = {asset.value_score for asset in assets}
    # The fixed-constant components no longer collapse distinct assets to one score.
    assert len(scores) == len(assets)


def test_risk_penalties_are_multiplicative_and_unknown_license_is_real():
    safe = _asset(
        "safe",
        source_kind="github",
        asset_type="repository",
        content_sha256="x",
        sensitivity="internal",
        source_provenance={"observed_by": "github_scan"},
        metadata={"license": "MIT"},
    )
    risky = _asset(
        "risky",
        source_kind="github",
        asset_type="repository",
        content_sha256="x",
        sensitivity="internal",
        source_provenance={"observed_by": "github_scan"},
        metadata={},
    )

    score_asset(safe, SCORING)
    score_asset(risky, {"weights": DEFAULT_WEIGHTS, "risk_penalties": {"unknown_license": 0.2}})

    assert risky.value_components["risk_factor"] == 80.0
    assert risky.value_score < safe.value_score


def test_stale_is_only_represented_by_freshness_component():
    current = _asset(
        "current",
        freshness_status="current",
        sensitivity="internal",
        content_sha256="x",
        source_provenance={"observed_by": "test"},
        size_bytes=128,
        metadata={"text_tokens": ["current", "asset"]},
    )
    stale = _asset(
        "stale",
        freshness_status="stale",
        sensitivity="internal",
        content_sha256="x",
        source_provenance={"observed_by": "test"},
        size_bytes=128,
        metadata={"text_tokens": ["stale", "asset"]},
    )

    score_asset(current, {"weights": {"freshness": 1.0}, "risk_penalties": {"stale": 0.9}})
    score_asset(stale, {"weights": {"freshness": 1.0}, "risk_penalties": {"stale": 0.9}})

    assert current.value_score == 100
    assert stale.value_score == 25


def test_temp_fixture_schema_is_discounted_below_source_schema():
    source_schema = _asset(
        "source-schema",
        asset_type="schema",
        logical_path="repo/schemas/claim.schema.json",
        content_sha256="same",
        size_bytes=2048,
        capabilities=["validate_contracts"],
        outcomes=["repeatable_quality"],
        metadata={"text_tokens": ["schema", "contract", "validation"]},
    )
    temp_schema = _asset(
        "temp-schema",
        asset_type="schema",
        logical_path="repo/.pytest-tmp-root/pytest-of-Lowell/pytest-1/test_x/contract-repo/schemas/claim.schema.json",
        content_sha256="same",
        size_bytes=2048,
        capabilities=["validate_contracts"],
        outcomes=["repeatable_quality"],
        metadata={"text_tokens": ["schema", "contract", "validation"]},
    )

    score_asset(source_schema, SCORING, duplicate_counts={"source-schema": 2})
    score_asset(temp_schema, SCORING, duplicate_counts={"temp-schema": 2})

    assert source_schema.value_score > temp_schema.value_score
    assert temp_schema.metadata["instance_class"] == "temp_fixture"
    assert (
        "temp_fixture_lineage_not_independent_value"
        in temp_schema.metadata["score_discount_reasons"]
    )


def test_empty_marker_and_os_junk_floor_out():
    marker = _asset(
        "marker",
        asset_type="code",
        logical_path="repo/eval/__init__.py",
        content_sha256="empty",
        size_bytes=0,
    )
    junk = _asset(
        "junk",
        asset_type="unknown",
        logical_path="repo/.DS_Store",
        content_sha256="junk",
        size_bytes=6148,
    )

    score_asset(marker, SCORING)
    score_asset(junk, SCORING)

    assert marker.value_components["score_discount_factor"] == 25.0
    assert junk.value_components["score_discount_factor"] == 2.0
    assert junk.value_score < marker.value_score


def test_duplicate_non_representative_gets_strong_discount():
    representative = _asset(
        "representative",
        logical_path="repo/a.md",
        content_sha256="same",
        size_bytes=2048,
        metadata={
            "text_tokens": ["validated", "source", "asset"],
            "duplicate_representative_id": "representative",
        },
    )
    copy = _asset(
        "copy",
        logical_path="repo/b.md",
        content_sha256="same",
        size_bytes=2048,
        metadata={
            "text_tokens": ["validated", "source", "asset"],
            "duplicate_representative_id": "representative",
        },
    )

    score_asset(representative, SCORING, duplicate_counts={"representative": 8})
    score_asset(copy, SCORING, duplicate_counts={"copy": 8})

    assert copy.value_score < representative.value_score
    assert "duplicate_non_representative_discount" in copy.metadata["score_discount_reasons"]


def test_content_profile_lifts_substantive_source_code_out_of_metadata_low():
    metadata_only = _asset(
        "metadata-code",
        asset_type="code",
        logical_path="repo/src/digital_asset_directory/admission_validator.py",
        content_sha256=None,
        size_bytes=14_000,
        sensitivity="internal",
        source_provenance={"observed_by": "local_scan"},
        capabilities=["validate_contracts"],
        outcomes=["repeatable_quality"],
    )
    profiled = _asset(
        "profiled-code",
        asset_type="code",
        logical_path="repo/src/digital_asset_directory/admission_validator.py",
        content_sha256=None,
        size_bytes=14_000,
        sensitivity="internal",
        source_provenance={"observed_by": "local_scan"},
        capabilities=["validate_contracts"],
        outcomes=["repeatable_quality"],
        metadata={
            "content_profile": {
                "non_empty_line_count": 190,
                "import_count": 8,
                "function_count": 14,
                "class_count": 2,
                "public_symbol_count": 16,
                "code_role": "runtime_core",
            }
        },
    )

    score_asset(metadata_only, SCORING)
    score_asset(profiled, SCORING)

    assert profiled.metadata["information_content_class"] == "content_profiled"
    assert profiled.value_components["content_role"] >= 90
    assert profiled.value_score >= 40
    assert profiled.value_score > metadata_only.value_score + 20
    assert profiled.metadata["score_methodology_version"] == "asset-value-v0.3-content-aware"


def test_workflow_templates_discount_below_validation_workflows():
    issue_template = _asset(
        "issue-template",
        asset_type="workflow",
        logical_path="repo/.github/ISSUE_TEMPLATE/bug_report.md",
        content_sha256=None,
        size_bytes=1200,
        sensitivity="internal",
        source_provenance={"observed_by": "local_scan"},
        metadata={
            "content_profile": {
                "non_empty_line_count": 24,
                "workflow_subtype": "issue_or_pr_template",
            }
        },
    )
    validation_workflow = _asset(
        "validation-workflow",
        asset_type="workflow",
        logical_path="repo/.github/workflows/validate.yml",
        content_sha256=None,
        size_bytes=2100,
        sensitivity="internal",
        source_provenance={"observed_by": "local_scan"},
        capabilities=["validate_contracts"],
        outcomes=["repeatable_quality"],
        metadata={
            "pattern_evidence": [{"term": "pytest"}, {"term": "validate"}],
            "content_profile": {
                "non_empty_line_count": 42,
                "workflow_subtype": "ci_validation_workflow",
            },
        },
    )

    score_asset(issue_template, SCORING)
    score_asset(validation_workflow, SCORING)

    assert issue_template.value_score < validation_workflow.value_score
    assert issue_template.value_score < 35
    assert "workflow_issue_or_pr_template" in issue_template.metadata["score_discount_reasons"]
    assert (
        validation_workflow.value_components["content_role"]
        > issue_template.value_components["content_role"]
    )


def test_package_marker_cannot_inflate_as_runtime_code():
    marker = _asset(
        "marker",
        asset_type="code",
        logical_path="repo/src/digital_asset_directory/__init__.py",
        content_sha256=None,
        size_bytes=40,
        sensitivity="internal",
        source_provenance={"observed_by": "local_scan"},
        capabilities=["validate_contracts"],
        metadata={
            "content_profile": {
                "non_empty_line_count": 1,
                "public_symbol_count": 0,
                "import_count": 0,
                "code_role": "package_marker",
            }
        },
    )

    score_asset(marker, SCORING)

    assert marker.value_score < 20
    assert marker.value_components["content_role"] == 5
    assert "package_marker_low_independent_value" in marker.metadata["score_discount_reasons"]


def test_small_support_module_stays_low_without_usage_evidence():
    helper = _asset(
        "helper",
        asset_type="code",
        logical_path="repo/src/package/storage/defect_store.py",
        content_sha256=None,
        size_bytes=900,
        sensitivity="internal",
        source_provenance={"observed_by": "local_scan"},
        metadata={
            "content_profile": {
                "non_empty_line_count": 18,
                "import_count": 4,
                "function_count": 4,
                "class_count": 0,
                "public_symbol_count": 4,
                "code_role": "support_module",
            }
        },
    )

    score_asset(helper, SCORING)

    assert helper.value_score < 45
    assert "small_support_module_needs_usage_evidence" in helper.metadata["score_discount_reasons"]


def test_source_ruleset_config_workflow_remains_review_worthy():
    ruleset = _asset(
        "ruleset",
        asset_type="workflow",
        logical_path="repo/.github/rulesets/main-canonical-ruleset.json",
        content_sha256=None,
        size_bytes=1300,
        sensitivity="internal",
        source_provenance={"observed_by": "local_scan"},
        metadata={
            "content_profile": {
                "non_empty_line_count": 42,
                "workflow_subtype": "ruleset_config",
            }
        },
    )

    score_asset(ruleset, SCORING)

    assert ruleset.value_score >= 45
    assert (
        "workflow_config_wrapper_needs_usage_evidence" in ruleset.metadata["score_discount_reasons"]
    )
