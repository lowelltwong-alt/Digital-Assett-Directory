from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .ids import stable_id
from .models import ArchitectureConsultRecord
from .utils import atomic_write_text, json_dumps, redact_sensitive_text, sha256_bytes, tokens
from .utils import utc_now

METHODOLOGY_VERSION = "architecture-consult-v0.1"
AUTHORITY_BOUNDARY = (
    "Generated architecture consult only. This is consult-and-compose, not copy-and-impose. "
    "DAD advises a seed architecture pack from local candidate evidence; the new repository "
    "retains its own canon. This command does not rescan, read source repositories, call "
    "GitHub, call models, mutate source repositories, install hooks, copy source-owned facts, "
    "promote candidates to truth, or mark roadmap phases complete."
)
CONSULT_FORMULA = (
    "match_score = 100 * (0.45*source_strength + 0.35*intent_overlap + "
    "0.20*context_boost); failed safety or privacy gates are surfaced as human gates"
)

FIELD_ALIASES = {
    "new_repo_purpose": {
        "purpose",
        "what the new repo is for",
        "repo purpose",
        "goal",
        "summary",
    },
    "domain": {"domain", "subject", "field", "area"},
    "risk_level": {"risk", "risk level", "risk tier"},
    "data_sensitivity": {"data sensitivity", "sensitivity", "privacy", "data privacy"},
    "expected_users_agents": {
        "expected users",
        "users",
        "agents",
        "expected users agents",
        "expected users/agents",
    },
    "workflows_needed": {"workflows", "workflows needed", "workflow needs"},
    "validation_needs": {"validation", "validation needs", "tests", "qa"},
}

ARCHITECTURE_ROLE_GUIDANCE = {
    "agent_navigation": "Create a single AI front door, deterministic AI TOC, and machine navigation manifest.",
    "architecture_docs": "Write architecture/dataflow docs before implementing too many moving parts.",
    "schemas_contracts": "Define schemas, registries, and contracts before generated outputs depend on them.",
    "rules_governance": "Add authority boundaries, source ownership, human gates, and stop conditions.",
    "validators_tests": "Back contracts with validators, tests, and repeatable validation commands.",
    "workflow_docs": "Document workflow order, handoffs, runbooks, and smallest bounded experiments.",
    "learning_loops": "Install before/during/after/review learning and pay-forward feedback surfaces.",
    "templates_scaffolds": "Use templates only after adapting dependencies and authority language.",
    "public_safe_boundary": "Separate public-safe architecture metadata from private source facts.",
    "dataflow_normalization": "Declare inputs, normalization rules, identity keys, and export boundaries.",
    "quality_eval": "Add calibration, review packets, scorecards, and QA gates where outputs can mislead.",
}


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
    return slug.strip("-._") or "architecture-consult"


def _split_list(value: str) -> list[str]:
    parts: list[str] = []
    for chunk in re.split(r"[,;\n]", value):
        item = chunk.strip().strip("-* ").strip()
        if item:
            parts.append(item)
    return parts


def _normalize_label(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9/ ]+", " ", value).strip().lower()
    return re.sub(r"\s+", " ", cleaned)


def _field_for_label(label: str) -> str | None:
    normalized = _normalize_label(label).replace("/", " ")
    for field, aliases in FIELD_ALIASES.items():
        if normalized in aliases:
            return field
    return None


def _infer_risk(text: str) -> str:
    lower = text.lower()
    if "high risk" in lower or any(
        term in lower
        for term in ("legal", "litigation", "client", "pii", "regulated", "source mutation")
    ):
        return "high"
    if "low risk" in lower or "scratch" in lower:
        return "low"
    if any(term in lower for term in ("governance", "human gate", "validation", "agent")):
        return "medium"
    return "unknown"


def _infer_sensitivity(text: str) -> str:
    lower = text.lower()
    if any(term in lower for term in ("restricted", "private", "client", "pii", "secret")):
        return "restricted"
    if "public" in lower and "not public" not in lower:
        return "public"
    if "internal" in lower:
        return "internal"
    return "unknown"


def _canonical_risk(value: str) -> str:
    lower = value.lower()
    if "high" in lower:
        return "high"
    if "medium" in lower or "moderate" in lower:
        return "medium"
    if "low" in lower:
        return "low"
    return "unknown"


def _canonical_sensitivity(value: str) -> str:
    lower = value.lower()
    if any(term in lower for term in ("restricted", "private", "client", "pii", "secret")):
        return "restricted"
    if "internal" in lower:
        return "internal"
    if "public" in lower and "not public" not in lower:
        return "public"
    return "unknown"


