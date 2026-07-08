from __future__ import annotations

from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from .transport import data_relative_path
from .utils import atomic_write_text, utc_now, write_json

PUBLIC_SAFE_SOURCE_SWEEP_METHOD = "public-safe-source-sweep-v1"

DATA_LANE_PARTS = {
    "data",
    "raw",
    "source_page_snapshots",
    "manual_rosters",
    "snapshots",
    "pages",
    "linkedin",
}
OUTPUT_LANE_PARTS = {
    "output",
    "outputs",
    "export",
    "exports",
    "stakeholder_package",
    "recruiting_intelligence",
    "organized",
    "dashboards",
}
CACHE_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".nox",
    ".tox",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
}

ROW_DATA_SUFFIXES = {
    ".bak",
    ".csv",
    ".db",
    ".docx",
    ".feather",
    ".html",
    ".htm",
    ".jsonl",
    ".parquet",
    ".pdf",
    ".pickle",
    ".pkl",
    ".sqlite",
    ".sqlite3",
    ".tsv",
    ".txt",
    ".xls",
    ".xlsx",
    ".zip",
}
SAFE_DOC_SUFFIXES = {".md", ".rst"}
SAFE_CODE_SUFFIXES = {".py", ".ps1", ".sh", ".sql"}
SAFE_CONFIG_SUFFIXES = {".toml", ".yaml", ".yml"}


def _relative(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.name


def _parts(relative_path: str) -> tuple[str, ...]:
    return tuple(part.lower() for part in PurePosixPath(relative_path).parts)


def _has_part(relative_path: str, values: set[str]) -> bool:
    return bool(set(_parts(relative_path)) & values)


def _role_for_safe_path(relative_path: str, suffix: str) -> str:
    normalized = relative_path.lower()
    name = PurePosixPath(normalized).name
    if "test" in normalized or name.startswith("test_"):
        return "test_or_validation_gate"
    if any(term in normalized for term in ("workflow", "roadmap", "handoff", "premortem")):
        return "workflow_or_governance_doc"
    if any(term in normalized for term in ("identity", "data_dictionary", "schema", "model")):
        return "identity_or_schema_design"
    if any(term in normalized for term in ("opportunity", "signal", "recruit", "acquisition", "liftout")):
        return "opportunity_signal_design"
    if any(term in normalized for term in ("scrape", "roster", "bio", "source", "extract")):
        return "source_intake_or_extraction_code"
    if suffix in SAFE_CONFIG_SUFFIXES:
        return "configuration_or_manifest"
    if suffix in SAFE_CODE_SUFFIXES:
        return "implementation_code"
    return "architecture_doc"


def _is_safe_json(relative_path: str) -> bool:
    normalized = relative_path.lower()
    return any(
        term in normalized
        for term in (
            "schema",
            "manifest",
            "config",
            "registry",
            "taxonomy",
            "source",
            "roadmap",
        )
    )


def classify_public_safe_path(relative_path: str) -> dict[str, str]:
    suffix = PurePosixPath(relative_path).suffix.lower()
    if _has_part(relative_path, CACHE_PARTS):
        return {"decision": "quarantine", "reason": "runtime_cache_or_dependency_noise"}
    if _has_part(relative_path, OUTPUT_LANE_PARTS):
        return {"decision": "quarantine", "reason": "generated_output_or_export_lane"}
    if _has_part(relative_path, DATA_LANE_PARTS):
        return {"decision": "quarantine", "reason": "row_data_or_source_snapshot_lane"}
    if suffix in ROW_DATA_SUFFIXES:
        return {"decision": "quarantine", "reason": "row_data_bulk_export_or_scraped_content"}
    if suffix == ".json" and not _is_safe_json(relative_path):
        return {"decision": "quarantine", "reason": "structured_data_default_private"}
    if suffix in SAFE_DOC_SUFFIXES | SAFE_CODE_SUFFIXES | SAFE_CONFIG_SUFFIXES or suffix == ".json":
        return {
            "decision": "include",
            "reason": "workflow_code_schema_or_governance_metadata_only",
        }
    return {"decision": "quarantine", "reason": "unsupported_or_private_by_default"}


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, str, str]:
    role_priority = {
        "workflow_or_governance_doc": 0,
        "identity_or_schema_design": 1,
        "opportunity_signal_design": 2,
        "test_or_validation_gate": 3,
        "source_intake_or_extraction_code": 4,
        "configuration_or_manifest": 5,
        "implementation_code": 6,
        "architecture_doc": 7,
    }
    return (
        role_priority.get(str(candidate["role"]), 99),
        str(candidate["relative_path"]).lower(),
        str(candidate["relative_path"]),
    )


