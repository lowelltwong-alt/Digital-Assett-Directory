from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .models import TemplateRecord
from .utils import atomic_write_text, json_dumps, utc_now

METHODOLOGY_VERSION = "template-library-governance-v0.1"
REGISTRY_PATH = Path("registry/template-registry.json")


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _today(generated_at: str | None = None) -> date:
    if generated_at:
        parsed = _parse_date(generated_at)
        if parsed:
            return parsed
    return datetime.now().date()


def load_template_registry(repo_root: Path) -> tuple[dict[str, Any], list[TemplateRecord]]:
    path = repo_root / REGISTRY_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = [TemplateRecord.model_validate(item) for item in payload.get("templates", [])]
    return payload, records


def validate_template_registry(repo_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        payload, records = load_template_registry(repo_root)
    except Exception as exc:
        return {
            "valid": False,
            "errors": [f"Invalid template registry: {exc}"],
            "warnings": [],
            "template_count": 0,
            "reverse_dependencies": {},
        }
    ids = [record.template_id for record in records]
    if len(ids) != len(set(ids)):
        errors.append("Template registry has duplicate template IDs.")
    by_id = {record.template_id: record for record in records}
    reverse: dict[str, set[str]] = defaultdict(set)
    for record in records:
        template_path = repo_root / record.path
        if not template_path.exists():
            errors.append(f"Template path missing for {record.template_id}: {record.path}")
        for contract in record.depends_on_contracts:
            if not (repo_root / contract).exists():
                warnings.append(
                    f"Template contract dependency missing for {record.template_id}: {contract}"
                )
        for dependency_id in record.depends_on_template_ids:
            if dependency_id not in by_id:
                errors.append(
                    f"Template dependency missing for {record.template_id}: {dependency_id}"
                )
            else:
                reverse[dependency_id].add(record.template_id)
        for dependent_id in record.dependent_template_ids:
            if dependent_id not in by_id:
                errors.append(
                    f"Template dependent missing for {record.template_id}: {dependent_id}"
                )
    for record in records:
        computed = sorted(reverse.get(record.template_id, set()))
        declared = sorted(record.dependent_template_ids)
        if computed != declared:
            errors.append(
                "Template reverse dependency mismatch for "
                f"{record.template_id}: declared {declared}, computed {computed}"
            )
    if payload.get("status") != "seed":
        warnings.append("Template registry status is not `seed`; review validation expectations.")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": sorted(set(warnings)),
        "template_count": len(records),
        "reverse_dependencies": {key: sorted(values) for key, values in sorted(reverse.items())},
    }


