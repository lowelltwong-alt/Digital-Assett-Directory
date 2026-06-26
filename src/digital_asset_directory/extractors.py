from __future__ import annotations

import mimetypes
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal, TypedDict

from .content_features import build_content_profile
from .utils import redact_sensitive_text, tokens

TEXT_EXTENSIONS = {
    ".md",
    ".mdx",
    ".txt",
    ".rst",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".cs",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".sh",
    ".ps1",
    ".bat",
    ".cmd",
    ".sql",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".xml",
    ".ttl",
    ".rdf",
    ".csv",
    ".tsv",
    ".html",
    ".css",
    ".scss",
    ".graphql",
    ".proto",
}

KEYWORD_MAP: dict[str, tuple[str, ...]] = {
    "knowledge-graph": ("knowledge graph", "graphrag", "networkx", "node", "edge", "ontology"),
    "governance": ("governance", "authority", "promotion decision", "trust zone", "policy"),
    "learning-loop": (
        "learning loop",
        "lesson learned",
        "feedback",
        "regression test",
        "exception",
    ),
    "evaluation": ("evaluation", "benchmark", "golden dataset", "gold case", "pytest", "recall@"),
    "retrieval": ("retrieval", "rag", "embedding", "rerank", "chunking", "tf-idf"),
    "provenance": ("provenance", "lineage", "source of truth", "citation", "evidence"),
    "security": ("security", "secret", "privilege", "confidential", "prompt injection", "pii"),
    "agent": ("agent", "codex", "claude code", "subagent", "swarm"),
    "skill": ("skill", "capability registry", "skill registry"),
    "orphan-radar": ("orphan radar", "orphan", "bridge candidate"),
    "research-radar": ("research radar", "watch item", "frontier signal"),
    "schema": ("json schema", "schema", "shacl"),
    "workflow": ("workflow", "orchestration", "pipeline", "preflight", "postflight"),
}

CAPABILITIES: dict[str, tuple[str, ...]] = {
    "catalog_assets": ("catalog", "inventory", "asset directory", "repository map"),
    "build_knowledge_graph": ("knowledge graph", "node", "edge", "networkx", "graph"),
    "detect_orphans": ("orphan", "disconnected", "bridge candidate"),
    "capture_lessons": ("lesson learned", "postflight", "handoff", "learning loop"),
    "validate_contracts": ("validator", "json schema", "validation", "pytest", "shacl"),
    "retrieve_context": ("retrieval", "context pack", "rag", "search"),
    "govern_agents": ("agent governance", "preflight", "allowed paths", "stop condition"),
    "score_assets": ("value score", "priority score", "ranking", "calibration"),
    "research_missing_parts": (
        "missing part",
        "github search",
        "frontier signal",
        "research radar",
    ),
    "protect_sensitive_data": ("pii", "confidential", "privilege", "redact", "access control"),
}

NEED_PATTERNS: dict[str, tuple[str, ...]] = {
    "evaluation_harness": (
        "needs evaluation",
        "missing evaluation",
        "golden dataset",
        "gold cases needed",
    ),
    "provenance": ("missing provenance", "needs provenance", "source unknown", "citation needed"),
    "human_review": ("human review required", "needs review", "unreviewed"),
    "access_control": ("access control needed", "needs entitlement", "permission model"),
    "data_source": ("missing data", "source needed", "needs source", "requires pdf"),
    "runtime_implementation": ("not implemented", "runtime needed", "future runtime"),
    "validator": ("validator needed", "validation missing", "tests missing"),
    "license_review": ("license unknown", "license review", "license needed"),
    "integration_adapter": ("adapter needed", "integration missing", "connector needed"),
}

OUTCOMES: dict[str, tuple[str, ...]] = {
    "faster_builds": ("faster", "accelerate", "reuse", "next project"),
    "lower_risk": ("risk", "safe", "fail closed", "human review"),
    "institutional_memory": ("institutional memory", "lessons learned", "decision memory"),
    "higher_discovery": ("discovery", "ideation", "synergy", "find forgotten"),
    "better_grounding": ("grounded", "citation", "source identity", "provenance"),
    "repeatable_quality": ("regression", "evaluation", "quality", "validation"),
}

