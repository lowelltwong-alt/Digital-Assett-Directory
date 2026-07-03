from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
HARNESS_ID = "dad:harness:language-frontier-research"
HARNESS_DIR = ROOT / "assets" / "coding-harnesses" / "language-frontier-research"
EXAMPLES = HARNESS_DIR / "examples" / "frontier-intake-cases.json"
MINIMUM_EVAL = HARNESS_DIR / "tests-or-evals" / "minimum-eval.json"
TRUSTED_SOURCES = ROOT / "registry" / "trusted-source-registry.json"
LANGUAGE_REGISTRY = ROOT / "registry" / "language-coding-advantage-registry.json"

FORBIDDEN_PAYLOAD_TERMS = {
    "copied documentation",
    "copied docs",
    "copied source",
    "private repo rows",
    "private rows",
    "credentials",
    "raw logs",
    "long source",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source_ref_matches_patterns(ref: str, url_patterns: list[str]) -> bool:
    if not ref.startswith("https://"):
        return False
    parsed = urlparse(ref)
    ref_host = (parsed.hostname or "").casefold()
    ref_path = parsed.path.strip("/").casefold()
    for pattern in url_patterns:
        pattern_text = pattern.removeprefix("https://").strip("/").casefold()
        pattern_host, _, pattern_path = pattern_text.partition("/")
        host_matches = ref_host == pattern_host or ref_host.endswith(f".{pattern_host}")
        if not host_matches:
            continue
        if pattern_path and not ref_path.startswith(pattern_path):
            continue
        return True
    return False


def is_trusted_source_ref(source: str, trusted_sources: dict[str, dict[str, Any]]) -> bool:
    if source in trusted_sources:
        return True
    return any(
        source_ref_matches_patterns(
            source,
            [str(pattern) for pattern in trusted_source.get("url_patterns", [])],
        )
        for trusted_source in trusted_sources.values()
    )


def classify_case(case: dict[str, Any], trusted_sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source = str(case.get("source_id_or_url", "")).strip()
    language = str(case.get("language", "")).strip().lower()
    known_language = language in {"python", "rust"}
    summary = str(case.get("safe_summary", "")).lower()
    validation = str(case.get("validation_or_eval_idea", "")).strip()
    payload_text = " ".join(
        str(case.get(field, ""))
        for field in [
            "safe_summary",
            "why_ai_coding_may_improve",
            "applicability_limits",
            "validation_or_eval_idea",
        ]
    ).lower()
    routes: list[str] = []
    blocked_reasons: list[str] = []
    review_reasons: list[str] = []

    trusted_source = is_trusted_source_ref(source, trusted_sources)
    if not trusted_source and not source.startswith("https://"):
        blocked_reasons.append("unknown_source_without_url")
    elif not trusted_source and known_language:
        review_reasons.append("unknown_https_source_needs_review")
    elif not trusted_source:
        review_reasons.append("future_language_source_needs_review")
    if not validation:
        blocked_reasons.append("missing_validation_or_eval_idea")
    if any(term in payload_text for term in FORBIDDEN_PAYLOAD_TERMS):
        blocked_reasons.append("unsafe_or_copied_payload")
    if "benchmark" in summary and "same-workload" not in validation.lower():
        blocked_reasons.append("benchmark_without_same_workload_evidence")

    if blocked_reasons:
        routes.append("reject")
    elif review_reasons and known_language:
        routes.append("source_review_required")
    elif language == "python":
        routes.extend(
            [
                "assets/python-ai-advantage-preflight",
                "dad:harness:language-frontier-research",
            ]
        )
    elif language == "rust":
        routes.extend(
            [
                "assets/rust-buildout-guide",
                "dad:harness:language-frontier-research",
            ]
        )
        if "fuzz" in summary or "parser" in summary:
            routes.append("dad:harness:rust-shadow-parity")
    else:
        routes.extend(
            [
                "registry/language-coding-advantage-registry.json",
                "dad:harness:language-frontier-research",
            ]
        )
        if review_reasons:
            routes.append("source_review_required")

    return {
        "case_id": case.get("case_id"),
        "routes": routes,
        "blocked_reasons": blocked_reasons,
        "review_reasons": review_reasons,
    }


def main() -> int:
    errors: list[str] = []
    trusted_sources = {
        source["source_id"]: source
        for source in load_json(TRUSTED_SOURCES).get("sources", [])
    }
    proof_surface_ids = {
        item["category_id"]
        for item in load_json(LANGUAGE_REGISTRY).get("proof_surface_categories", [])
    }
    harness = load_json(HARNESS_DIR / "harness.json")
    examples = load_json(EXAMPLES)
    minimum_eval = load_json(MINIMUM_EVAL)

    for label, payload in {
        "harness": harness,
        "examples": examples,
        "minimum_eval": minimum_eval,
    }.items():
        if payload.get("harness_id") != HARNESS_ID:
            errors.append(f"{label} uses wrong harness_id: {payload.get('harness_id')}")

    eval_case_ids = {case["case_id"] for case in minimum_eval.get("cases", [])}
    required_eval_cases = {
        "accept-python-property-boundary-as-candidate",
        "hold-rust-speed-claim-without-parity",
        "block-copied-docs-or-private-data",
        "future-language-needs-proof-tool",
    }
    missing_eval_cases = sorted(required_eval_cases - eval_case_ids)
    if missing_eval_cases:
        errors.append(f"minimum eval missing required cases: {missing_eval_cases}")
    if "proof_surface_refs" not in minimum_eval.get("input_contract", []):
        errors.append("minimum eval input_contract missing proof_surface_refs")

    results = [
        classify_case(case, trusted_sources)
        for case in examples.get("cases", [])
    ]
    result_by_case = {str(result["case_id"]): result for result in results}
    for case in examples.get("cases", []):
        case_id = str(case.get("case_id"))
        proof_refs = [str(item) for item in case.get("proof_surface_refs", [])]
        if not proof_refs:
            errors.append(f"{case_id} missing proof_surface_refs")
        unknown_proof_refs = sorted(set(proof_refs) - proof_surface_ids)
        if unknown_proof_refs:
            errors.append(f"{case_id} has unknown proof_surface_refs: {unknown_proof_refs}")
        expected_routes = set(case.get("expected_route", []))
        actual_routes = set(result_by_case[case_id]["routes"])
        if not expected_routes.issubset(actual_routes):
            errors.append(
                f"{case_id} expected routes {sorted(expected_routes)} "
                f"not in actual routes {sorted(actual_routes)}"
            )

    if "reject" not in result_by_case.get("benchmark-only-rust-rewrite", {}).get("routes", []):
        errors.append("benchmark-only-rust-rewrite did not reject")
    if result_by_case.get("benchmark-only-rust-rewrite", {}).get("blocked_reasons") != [
        "unknown_source_without_url",
        "missing_validation_or_eval_idea",
    ]:
        errors.append("benchmark-only-rust-rewrite rejection reasons changed")

    must_not_claim = " ".join(minimum_eval.get("must_not_claim", [])).lower()
    for phrase in [
        "state of the art",
        "authorizes copying",
        "overrides repo-local",
    ]:
        if phrase not in must_not_claim:
            errors.append(f"minimum eval must_not_claim missing phrase: {phrase}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"language frontier harness valid: {len(results)} example cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