def parse_architecture_intent(intent_file: Path) -> dict[str, Any]:
    raw = intent_file.read_text(encoding="utf-8")
    redacted, redaction_count = redact_sensitive_text(raw)
    parsed: dict[str, Any] = {
        "new_repo_purpose": "",
        "domain": "unknown",
        "risk_level": "unknown",
        "data_sensitivity": "unknown",
        "expected_users_agents": [],
        "workflows_needed": [],
        "validation_needs": [],
        "raw_text_redacted": redacted,
        "redaction_count": redaction_count,
    }
    for line in redacted.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^(?:[-*]\s*)?(?:#+\s*)?([^:]{2,80})\s*:\s*(.+)$", stripped)
        if not match:
            continue
        field = _field_for_label(match.group(1))
        if not field:
            continue
        value = match.group(2).strip()
        if field in {"expected_users_agents", "workflows_needed", "validation_needs"}:
            parsed[field] = _split_list(value)
        else:
            parsed[field] = value

    if not parsed["new_repo_purpose"]:
        paragraphs = [
            " ".join(part.split())
            for part in re.split(r"\n\s*\n", redacted)
            if part.strip() and ":" not in part[:90]
        ]
        parsed["new_repo_purpose"] = (paragraphs[0] if paragraphs else redacted.strip())[:300]
    if parsed["risk_level"] == "unknown":
        parsed["risk_level"] = _infer_risk(redacted)
    if parsed["data_sensitivity"] == "unknown":
        parsed["data_sensitivity"] = _infer_sensitivity(redacted)
    parsed["risk_level"] = _canonical_risk(str(parsed["risk_level"]))
    parsed["data_sensitivity"] = _canonical_sensitivity(str(parsed["data_sensitivity"]))
    if parsed["domain"] == "unknown":
        lower = redacted.lower()
        for domain in ("legal", "litigation", "bible", "logos", "ai", "data", "governance"):
            if domain in lower:
                parsed["domain"] = domain
                break
    return parsed


def _load_json(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"Missing optional input: {path.as_posix()}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        warnings.append(f"Invalid JSON optional input: {path.as_posix()}")
        return {}


def _load_jsonl(path: Path, warnings: list[str], *, limit: int = 1000) -> list[dict[str, Any]]:
    if not path.exists():
        warnings.append(f"Missing optional input: {path.as_posix()}")
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if len(rows) >= limit:
            break
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            warnings.append(f"Invalid JSONL row in optional input: {path.as_posix()}")
            break
    return rows


def _intent_text(intent: dict[str, Any]) -> str:
    return " ".join(
        [
            str(intent.get("new_repo_purpose", "")),
            str(intent.get("domain", "")),
            str(intent.get("risk_level", "")),
            str(intent.get("data_sensitivity", "")),
            " ".join(intent.get("expected_users_agents", [])),
            " ".join(intent.get("workflows_needed", [])),
            " ".join(intent.get("validation_needs", [])),
            str(intent.get("raw_text_redacted", "")),
        ]
    )


def _context_boost(record: dict[str, Any], intent: dict[str, Any]) -> float:
    architecture_type = str(record.get("architecture_type", ""))
    roles = set(record.get("component_roles", {}).keys())
    workflows = " ".join(intent.get("workflows_needed", [])).lower()
    validation = " ".join(intent.get("validation_needs", [])).lower()
    boost = 0.0
    if intent.get("risk_level") == "high" and "rules_governance" in roles:
        boost += 0.25
    if intent.get("data_sensitivity") in {"restricted", "internal"} and (
        "public_safe_boundary" in roles or "rules_governance" in roles
    ):
        boost += 0.2
    if ("agent" in workflows or "ai" in workflows) and "agent_navigation" in roles:
        boost += 0.15
    if ("learning" in workflows or "feedback" in workflows) and "learning_loops" in roles:
        boost += 0.15
    if ("schema" in validation or "contract" in validation) and "schemas_contracts" in roles:
        boost += 0.15
    if ("test" in validation or "validator" in validation) and "validators_tests" in roles:
        boost += 0.15
    if architecture_type == "governance_control_plane" and intent.get("risk_level") != "low":
        boost += 0.1
    return min(1.0, boost)


def _score_candidate(
    source_strength: float,
    overlap: float,
    context_boost: float,
) -> float:
    return round(100.0 * (0.45 * source_strength + 0.35 * overlap + 0.20 * context_boost), 2)


def _rank_reference_architectures(
    records: list[dict[str, Any]],
    intent: dict[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    intent_tokens = tokens(_intent_text(intent))
    ranked: list[dict[str, Any]] = []
    for record in records:
        record_text = " ".join(
            [
                str(record.get("architecture_label", "")),
                str(record.get("architecture_type", "")),
                " ".join(record.get("detected_patterns", [])),
                " ".join(record.get("component_roles", {}).keys()),
                " ".join(record.get("why_it_is_good_reference", [])),
                " ".join(record.get("reuse_guidance", [])),
            ]
        )
        candidate_tokens = tokens(record_text)
        shared = sorted(intent_tokens & candidate_tokens)[:12]
        overlap = len(intent_tokens & candidate_tokens) / max(1, len(intent_tokens | candidate_tokens))
        source_strength = min(1.0, float(record.get("reference_score") or 0.0) / 100.0)
        boost = _context_boost(record, intent)
        score = _score_candidate(source_strength, overlap, boost)
        ranked.append(
            {
                "reference_architecture_id": record.get("reference_architecture_id", ""),
                "architecture_label": record.get("architecture_label", ""),
                "architecture_type": record.get("architecture_type", ""),
                "match_score": score,
                "reference_score": record.get("reference_score", 0.0),
                "matched_terms": shared,
                "why_applies": _why_reference_applies(record, shared, intent),
                "reuse_parts": _reuse_parts_from_roles(record),
                "do_not_copy": [
                    "Do not copy source-owned facts, private data, repo-specific authority, or generated outputs as truth.",
                    "Do not reuse validators or workflows until inputs, outputs, side effects, and human gates are adapted.",
                ],
                "human_gates": record.get("human_gates", []),
                "component_roles": sorted(record.get("component_roles", {}).keys()),
                "candidate_only": True,
            }
        )
    return sorted(
        ranked,
        key=lambda item: (-float(item["match_score"]), item["architecture_label"]),
    )[:limit]


def _why_reference_applies(
    record: dict[str, Any], shared_terms: list[str], intent: dict[str, Any]
) -> list[str]:
    reasons = []
    if shared_terms:
        reasons.append(f"Intent overlaps on: {', '.join(shared_terms[:8])}.")
    if record.get("architecture_type") == "governance_control_plane":
        reasons.append("Governance control planes are useful seed patterns for authority, gates, and validation.")
    if intent.get("data_sensitivity") in {"restricted", "internal"}:
        reasons.append("Intent has non-public data posture, so boundary and privacy patterns matter early.")
    if intent.get("risk_level") == "high":
        reasons.append("Intent is high risk, so human gates and red-team review should be present from seed.")
    if not reasons:
        reasons.append("High-scoring reference candidate from the local catalog; verify fit before reuse.")
    return reasons


def _reuse_parts_from_roles(record: dict[str, Any]) -> list[str]:
    roles = record.get("component_roles", {})
    guidance = []
    for role in sorted(roles):
        if role in ARCHITECTURE_ROLE_GUIDANCE:
            guidance.append(ARCHITECTURE_ROLE_GUIDANCE[role])
    return guidance[:8]


def _rank_templates(
    templates: list[dict[str, Any]],
    intent: dict[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    intent_tokens = tokens(_intent_text(intent))
    required_ids = {
        "template:ai-table-of-contents",
        "template:software-repo-checklist-tree",
        "template:asset-use-feedback",
        "template:handoff-json",
        "template:lesson-json",
    }
    if intent.get("risk_level") == "high":
        required_ids.add("template:load-bearing-decision-review")
    if "governance" in _intent_text(intent).lower() or intent.get("data_sensitivity") != "public":
        required_ids.add("template:cross-repo-governance-dependency-map")
    ranked = []
    for template in templates:
        text = " ".join(
            [
                str(template.get("template_name", "")),
                str(template.get("template_type", "")),
                str(template.get("purpose", "")),
                " ".join(template.get("applies_when", [])),
                " ".join(template.get("depends_on_contracts", [])),
            ]
        )
        overlap = len(intent_tokens & tokens(text)) / max(1, len(intent_tokens | tokens(text)))
        required_boost = 0.45 if template.get("template_id") in required_ids else 0.0
        score = round(100.0 * min(1.0, 0.55 * overlap + required_boost), 2)
        if score <= 0 and template.get("template_id") not in required_ids:
            continue
        ranked.append(
            {
                "template_id": template.get("template_id", ""),
                "template_name": template.get("template_name", ""),
                "template_type": template.get("template_type", ""),
                "path": template.get("path", ""),
                "match_score": score,
                "purpose": template.get("purpose", ""),
                "depends_on_template_ids": template.get("depends_on_template_ids", []),
                "dependent_template_ids": template.get("dependent_template_ids", []),
                "depends_on_contracts": template.get("depends_on_contracts", []),
                "validation_commands": template.get("validation_commands", []),
                "authority_boundary": template.get("authority_boundary", ""),
            }
        )
    return sorted(ranked, key=lambda item: (-float(item["match_score"]), item["template_id"]))[
        :limit
    ]


def _rank_workflow_parts(
    guidance: dict[str, Any],
    intent: dict[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    rows = list(guidance.get("review_use_candidates", [])) + list(
        guidance.get("human_gated_candidates", [])
    )
    intent_tokens = tokens(_intent_text(intent))
    ranked = []
    for row in rows:
        text = " ".join(
            [
                str(row.get("part_type", "")),
                str(row.get("asset_pattern_id", "")),
                str(row.get("representative_path", "")),
                str(row.get("note", "")),
                str(row.get("useful_example_note", "")),
            ]
        )
        row_tokens = tokens(text)
        overlap = len(intent_tokens & row_tokens) / max(1, len(intent_tokens | row_tokens))
        useful_boost = 0.2 if row.get("decision") == "accept_for_review_use" else 0.05
        score = round(100.0 * min(1.0, overlap + useful_boost), 2)
        if score <= 5 and row.get("decision") != "accept_for_review_use":
            continue
        ranked.append(
            {
                "part_id": row.get("part_id", ""),
                "part_type": row.get("part_type", ""),
                "asset_pattern_id": row.get("asset_pattern_id", ""),
                "representative_path": row.get("representative_path", ""),
                "match_score": score,
                "decision": row.get("decision", ""),
                "action": row.get("action", ""),
                "safety": row.get("safety", ""),
                "dataflow_completeness": row.get("dataflow_completeness", ""),
                "note": row.get("note", ""),
            }
        )
    return sorted(ranked, key=lambda item: (-float(item["match_score"]), item["part_id"]))[:limit]


def _rank_learning_rules(
    rules: list[dict[str, Any]],
    intent: dict[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    intent_tokens = tokens(_intent_text(intent))
    ranked = []
    for rule in rules:
        text = " ".join(
            [
                str(rule.get("rule_id", "")),
                str(rule.get("title", "")),
                str(rule.get("summary", "")),
                " ".join(rule.get("trigger_terms", [])),
                " ".join(rule.get("applies_when", [])),
                " ".join(rule.get("required_actions", [])),
            ]
        )
        rule_tokens = tokens(text)
        overlap = len(intent_tokens & rule_tokens) / max(1, len(intent_tokens | rule_tokens))
        id_boost = (
            0.35
            if rule.get("rule_id")
            in {
                "learning-rule:software-repo-work-uses-checklist-tree",
                "learning-rule:load-bearing-decisions-need-risk-tier-review",
                "learning-rule:ai-entrypoint-toc-routing-required",
                "learning-rule:software-work-should-search-asset-use-pay-forward",
                "learning-rule:context-bound-lessons-need-non-applicability",
            }
            else 0.0
        )
        if intent.get("risk_level") != "high" and "load-bearing" in str(rule.get("rule_id", "")):
            id_boost = 0.15
        score = round(100.0 * min(1.0, overlap + id_boost), 2)
        if score <= 0:
            continue
        ranked.append(
            {
                "rule_id": rule.get("rule_id", ""),
                "title": rule.get("title", ""),
                "match_score": score,
                "enforcement_level": rule.get("enforcement_level", ""),
                "required_actions": rule.get("required_actions", [])[:4],
                "danger_if_ignored": rule.get("danger_if_ignored", ""),
            }
        )
    return sorted(ranked, key=lambda item: (-float(item["match_score"]), item["rule_id"]))[:limit]


def _rank_background_cues(
    rows: list[dict[str, Any]], intent: dict[str, Any], *, limit: int
) -> list[dict[str, Any]]:
    intent_tokens = tokens(_intent_text(intent))
    ranked = []
    for row in rows:
        text = " ".join(
            [
                str(row.get("connection_type", "")),
                str(row.get("why_might_matter_now", "")),
                str(row.get("why_might_be_false", "")),
                " ".join(row.get("reuse_first_edge_mapping", [])),
            ]
        )
        row_tokens = tokens(text)
        overlap = len(intent_tokens & row_tokens) / max(1, len(intent_tokens | row_tokens))
        if overlap <= 0:
            continue
        ranked.append(
            {
                "connection_candidate_id": row.get("connection_candidate_id", ""),
                "connection_type": row.get("connection_type", ""),
                "connectivity_score": row.get("connectivity_score", 0.0),
                "match_score": round(100.0 * overlap, 2),
                "why_might_matter_now": row.get("why_might_matter_now", ""),
                "why_might_be_false": row.get("why_might_be_false", ""),
            }
        )
    return sorted(
        ranked,
        key=lambda item: (-float(item["match_score"]), item["connection_candidate_id"]),
    )[:limit]


def _governance_cues(
    scope: dict[str, Any], intent: dict[str, Any], *, limit: int
) -> list[dict[str, Any]]:
    rows = scope.get("repo_candidates", [])
    if not rows or "governance" not in _intent_text(intent).lower():
        return []
    return [
        {
            "repo_key": row.get("repo_key", ""),
            "repo_label": row.get("repo_label", ""),
            "priority_score": row.get("priority_score", 0.0),
            "proposed_role": row.get("proposed_role", ""),
            "missing_surface_ids": row.get("missing_surface_ids", []),
            "human_gate_required": row.get("human_gate_required", True),
            "candidate_only": True,
        }
        for row in sorted(
            rows,
            key=lambda item: (
                -float(item.get("priority_score", 0.0)),
                item.get("repo_key", ""),
            ),
        )[:limit]
    ]


def _scan_watermark(records: list[dict[str, Any]]) -> str:
    for record in records:
        scan_id = record.get("scan_id")
        if scan_id:
            return str(scan_id)
    return "catalog-without-scan"


def _starter_structure(intent: dict[str, Any]) -> list[str]:
    structure = [
        "AI_FRONT_DOOR.md",
        "AI_TABLE_OF_CONTENTS.md",
        "MACHINE_NAVIGATION_MANIFEST.json",
        "AGENTS.md",
        "docs/ARCHITECTURE.md",
        "docs/DATA_FLOW.md",
        "docs/OPERATIONS.md",
        "docs/SECURITY_AND_PRIVACY.md",
        "schemas/",
        "registry/",
        "src/",
        "tests/",
        "scripts/",
        "roadmap/",
        ".digital-asset-directory/learning/README.md",
    ]
    text = _intent_text(intent).lower()
    if "template" in text or "seed" in text or "scaffold" in text:
        structure.append("templates/")
    if intent.get("risk_level") == "high" or intent.get("data_sensitivity") == "restricted":
        structure.extend(["governance/", "docs/LOAD_BEARING_DECISIONS.md"])
    if "workflow" in text:
        structure.append("docs/WORKFLOWS.md")
    return list(dict.fromkeys(structure))


def _validation_checklist(intent: dict[str, Any], templates: list[dict[str, Any]]) -> list[str]:
    checklist = [
        "Run repo-local unit tests.",
        "Validate schemas/contracts before generated outputs rely on them.",
        "Run AI navigation checks for AI_FRONT_DOOR.md and AI_TABLE_OF_CONTENTS.md.",
        "Run security/privacy review before any public release or external data flow.",
        "Record postflight and pay-forward feedback after the seed build.",
    ]
    if intent.get("risk_level") == "high":
        checklist.insert(0, "Run load-bearing decision review with red-team and premortem.")
    for template in templates:
        for command in template.get("validation_commands", []):
            checklist.append(str(command))
    for need in intent.get("validation_needs", []):
        checklist.append(f"Intent-specific validation: {need}")
    return list(dict.fromkeys(checklist))


def _human_gates(intent: dict[str, Any], templates: list[dict[str, Any]]) -> list[str]:
    gates = ["Human review before treating DAD consult output as repo canon."]
    if intent.get("risk_level") == "high":
        gates.append("High-risk load-bearing decision review before implementation defaults harden.")
    if intent.get("data_sensitivity") in {"restricted", "internal"}:
        gates.append("Privacy/source-authority review before copying examples or publishing artifacts.")
    if any(template.get("template_id") == "template:cross-repo-governance-dependency-map" for template in templates):
        gates.append("Human approval before installing governance maps, mirrors, validators, or hooks.")
    return gates


def _reuse_plan(matches: list[dict[str, Any]], templates: list[dict[str, Any]]) -> list[str]:
    plan = [
        "Reuse the shape of matched reference architectures, not their source-owned facts.",
        "Start with AI navigation, authority boundaries, schema contracts, validation, and learning loop surfaces.",
    ]
    if matches:
        plan.append(f"Use `{matches[0]['architecture_label']}` as the first comparison pattern.")
    if templates:
        plan.append(
            "Apply template dependencies in this order: "
            + ", ".join(template["template_id"] for template in templates[:5])
            + "."
        )
    return plan


def _not_to_copy(intent: dict[str, Any]) -> list[str]:
    items = [
        "Do not copy source repo canon, private rows, client facts, secrets, or generated candidate outputs as truth.",
        "Do not copy validators without adapting inputs, outputs, fixtures, side effects, and failure behavior.",
        "Do not install hooks, governance maps, or downstream managed blocks without explicit repo approval.",
        "Do not let DAD's recommendation override the new repo's local source-of-truth and design authority.",
    ]
    if intent.get("data_sensitivity") == "restricted":
        items.append("Do not include sensitive examples in seed docs; use redacted structural examples only.")
    return items


def _consult_slug(intent_file: Path, intent: dict[str, Any]) -> str:
    purpose = str(intent.get("new_repo_purpose") or intent_file.stem)
    return _safe_slug(purpose[:64] or intent_file.stem)


def _default_reference_records(repo_root: Path, warnings: list[str]) -> list[dict[str, Any]]:
    jsonl = repo_root / "processed" / "learning" / "reference_architecture_candidates.jsonl"
    records = _load_jsonl(jsonl, warnings, limit=500)
    if records:
        return records
    payload = _load_json(repo_root / "processed" / "reports" / "reference_architectures.json", warnings)
    return list(payload.get("records", []))


def build_architecture_consult(
    repo_root: Path,
    intent_file: Path,
    *,
    limit: int = 10,
    generated_at: str | None = None,
) -> ArchitectureConsultRecord:
    generated = generated_at or utc_now()
    warnings: list[str] = []
    intent = parse_architecture_intent(intent_file)
    intent_hash = sha256_bytes(intent["raw_text_redacted"].encode("utf-8"))
    if intent.get("redaction_count"):
        warnings.append("Intent file contained secret-like text; output uses redacted text and privacy gate fails.")
    reference_records = _default_reference_records(repo_root, warnings)
    scan_id = _scan_watermark(reference_records)
    template_registry = _load_json(repo_root / "registry" / "template-registry.json", warnings)
    workflow_guidance = _load_json(
        repo_root / "processed" / "workflow_parts" / "workflow_part_usage_guidance.json",
        warnings,
    )
    background_rows = _load_jsonl(
        repo_root / "processed" / "learning" / "background_connection_candidates.jsonl",
        warnings,
        limit=1000,
    )
    governance_scope = _load_json(
        repo_root / "processed" / "reports" / "governance_map_adoption_scope.json",
        warnings,
    )
    learning_registry = _load_json(repo_root / "registry" / "learning-rule-registry.json", warnings)

    reference_matches = _rank_reference_architectures(reference_records, intent, limit=limit)
    templates = _rank_templates(template_registry.get("templates", []), intent, limit=max(limit, 8))
    workflow_parts = _rank_workflow_parts(workflow_guidance, intent, limit=limit)
    learning_rules = _rank_learning_rules(learning_registry.get("rules", []), intent, limit=limit)
    background_cues = _rank_background_cues(background_rows, intent, limit=min(5, limit))
    governance_cues = _governance_cues(governance_scope, intent, limit=min(5, limit))
    gates = {
        "intent_present_gate": bool(intent.get("new_repo_purpose")),
        "source_boundary_gate": True,
        "privacy_gate": int(intent.get("redaction_count", 0)) == 0,
        "no_source_mutation_gate": True,
        "no_external_call_gate": True,
        "candidate_only_gate": True,
    }
    gate_failures = [key for key, value in gates.items() if not value]
    template_dependencies = [
        {
            "template_id": template["template_id"],
            "depends_on_template_ids": template.get("depends_on_template_ids", []),
            "dependent_template_ids": template.get("dependent_template_ids", []),
            "depends_on_contracts": template.get("depends_on_contracts", []),
        }
        for template in templates
    ]
    consult_id = stable_id(
        "architecture-consult",
        intent_hash,
        str(intent_file),
        scan_id,
        METHODOLOGY_VERSION,
    )
    return ArchitectureConsultRecord(
        consult_id=consult_id,
        intent_file=str(intent_file),
        intent_hash=intent_hash,
        new_repo_purpose=str(intent.get("new_repo_purpose") or "unknown"),
        domain=str(intent.get("domain") or "unknown"),
        risk_level=str(intent.get("risk_level") or "unknown"),  # type: ignore[arg-type]
        data_sensitivity=str(intent.get("data_sensitivity") or "unknown"),  # type: ignore[arg-type]
        expected_users_agents=list(intent.get("expected_users_agents", [])),
        workflows_needed=list(intent.get("workflows_needed", [])),
        validation_needs=list(intent.get("validation_needs", [])),
        matched_reference_architectures=reference_matches,
        recommended_templates=templates,
        recommended_workflow_parts=workflow_parts,
        background_connection_cues=background_cues,
        governance_map_cues=governance_cues,
        learning_rule_cues=learning_rules,
        what_to_reuse=_reuse_plan(reference_matches, templates),
        what_not_to_copy=_not_to_copy(intent),
        architecture_combination_plan=_architecture_combination_plan(intent, reference_matches),
        starter_repo_structure=_starter_structure(intent),
        template_dependencies=template_dependencies,
        validation_checklist=_validation_checklist(intent, templates),
        required_human_gates=_human_gates(intent, templates),
        gates=gates,
        gate_failures=gate_failures,
        warnings=warnings,
        authority_boundary=AUTHORITY_BOUNDARY,
        evidence={
            "methodology_version": METHODOLOGY_VERSION,
            "formula": CONSULT_FORMULA,
            "inputs_read": [
                str(intent_file),
                "processed/learning/reference_architecture_candidates.jsonl",
                "registry/template-registry.json",
                "processed/workflow_parts/workflow_part_usage_guidance.json",
                "processed/learning/background_connection_candidates.jsonl",
                "processed/reports/governance_map_adoption_scope.json",
                "registry/learning-rule-registry.json",
                "docs/SOFTWARE_REPO_CHECKLIST_TREE.md",
            ],
            "intentionally_not_done": [
                "source repo content reads",
                "fresh scans",
                "GitHub or external API calls",
                "model calls",
                "target repo mutation",
                "template installation",
                "candidate promotion",
            ],
            "intent_redaction_count": intent.get("redaction_count", 0),
        },
        methodology_version=METHODOLOGY_VERSION,
        generated_at=generated,
        scan_id=scan_id,
    )


def _architecture_combination_plan(
    intent: dict[str, Any], matches: list[dict[str, Any]]
) -> list[str]:
    plan = [
        "Start with DAD's AI navigation pattern so future agents have one front door and tagged TOC routing.",
        "Add governance and source-authority boundaries before adding automation or generated outputs.",
        "Define schemas/contracts and validators together; do not let generated outputs outrun contracts.",
        "Install a files-only learning/pay-forward loop so future usage feedback returns to DAD as data.",
        "Use the software repo checklist tree to choose only the branches that match this repo's risk and domain.",
    ]
    if intent.get("data_sensitivity") in {"restricted", "internal"}:
        plan.insert(2, "Add a public-safe/private-source boundary before examples, reports, or exports.")
    if intent.get("risk_level") == "high":
        plan.insert(1, "Run load-bearing decision review before hardening defaults or repo-wide rules.")
    if matches:
        plan.append(
            f"Compare against `{matches[0]['architecture_label']}` for component roles, then adapt locally."
        )
    return plan


def architecture_consult_markdown(record: ArchitectureConsultRecord) -> str:
    lines = [
        "# Architecture Consult",
        "",
        f"Generated at: `{record.generated_at}`",
        f"Methodology: `{record.methodology_version}`",
        f"Scan watermark: `{record.scan_id}`",
        "",
        record.authority_boundary,
        "",
        "## Intent",
        "",
        f"- Purpose: {record.new_repo_purpose}",
        f"- Domain: `{record.domain}`",
        f"- Risk level: `{record.risk_level}`",
        f"- Data sensitivity: `{record.data_sensitivity}`",
        f"- Expected users/agents: {', '.join(record.expected_users_agents) or 'not specified'}",
        f"- Workflows needed: {', '.join(record.workflows_needed) or 'not specified'}",
        f"- Validation needs: {', '.join(record.validation_needs) or 'not specified'}",
        f"- Gates: `{', '.join(record.gate_failures) or 'pass'}`",
        "",
        "## Best Matching Reference Architectures",
        "",
    ]
    lines.extend(_table(record.matched_reference_architectures, [
        ("score", "match_score"),
        ("reference", "architecture_label"),
        ("type", "architecture_type"),
        ("terms", "matched_terms"),
    ]))
    for match in record.matched_reference_architectures[:5]:
        lines.extend(
            [
                f"### {match['architecture_label']}",
                "",
                f"- Match score: **{float(match['match_score']):.2f}**",
                f"- Reference score: **{float(match.get('reference_score') or 0):.2f}**",
                f"- Component roles: `{', '.join(match.get('component_roles', []))}`",
                "",
                "Why it applies:",
                "",
                *[f"- {item}" for item in match.get("why_applies", [])],
                "",
                "Parts to reuse:",
                "",
                *[f"- {item}" for item in match.get("reuse_parts", [])],
                "",
            ]
        )
    lines.extend(["## What To Reuse", ""])
    lines.extend(f"- {item}" for item in record.what_to_reuse)
    lines.extend(["", "## What Not To Copy", ""])
    lines.extend(f"- {item}" for item in record.what_not_to_copy)
    lines.extend(["", "## Unique Architecture Combination", ""])
    lines.extend(f"- {item}" for item in record.architecture_combination_plan)
    lines.extend(["", "## Starter Repo Structure", ""])
    lines.extend(f"- `{item}`" for item in record.starter_repo_structure)
    lines.extend(["", "## Template Dependencies", ""])
    lines.extend(_table(record.template_dependencies, [
        ("template", "template_id"),
        ("depends on templates", "depends_on_template_ids"),
        ("depends on contracts", "depends_on_contracts"),
    ]))
    lines.extend(["## Workflow Parts", ""])
    lines.extend(_table(record.recommended_workflow_parts, [
        ("score", "match_score"),
        ("part", "part_type"),
        ("pattern", "asset_pattern_id"),
        ("action", "action"),
    ]))
    lines.extend(["## Learning Rules", ""])
    lines.extend(_table(record.learning_rule_cues, [
        ("score", "match_score"),
        ("rule", "rule_id"),
        ("title", "title"),
        ("level", "enforcement_level"),
    ]))
    lines.extend(["## Required Human Gates", ""])
    lines.extend(f"- {gate}" for gate in record.required_human_gates)
    lines.extend(["", "## Validation Checklist", ""])
    lines.extend(f"- {item}" for item in record.validation_checklist)
    lines.extend(["", "## Warnings", ""])
    if record.warnings:
        lines.extend(f"- {warning}" for warning in record.warnings)
    else:
        lines.append("No warnings.")
    lines.extend(["", "## Red Team", ""])
    lines.extend(
        [
            "- This consult can overfit to file names and generated candidates; verify before building.",
            "- Cross-repo inspiration is not permission to copy source-owned implementation.",
            "- Missing generated inputs reduce recommendation quality; regenerate only through approved commands.",
            "- The new repo owns its own canon; DAD supplies seed advice only.",
            "",
        ]
    )
    return "\n".join(lines)


def architecture_consult_seed_prompt(record: ArchitectureConsultRecord) -> str:
    references = "\n".join(
        f"- {match['architecture_label']} ({match['architecture_type']}), match {match['match_score']}"
        for match in record.matched_reference_architectures[:5]
    )
    templates = "\n".join(
        f"- {template['template_id']} -> {template['path']}"
        for template in record.recommended_templates[:8]
    )
    structure = "\n".join(f"- {item}" for item in record.starter_repo_structure)
    gates = "\n".join(f"- {item}" for item in record.required_human_gates)
    return "\n".join(
        [
            "You are seeding a new repository using Digital Asset Directory architecture consult output.",
            "",
            "Authority boundary:",
            record.authority_boundary,
            "",
            "Intent:",
            f"- Purpose: {record.new_repo_purpose}",
            f"- Domain: {record.domain}",
            f"- Risk level: {record.risk_level}",
            f"- Data sensitivity: {record.data_sensitivity}",
            "",
            "Best matching reference architectures:",
            references or "- No reference architectures matched; use defaults and ask for review.",
            "",
            "Recommended templates:",
            templates or "- No templates matched; use AI navigation and checklist defaults.",
            "",
            "Starter structure:",
            structure,
            "",
            "Human gates:",
            gates or "- Normal source-authority review.",
            "",
            "Instructions:",
            "- Reuse architecture shapes and dependency order, not source-owned facts.",
            "- Adapt every template to the new repo's own authority and domain.",
            "- Put scope, caveats, and candidate-only status inside durable artifacts.",
            "- Do not call GitHub, install hooks, or mutate other repos unless explicitly approved.",
            "- Before completion, run the validation checklist from the consult report.",
            "",
        ]
    )


def _table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> list[str]:
    if not rows:
        return ["No rows.", ""]
    lines = [
        "| " + " | ".join(label for label, _ in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        cells = []
        for _, key in columns:
            value = row.get(key, "")
            if isinstance(value, float):
                text = f"{value:.2f}"
            elif isinstance(value, list):
                text = ", ".join(str(item) for item in value[:4])
            else:
                text = str(value)
            cells.append(text.replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def write_architecture_consult_outputs(
    repo_root: Path,
    intent_file: Path,
    *,
    limit: int = 10,
    generated_at: str | None = None,
) -> dict[str, Any]:
    record = build_architecture_consult(
        repo_root,
        intent_file,
        limit=limit,
        generated_at=generated_at,
    )
    slug = _consult_slug(intent_file, record.model_dump(mode="json"))
    output_dir = repo_root / "processed" / "reports" / "architecture_consults"
    markdown_path = output_dir / f"{slug}.md"
    json_path = output_dir / f"{slug}.json"
    seed_prompt_path = output_dir / f"{slug}_seed_prompt.md"
    record.seed_prompt_path = str(seed_prompt_path)
    atomic_write_text(markdown_path, architecture_consult_markdown(record) + "\n")
    atomic_write_text(json_path, json_dumps(record.model_dump(mode="json"), pretty=True) + "\n")
    atomic_write_text(seed_prompt_path, architecture_consult_seed_prompt(record))
    return {
        "report": str(markdown_path),
        "payload": str(json_path),
        "seed_prompt": str(seed_prompt_path),
        "consult_id": record.consult_id,
        "candidate_only": True,
        "methodology_version": METHODOLOGY_VERSION,
        "matched_reference_architecture_count": len(record.matched_reference_architectures),
        "recommended_template_count": len(record.recommended_templates),
        "warnings": record.warnings,
    }