ASSET_PATTERN_HINTS: dict[str, dict[str, tuple[str, ...]]] = {
    "ai_agent_workflow": {
        "asset_types": ("agent", "skill", "workflow", "prompt"),
        "tags": ("agent", "skill", "workflow", "governance"),
        "capabilities": ("govern_agents", "capture_lessons", "retrieve_context"),
        "text": ("agent", "skill", "orchestration", "handoff", "swarm", "preflight"),
    },
    "evaluation_harness": {
        "asset_types": ("evaluation", "test"),
        "tags": ("evaluation",),
        "capabilities": ("validate_contracts",),
        "text": ("evaluation", "benchmark", "golden", "pytest", "regression"),
    },
    "schema_contract_system": {
        "asset_types": ("schema", "ontology", "taxonomy"),
        "tags": ("schema", "knowledge-graph"),
        "capabilities": ("validate_contracts", "build_knowledge_graph"),
        "text": ("json schema", "schema", "ontology", "taxonomy", "contract"),
    },
    "knowledge_graph_system": {
        "asset_types": ("ontology", "taxonomy", "dataset", "code", "workflow"),
        "tags": ("knowledge-graph", "retrieval"),
        "capabilities": ("build_knowledge_graph", "retrieve_context", "catalog_assets"),
        "text": ("knowledge graph", "graph", "node", "edge", "retrieval", "context pack"),
    },
    "governed_learning_loop": {
        "asset_types": ("lesson", "workflow", "test", "document"),
        "tags": ("learning-loop", "governance"),
        "capabilities": ("capture_lessons", "govern_agents", "validate_contracts"),
        "text": ("lesson", "handoff", "postflight", "feedback", "learning loop"),
    },
    "asset_use_pay_forward_loop": {
        "asset_types": ("lesson", "workflow", "document", "test"),
        "tags": ("learning-loop", "governance", "provenance"),
        "capabilities": ("capture_lessons", "catalog_assets"),
        "text": (
            "dad_asset_use_feedback_v1",
            "asset-use feedback",
            "before-use",
            "after-use",
            "observed usefulness",
            "observed futurefulness",
            "pay-forward",
            "reuse when",
            "avoid when",
            "next-agent action",
        ),
    },
    "route_isolated_evaluation_harness": {
        "asset_types": ("evaluation", "test", "workflow", "code", "document"),
        "tags": ("evaluation", "retrieval", "workflow"),
        "capabilities": ("validate_contracts", "retrieve_context"),
        "text": (
            "route",
            "routing",
            "form classification",
            "chunking",
            "context packet",
            "scorecard",
            "gold case",
        ),
    },
    "agent_skill_graph_system": {
        "asset_types": ("agent", "skill", "workflow", "ontology", "taxonomy", "document"),
        "tags": ("agent", "skill", "knowledge-graph", "workflow"),
        "capabilities": ("govern_agents", "retrieve_context", "build_knowledge_graph"),
        "text": ("agent", "skill", "capability registry", "tool route", "handoff", "orchestration"),
    },
    "boundary_contamination_firewall": {
        "asset_types": ("workflow", "configuration", "test", "document", "schema"),
        "tags": ("security", "governance", "provenance"),
        "capabilities": ("protect_sensitive_data", "govern_agents", "validate_contracts"),
        "text": (
            "authority boundary",
            "source authority",
            "candidate-only",
            "contamination",
            "prompt injection",
            "quarantine",
        ),
    },
    "proposal_promotion_workflow": {
        "asset_types": ("workflow", "decision", "schema", "document", "code"),
        "tags": ("governance", "workflow", "provenance"),
        "capabilities": ("govern_agents", "validate_contracts", "capture_lessons"),
        "text": ("proposal", "promotion", "human review", "review gate", "approval", "rollback"),
    },
    "load_bearing_decision_review_system": {
        "asset_types": ("decision", "workflow", "document", "test", "configuration"),
        "tags": ("governance", "workflow", "provenance"),
        "capabilities": ("govern_agents", "validate_contracts", "capture_lessons"),
        "text": (
            "load-bearing decision",
            "risk tier",
            "red-team",
            "red team",
            "premortem",
            "fresh-eyes",
            "fresh eyes",
            "a/b",
            "rollback",
            "kill criteria",
        ),
    },
    "frontier_signal_intake_loop": {
        "asset_types": ("research", "document", "workflow", "dataset"),
        "tags": ("research-radar", "provenance"),
        "capabilities": ("research_missing_parts",),
        "text": (
            "frontier",
            "signal",
            "watch item",
            "literature",
            "source terms",
            "license review",
        ),
    },
    "gold_review_packet_system": {
        "asset_types": ("evaluation", "test", "dataset", "document"),
        "tags": ("evaluation",),
        "capabilities": ("validate_contracts",),
        "text": ("gold", "golden", "review packet", "label", "scorecard", "calibration"),
    },
    "duplicate_variant_preservation_system": {
        "asset_types": ("document", "code", "dataset", "archive"),
        "tags": ("provenance", "knowledge-graph"),
        "capabilities": ("catalog_assets", "build_knowledge_graph"),
        "text": ("duplicate", "variant", "delta", "cluster", "shingle", "fingerprint", "hash"),
    },
    "security_governance_gate": {
        "asset_types": ("workflow", "configuration", "test", "document"),
        "tags": ("security", "governance"),
        "capabilities": ("protect_sensitive_data", "govern_agents"),
        "text": ("security", "secret", "prompt injection", "pre-push", "policy", "gate"),
    },
    "adapter_connector": {
        "asset_types": ("code", "configuration", "workflow"),
        "tags": ("retrieval",),
        "capabilities": ("retrieve_context", "catalog_assets"),
        "text": ("adapter", "connector", "import", "export", "api", "integration"),
    },
    "model_algorithm": {
        "asset_types": ("code", "dataset", "document"),
        "tags": ("evaluation", "research-radar"),
        "capabilities": ("score_assets", "research_missing_parts"),
        "text": ("algorithm", "model", "forecast", "predict", "optimize", "scoring"),
    },
    "research_discovery": {
        "asset_types": ("research", "document", "dataset"),
        "tags": ("research-radar", "provenance"),
        "capabilities": ("research_missing_parts",),
        "text": ("research", "frontier", "discovery", "citation", "paper", "conjecture"),
    },
}


