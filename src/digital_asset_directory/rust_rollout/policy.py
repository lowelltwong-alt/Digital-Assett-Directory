from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import RustRepoRecord, RustRolloutDecision

BLOCKED_ACTIVE_STATUSES = {"disabled", "archived", "inactive", "unsafe"}


def is_logos_repo(repo_name: str | None) -> bool:
    return "logos" in (repo_name or "").casefold()


def rollout_mode(repo_name: str | None) -> str:
    if not (repo_name or "").strip():
        return "unknown_review_required"
    if is_logos_repo(repo_name):
        return "instruction_mail_only"
    return "dad_forced_implementation"


def load_rust_repo_records(path: Path) -> list[RustRepoRecord]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = payload.get("repos", [])
    if not isinstance(rows, list):
        raise ValueError(f"Expected {path} to contain a list at `repos`.")
    return [RustRepoRecord.from_mapping(_ensure_mapping(row)) for row in rows]


def can_apply_forced_rollout(record: RustRepoRecord) -> RustRolloutDecision:
    mode = rollout_mode(record.repo_name)
    contains_logos = is_logos_repo(record.repo_name)
    instruction_mail_required = True
    rust_priority = _priority_label(record)
    rust_needed_now = rust_priority in {"immediate", "high", "medium_high"} or (
        record.priority is not None and record.priority <= 5
    )

    can_apply = True
    block_reason = ""
    if mode == "unknown_review_required":
        can_apply = False
        block_reason = "missing repo identity"
    elif contains_logos:
        can_apply = False
        block_reason = "logos repos are instruction-mail-only and cannot receive forced rollout"
    elif not record.rollout_enabled:
        can_apply = False
        block_reason = "rollout disabled in config"
    elif _active_status(record) in BLOCKED_ACTIVE_STATUSES and not record.allow_inactive_override:
        can_apply = False
        block_reason = f"active_status blocks rollout: {record.active_status}"
    elif not record.local_path:
        can_apply = False
        block_reason = "missing configured local_path"
    elif Path(record.local_path).is_absolute() and not record.allow_absolute_local_path:
        can_apply = False
        block_reason = "absolute local_path requires reviewed allow_absolute_local_path"

    return RustRolloutDecision(
        repo=record.repo,
        repo_name=record.repo_name,
        contains_logos=contains_logos,
        rollout_mode=mode,
        can_apply=can_apply,
        block_reason=block_reason,
        local_path=record.local_path,
        rust_status=record.rust_status,
        rust_priority=rust_priority,
        rust_needed_now=rust_needed_now,
        recommended_first_rust_slice=record.recommended_first_rust_slice,
        target_repo_owns_rust_files=record.target_repo_owns_rust_files,
        instruction_mail_required=instruction_mail_required,
        validation_commands=record.validation_commands or _default_validation_commands(record),
    )


def _default_validation_commands(record: RustRepoRecord) -> list[str]:
    if record.repo_name == "Digital-Assett-Directory":
        return [
            "cargo fmt --manifest-path tools/dad_scan_core/Cargo.toml --check",
            "cargo check --manifest-path tools/dad_scan_core/Cargo.toml",
            "cargo test --manifest-path tools/dad_scan_core/Cargo.toml",
            "cargo clippy --manifest-path tools/dad_scan_core/Cargo.toml --all-targets -- -D warnings",
            "python -m pytest tests/test_rust_bridge_dad_scan_core.py -q",
        ]
    return [
        "cargo fmt --check",
        "cargo check",
        "cargo test",
        "cargo clippy --all-targets -- -D warnings",
    ]


def _priority_label(record: RustRepoRecord) -> str:
    status = record.rust_status.casefold()
    if "immediate" in status:
        return "immediate"
    if "high" in status:
        return "high" if "medium" not in status else "medium_high"
    if "medium" in status:
        return "medium"
    if "low" in status:
        return "low"
    if "none" in status:
        return "none"
    return "unknown"


def _active_status(record: RustRepoRecord) -> str:
    return record.active_status.strip().casefold().replace("-", "_")


def _ensure_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Rust repo records must be mappings.")
    return value
