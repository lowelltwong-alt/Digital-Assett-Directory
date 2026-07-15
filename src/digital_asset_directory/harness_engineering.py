"""Immutable harness revisions and a typed, deny-by-default command runner."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable

from jsonschema.validators import validator_for


REGISTRY_PATH = Path("registry/harness-engineering-registry.json")
REVISION_SCHEMA_PATH = Path("schemas/harness-revision.schema.json")
_EXECUTABLE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_SHELL_META_RE = re.compile(r"[;&|<>`\r\n]")
_LIFECYCLE_TRANSITIONS = {
    "discovered": {"candidate", "rejected"},
    "candidate": {"shadow", "rejected"},
    "shadow": {"piloted", "rejected"},
    "piloted": {"reviewed_active", "rejected"},
    "reviewed_active": {"watch", "stale", "superseded"},
    "watch": {"reviewed_active", "stale", "superseded"},
    "stale": {"reviewed_active", "superseded", "retired"},
    "superseded": {"retired"},
    "retired": set(),
    "rejected": set(),
}


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object in {path}")
    return value


def _validate_schema(value: dict[str, Any], path: Path) -> None:
    schema = _load_object(path)
    cls = validator_for(schema)
    cls.check_schema(schema)
    errors = sorted(cls(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "<root>"
        raise ValueError(f"Invalid {path.name} at {location}: {error.message}")


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def load_harness_registry(repo_root: Path) -> dict[str, Any]:
    registry = _load_object(repo_root / REGISTRY_PATH)
    if registry.get("execution_authorized") is not False:
        raise ValueError("Harness registry must deny execution by default")
    if registry.get("typed_command_policy", {}).get("shell") is not False:
        raise ValueError("Harness registry must require shell=false")
    return registry


def validate_command_spec(spec: dict[str, Any]) -> dict[str, Any]:
    required = {
        "command_id",
        "argv",
        "cwd_policy",
        "timeout_seconds",
        "effect_class",
        "required_tool_capabilities",
        "allowed_environment_keys",
    }
    missing = sorted(required - set(spec))
    if missing:
        raise ValueError(f"Typed command is missing fields: {missing}")
    unexpected = sorted(set(spec) - required)
    if unexpected:
        raise ValueError(f"Typed command has unsupported fields: {unexpected}")
    argv = spec["argv"]
    if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and arg for arg in argv):
        raise ValueError("argv must be a non-empty list of non-empty strings")
    executable = argv[0]
    if not _EXECUTABLE_RE.fullmatch(executable) or Path(executable).name != executable:
        raise ValueError("Executable must be an unambiguous allowlisted basename")
    for argument in argv:
        if _SHELL_META_RE.search(argument):
            raise ValueError("Shell metacharacters are forbidden even though shell=false")
        argument_path = Path(argument)
        if argument_path.is_absolute() or ".." in argument_path.parts:
            raise ValueError("Absolute and parent-traversal argv paths are forbidden")
    if spec["cwd_policy"] not in {"target_repo", "harness_package"}:
        raise ValueError("Unknown cwd policy")
    timeout = int(spec["timeout_seconds"])
    if not 1 <= timeout <= 120:
        raise ValueError("Command timeout must be between 1 and 120 seconds")
    if spec["effect_class"] not in {"read_only", "local_build_artifact"}:
        raise ValueError("Unsupported effect class")
    tools = spec["required_tool_capabilities"]
    if not isinstance(tools, list) or not tools or any(not isinstance(item, str) or not item for item in tools):
        raise ValueError("At least one required tool capability is required")
    keys = spec["allowed_environment_keys"]
    if not isinstance(keys, list) or any(not isinstance(key, str) or not _ENV_RE.fullmatch(key) for key in keys):
        raise ValueError("Environment keys must be explicit uppercase identifiers")
    if len(keys) != len(set(keys)) or len(tools) != len(set(tools)):
        raise ValueError("Tool and environment allowlists must be unique")
    return deepcopy(spec)


def resolve_command_cwd(
    spec: dict[str, Any], *, target_repo: Path, harness_package: Path
) -> Path:
    selected = target_repo if spec["cwd_policy"] == "target_repo" else harness_package
    resolved = selected.resolve(strict=True)
    authority_root = (target_repo if spec["cwd_policy"] == "target_repo" else harness_package).resolve(strict=True)
    if resolved != authority_root or not resolved.is_dir():
        raise ValueError("Command cwd escaped its declared authority root")
    return resolved


def prepare_typed_command(
    spec: dict[str, Any],
    *,
    target_repo: Path,
    harness_package: Path,
    available_tool_capabilities: Iterable[str],
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    normalized = validate_command_spec(spec)
    available = set(available_tool_capabilities)
    required = set(normalized["required_tool_capabilities"])
    if not required.issubset(available) or normalized["argv"][0] not in available:
        raise ValueError("Required tool capability or executable is unavailable")
    supplied = environment or {}
    disallowed_keys = set(supplied) - set(normalized["allowed_environment_keys"])
    if disallowed_keys:
        raise ValueError(f"Undeclared environment keys: {sorted(disallowed_keys)}")
    selected_env_keys = sorted(
        key
        for key in normalized["allowed_environment_keys"]
        if key in supplied or key in os.environ
    )
    cwd = resolve_command_cwd(
        normalized, target_repo=target_repo, harness_package=harness_package
    )
    return {
        "command_id": normalized["command_id"],
        "argv": normalized["argv"],
        "cwd": str(cwd),
        "timeout_seconds": normalized["timeout_seconds"],
        "effect_class": normalized["effect_class"],
        # Candidate/dry-run packets never contain environment values.  A later
        # independently authorized executor must resolve the approved keys.
        "environment_keys": selected_env_keys,
        "shell": False,
        "execution_authorized": False,
    }


def run_typed_command(
    spec: dict[str, Any],
    *,
    target_repo: Path,
    harness_package: Path,
    available_tool_capabilities: Iterable[str],
    environment: dict[str, str] | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    """Prepare by default; local execution needs an explicit caller gate.

    The repository registry remains deny-execute, so this function never turns
    a candidate harness into active authority.  ``execute`` exists for an
    already-authorized outer executor and for isolated tests.
    """

    packet = prepare_typed_command(
        spec,
        target_repo=target_repo,
        harness_package=harness_package,
        available_tool_capabilities=available_tool_capabilities,
        environment=environment,
    )
    if execute:
        raise ValueError(
            "The candidate harness registry denies execution; an independently "
            "approved outer A2 fixture executor is required."
        )
    return {**packet, "status": "prepared_dry_run"}


def validate_harness_revision(repo_root: Path, revision: dict[str, Any]) -> dict[str, Any]:
    _validate_schema(revision, repo_root / REVISION_SCHEMA_PATH)
    material = deepcopy(revision)
    claimed = material.pop("content_digest")
    if canonical_digest(material) != claimed:
        raise ValueError("Harness revision content digest does not match immutable content")
    command_ids: set[str] = set()
    for command in revision["commands"]:
        normalized = validate_command_spec(command)
        if normalized["command_id"] in command_ids:
            raise ValueError("Harness command IDs must be unique within a revision")
        command_ids.add(normalized["command_id"])
    return deepcopy(revision)


def add_harness_revision(
    repo_root: Path,
    existing: Iterable[dict[str, Any]],
    revision: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return a new revision collection; existing revision objects are untouched."""

    rows = [validate_harness_revision(repo_root, row) for row in existing]
    candidate = validate_harness_revision(repo_root, revision)
    by_revision = {row["revision_id"]: row for row in rows}
    if candidate["revision_id"] in by_revision:
        if by_revision[candidate["revision_id"]] == candidate:
            return deepcopy(rows)
        raise ValueError("Immutable harness revision identity conflict")
    predecessor = candidate["predecessor_revision_id"]
    family_rows = [row for row in rows if row["harness_id"] == candidate["harness_id"]]
    if family_rows and predecessor not in by_revision:
        raise ValueError("A later harness revision requires a known predecessor")
    if not family_rows and predecessor:
        raise ValueError("The first harness revision cannot name a predecessor")
    rows.append(candidate)
    return sorted(rows, key=lambda row: (row["harness_id"], row["version"], row["revision_id"]))