def is_probably_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name.lower() in {
        "dockerfile",
        "makefile",
        "license",
        "notice",
        "agents.md",
        "claude.md",
    }


def classify_asset(path: str) -> str:
    p = Path(path)
    name, suffix = p.name.lower(), p.suffix.lower()
    parts = {part.lower() for part in p.parts}
    if name == "__init__.py":
        return "code"
    if suffix in {".zip", ".tar", ".gz", ".7z", ".rar"}:
        return "archive"
    if name in {"pyproject.toml", "package.json", "requirements.txt", "dockerfile"} or suffix in {
        ".ini",
        ".cfg",
        ".toml",
    }:
        return "configuration"
    if "schemas" in parts or "schema" in parts or name.endswith(".schema.json"):
        return "schema"
    if "ontology" in parts or suffix in {".ttl", ".rdf", ".owl"}:
        return "ontology"
    if "taxonomy" in name or "taxonomy" in parts or "skos" in name:
        return "taxonomy"
    if suffix in {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".webp",
        ".mp3",
        ".mp4",
        ".wav",
        ".pdf",
        ".docx",
        ".pptx",
        ".xlsx",
    }:
        return "media"
    if "test" in parts or name.startswith("test_") or name.endswith("_test.py"):
        return "test"
    if "forecast" in name or "forecaster" in name or "forecasting" in parts:
        return "forecaster"
    if "algorithm" in name or "algorithms" in parts:
        return "algorithm"
    if "model" in name or "models" in parts:
        return "model"
    if "adapter" in name or "adapters" in parts:
        return "adapter"
    if "connector" in name or "connectors" in parts or "integration" in parts:
        return "connector"
    if "workflow" in name or "workflow" in parts or "workflows" in parts or ".github" in parts:
        return "workflow"
    if "prompt" in name or "prompts" in parts:
        return "prompt"
    if "skill" in name or "skills" in parts:
        return "skill"
    if "agent" in name or "agents" in parts:
        return "agent"
    if "decision" in name or "adr" in parts:
        return "decision"
    if "lesson" in name or "handoff" in name:
        return "lesson"
    if "research" in parts or "research" in name or "literature" in name:
        return "research"
    if suffix in {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".cs",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".sh",
        ".ps1",
        ".sql",
    }:
        return "code"
    if "eval" in parts or "evaluation" in name or "benchmark" in name or "golden" in name:
        return "evaluation"
    if suffix in {".json", ".jsonl", ".csv", ".tsv", ".parquet", ".sqlite", ".db"}:
        return "dataset"
    if suffix in {".md", ".mdx", ".txt", ".rst", ".html"}:
        return "document"
    return "unknown"


def extract_title(path: str, text: str) -> str:
    for line in text.splitlines()[:40]:
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()[:240]
    stem = Path(path).stem.replace("_", " ").replace("-", " ").strip()
    return stem or Path(path).name


@lru_cache(maxsize=4096)
def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Match a phrase only at word boundaries so 'agent' does not match 'management'.

    Boundaries are applied only at alphanumeric ends, so phrases ending in symbols
    (for example 'recall@' or 'tf-idf') still match in running text.
    """
    escaped = re.escape(phrase)
    prefix = r"(?<!\w)" if phrase[:1].isalnum() else ""
    suffix = r"(?!\w)" if phrase[-1:].isalnum() else ""
    return re.compile(prefix + escaped + suffix)


def _matches(text: str, mapping: dict[str, tuple[str, ...]]) -> list[str]:
    lowered = text.lower()
    return sorted(
        key
        for key, phrases in mapping.items()
        if any(_phrase_pattern(phrase).search(lowered) for phrase in phrases)
    )


class SemanticFields(TypedDict):
    """Semantic labels inferred from an asset's path and (redacted) text."""

    tags: list[str]
    capabilities: list[str]
    needs: list[str]
    outcomes: list[str]
    asset_patterns: list[str]
    pattern_evidence: dict[str, list[str]]


