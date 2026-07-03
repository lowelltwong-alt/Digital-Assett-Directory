from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RustRepoRecord:
    repo: str
    repo_name: str
    rust_status: str
    priority: int | None
    plane: str
    reason: str
    recommended_first_rust_slice: str
    python_stays: str
    ci_profile: str
    confidence: str
    risk: str
    local_path: str | None
    allow_absolute_local_path: bool
    active_status: str
    rollout_enabled: bool
    allow_inactive_override: bool
    target_repo_owns_rust_files: bool
    validation_commands: list[str]
    notes: str

    @classmethod
    def from_mapping(cls, row: dict[str, Any]) -> "RustRepoRecord":
        repo = str(row.get("repo") or row.get("repo_name") or "").strip()
        repo_name = str(row.get("repo_name") or repo).strip()
        return cls(
            repo=repo,
            repo_name=repo_name,
            rust_status=str(row.get("rust_status") or "unknown"),
            priority=_optional_int(row.get("priority")),
            plane=str(row.get("plane") or ""),
            reason=str(row.get("reason") or ""),
            recommended_first_rust_slice=str(
                row.get("recommended_first_rust_slice") or row.get("first_rust_slice") or ""
            ),
            python_stays=str(row.get("python_stays") or ""),
            ci_profile=str(row.get("ci_profile") or ""),
            confidence=str(row.get("confidence") or "unknown"),
            risk=str(row.get("risk") or "unknown"),
            local_path=_optional_string(row.get("local_path")),
            allow_absolute_local_path=bool(row.get("allow_absolute_local_path", False)),
            active_status=str(row.get("active_status") or "active"),
            rollout_enabled=bool(row.get("rollout_enabled", True)),
            allow_inactive_override=bool(row.get("allow_inactive_override", False)),
            target_repo_owns_rust_files=bool(row.get("target_repo_owns_rust_files", True)),
            validation_commands=[
                str(item) for item in row.get("validation_commands", []) if str(item).strip()
            ],
            notes=str(row.get("notes") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RustRolloutDecision:
    repo: str
    repo_name: str
    contains_logos: bool
    rollout_mode: str
    can_apply: bool
    block_reason: str
    local_path: str | None
    rust_status: str
    rust_priority: str
    rust_needed_now: bool
    recommended_first_rust_slice: str
    target_repo_owns_rust_files: bool
    instruction_mail_required: bool
    validation_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RustApplyResult:
    repo: str
    status: str
    decision: RustRolloutDecision
    approval_id: str | None
    files_written: list[str]
    files_skipped: list[str]
    message: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["decision"] = self.decision.to_dict()
        return value


def resolve_local_path(repo_root: Path, local_path: str | None) -> Path | None:
    if not local_path:
        return None
    path = Path(local_path)
    return path if path.is_absolute() else repo_root / path


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
