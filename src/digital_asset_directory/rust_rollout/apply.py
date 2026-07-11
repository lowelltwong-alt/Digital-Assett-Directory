from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..logos_write_guard import LogosWriteBlocked, assert_dad_write_allowed
from .models import RustApplyResult, RustRepoRecord, resolve_local_path
from .policy import can_apply_forced_rollout


def apply_rust_rollout_scaffold(
    *,
    repo_root: Path,
    record: RustRepoRecord,
    approval_id: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> RustApplyResult:
    decision = can_apply_forced_rollout(record)
    if not decision.can_apply:
        return RustApplyResult(
            repo=record.repo,
            status="blocked",
            decision=decision,
            approval_id=approval_id,
            files_written=[],
            files_skipped=[],
            message=decision.block_reason,
        )
    if not force:
        return RustApplyResult(
            repo=record.repo,
            status="blocked",
            decision=decision,
            approval_id=approval_id,
            files_written=[],
            files_skipped=[],
            message="apply requires --force after reviewing the rollout plan",
        )
    if not _valid_approval_id(approval_id):
        return RustApplyResult(
            repo=record.repo,
            status="blocked",
            decision=decision,
            approval_id=approval_id,
            files_written=[],
            files_skipped=[],
            message="apply requires a reviewed --approval-id starting with dad:approval:",
        )

    target = resolve_local_path(repo_root, record.local_path)
    if target is None or not target.exists():
        return RustApplyResult(
            repo=record.repo,
            status="blocked",
            decision=decision,
            approval_id=approval_id,
            files_written=[],
            files_skipped=[],
            message="configured local_path does not exist",
        )
    if block_reason := _target_git_block_reason(target):
        return RustApplyResult(
            repo=record.repo,
            status="blocked",
            decision=decision,
            approval_id=approval_id,
            files_written=[],
            files_skipped=[],
            message=block_reason,
        )
    try:
        assert_dad_write_allowed(target, approval_id=approval_id)
    except LogosWriteBlocked as exc:
        return RustApplyResult(
            repo=record.repo,
            status="blocked",
            decision=decision,
            approval_id=approval_id,
            files_written=[],
            files_skipped=[],
            message=str(exc),
        )

    files = _scaffold_files(record)
    written: list[str] = []
    skipped: list[str] = []
    for relative, text in files.items():
        path = _safe_target_path(target, relative)
        if path.exists():
            skipped.append(str(path))
            continue
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        written.append(str(path))

    return RustApplyResult(
        repo=record.repo,
        status="dry_run" if dry_run else "applied",
        decision=decision,
        approval_id=approval_id,
        files_written=written,
        files_skipped=skipped,
        message="target repo owns all generated Rust files; no external send or GitHub write performed",
    )


def _scaffold_files(record: RustRepoRecord) -> dict[str, str]:
    crate_name = _crate_name(record)
    return {
        "docs/rust/RUST_ADOPTION_PLAN.md": _doc(
            "Rust Adoption Plan",
            record,
            "Candidate local plan. Python remains the orchestrator; Rust is deterministic leaf tooling.",
        ),
        "docs/rust/PYTHON_RUST_BOUNDARY.md": _doc(
            "Python/Rust Boundary",
            record,
            "Python owns orchestration, review, governance, and model use. Rust owns scanning, hashing, file inventory, and JSONL validation.",
        ),
        "docs/rust/RUST_CI_QA_PLAN.md": _doc(
            "Rust CI QA Plan",
            record,
            "Run fmt, check, test, and clippy for Rust changes. Long CI stays manual or scheduled unless locally promoted.",
        ),
        "docs/rust/TARGET_REPO_RUST_OWNERSHIP.md": _doc(
            "Target Repo Rust Ownership",
            record,
            "This repo owns its own Cargo files, Rust source, Rust CI, reports, and lessons. Do not depend on a local DAD path.",
        ),
        "config/rust_adoption.yaml": (
            "schema_version: dad_target_rust_adoption.v1\n"
            f"repo: {record.repo}\n"
            "target_repo_owns_rust_files: true\n"
            "python_stays_orchestrator: true\n"
            "rust_boundary: deterministic_leaf_tooling_only\n"
            "external_send_allowed: false\n"
            "github_write_allowed: false\n"
            "destructive_write_allowed: false\n"
        ),
        "reports/rust_adoption/README.md": (
            "# Rust Adoption Reports\n\nGenerated reports belong to this target repo.\n"
        ),
        "lessons/rust_adoption/README.md": (
            "# Rust Adoption Lessons\n\nAppend local lessons here and send metadata-only candidates to DAD when useful.\n"
        ),
        f"tools/{crate_name}/README.md": (
            f"# {crate_name}\n\nCandidate Rust leaf tool for `{record.repo}`.\n"
        ),
    }


def _doc(title: str, record: RustRepoRecord, body: str) -> str:
    return (
        f"# {title}\n\n"
        f"Repo: `{record.repo}`\n\n"
        f"First Rust slice: {record.recommended_first_rust_slice or 'review required'}\n\n"
        f"{body}\n\n"
        "Rust must not own legal judgment, theological judgment, source authority, "
        "governance promotion, model orchestration, external writes, or destructive source mutation.\n"
    )


def _crate_name(record: RustRepoRecord) -> str:
    first = record.recommended_first_rust_slice.split(":", 1)[0].strip()
    if first.startswith("tools/"):
        candidate = first.removeprefix("tools/").strip("/\\").split("/", 1)[0].split("\\", 1)[0]
        if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", candidate):
            return candidate
    return "rust_leaf_tool"


def _valid_approval_id(value: str | None) -> bool:
    return bool(value and value.startswith("dad:approval:") and len(value) > len("dad:approval:"))


def _safe_target_path(target: Path, relative: str) -> Path:
    target_root = target.resolve()
    path = (target_root / relative).resolve()
    if not path.is_relative_to(target_root):
        raise ValueError(f"scaffold path escapes target repo: {relative}")
    return path


def _target_git_block_reason(target: Path) -> str | None:
    if not (target / ".git").exists():
        return None
    inside = _git(target, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return "target git worktree could not be verified"
    branch = _git(target, "branch", "--show-current")
    if branch.returncode == 0 and not branch.stdout.strip():
        branch = _git(target, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch.returncode != 0:
        return "target git branch could not be verified"
    branch_name = branch.stdout.strip()
    if branch_name not in {"main", "master"}:
        return f"target git branch blocks rollout: {branch_name}"
    status = _git(target, "status", "--porcelain")
    if status.returncode != 0:
        return "target git status could not be verified"
    if status.stdout.strip():
        return "target git worktree is dirty; commit or stash before rollout apply"
    return None


def _git(target: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(target), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