def build_template_library_report(
    repo_root: Path, *, generated_at: str | None = None
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    _, records = load_template_registry(repo_root)
    validation = validate_template_registry(repo_root)
    current_day = _today(generated)
    due_records: list[TemplateRecord] = []
    for record in records:
        due = _parse_date(record.next_review_due_at)
        if due and due <= current_day:
            due_records.append(record)
    type_counts: dict[str, int] = {}
    for record in records:
        type_counts[record.template_type] = type_counts.get(record.template_type, 0) + 1
    dependency_rows = []
    for record in sorted(records, key=lambda item: item.template_id):
        dependency_rows.append(
            {
                "template_id": record.template_id,
                "path": record.path,
                "template_type": record.template_type,
                "depends_on_template_ids": record.depends_on_template_ids,
                "dependent_template_ids": record.dependent_template_ids,
                "depends_on_contracts": record.depends_on_contracts,
                "next_review_due_at": record.next_review_due_at,
                "upgrade_policy": record.upgrade_policy,
                "validation_commands": record.validation_commands,
            }
        )
    return {
        "schema": "template_library_governance.v1",
        "methodology_version": METHODOLOGY_VERSION,
        "generated_at": generated,
        "candidate_only": False,
        "authority_boundary": (
            "Template registry metadata is DAD-owned. Template update recommendations are review "
            "signals only and never rewrite downstream repositories automatically."
        ),
        "registry": str(REGISTRY_PATH),
        "template_count": len(records),
        "template_type_counts": dict(sorted(type_counts.items())),
        "due_for_review_count": len(due_records),
        "due_for_review": [
            {
                "template_id": record.template_id,
                "path": record.path,
                "next_review_due_at": record.next_review_due_at,
                "upgrade_policy": record.upgrade_policy,
                "upgrade_triggers": record.upgrade_triggers,
            }
            for record in sorted(due_records, key=lambda item: (item.next_review_due_at, item.template_id))
        ],
        "dependency_graph": dependency_rows,
        "validation": validation,
        "deterministic_enforcement": [
            "Every registered template path must exist.",
            "Template IDs must be unique.",
            "Template dependencies must reference registered templates.",
            "Declared dependent_template_ids must match computed reverse dependencies.",
            "Template update automation is recommend-only unless a human-approved patch or managed block policy says otherwise.",
        ],
    }


def _markdown_table(items: list[dict[str, Any]], columns: list[tuple[str, str]]) -> list[str]:
    if not items:
        return ["No rows.", ""]
    lines = [
        "| " + " | ".join(label for label, _ in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for item in items:
        values = []
        for _, key in columns:
            value = item.get(key, "")
            if isinstance(value, list):
                text = ", ".join(str(part) for part in value)
            else:
                text = str(value)
            text = text.replace("\n", " ").replace("|", "\\|")
            if key in {"template_id", "template_type", "path", "upgrade_policy"} and text:
                text = f"`{text}`"
            values.append(text)
        lines.append("| " + " | ".join(values) + " |")
    lines.append("")
    return lines


def template_library_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Template Library Governance",
        "",
        f"Generated at: `{result['generated_at']}`",
        f"Methodology: `{result['methodology_version']}`",
        f"Registry: `{result['registry']}`",
        "",
        result["authority_boundary"],
        "",
        "## Summary",
        "",
        f"- Registered templates: **{result['template_count']}**",
        f"- Type counts: `{result['template_type_counts']}`",
        f"- Due for review: **{result['due_for_review_count']}**",
        f"- Registry valid: **{result['validation']['valid']}**",
        "",
        "## Due For Review",
        "",
    ]
    lines.extend(
        _markdown_table(
            result["due_for_review"],
            [
                ("template", "template_id"),
                ("path", "path"),
                ("due", "next_review_due_at"),
                ("policy", "upgrade_policy"),
                ("triggers", "upgrade_triggers"),
            ],
        )
    )
    lines.extend(["## Dependency Graph", ""])
    lines.extend(
        _markdown_table(
            result["dependency_graph"],
            [
                ("template", "template_id"),
                ("type", "template_type"),
                ("depends on templates", "depends_on_template_ids"),
                ("dependents", "dependent_template_ids"),
                ("contract deps", "depends_on_contracts"),
                ("policy", "upgrade_policy"),
            ],
        )
    )
    lines.extend(["## Deterministic Enforcement", ""])
    lines.extend(f"- {item}" for item in result["deterministic_enforcement"])
    lines.extend(["", "## Validation Findings", ""])
    if result["validation"]["errors"]:
        lines.extend(f"- ERROR: {item}" for item in result["validation"]["errors"])
    if result["validation"]["warnings"]:
        lines.extend(f"- WARNING: {item}" for item in result["validation"]["warnings"])
    if not result["validation"]["errors"] and not result["validation"]["warnings"]:
        lines.append("No registry errors or warnings.")
    lines.extend(
        [
            "",
            "## Automation Boundary",
            "",
            "Periodic template improvement should start as a scheduled or manual check that flags due templates, dependency impacts, and suggested review paths. It must not silently rewrite repo templates or downstream repos until a separate human-approved updater exists.",
            "",
        ]
    )
    return "\n".join(lines)


def write_template_library_report(
    repo_root: Path, *, generated_at: str | None = None
) -> dict[str, Any]:
    result = build_template_library_report(repo_root, generated_at=generated_at)
    report_path = repo_root / "processed" / "reports" / "template_library.md"
    payload_path = repo_root / "processed" / "reports" / "template_library.json"
    atomic_write_text(report_path, template_library_markdown(result) + "\n")
    atomic_write_text(payload_path, json_dumps(result, pretty=True) + "\n")
    return {
        "report": str(report_path),
        "payload": str(payload_path),
        "template_count": result["template_count"],
        "due_for_review_count": result["due_for_review_count"],
        "valid": result["validation"]["valid"],
        "errors": result["validation"]["errors"],
        "warnings": result["validation"]["warnings"],
        "methodology_version": METHODOLOGY_VERSION,
    }
