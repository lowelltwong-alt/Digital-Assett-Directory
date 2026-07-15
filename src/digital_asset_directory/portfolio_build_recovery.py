"""Read-only plan/build/worktree reconciliation for unfinished-build recovery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any

from .portfolio_events import minimize_text


AUTHORITY_BOUNDARY = (
    "Recovery bundles are immutable diagnostic evidence and proposal-only. They cannot "
    "checkout, commit, merge, stash, reset, clean, delete, rebase, push, bind, close, or dispatch."
)
_LOCAL_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|/(?:Users|home|tmp)/)[^\s\"'<>|?*]*")


def _safe_refs(values: list[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        minimized, _ = minimize_text(value)
        result.append(_LOCAL_PATH.sub("[LOCAL_PATH]", minimized)[:240])
    return sorted(set(result))


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def classify_worktree(observation: dict[str, Any]) -> str:
    if observation.get("status_available") is not True:
        return "unknown"
    if observation.get("conflicted"):
        return "blocked"
    if observation.get("intentionally_held"):
        return "intentionally_held"
    if observation.get("diverged") or (
        int(observation.get("ahead", 0)) > 0 and int(observation.get("behind", 0)) > 0
    ):
        return "diverged"
    if observation.get("patch_equivalent"):
        return "patch_equivalent"
    if int(observation.get("ahead", 0)) > 0:
        return "ahead_unintegrated"
    if any(observation.get(key) for key in ("dirty", "staged", "untracked")):
        return "dirty_unique_value_possible"
    if observation.get("contained_in_main") is True:
        return "contained_in_main"
    return "unknown"


def build_recovery_bundle(
    *,
    plan: dict[str, Any],
    worktree_observation: dict[str, Any],
    acceptance_evidence: list[str] | None = None,
    validation_evidence: list[str] | None = None,
) -> dict[str, Any]:
    required = {"plan_id", "revision_id", "implementation_state"}
    missing = sorted(required - set(plan))
    if missing:
        raise ValueError(f"Plan recovery input missing fields: {missing}")
    observation_required = {"repository_id", "worktree_id", "head_id", "observed_at"}
    observation_missing = sorted(observation_required - set(worktree_observation))
    if observation_missing:
        raise ValueError(f"Worktree recovery input missing stable snapshot fields: {observation_missing}")
    try:
        source_observed = datetime.fromisoformat(
            str(worktree_observation["observed_at"]).replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError("Worktree observation requires a valid observed_at") from exc
    if source_observed.tzinfo is None:
        raise ValueError("Worktree observation observed_at must be timezone-aware")
    observed_now = datetime.now(timezone.utc)
    source_age = observed_now - source_observed.astimezone(timezone.utc)
    snapshot_current = timedelta(0) <= source_age <= timedelta(minutes=15)
    classification = classify_worktree(worktree_observation) if snapshot_current else "unknown"
    acceptance = _safe_refs(acceptance_evidence)
    validation = _safe_refs(validation_evidence)
    completion_supported = (
        snapshot_current
        and
        plan["implementation_state"] == "verified_complete"
        and bool(acceptance)
        and bool(validation)
        and bool(plan.get("independent_check_ref"))
    )
    snapshot_material = {
        "plan_id": plan["plan_id"],
        "revision_id": plan["revision_id"],
        "worktree": worktree_observation,
        "acceptance_evidence": acceptance,
        "validation_evidence": validation,
    }
    proposed = "inspect"
    if classification in {"dirty_unique_value_possible", "ahead_unintegrated", "diverged"}:
        proposed = "preserve_or_resume_review"
    elif classification == "blocked":
        proposed = "create_handoff_or_hold"
    elif classification in {"contained_in_main", "patch_equivalent"} and not completion_supported:
        proposed = "verify_acceptance_before_close"
    bundle = {
        "schema_version": "dad.plan_build_recovery_bundle.v1",
        "bundle_id": "dad:recovery-bundle:" + _digest(snapshot_material).split(":", 1)[1],
        "observed_at": observed_now.isoformat(),
        "source_observed_at": source_observed.astimezone(timezone.utc).isoformat(),
        "repository_id": worktree_observation["repository_id"],
        "worktree_id": worktree_observation["worktree_id"],
        "head_id": worktree_observation["head_id"],
        "plan_id": plan["plan_id"],
        "plan_revision_id": plan["revision_id"],
        "source_snapshot_digest": _digest(snapshot_material),
        "snapshot_current": snapshot_current,
        "classification": classification,
        "completion_supported": completion_supported,
        "acceptance_evidence": acceptance,
        "validation_evidence": validation,
        "proposed_disposition": proposed,
        "allowed_actions": ["inspect", "resume_request", "hold", "supersede_candidate", "archive_candidate"],
        "forbidden_git_actions": ["checkout", "commit", "merge", "stash", "reset", "clean", "delete", "rebase", "push"],
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    return bundle


def snapshot_is_current(
    bundle: dict[str, Any],
    current_material: dict[str, Any],
    *,
    now: datetime | None = None,
    max_age: timedelta = timedelta(minutes=15),
) -> bool:
    if bundle.get("source_snapshot_digest") != _digest(current_material):
        return False
    try:
        observed = datetime.fromisoformat(str(bundle["source_observed_at"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return False
    if observed.tzinfo is None:
        return False
    age = (now or datetime.now(timezone.utc)).astimezone(timezone.utc) - observed.astimezone(timezone.utc)
    return timedelta(0) <= age <= max_age


__all__ = ["AUTHORITY_BOUNDARY", "build_recovery_bundle", "classify_worktree", "snapshot_is_current"]