def infer_semantics(path: str, text: str) -> SemanticFields:
    combined = f"{path}\n{text[:50000]}"
    tags = _matches(combined, KEYWORD_MAP)
    capabilities = _matches(combined, CAPABILITIES)
    needs = _matches(combined, NEED_PATTERNS)
    outcomes = _matches(combined, OUTCOMES)
    if classify_asset(path) == "test":
        capabilities.append("validate_contracts")
        tags.append("evaluation")
    asset_type = classify_asset(path)
    combined_lower = combined.lower()
    pattern_evidence: dict[str, list[str]] = {}
    for pattern_id, hints in ASSET_PATTERN_HINTS.items():
        evidence: list[str] = []
        if asset_type in hints.get("asset_types", ()):
            evidence.append(f"asset_type:{asset_type}")
        evidence.extend(f"tag:{tag}" for tag in tags if tag in hints.get("tags", ()))
        evidence.extend(
            f"capability:{capability}"
            for capability in capabilities
            if capability in hints.get("capabilities", ())
        )
        evidence.extend(
            f"text:{phrase}" for phrase in hints.get("text", ()) if phrase in combined_lower
        )
        if len(evidence) >= 2:
            pattern_evidence[pattern_id] = sorted(set(evidence))
    return {
        "tags": sorted(set(tags)),
        "capabilities": sorted(set(capabilities)),
        "needs": sorted(set(needs)),
        "outcomes": sorted(set(outcomes)),
        "asset_patterns": sorted(pattern_evidence),
        "pattern_evidence": pattern_evidence,
    }


class ExtractedContent(SemanticFields):
    """Everything `scan_local_source` persists for a single scanned file.

    Shared by both extraction branches: `extract_bytes` (file read and decoded)
    and the skipped-content placeholder built when a file exceeds the size limit.
    Keeping it a single TypedDict documents the contract and lets mypy type the
    individual fields (title, tags, ...) instead of falling back to `object`.
    """

    title: str
    description: str
    excerpt: str
    chunk_text: str
    text_tokens: list[str]
    mime_type: str
    decode_error: bool
    redaction_count: int
    extraction_method: str
    content_profile: dict[str, object]


def extract_bytes(
    path: str,
    data: bytes,
    excerpt_chars: int,
    redact: bool = True,
    extracted_text: str | None = None,
    extraction_method: str = "direct_text",
) -> ExtractedContent:
    text = ""
    decode_error = False
    if extracted_text is not None:
        text = extracted_text
    elif is_probably_text(Path(path)):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
            decode_error = True
    # Redact secrets from the raw text once, then derive every persisted field
    # (title, description, excerpt, tokens, semantics) from the redacted copy. The
    # excerpt is not the only sink: tokens, title, and description are exported to the
    # catalog and context packs, so redacting only the excerpt would still leak.
    redaction_count = 0
    safe_text = text
    if redact and text:
        safe_text, redaction_count = redact_sensitive_text(text)
    excerpt = safe_text[:excerpt_chars]
    semantic = infer_semantics(path, safe_text)
    asset_type = classify_asset(path)
    return {
        "title": extract_title(path, safe_text),
        "description": next(
            (
                line.strip()
                for line in safe_text.splitlines()
                if line.strip() and not line.lstrip().startswith(("#", "---"))
            ),
            "",
        )[:500],
        "excerpt": excerpt,
        "chunk_text": safe_text,
        "text_tokens": sorted(tokens(f"{path} {safe_text[:20000]}"))[:1000],
        "mime_type": mimetypes.guess_type(path)[0] or "application/octet-stream",
        "decode_error": decode_error,
        "redaction_count": redaction_count,
        "extraction_method": extraction_method,
        "content_profile": build_content_profile(path, safe_text, asset_type),
        **semantic,
    }


def freshness_status(
    modified_at: str | None, stale_days: int
) -> Literal["current", "watch", "stale", "unknown"]:
    if not modified_at:
        return "unknown"
    try:
        value = datetime.fromisoformat(modified_at.replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - value.astimezone(timezone.utc)).days
    except ValueError:
        return "unknown"
    if age > stale_days:
        return "stale"
    if age > int(stale_days * 0.75):
        return "watch"
    return "current"