def lifecycle_candidate(
    revision: dict[str, Any],
    to_state: str,
    *,
    evidence_refs: Iterable[str],
    human_approval_ref: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    current = str(revision["lifecycle_state"])
    if to_state not in _LIFECYCLE_TRANSITIONS.get(current, set()):
        raise ValueError(f"Illegal harness lifecycle transition: {current} -> {to_state}")
    evidence = sorted(set(str(ref) for ref in evidence_refs if str(ref)))
    activation = to_state == "reviewed_active"
    retirement = to_state in {"superseded", "retired"}
    if (activation or retirement) and not human_approval_ref:
        raise ValueError("Activation, supersession, and retirement need human approval")
    material = {
        "revision_id": revision["revision_id"],
        "from_state": current,
        "to_state": to_state,
        "evidence_refs": evidence,
        "human_approval_ref": human_approval_ref,
    }
    return {
        "decision_id": f"dad:harness-lifecycle:{canonical_digest(material).split(':', 1)[1]}",
        **material,
        "recorded_at": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "candidate_only": True,
        "applied": False,
    }


def route_harness(
    revisions: Iterable[dict[str, Any]],
    *,
    task_tags: Iterable[str],
    runtime_capability_ids: Iterable[str],
) -> dict[str, Any]:
    tags = set(task_tags)
    runtime = set(runtime_capability_ids)
    candidates: list[dict[str, Any]] = []
    for row in revisions:
        if row["lifecycle_state"] not in {"shadow", "piloted", "reviewed_active", "watch"}:
            continue
        required = set(row.get("runtime_requirements", {}).get("capability_ids", []))
        overlap = len(tags & set(row["applicability_tags"]))
        if overlap and required.issubset(runtime):
            candidates.append({"revision_id": row["revision_id"], "overlap": overlap})
    candidates.sort(key=lambda row: (-row["overlap"], row["revision_id"]))
    return {
        "status": "selected" if candidates else "blocked",
        "selected_revision_id": candidates[0]["revision_id"] if candidates else "",
        "considered": candidates,
        "execution_authorized": False,
    }


__all__ = [
    "add_harness_revision",
    "canonical_digest",
    "lifecycle_candidate",
    "load_harness_registry",
    "prepare_typed_command",
    "route_harness",
    "run_typed_command",
    "validate_command_spec",
    "validate_harness_revision",
]
