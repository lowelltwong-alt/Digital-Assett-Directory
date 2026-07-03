from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema.validators import validator_for

import pytest

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def validate(schema_rel: str, payload: dict) -> None:
    schema = load_json(schema_rel)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


def test_trusted_source_url_matching_rejects_redirect_spoof():
    sys.path.insert(0, str(ROOT / "scripts"))
    from validate_coding_asset_control_plane import source_ref_matches_patterns

    patterns = ["github.com/obi1kenobi/cargo-semver-checks"]
    assert source_ref_matches_patterns(
        "https://github.com/obi1kenobi/cargo-semver-checks",
        patterns,
    )
    assert not source_ref_matches_patterns(
        "https://attacker.example/redirect?u=github.com/obi1kenobi/cargo-semver-checks",
        patterns,
    )
    assert source_ref_matches_patterns(
        "https://docs.python.org/3/whatsnew/",
        ["python.org"],
    )


def test_language_frontier_harness_holds_untrusted_https_and_screens_all_fields():
    sys.path.insert(0, str(ROOT / "scripts"))
    from validate_language_frontier_harness import classify_case

    trusted_sources = {
        source["source_id"]: source
        for source in load_json("registry/trusted-source-registry.json")["sources"]
    }

    spoofed_rust = classify_case(
        {
            "case_id": "spoofed-rust-source",
            "language": "rust",
            "source_id_or_url": (
                "https://attacker.example/redirect?"
                "u=github.com/obi1kenobi/cargo-semver-checks"
            ),
            "safe_summary": "A Rust API compatibility idea may help.",
            "why_ai_coding_may_improve": "It may catch breakage.",
            "applicability_limits": "Use only as candidate evidence.",
            "validation_or_eval_idea": "Run cargo semver-checks on a reviewed crate.",
        },
        trusted_sources,
    )
    assert spoofed_rust["routes"] == ["source_review_required"]
    assert "unknown_https_source_needs_review" in spoofed_rust["review_reasons"]

    unsafe_payload = classify_case(
        {
            "case_id": "hidden-private-data",
            "language": "python",
            "source_id_or_url": "python-core",
            "safe_summary": "A property-test idea may help.",
            "why_ai_coding_may_improve": "It checks generated rows.",
            "applicability_limits": "Do not include private rows.",
            "validation_or_eval_idea": "Manual review.",
        },
        trusted_sources,
    )
    assert unsafe_payload["routes"] == ["reject"]
    assert "unsafe_or_copied_payload" in unsafe_payload["blocked_reasons"]