def build_public_safe_source_sweep(
    source_path: Path,
    *,
    source_id: str,
    review_sample: int = 50,
    max_files: int | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    base = source_path.resolve()
    if not base.exists():
        raise FileNotFoundError(f"Source path not found: {source_path}")
    generated = generated_at or utc_now()
    extensions: Counter[str] = Counter()
    quarantine_reasons: Counter[str] = Counter()
    safe_role_counts: Counter[str] = Counter()
    safe_candidates: list[dict[str, Any]] = []
    observed_files = 0
    truncated = False

    for path in sorted(base.rglob("*"), key=lambda p: str(p)):
        if path.is_symlink() or not path.is_file():
            continue
        if max_files is not None and observed_files >= max_files:
            truncated = True
            break
        observed_files += 1
        rel = _relative(path, base)
        suffix = path.suffix.lower() or "[none]"
        extensions[suffix] += 1
        decision = classify_public_safe_path(rel)
        if decision["decision"] != "include":
            quarantine_reasons[decision["reason"]] += 1
            continue
        try:
            stat = path.stat()
        except OSError:
            quarantine_reasons["metadata_unreadable"] += 1
            continue
        role = _role_for_safe_path(rel, path.suffix.lower())
        safe_role_counts[role] += 1
        safe_candidates.append(
            {
                "relative_path": rel,
                "suffix": path.suffix.lower() or "[none]",
                "size_bytes": stat.st_size,
                "role": role,
                "decision": "metadata_only_candidate",
                "privacy_note": "File contents were not read; this path is a candidate architecture/workflow/code asset only.",
            }
        )

    safe_candidates = sorted(safe_candidates, key=_candidate_sort_key)
    sample = safe_candidates[:review_sample]
    return {
        "schema_version": "0.1.0",
        "methodology": PUBLIC_SAFE_SOURCE_SWEEP_METHOD,
        "source_id": source_id,
        "source_root_label": base.name,
        "source_path_redacted": True,
        "generated_at": generated,
        "review_status": "generated_candidate",
        "authority_boundary": (
            "Generated metadata-only sweep; source folder remains authoritative; no scraped "
            "row data, source snapshots, exports, or source files are imported into tracked DAD evidence."
        ),
        "privacy_boundary": {
            "file_contents_read": False,
            "sqlite_opened": False,
            "row_level_data_imported": False,
            "absolute_source_path_tracked": False,
            "tracked_evidence_allowed": [
                "methodology",
                "safe-scope decision",
                "aggregate category counts",
                "workflow and architecture pattern descriptions",
            ],
            "tracked_evidence_forbidden": [
                "scraped person rows",
                "raw source snapshots",
                "SQLite, CSV, XLSX, PDF, DOCX, ZIP, HTML, or TXT contents",
                "personal profile facts",
                "candidate recruiting or opportunity leads about specific people",
            ],
        },
        "observed": {
            "files_seen": observed_files,
            "truncated": truncated,
            "extension_counts": dict(sorted(extensions.items())),
            "metadata_only_candidate_files": len(safe_candidates),
            "quarantined_files": sum(quarantine_reasons.values()),
            "quarantine_reason_counts": dict(sorted(quarantine_reasons.items())),
            "safe_role_counts": dict(sorted(safe_role_counts.items())),
        },
        "safe_candidate_sample": sample,
        "next_review_questions": [
            "Which workflow/code/schema candidates should become curated DAD evidence?",
            "Which scraper variants should be clustered for delta review before reuse?",
            "Which private data lanes need a separate non-public catalog or encrypted store?",
            "Which source terms or privacy constraints govern any future row-level private scan?",
        ],
    }


def public_safe_source_sweep_markdown(record: dict[str, Any]) -> str:
    observed = record["observed"]
    lines = [
        "# Public-Safe Source Sweep",
        "",
        "Generated candidate report only. This report is metadata-only and does not import scraped data.",
        "",
        f"- Methodology: `{record['methodology']}`",
        f"- Source id: `{record['source_id']}`",
        f"- Source label: `{record['source_root_label']}`",
        f"- Generated at: `{record['generated_at']}`",
        f"- Review status: `{record['review_status']}`",
        f"- Files seen: **{observed['files_seen']}**",
        f"- Metadata-only candidate files: **{observed['metadata_only_candidate_files']}**",
        f"- Quarantined files: **{observed['quarantined_files']}**",
        f"- Truncated: **{observed['truncated']}**",
        "",
        "## Privacy Boundary",
        "",
        "- File contents read: **False**",
        "- SQLite opened: **False**",
        "- Row-level data imported: **False**",
        "- Absolute source path tracked: **False**",
        "",
        "Tracked evidence may describe methodology, aggregate categories, and reusable workflow patterns. It must not include scraped person rows, source snapshots, profile facts, or candidate recruiting leads about specific people.",
        "",
        "## Quarantine Summary",
        "",
    ]
    for reason, count in observed["quarantine_reason_counts"].items():
        lines.append(f"- `{reason}`: {count}")
    if not observed["quarantine_reason_counts"]:
        lines.append("- No quarantined files.")
    lines.extend(["", "## Safe Candidate Role Counts", ""])
    for role, count in observed["safe_role_counts"].items():
        lines.append(f"- `{role}`: {count}")
    if not observed["safe_role_counts"]:
        lines.append("- No safe metadata-only candidates.")
    lines.extend(["", "## Review Sample", ""])
    for candidate in record["safe_candidate_sample"]:
        lines.extend(
            [
                f"### `{candidate['relative_path']}`",
                "",
                f"- Role: `{candidate['role']}`",
                f"- Suffix: `{candidate['suffix']}`",
                f"- Size bytes: `{candidate['size_bytes']}`",
                "- Decision: `metadata_only_candidate`",
                "- Privacy note: file contents were not read.",
                "",
            ]
        )
    if not record["safe_candidate_sample"]:
        lines.append("No review sample candidates.")
    lines.extend(["", "## Next Review Questions", ""])
    for question in record["next_review_questions"]:
        lines.append(f"- {question}")
    return "\n".join(lines)


def write_public_safe_source_sweep(
    repo_root: Path,
    source_path: Path,
    *,
    source_id: str,
    review_sample: int = 50,
    max_files: int | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    record = build_public_safe_source_sweep(
        source_path,
        source_id=source_id,
        review_sample=review_sample,
        max_files=max_files,
        generated_at=generated_at,
    )
    output_dir = data_relative_path(repo_root, Path("processed") / "reports" / "external_sweeps")
    report_path = output_dir / f"{source_id}_public_safe_sweep.md"
    json_path = output_dir / f"{source_id}_public_safe_sweep.json"
    atomic_write_text(report_path, public_safe_source_sweep_markdown(record) + "\n")
    write_json(json_path, record)
    return {
        "source_id": source_id,
        "methodology": PUBLIC_SAFE_SOURCE_SWEEP_METHOD,
        "report": str(report_path),
        "record": str(json_path),
        "files_seen": record["observed"]["files_seen"],
        "metadata_only_candidate_files": record["observed"]["metadata_only_candidate_files"],
        "quarantined_files": record["observed"]["quarantined_files"],
        "row_level_data_imported": False,
        "file_contents_read": False,
        "sqlite_opened": False,
    }