def test_coding_asset_control_plane_validator_passes():
    result = subprocess.run(
        [sys.executable, "scripts/validate_coding_asset_control_plane.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "coding asset control plane valid" in result.stdout


def test_language_frontier_harness_validator_passes():
    result = subprocess.run(
        [sys.executable, "scripts/validate_language_frontier_harness.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "language frontier harness valid" in result.stdout


def test_language_frontier_refresh_prompt_is_pointer_only_and_operational():
    harness = load_json("assets/coding-harnesses/language-frontier-research/harness.json")
    prompt_path = ROOT / "assets/coding-harnesses/language-frontier-research/prompts/language-frontier-refresh.prompt.md"
    prompt = prompt_path.read_text(encoding="utf-8").lower()

    assert "prompts/language-frontier-refresh.prompt.md" in harness["entrypoints"]
    for required in [
        "trusted-source",
        "proof surface",
        "proof_surface_refs",
        "falsify",
        "python",
        "rust",
        "future-language",
        "target_dad_surface",
    ]:
        assert required in prompt
    for forbidden in [
        "do not copy third-party docs",
        "do not include private repo data",
        "do not claim state of the art",
        "do not recommend downstream adoption without local validation evidence",
    ]:
        assert forbidden in prompt


def test_suggest_coding_tactics_marks_output_candidate_only():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/suggest_coding_tactics.py",
            "--task",
            "python json boundary refactor",
            "--language",
            "python",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["candidate_only"] is True
    assert "not a governed preflight context pack" in payload["match_basis"]
    assert "Repo-local authority" in payload["authority_boundary"]


def test_coding_asset_schemas_are_registered_and_payloads_conform():
    schema_registry = load_json("registry/schema-registry.json")["schemas"]
    expected = {
        "coding_asset_registry": "schemas/coding-asset-registry.schema.json",
        "coding_tactic": "schemas/coding-tactic.schema.json",
        "language_coding_advantage_registry": (
            "schemas/language-coding-advantage-registry.schema.json"
        ),
        "preflight_profile_router": "schemas/preflight-profile-router.schema.json",
        "tactic_use_feedback": "schemas/tactic-use-feedback.schema.json",
    }
    for key, rel in expected.items():
        assert schema_registry[key] == rel

    validate(
        "schemas/coding-asset-registry.schema.json",
        load_json("registry/coding-asset-registry.json"),
    )
    validate(
        "schemas/preflight-profile-router.schema.json",
        load_json("registry/preflight-profile-router.json"),
    )
    validate(
        "schemas/tactic-use-feedback.schema.json",
        load_json("templates/tactic-use-feedback.template.json"),
    )
    validate(
        "schemas/language-coding-advantage-registry.schema.json",
        load_json("registry/language-coding-advantage-registry.json"),
    )
    tactic_schema = "schemas/coding-tactic.schema.json"
    for tactic in load_json("registry/coding-tactics-radar.json")["tactics"]:
        validate(tactic_schema, tactic)


def test_language_coding_advantage_registry_resolves_sources_and_assets():
    language_registry = load_json("registry/language-coding-advantage-registry.json")
    harness_registry = load_json("registry/coding-harness-registry.json")
    trusted_source_ids = {
        source["source_id"] for source in load_json("registry/trusted-source-registry.json")["sources"]
    }
    coding_asset_ids = {
        asset["asset_id"] for asset in load_json("registry/coding-asset-registry.json")["assets"]
    }
    reusable_asset_ids = {
        asset["asset_id"] for asset in load_json("assets/asset-registry.json")["assets"]
    }
    offering_ids = {
        offering["offering_id"]
        for offering in load_json("registry/dad-offerings-registry.json")["offerings"]
    }
    known_assets = coding_asset_ids | reusable_asset_ids | offering_ids

    proof_surface_ids = [
        item["category_id"]
        for item in language_registry["proof_surface_categories"]
    ]
    assert len(proof_surface_ids) == len(set(proof_surface_ids))
    proof_surfaces = {
        item["category_id"]: item
        for item in language_registry["proof_surface_categories"]
    }
    assert {
        "proof:syntax-compile",
        "proof:compiler-type-system",
        "proof:formatter-linter",
        "proof:structured-data-boundary",
        "proof:test-orchestration",
        "proof:property-fuzz",
        "proof:runtime-profile-trace",
        "proof:package-security",
        "proof:api-compatibility",
        "proof:agent-readable-output",
        "proof:interop-boundary",
    }.issubset(proof_surfaces)
    for proof_surface in proof_surfaces.values():
        assert proof_surface["candidate_evidence"]
        assert proof_surface["promotion_gate"]

    languages = {item["language_id"]: item for item in language_registry["languages"]}
    assert {"python", "rust", "future-language-template"}.issubset(languages)
    assert languages["python"]["recommendable"] is True
    assert languages["rust"]["recommendable"] is True
    assert languages["future-language-template"]["recommendable"] is False
    assert {
        "pytest-dev",
        "hypothesis",
        "python-type-checkers",
        "python-test-quality-frontier",
        "python-performance-profiling",
        "python-interface-boundary-codebases",
    }.issubset(languages["python"]["trusted_source_ids"])
    assert {"rust-ecosystem-curation", "rust-fuzz", "rust-test-frontier"}.issubset(
        languages["rust"]["trusted_source_ids"]
    )
    assert {"rust-api-compatibility", "rust-mutation-testing"}.issubset(
        languages["rust"]["trusted_source_ids"]
    )
    assert "rust-high-signal-codebases" in languages["rust"]["trusted_source_ids"]
    assert "rust-parser-indexing-codebases" in languages["rust"]["trusted_source_ids"]
    assert "rust-performance-measurement" in languages["rust"]["trusted_source_ids"]
    harness_ids = {harness["harness_id"] for harness in harness_registry["harnesses"]}
    assert "dad:harness:language-frontier-research" in harness_ids
    assert "dad:offering:language-frontier-research-harness" in offering_ids
    trusted_sources = {
        source["source_id"]: source
        for source in load_json("registry/trusted-source-registry.json")["sources"]
    }
    rust_ecosystem_patterns = set(trusted_sources["rust-ecosystem-curation"]["url_patterns"])
    assert {"lib.rs", "docs.rs", "blessed.rs"}.issubset(rust_ecosystem_patterns)
    assert "ty" in trusted_sources["astral"]["label"].lower()
    assert any("type-checking" in item for item in trusted_sources["astral"]["frontier_watch"])
    assert "mutants.rs" in set(trusted_sources["rust-mutation-testing"]["url_patterns"])
    assert "github.com/obi1kenobi/cargo-semver-checks" in set(
        trusted_sources["rust-api-compatibility"]["url_patterns"]
    )
    assert "github.com/tree-sitter/tree-sitter" in set(
        trusted_sources["rust-parser-indexing-codebases"]["url_patterns"]
    )
    assert "github.com/flamegraph-rs/flamegraph" in set(
        trusted_sources["rust-performance-measurement"]["url_patterns"]
    )
    assert "docs.pydantic.dev" in set(
        trusted_sources["python-interface-boundary-codebases"]["url_patterns"]
    )
    assert "coverage.readthedocs.io" in set(
        trusted_sources["python-test-quality-frontier"]["url_patterns"]
    )
    assert "github.com/psf/pyperf" in set(
        trusted_sources["python-performance-profiling"]["url_patterns"]
    )
    assert {
        "proof:structured-data-boundary",
        "proof:test-orchestration",
        "proof:runtime-profile-trace",
    }.issubset(languages["python"]["proof_surface_refs"])
    assert {
        "proof:compiler-type-system",
        "proof:property-fuzz",
        "proof:api-compatibility",
        "proof:interop-boundary",
    }.issubset(languages["rust"]["proof_surface_refs"])
    assert {
        "proof:syntax-compile",
        "proof:agent-readable-output",
        "proof:package-security",
    }.issubset(languages["future-language-template"]["proof_surface_refs"])
    python_patterns = {
        pattern["pattern_id"] for pattern in languages["python"]["ai_overlooked_patterns"]
    }
    rust_patterns = {
        pattern["pattern_id"] for pattern in languages["rust"]["ai_overlooked_patterns"]
    }
    assert "py-pattern:property-based-invariant" in python_patterns
    assert "py-pattern:static-checker-negative-contract" in python_patterns
    assert "rs-pattern:fuzz-target-at-parser-boundary" in rust_patterns
    assert "rs-pattern:isolated-test-runner-before-speed-claim" in rust_patterns
    python_operations = {
        operation["operation_id"]
        for operation in languages["python"]["ai_overlooked_operations"]
    }
    rust_operations = {
        operation["operation_id"]
        for operation in languages["rust"]["ai_overlooked_operations"]
    }
    future_operations = {
        operation["operation_id"]
        for operation in languages["future-language-template"]["ai_overlooked_operations"]
    }
    assert {
        "py-operation:structural-source-query",
        "py-operation:runtime-cost-and-failure-trace",
        "py-operation:test-collection-and-invariant-map",
        "py-operation:environment-and-tooling-census",
        "py-operation:test-strength-and-measurement-scout",
    }.issubset(python_operations)
    assert {
        "rs-operation:cargo-metadata-and-dependency-graph",
        "rs-operation:compiler-lint-doc-proof",
        "rs-operation:structured-test-and-parity-run",
        "rs-operation:fuzz-mutation-and-ub-scout",
        "rs-operation:api-compatibility-gate",
        "rs-operation:profile-before-parallelism",
    }.issubset(rust_operations)
    assert future_operations == {"future-operation:proof-surface-inventory"}
    python_guidelines = {
        item["guideline_id"] for item in languages["python"]["agent_coding_guidelines"]
    }
    rust_guidelines = {
        item["guideline_id"] for item in languages["rust"]["agent_coding_guidelines"]
    }
    assert {
        "py-guideline:shape-first-boundaries",
        "py-guideline:measure-before-rust",
        "py-guideline:contracts-as-executable-checks",
        "py-guideline:ai-legible-change-surfaces",
    }.issubset(python_guidelines)
    assert {
        "rs-guideline:compiler-owns-closed-worlds",
        "rs-guideline:leaf-tool-before-platform",
        "rs-guideline:structured-evidence-for-speed",
        "rs-guideline:ai-legible-leaf-contract",
    }.issubset(rust_guidelines)
    python_watch_targets = {
        target["target_id"] for target in languages["python"]["codebase_watch_targets"]
    }
    rust_watch_targets = {
        target["target_id"] for target in languages["rust"]["codebase_watch_targets"]
    }
    assert {
        "py-codebase:cpython-and-stdlib",
        "py-codebase:pytest-hypothesis-type-checkers",
        "py-codebase:rust-backed-python-tools",
        "py-codebase:schema-cli-agent-interfaces",
        "py-codebase:test-quality-and-profiling-tools",
    }.issubset(python_watch_targets)
    assert {
        "rs-codebase:compiler-cargo-clippy",
        "rs-codebase:scanner-parser-cli-tools",
        "rs-codebase:fuzz-security-test-frontier",
        "rs-codebase:mixed-python-rust-boundaries",
        "rs-codebase:performance-measurement-tools",
    }.issubset(rust_watch_targets)
    for language_id in ("python", "rust", "future-language-template"):
        route_ids = {
            route["harness_id"] for route in languages[language_id]["harness_routes"]
        }
        assert "dad:harness:language-frontier-research" in route_ids
    eval_payload = load_json(
        "assets/coding-harnesses/language-frontier-research/tests-or-evals/minimum-eval.json"
    )
    assert eval_payload["harness_id"] == "dad:harness:language-frontier-research"
    assert "proof_surface_refs" in eval_payload["input_contract"]
    assert any("state of the art" in claim for claim in eval_payload["must_not_claim"])
    assert any(
        "copied docs" in item
        for case in eval_payload["cases"]
        for item in case["expected"] + case["fail_if"]
    )

    for language in language_registry["languages"]:
        assert len(language["proof_surface_refs"]) == len(set(language["proof_surface_refs"]))
        assert set(language["proof_surface_refs"]).issubset(proof_surfaces)
        assert set(language["trusted_source_ids"]).issubset(trusted_source_ids)
        assert set(language["primary_assets"]).issubset(known_assets)
        assert {
            target_source_id
            for target in language["codebase_watch_targets"]
            for target_source_id in target["source_ids"]
        }.issubset(trusted_source_ids)
        for operation in language["ai_overlooked_operations"]:
            assert operation["candidate_only"] is True
            assert set(operation["source_ids"]).issubset(trusted_source_ids)
            assert not any(
                route.startswith("registry/trusted-source-registry.json")
                for route in operation["route_to"]
            )
            if language["language_id"] == "future-language-template":
                assert operation["review_status"] == "template"
                assert operation["maturity"] == "template_operation"
            else:
                assert operation["review_status"] in {
                    "candidate",
                    "installed_for_local_reuse",
                }
                assert operation["maturity"] in {"proof_operation", "scout_operation"}
        for target in language["codebase_watch_targets"]:
            for example in target["example_refs"]:
                assert set(example) == {
                    "source_id",
                    "ref",
                    "review_status",
                    "provenance_note",
                }
        assert "promotion_evidence" in language["frontier_promotion_policy"]
        assert "rejection_signals" in language["frontier_promotion_policy"]
        assert language["research_intake_packet"]["dad_need_id"] == (
            "dad:need:language-frontier-signals"
        )
        assert "copied_third_party_docs" in language["research_intake_packet"]["forbidden_fields"]
        assert "does not override repo-local style" in language_registry["authority_boundary"].lower()


def test_router_references_registered_assets_and_tactics():
    asset_ids = {
        asset["asset_id"] for asset in load_json("registry/coding-asset-registry.json")["assets"]
    }
    tactic_ids = {
        tactic["tactic_id"] for tactic in load_json("registry/coding-tactics-radar.json")["tactics"]
    }
    harness_ids = {
        harness["harness_id"] for harness in load_json("registry/coding-harness-registry.json")["harnesses"]
    }
    assert {
        "python-property-based-invariants",
        "python-static-checker-negative-contract",
        "rust-fuzz-parser-boundary",
        "rust-nextest-isolated-runner",
    }.issubset(tactic_ids)

    routes = {
        route["route_id"]: route for route in load_json("registry/preflight-profile-router.json")["routes"]
    }
    assert "route:language-frontier-research" in routes
    language_route = routes["route:language-frontier-research"]
    assert "dad:harness:language-frontier-research" in language_route["recommended_harness_ids"]
    assert {
        "language_guidance",
        "code_research",
        "harness_research",
    }.issubset(language_route["match"]["task_types"])
    assert {
        "python-property-based-invariants",
        "python-static-checker-negative-contract",
        "rust-fuzz-parser-boundary",
        "rust-nextest-isolated-runner",
    }.issubset(routes["route:test-validation-orchestration"]["recommended_tactic_ids"])
    assert {
        "dad:harness:python-test-performance-orchestration",
        "dad:harness:rust-shadow-parity",
        "dad:harness:language-frontier-research",
    }.issubset(routes["route:test-validation-orchestration"]["recommended_harness_ids"])

    for route in routes.values():
        assert set(route["required_preflight_profiles"]).issubset(asset_ids)
        assert set(route["optional_tactic_bundles"]).issubset(asset_ids)
        assert set(route["recommended_tactic_ids"]).issubset(tactic_ids)
        assert set(route.get("recommended_harness_ids", [])).issubset(harness_ids)


def test_control_plane_paths_and_templates_exist():
    for asset in load_json("registry/coding-asset-registry.json")["assets"]:
        assert (ROOT / asset["path"]).exists(), asset["asset_id"]
    for tactic in load_json("registry/coding-tactics-radar.json")["tactics"]:
        assert (ROOT / tactic["minimal_code_example_path"]).exists(), tactic["tactic_id"]
        assert (ROOT / tactic["counterexample_path"]).exists(), tactic["tactic_id"]

    managed_block = (ROOT / "templates/downstream/CODING_ASSET_MANAGED_BLOCK.md").read_text(
        encoding="utf-8"
    )
    assert "--test " in managed_block
    assert "--tests" not in managed_block
    assert "Do not copy full DAD assets" in managed_block


def test_mail_templates_conform_to_mail_schema_and_stay_candidate_only():
    mail_schema = load_json("schemas/mail-message.schema.json")
    validator_cls = validator_for(mail_schema)
    validator_cls.check_schema(mail_schema)
    validator = validator_cls(mail_schema)

    for path in sorted((ROOT / "templates/mail").glob("*.mail.template.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        validator.validate(payload)
        assert payload["review_status"] == "generated_candidate"
        assert payload["sensitivity"] in {"public", "internal"}
        text = json.dumps(payload).lower()
        assert "candidate" in text
        assert "copy full dad asset" in text or "full copied assets" in text
