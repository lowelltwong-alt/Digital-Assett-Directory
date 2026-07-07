from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Sequence

from jsonschema.exceptions import ValidationError
from jsonschema.validators import validator_for
import yaml

from .config import AppConfig, EnrollmentRepoPolicy
from .mail_center import mail_digest_status, mail_gitignore_text, mail_readme_text
from .transport import TRANSPORT_SURFACE_VERSION
from .utils import append_jsonl, atomic_write_text, json_dumps, utc_now

ENROLLMENT_VERSION = "0.1.0"
ENROLLMENT_SCHEMA_VERSION = "0.1.0"
ENROLLMENT_DIR = Path("processed") / "enrollment"
AUDIT_PATH = ENROLLMENT_DIR / "audit.jsonl"
CAPTURE_PATTERN_REGISTRY = Path("registry") / "exception-capture-pattern-registry.json"
REPO_ENROLLMENT_SCHEMA = Path("schemas") / "repo-enrollment-contract.schema.json"
DOWNSTREAM_EXCEPTION_README = Path("templates") / "downstream" / "EXCEPTIONS_README.md"
DOWNSTREAM_ASSETS_README = Path("templates") / "downstream" / "DAD_ASSETS_README.md"

GOVERNANCE_BEGIN = "<!-- BEGIN DIGITAL_ASSET_DIRECTORY_GOVERNANCE -->"
GOVERNANCE_END = "<!-- END DIGITAL_ASSET_DIRECTORY_GOVERNANCE -->"
ENROLLMENT_BEGIN = "<!-- BEGIN DIGITAL_ASSET_DIRECTORY_ENROLLMENT -->"
ENROLLMENT_END = "<!-- END DIGITAL_ASSET_DIRECTORY_ENROLLMENT -->"
CLAUDE_BEGIN = "<!-- BEGIN DIGITAL_ASSET_DIRECTORY_CLAUDE_IMPORT -->"
CLAUDE_END = "<!-- END DIGITAL_ASSET_DIRECTORY_CLAUDE_IMPORT -->"
TOC_BEGIN = "<!-- BEGIN DIGITAL_ASSET_DIRECTORY_TOC_ROWS -->"
TOC_END = "<!-- END DIGITAL_ASSET_DIRECTORY_TOC_ROWS -->"

CONTROL_PLANE_IDS = [
    "dad_library",
    "mail_center",
    "reusable_assets",
    "coding_harnesses",
    "agent_skills",
    "templates",
    "architecture_references",
    "repo_enrollment",
    "coding_test_parity",
    "governance_maps",
    "data_maps",
    "learning_postflight_loops",
]

AGENT_RUNTIME_POLICY = {
    "core_contract": "AGENTS.md",
    "adapter_authority": "optional_wrapper_only",
    "agent_id_policy": "arbitrary_non_empty_string",
    "vendor_lock_in_prohibited": True,
}

WEEKLY_CHECKS = [
    "asset_update_available",
    "skill_update_retirement_or_replacement",
    "template_update_available",
    "architecture_reference_update",
    "governance_map_drift",
    "data_map_drift",
    "new_best_practice_or_library_recommendation",
]

APPROVED_RELATIVE_PATHS = [
    ".digital-asset/dad-integration.json",
    ".digital-asset/mail/README.md",
    ".digital-asset/mail/.gitignore",
    ".digital-asset/mail/inbox.jsonl",
    ".digital-asset/mail/outbox.jsonl",
    ".digital-asset/mail/archive.jsonl",
    ".digital-asset/mail/adoption.jsonl",
    ".digital-asset/assets/README.md",
    ".digital-asset/assets/index.jsonl",
    ".digital-asset/assets/adoption.jsonl",
    ".digital-asset/learning/events.jsonl",
    ".digital-asset/skills/checkout.json",
    ".digital-asset/context-map.json",
    ".digital-asset/governance-map.yaml",
    ".digital-asset/data-map.yaml",
    ".ai-assets.json",
    "AGENTS.md",
    "CLAUDE.md",
    "AI_FRONT_DOOR.md",
    "AI_TABLE_OF_CONTENTS.md",
    ".githooks/pre-push",
    ".githooks/pre-push.ps1",
]

REPO_LOCAL_ONLY_PATHS = [
    ".digital-asset/exceptions/README.md",
    ".digital-asset/exceptions/.gitignore",
    ".digital-asset/exceptions/outbox.jsonl",
    ".digital-asset/exceptions/inbox.jsonl",
    ".digital-asset/exceptions/archive.jsonl",
    "processed/exceptions/fix-outcomes/outcomes.jsonl",
]

AUTHORITY_BOUNDARY = (
    "DAD enrollment installs or updates only reviewed, marker-bounded governance "
    "surfaces after a human approval ID. Normal recurring DAD operation remains "
    "mailbox-only under .digital-asset/mail/**."
)

REPO_LOCAL_ONLY_BOUNDARY = (
    "Repo-local exception and fix-outcome paths are bootstrapped for the source "
    "repo to append safe metadata packets. They are not DAD-managed authority "
    "surfaces and normal DAD operation may not mutate them."
)


def _normalize_path(path: Path | str) -> str:
    return str(Path(path).resolve()).replace("\\", "/")


def _public_safe(policy: EnrollmentRepoPolicy) -> bool:
    return bool(policy.public_facing and not policy.local_paths_allowed)


def _hub_ref(hub_root: Path, policy: EnrollmentRepoPolicy) -> str:
    return "dad://hub/Digital-Assett-Directory"


def _repo_ref(policy: EnrollmentRepoPolicy) -> str:
    return f"dad://repo/{policy.id}"


def _return_address(policy: EnrollmentRepoPolicy) -> str:
    return f"dad://repo/{policy.id}/.digital-asset/mail/outbox.jsonl"


def _enabled_control_planes(policy: EnrollmentRepoPolicy) -> list[str]:
    requested = policy.enabled_control_planes or CONTROL_PLANE_IDS
    return [plane for plane in requested if plane in CONTROL_PLANE_IDS]


def _policy_aliases(policy: EnrollmentRepoPolicy) -> set[str]:
    aliases = {policy.id, policy.alias, policy.path.name}
    aliases.add(_normalize_path(policy.path))
    return {alias for alias in aliases if alias}


def _git_stdout(repo_root: Path, args: Sequence[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _repo_git_state(repo_root: Path) -> dict[str, Any]:
    exists = repo_root.exists() and repo_root.is_dir()
    state: dict[str, Any] = {
        "exists": exists,
        "git_detected": False,
        "branch": "",
        "remote_origin": "",
        "head": "",
        "dirty_count": 0,
        "is_dirty": False,
    }
    if not exists:
        return state
    inside = _git_stdout(repo_root, ["rev-parse", "--is-inside-work-tree"])
    if inside != "true":
        return state
    status = _git_stdout(repo_root, ["status", "--porcelain=v1"]) or ""
    dirty_lines = [line for line in status.splitlines() if line.strip()]
    state.update(
        {
            "git_detected": True,
            "branch": _git_stdout(repo_root, ["branch", "--show-current"]) or "",
            "remote_origin": _git_stdout(repo_root, ["remote", "get-url", "origin"]) or "",
            "head": _git_stdout(repo_root, ["rev-parse", "--short", "HEAD"]) or "",
            "dirty_count": len(dirty_lines),
            "is_dirty": bool(dirty_lines),
        }
    )
    return state


def _policy_hold_reasons(
    policy: EnrollmentRepoPolicy, git_state: dict[str, Any]
) -> list[str]:
    reasons: list[str] = []
    if policy.active_hold:
        reason = policy.active_hold_reason or "repo is marked active/protected in policy"
        reasons.append(f"active_hold: {reason}")
    if git_state["git_detected"] and git_state["is_dirty"] and not policy.allow_dirty_worktree:
        reasons.append(
            "dirty_worktree: set allow_dirty_worktree only after reviewing local work"
        )
    branch = str(git_state.get("branch") or "")
    if (
        git_state["git_detected"]
        and branch
        and branch not in {"main", "master"}
        and not policy.allow_non_main_branch
    ):
        reasons.append(
            f"non_main_branch: {branch}; set allow_non_main_branch only for a reviewed wave"
        )
    return reasons


def _policy_for_repo(
    value: str | Path, policies: Sequence[EnrollmentRepoPolicy]
) -> EnrollmentRepoPolicy | None:
    raw = str(value).strip()
    path_like = (
        raw in {".", ".."}
        or raw.startswith(".")
        or "/" in raw
        or "\\" in raw
        or bool(re.match(r"^[A-Za-z]:", raw))
    )
    normalized = _normalize_path(raw) if path_like else raw
    matches = [
        policy
        for policy in policies
        if policy.enrollment_enabled and normalized in _policy_aliases(policy)
    ]
    return matches[0] if len(matches) == 1 else None


def select_enrollment_policies(
    raw_repos: list[str], cfg: AppConfig, *, wave: str | None = None
) -> list[EnrollmentRepoPolicy]:
    if not raw_repos:
        raise ValueError("Provide at least one --repo value, or --repo all.")
    if raw_repos == ["all"]:
        if not wave:
            raise ValueError("--repo all requires --wave so rollout stays reviewed.")
        selected = [
            policy
            for policy in cfg.enrollment_repos
            if policy.enrollment_enabled and policy.wave == wave
        ]
        if not selected:
            raise ValueError(f"No enabled enrollment.repos entries for reviewed wave: {wave}")
        return selected

    selected: list[EnrollmentRepoPolicy] = []
    missing: list[str] = []
    for repo in raw_repos:
        policy = _policy_for_repo(repo, cfg.enrollment_repos)
        if policy is None:
            missing.append(repo)
        else:
            selected.append(policy)
    if missing:
        raise ValueError(
            "Enrollment can target only reviewed enrollment.repos entries: "
            + ", ".join(missing)
        )
    if wave:
        wrong_wave = [policy.id for policy in selected if policy.wave != wave]
        if wrong_wave:
            raise ValueError(
                f"Selected repo policy is not in wave {wave}: {', '.join(wrong_wave)}"
            )
    return selected


def discover_enrollment_candidates(cfg: AppConfig) -> dict[str, Any]:
    configured = {_normalize_path(policy.path): policy for policy in cfg.enrollment_repos}
    discovered: dict[str, Path] = {_normalize_path(cfg.repo_root): cfg.repo_root}
    for policy in cfg.enrollment_repos:
        discovered[_normalize_path(policy.path)] = policy.path
    for source in cfg.local_sources:
        if not source.enabled:
            continue
        base = source.path.resolve()
        if not base.exists():
            continue
        candidates = [base, *(item for item in base.iterdir() if item.is_dir())]
        for candidate in candidates:
            if any(
                (candidate / marker).exists()
                for marker in (".git", "AGENTS.md", "pyproject.toml", "package.json")
            ):
                discovered[_normalize_path(candidate)] = candidate
    rows: list[dict[str, Any]] = []
    for key in sorted(discovered):
        path = discovered[key]
        policy = configured.get(key)
        contract = path / ".digital-asset" / "dad-integration.json"
        rows.append(
            {
                "repo_ref": f"dad://repo/{policy.id}" if policy else path.name,
                "path": key,
                "configured": policy is not None,
                "enrollment_enabled": bool(policy.enrollment_enabled) if policy else False,
                "apply_allowed": bool(policy.apply_allowed) if policy else False,
                "update_allowed": bool(policy.update_allowed) if policy else False,
                "wave": policy.wave if policy else "",
                "visibility": policy.visibility if policy else "unreviewed_candidate",
                "public_facing": bool(policy.public_facing) if policy else False,
                "has_contract": contract.exists(),
            }
        )
    return {
        "candidates": rows,
        "authority_boundary": (
            "Discovery is read-only. Add reviewed enrollment.repos policy and a "
            "reviewed wave before planning or applying enrollment."
        ),
    }


def _plan_item(policy: EnrollmentRepoPolicy, hub_root: Path, *, update: bool) -> dict[str, Any]:
    git_state = _repo_git_state(policy.path.resolve())
    hold_reasons = _policy_hold_reasons(policy, git_state)
    return {
        "repo_id": policy.id,
        "repo_alias": policy.alias,
        "repo_ref": _repo_ref(policy),
        "visibility": policy.visibility,
        "public_facing": policy.public_facing,
        "wave": policy.wave,
        "operation": "update" if update else "enroll",
        "approval_required": True,
        "approved_approval_ids": list(policy.approved_approval_ids),
        "apply_allowed": policy.apply_allowed,
        "update_allowed": policy.update_allowed,
        "active_hold": policy.active_hold,
        "active_hold_reason": policy.active_hold_reason,
        "allow_dirty_worktree": policy.allow_dirty_worktree,
        "allow_non_main_branch": policy.allow_non_main_branch,
        "git_state": git_state,
        "hold_reasons": hold_reasons,
        "apply_ready": not hold_reasons and bool(policy.apply_allowed),
        "update_ready": not hold_reasons and bool(policy.update_allowed),
        "hook_install_disclosed": True,
        "dad_hub_ref": _hub_ref(hub_root, policy),
        "approved_dad_managed_paths": APPROVED_RELATIVE_PATHS,
        "repo_local_only_paths": REPO_LOCAL_ONLY_PATHS,
        "repo_local_only_boundary": REPO_LOCAL_ONLY_BOUNDARY,
        "normal_operation_write_boundary": ".digital-asset/mail/**",
        "cadence": {
            "mail": "daily",
            "asset_skill_template_enrollment_checks": "weekly",
            "preflight": "warn_only_when_stale",
        },
        "candidate_weekly_notices": WEEKLY_CHECKS,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _append_audit(hub_root: Path, event: dict[str, Any]) -> None:
    append_jsonl(
        hub_root / AUDIT_PATH,
        {
            "schema_version": ENROLLMENT_SCHEMA_VERSION,
            "created_at": utc_now(),
            **event,
        },
    )


def build_enrollment_plan(
    hub_root: Path,
    policies: Sequence[EnrollmentRepoPolicy],
    *,
    wave: str,
    update: bool = False,
) -> dict[str, Any]:
    hub_root = hub_root.resolve()
    plan_id = f"{'update' if update else 'enroll'}-{wave or 'selected'}"
    items = [_plan_item(policy, hub_root, update=update) for policy in policies]
    payload = {
        "schema_version": ENROLLMENT_SCHEMA_VERSION,
        "plan_id": plan_id,
        "generated_at": utc_now(),
        "wave": wave,
        "operation": "update" if update else "enroll",
        "item_count": len(items),
        "items": items,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    plan_dir = hub_root / ENROLLMENT_DIR / "plans"
    json_path = plan_dir / f"{plan_id}.json"
    md_path = plan_dir / f"{plan_id}.md"
    atomic_write_text(json_path, json_dumps(payload, pretty=True) + "\n")
    atomic_write_text(md_path, _plan_markdown(payload))
    for item in items:
        _append_audit(
            hub_root,
            {
                "event_type": "update_planned" if update else "planned",
                "plan_id": plan_id,
                "repo_id": item["repo_id"],
                "repo_ref": item["repo_ref"],
                "wave": wave,
                "approved_dad_managed_paths": APPROVED_RELATIVE_PATHS,
                "repo_local_only_paths": REPO_LOCAL_ONLY_PATHS,
                "repo_local_only_boundary": REPO_LOCAL_ONLY_BOUNDARY,
                "hook_install_disclosed": True,
                "git_state": item["git_state"],
                "hold_reasons": item["hold_reasons"],
                "apply_ready": item["apply_ready"],
                "update_ready": item["update_ready"],
            },
        )
    return {
        **payload,
        "plan_path": str((ENROLLMENT_DIR / "plans" / f"{plan_id}.json").as_posix()),
        "plan_markdown_path": str((ENROLLMENT_DIR / "plans" / f"{plan_id}.md").as_posix()),
    }


def _plan_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# DAD Enrollment Plan: {payload['plan_id']}",
        "",
        payload["authority_boundary"],
        "",
        "| Repo | Operation | Wave | Apply Ready | Update Ready | Branch | Dirty | Holds |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in payload["items"]:
        git_state = item["git_state"]
        holds = "; ".join(item["hold_reasons"]) if item["hold_reasons"] else ""
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{item['repo_id']}`",
                    f"`{item['operation']}`",
                    f"`{item['wave']}`",
                    str(item["apply_ready"]),
                    str(item["update_ready"]),
                    f"`{git_state.get('branch') or ''}`",
                    str(git_state.get("dirty_count", 0)),
                    holds,
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Approved DAD-managed paths:",
            "",
            *[f"- `{path}`" for path in APPROVED_RELATIVE_PATHS],
            "",
            "Repo-local exception bootstrap paths:",
            "",
            REPO_LOCAL_ONLY_BOUNDARY,
            "",
            *[f"- `{path}`" for path in REPO_LOCAL_ONLY_PATHS],
            "",
            "Normal recurring operation after enrollment writes only to `.digital-asset/mail/**`.",
        ]
    )
    return "\n".join(lines) + "\n"


def _target_path(repo_root: Path, rel: str, *, allow_local_only: bool = False) -> Path:
    allowed = set(APPROVED_RELATIVE_PATHS)
    if allow_local_only:
        allowed.update(REPO_LOCAL_ONLY_PATHS)
    if rel not in allowed:
        raise ValueError(f"Enrollment attempted to write an unapproved path: {rel}")
    root = repo_root.resolve()
    path = root / rel
    resolved = path.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ValueError(f"Enrollment path escapes repository boundary: {rel}")
    return path


def _write_text_if_changed(path: Path, text: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    atomic_write_text(path, text)
    return True


def _write_json_if_changed(path: Path, payload: dict[str, Any]) -> bool:
    return _write_text_if_changed(path, json_dumps(payload, pretty=True) + "\n")


def _managed_update(existing: str, begin: str, end: str, block: str) -> str:
    if begin in existing and end in existing:
        prefix, rest = existing.split(begin, 1)
        _, suffix = rest.split(end, 1)
        return prefix.rstrip() + "\n\n" + block + "\n" + suffix.lstrip("\n")
    return existing.rstrip() + "\n\n" + block + "\n"


def _write_managed_block(path: Path, default_text: str, begin: str, end: str, body: str) -> bool:
    existing = path.read_text(encoding="utf-8") if path.exists() else default_text
    block = f"{begin}\n{body.rstrip()}\n{end}"
    return _write_text_if_changed(path, _managed_update(existing, begin, end, block))


def _existing_installed_at(repo_root: Path) -> str:
    contract_path = repo_root / ".digital-asset" / "dad-integration.json"
    if not contract_path.exists():
        return utc_now()
    try:
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return utc_now()
    return str(payload.get("enrollment", {}).get("installed_at") or utc_now())


def _capture_surface_payload(hub_root: Path) -> dict[str, Any]:
    surface_version = "unknown"
    registry_path = hub_root / CAPTURE_PATTERN_REGISTRY
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            surface_version = str(registry.get("capture_surface_version") or surface_version)
        except (OSError, json.JSONDecodeError):
            surface_version = "unknown"
    return {
        "surface_version": surface_version,
        "pattern_registry_ref": (
            "dad://hub/Digital-Assett-Directory/"
            "registry/exception-capture-pattern-registry.json"
        ),
        "mail_outbox": ".digital-asset/mail/outbox.jsonl",
        "exceptions_outbox": ".digital-asset/exceptions/outbox.jsonl",
        "fix_outcomes": "processed/exceptions/fix-outcomes/outcomes.jsonl",
        "repo_local_only_paths": REPO_LOCAL_ONLY_PATHS,
        "cli_fallback": (
            "If asset-dir is unavailable, first try the stable DAD user shim at "
            "~/.dad/bin/asset-dir or ~/.dad/bin/asset-dir.ps1; if the shim is "
            "unavailable too, try PYTHONPATH=src python -m digital_asset_directory.cli "
            "from the DAD checkout; otherwise append metadata-only JSONL with "
            "dad_cli_unavailable and safe refs."
        ),
    }


def _contract_payload(
    policy: EnrollmentRepoPolicy, hub_root: Path, approval_id: str, *, update: bool
) -> dict[str, Any]:
    public_safe = _public_safe(policy)
    payload: dict[str, Any] = {
        "schema_version": ENROLLMENT_SCHEMA_VERSION,
        "repo_id": policy.id,
        "repo_alias": policy.alias,
        "repo_ref": _repo_ref(policy),
        "visibility": policy.visibility,
        "public_facing": policy.public_facing,
        "dad_hub": {
            "hub_id": "dad",
            "hub_ref": _hub_ref(hub_root, policy),
            "local_paths_included": not public_safe,
        },
        "enrollment": {
            "version": ENROLLMENT_VERSION,
            "status": "enrolled",
            "wave": policy.wave,
            "approval_id": approval_id,
            "installed_at": _existing_installed_at(policy.path),
            "last_operation": "update" if update else "enroll",
            "normal_write_boundary": ".digital-asset/mail/**",
            "one_time_full_governance_install": True,
        },
        "transport": {
            "surface_version": TRANSPORT_SURFACE_VERSION,
            "mode": "local_pull",
            "journal_fallback": True,
        },
        "cadence": {
            "mail": {
                "frequency": "daily",
                "preflight_behavior": "warn_only_when_stale",
                "stale_after_hours": 24,
            },
            "weekly_checks": {
                "frequency": "weekly",
                "checks": WEEKLY_CHECKS,
                "preflight_behavior": "warn_only_when_stale",
            },
        },
        "capture": _capture_surface_payload(hub_root),
        "agent_runtime_policy": AGENT_RUNTIME_POLICY,
        "enabled_control_planes": _enabled_control_planes(policy),
        "local_validation_commands": policy.validation_commands,
        "approved_dad_managed_paths": APPROVED_RELATIVE_PATHS,
        "return_address": _return_address(policy),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    if not public_safe:
        payload["repo_path"] = _normalize_path(policy.path)
    return payload


def _context_map_payload(policy: EnrollmentRepoPolicy, hub_root: Path) -> dict[str, Any]:
    return {
        "schema_version": ENROLLMENT_SCHEMA_VERSION,
        "repo_id": policy.id,
        "repo_alias": policy.alias,
        "repo_ref": _repo_ref(policy),
        "dad_hub_ref": _hub_ref(hub_root, policy),
        "context_dimensions": {
            "languages": policy.languages,
            "repo_type": policy.repo_type,
            "domains": policy.domains,
            "visibility": policy.visibility,
            "public_facing": policy.public_facing,
            "context_tags": policy.context_tags,
        },
        "routes": [
            {
                "route_id": "software-work-preflight",
                "use_when": [
                    "coding",
                    "refactoring",
                    "test-strategy",
                    "agent-instruction-design",
                ],
                "dad_assets": [
                    "dad://asset/assets/ai-engineering-preflight",
                    "dad://registry/preflight-profile-router",
                    "dad://registry/coding-tactics-radar",
                ],
                "control_planes": ["reusable_assets", "coding_test_parity", "learning_postflight_loops"],
            },
            {
                "route_id": "repo-governance-work",
                "use_when": ["governance", "schemas", "templates", "hooks", "repo-enrollment"],
                "dad_assets": [
                    "dad://docs/DOWNSTREAM_REPO_GOVERNANCE",
                    "dad://docs/DAD_REPO_ENROLLMENT",
                    "dad://registry/control-plane-registry",
                ],
                "control_planes": ["templates", "governance_maps", "data_maps"],
            },
        ],
        "mail_feedback": {
            "send_to": _return_address(policy),
            "message_types": [
                "lesson_suggestion",
                "asset_suggestion",
                "workflow_suggestion",
                "capability_suggestion",
                "governance_notice",
            ],
        },
        "authority_boundary": (
            "Context routes choose candidate DAD assets to consult. They do not "
            "override local repo authority, tests, or human approvals."
        ),
    }


def _governance_map_payload(policy: EnrollmentRepoPolicy, hub_root: Path) -> dict[str, Any]:
    return {
        "schema_version": ENROLLMENT_SCHEMA_VERSION,
        "repo_id": policy.id,
        "repo_ref": _repo_ref(policy),
        "dad_hub_ref": _hub_ref(hub_root, policy),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_authority": "target_repo_retains_local_canon",
        "agent_runtime_policy": AGENT_RUNTIME_POLICY,
        "dad_managed_surfaces": APPROVED_RELATIVE_PATHS,
        "normal_operation_write_boundary": ".digital-asset/mail/**",
        "control_planes": _enabled_control_planes(policy),
        "validation_commands": policy.validation_commands,
        "human_gates": [
            "enroll apply requires reviewed approval ID",
            "enroll update-apply requires reviewed approval ID",
            "private/internal/restricted/unknown-origin mail to public-facing repos requires human release",
        ],
    }


def _data_map_payload(policy: EnrollmentRepoPolicy, hub_root: Path) -> dict[str, Any]:
    return {
        "schema_version": ENROLLMENT_SCHEMA_VERSION,
        "repo_id": policy.id,
        "repo_ref": _repo_ref(policy),
        "dad_hub_ref": _hub_ref(hub_root, policy),
        "visibility": policy.visibility,
        "public_facing": policy.public_facing,
        "data_inputs": [
            {
                "name": "repo-local outbox mail",
                "path": ".digital-asset/mail/outbox.jsonl",
                "sensitivity_allowed": ["public", "internal"],
                "raw_private_content_allowed": False,
            }
        ],
        "generated_outputs": [
            ".digital-asset/mail/inbox.jsonl",
            ".digital-asset/mail/archive.jsonl",
            ".digital-asset/mail/last_checked.json",
            ".digital-asset/dad-integration.json",
            ".digital-asset/context-map.json",
        ],
        "sensitive_boundaries": [
            "Do not store secrets, credentials, raw private rows, or large copied source blobs in mail.",
            "Public-facing repos receive public-safe pointers by default.",
            "Private/internal/restricted/unknown origins require human release before public delivery.",
        ],
        "allowed_movement": {
            "normal_operation": ".digital-asset/mail/** only",
            "full_enrollment_or_update": "approved DAD-managed paths only with approval ID",
        },
        "authority_boundary": "Data map is candidate governance metadata until reviewed locally.",
    }


def _ai_assets_payload(policy: EnrollmentRepoPolicy, hub_root: Path) -> dict[str, Any]:
    return {
        "schema_version": ENROLLMENT_SCHEMA_VERSION,
        "pointer_type": "dad_coding_assets",
        "repo_id": policy.id,
        "hub": _hub_ref(hub_root, policy),
        "authority_boundary": (
            "This pointer helps local AI agents find DAD coding assets. It does not "
            "copy assets into this repo or authorize DAD to override local authority."
        ),
        "daily_check": {
            "mail_digest_stale_after_hours": 24,
            "preflight_behavior": "warn_only_when_stale",
        },
        "weekly_check": {
            "asset_skill_template_enrollment_stale_after_days": 7,
            "preflight_behavior": "warn_only_when_stale",
        },
        "assets": [
            {
                "asset_id": "asset:ai-engineering-preflight",
                "source": "dad://asset/assets/ai-engineering-preflight",
                "profiles": ["common", "python", "rust", "mixed-language"],
                "required_before": ["coding", "refactoring", "test-strategy"],
            },
            {
                "asset_id": "asset:python-ai-advantage-preflight",
                "source": "dad://asset/assets/python-ai-advantage-preflight",
                "profiles": ["python", "long-script-refactor"],
                "required_before": ["python-coding", "python-refactor"],
            },
            {
                "asset_id": "asset:preflight-profile-router",
                "source": "dad://registry/preflight-profile-router",
                "profiles": ["profile-router", "midflight-tactic-recommendation"],
                "required_before": ["high-risk-coding", "governance-sensitive-work"],
            },
        ],
        "do_not_copy_full_assets_without_approval": True,
        "local_adoption_required": True,
    }


def _skill_checkout_payload(policy: EnrollmentRepoPolicy, hub_root: Path) -> dict[str, Any]:
    return {
        "schema_version": ENROLLMENT_SCHEMA_VERSION,
        "pointer_type": "dad_agent_skill_checkout",
        "hub": _hub_ref(hub_root, policy),
        "authority_boundary": (
            "This pointer helps local AI agents find DAD-managed skills. It does not "
            "copy full skills or authorize DAD to override local authority."
        ),
        "daily_check": {
            "skill_digest_stale_after_hours": 24,
            "preflight_behavior": "warn_only_when_stale",
        },
        "source_provenance": {
            "source_repo_id": "dad",
            "source_repo_alias": "Digital-Assett-Directory",
            "source_visibility": "internal",
            "source_registry": "dad://registry/agent-skill-library",
            "return_address": _return_address(policy),
            "local_paths_included": not _public_safe(policy),
        },
        "checked_out_skills": [
            {
                "skill_id": "skill:dad-coding-asset-control-plane",
                "source": "dad://skill/skill:dad-coding-asset-control-plane/0.1.0",
                "entrypoint": "dad://skill/skill:dad-coding-asset-control-plane/0.1.0/SKILL.md",
                "version": "0.1.0",
                "status": "active",
                "skill_format": "codex_skill",
                "checkout_mode": "pointer",
                "return_address": _return_address(policy),
                "update_channel": "dad_mail",
                "required_before": [
                    "coding",
                    "refactoring",
                    "repo-template-creation",
                    "test-strategy",
                    "agent-instruction-design",
                ],
                "capabilities": [
                    "preflight_profile_routing",
                    "coding_tactic_selection",
                    "downstream_pointer_guidance",
                    "postflight_pay_forward",
                ],
            }
        ],
        "do_not_copy_full_skills_without_approval": True,
        "local_adoption_required": True,
    }


def _agents_body(policy: EnrollmentRepoPolicy, hub_root: Path) -> str:
    hub_ref = _hub_ref(hub_root, policy)
    return f"""## Digital Asset Directory enrollment contract

Repo enrollment ID: `{policy.id}`
Central DAD hub: `{hub_ref}` resolved by `--hub`, `DAD_HUB`, or
`~/.dad/hub.json`.
Contract: `.digital-asset/dad-integration.json`

Before material AI-assisted work, read this repo's front door and run:

```text
asset-dir agent preflight --repo . --agent <agent-id> --task "<task>"
```

Use the actual runtime name as `<agent-id>` when useful, such as `codex`,
`claude-code`, `cursor`, `copilot`, `human`, `ci`, or `other`. DAD's core
contract is `AGENTS.md`; runtime-specific files and hooks are optional wrappers
and must not become the only place where governance rules live.

Read the returned `context_pack` before editing. If DAD is unavailable, local
coding may continue with a logged warning, but cross-repo writes, public
release, enrollment apply/update, protected repo work, and mail containing
sensitive payloads fail closed unless a named human bypass is recorded.

Use `.digital-asset/context-map.json` to decide which DAD assets, skills,
templates, architecture references, governance maps, or data maps are relevant.
Mail is checked daily by digest; asset, skill, template, architecture,
governance-map, data-map, and enrollment freshness checks are weekly and should
surface preflight warnings only when stale.

DAD may write broadly only during `asset-dir enroll apply` or
`asset-dir enroll update-apply` with a reviewed approval ID. Normal recurring
DAD operation writes only to `.digital-asset/mail/**`.

Mail, assets, skills, and templates are candidate evidence until reviewed
locally. This repo keeps local source authority and decides whether to adopt
any suggestion. Public-facing repos cannot receive private/internal/
restricted/unknown-origin mail without a DAD human release record.

If work is PR-ready, an actual PR is open, or a branch is intentionally left
after a work session, record branch/PR status, owner or next reviewer,
validation refs, next action, and escalation date. Send metadata-only DAD mail
for stuck, superseded, duplicate, conflict-heavy, or stale PR/branch queues when
local policy allows.

Close material work with postflight and include the preflight trace ID plus any
used, ignored, failed, or harmful DAD recommendations.
"""


def _front_door_body(policy: EnrollmentRepoPolicy) -> str:
    return f"""## Digital Asset Directory Enrollment

- Contract: `.digital-asset/dad-integration.json`
- Context map: `.digital-asset/context-map.json`
- Mailbox: `.digital-asset/mail/`
- Governance map: `.digital-asset/governance-map.yaml`
- Data map: `.digital-asset/data-map.yaml`
- Skill checkout: `.digital-asset/skills/checkout.json`
- Coding asset pointer: `.ai-assets.json`
- Asset memory: `.digital-asset/assets/index.jsonl`

Use these surfaces when work involves AI-assisted coding, repo governance,
lessons, reusable assets, templates, agent skills, or cross-repo suggestions.
DAD mail is candidate-only and local review controls adoption for `{policy.id}`.
Use `.digital-asset/assets/` for compact metadata-only asset cards. DAD's
address model uses 9 compact layers with layer 9 as learning/adaptation; put
long workflow details in workflow cards or source docs and reference them.
"""


def _toc_body() -> str:
    return """| Path | What It Is | Tags | Use When |
| --- | --- | --- | --- |
| `.digital-asset/dad-integration.json` | Versioned DAD enrollment contract and approved write boundary. | dad, enrollment, governance | Confirm DAD cadence, control planes, approval IDs, and managed paths. |
| `.digital-asset/context-map.json` | Repo context to DAD asset/control-plane route map. | dad, context, assets | Choose relevant DAD assets, skills, templates, or architecture references for a task. |
| `.digital-asset/governance-map.yaml` | Repo-local governance dependency mirror. | governance, authority, dependencies | Check local authority boundaries and DAD-managed surfaces. |
| `.digital-asset/data-map.yaml` | Repo-local sensitive-boundary and data-movement map. | data-map, privacy, release | Check what data can move through DAD mail or public-facing release paths. |
| `.digital-asset/mail/` | Candidate-only DAD inbox/outbox/archive. | mail, suggestions, daily | Read or send cross-repo suggestions without mutating source authority. |
| `.digital-asset/assets/index.jsonl` | Repo-local metadata-only digital asset cards using compact DAD address layers. | assets, address-model, learning | Record source-owned asset pointers, workflow refs, validation refs, and learning deltas without copying private content. |
"""


def _claude_body() -> str:
    return """@AGENTS.md

Claude Code should follow the DAD enrollment contract in `AGENTS.md` and
`.digital-asset/dad-integration.json`. `CLAUDE.md` is an optional runtime
adapter, not the DAD source of truth. Agent review is triage only; human
approval gates remain separate.
"""


def _hook_text(hub_root: Path, policy: EnrollmentRepoPolicy) -> str:
    hub_line = 'DAD_HUB="${DAD_HUB:-${DAD_HUB_PATH:-}}"'
    locator = (
        'if [ -z "$DAD_HUB" ] && [ -f "$HOME/.dad/hub.json" ]; then\n'
        "  DAD_HUB=\"$(python -c 'import json,pathlib; "
        'p=pathlib.Path.home()/".dad"/"hub.json"; '
        'd=json.loads(p.read_text(encoding="utf-8")); '
        'print(d.get("hub_path") or d.get("path") or "")'
        "')\"\n"
        "fi\n"
    )
    missing = (
        'if [ -z "$DAD_HUB" ]; then\n'
        '  echo "DAD_HUB, DAD_HUB_PATH, or ~/.dad/hub.json is required before this DAD hook can enforce postflight." >&2\n'
        "  exit 1\n"
        "fi\n"
    )
    return (
        "#!/usr/bin/env sh\n"
        "set -eu\n"
        f"{hub_line}\n"
        f"{locator}"
        f"{missing}"
        'python "$DAD_HUB/scripts/enforce_postflight.py" --hub "$DAD_HUB" --repo "$(pwd)"\n'
    )


def _ps_hook_text(hub_root: Path, policy: EnrollmentRepoPolicy) -> str:
    hub_line = "$DadHub = if ($env:DAD_HUB) { $env:DAD_HUB } else { $env:DAD_HUB_PATH }"
    locator = (
        "if (-not $DadHub) {\n"
        "  $Locator = Join-Path $HOME '.dad/hub.json'\n"
        "  if (Test-Path $Locator) {\n"
        "    $Payload = Get-Content $Locator -Raw | ConvertFrom-Json\n"
        "    $DadHub = if ($Payload.hub_path) { $Payload.hub_path } else { $Payload.path }\n"
        "  }\n"
        "}\n"
    )
    missing = (
        "if (-not $DadHub) {\n"
        "  Write-Error 'DAD_HUB, DAD_HUB_PATH, or ~/.dad/hub.json is required before this DAD hook can enforce postflight.'\n"
        "  exit 1\n"
        "}\n"
    )
    return (
        "$ErrorActionPreference = 'Stop'\n"
        f"{hub_line}\n"
        f"{locator}"
        f"{missing}"
        "python \"$DadHub/scripts/enforce_postflight.py\" --hub \"$DadHub\" --repo (Get-Location).Path\n"
    )


def _write_mailbox(repo_root: Path, changed: list[str]) -> None:
    for rel, text in {
        ".digital-asset/mail/README.md": mail_readme_text(),
        ".digital-asset/mail/.gitignore": mail_gitignore_text(),
    }.items():
        if _write_text_if_changed(_target_path(repo_root, rel), text):
            changed.append(rel)
    for rel in (
        ".digital-asset/mail/inbox.jsonl",
        ".digital-asset/mail/outbox.jsonl",
        ".digital-asset/mail/archive.jsonl",
        ".digital-asset/mail/adoption.jsonl",
    ):
        path = _target_path(repo_root, rel)
        if not path.exists():
            atomic_write_text(path, "")
            changed.append(rel)


def _exception_gitignore_text() -> str:
    return "*.jsonl\n*.lock\nlast_*.json\n"


def _exception_readme_text(hub_root: Path) -> str:
    template = hub_root / DOWNSTREAM_EXCEPTION_README
    if template.exists():
        return template.read_text(encoding="utf-8")
    return (
        "# DAD Exceptions Outbox\n\n"
        "Append metadata-only exception packets to `outbox.jsonl`. Do not copy "
        "secrets, raw logs, private rows, source blobs, or hidden reasoning. "
        "DAD treats these rows as candidate evidence until locally reviewed.\n\n"
        "## Never Send\n\n"
        "Do not send credentials, tokens, cookies, private keys, raw logs, full "
        "stack traces, copied private rows, complete source files, generated "
        "diffs, hidden reasoning, or long pasted payloads.\n"
    )


def _write_exception_surface(repo_root: Path, hub_root: Path, changed: list[str]) -> None:
    for rel, text in {
        ".digital-asset/exceptions/README.md": _exception_readme_text(hub_root),
        ".digital-asset/exceptions/.gitignore": _exception_gitignore_text(),
    }.items():
        if _write_text_if_changed(_target_path(repo_root, rel, allow_local_only=True), text):
            changed.append(rel)
    for rel in (
        ".digital-asset/exceptions/outbox.jsonl",
        ".digital-asset/exceptions/inbox.jsonl",
        ".digital-asset/exceptions/archive.jsonl",
    ):
        path = _target_path(repo_root, rel, allow_local_only=True)
        if not path.exists():
            atomic_write_text(path, "")
            changed.append(rel)


def _asset_memory_readme_text(hub_root: Path) -> str:
    template = hub_root / DOWNSTREAM_ASSETS_README
    if template.exists():
        return template.read_text(encoding="utf-8")
    return (
        "# DAD Repo-Local Digital Asset Memory\n\n"
        "This directory stores source-repo owned candidate asset cards for DAD. "
        "Rows are metadata pointers only. Do not copy secrets, private rows, raw "
        "source blobs, large generated outputs, or governed source authority into "
        "`index.jsonl`.\n"
    )


def _write_asset_memory_surface(repo_root: Path, hub_root: Path, changed: list[str]) -> None:
    if _write_text_if_changed(
        _target_path(repo_root, ".digital-asset/assets/README.md"),
        _asset_memory_readme_text(hub_root),
    ):
        changed.append(".digital-asset/assets/README.md")
    for rel in (
        ".digital-asset/assets/index.jsonl",
        ".digital-asset/assets/adoption.jsonl",
        ".digital-asset/learning/events.jsonl",
    ):
        path = _target_path(repo_root, rel)
        if not path.exists():
            atomic_write_text(path, "")
            changed.append(rel)


def _apply_payloads(
    policy: EnrollmentRepoPolicy, hub_root: Path, approval_id: str, *, update: bool
) -> list[str]:
    repo_root = policy.path.resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise ValueError(f"Enrollment target repo does not exist: {policy.id}")
    changed: list[str] = []

    payloads = {
        ".digital-asset/dad-integration.json": _contract_payload(
            policy, hub_root, approval_id, update=update
        ),
        ".digital-asset/context-map.json": _context_map_payload(policy, hub_root),
        ".ai-assets.json": _ai_assets_payload(policy, hub_root),
        ".digital-asset/skills/checkout.json": _skill_checkout_payload(policy, hub_root),
    }
    for rel, payload in payloads.items():
        if _write_json_if_changed(_target_path(repo_root, rel), payload):
            changed.append(rel)

    yaml_payloads = {
        ".digital-asset/governance-map.yaml": _governance_map_payload(policy, hub_root),
        ".digital-asset/data-map.yaml": _data_map_payload(policy, hub_root),
    }
    for rel, payload in yaml_payloads.items():
        if _write_text_if_changed(
            _target_path(repo_root, rel),
            yaml.safe_dump(payload, sort_keys=False),
        ):
            changed.append(rel)

    _write_mailbox(repo_root, changed)
    _write_asset_memory_surface(repo_root, hub_root, changed)
    _write_exception_surface(repo_root, hub_root, changed)

    if _write_managed_block(
        _target_path(repo_root, "AGENTS.md"),
        "# Agent Instructions\n",
        GOVERNANCE_BEGIN,
        GOVERNANCE_END,
        _agents_body(policy, hub_root),
    ):
        changed.append("AGENTS.md")
    if _write_managed_block(
        _target_path(repo_root, "CLAUDE.md"),
        "# Claude Code Instructions\n",
        CLAUDE_BEGIN,
        CLAUDE_END,
        _claude_body(),
    ):
        changed.append("CLAUDE.md")
    if _write_managed_block(
        _target_path(repo_root, "AI_FRONT_DOOR.md"),
        "# AI Front Door\n",
        ENROLLMENT_BEGIN,
        ENROLLMENT_END,
        _front_door_body(policy),
    ):
        changed.append("AI_FRONT_DOOR.md")
    if _write_managed_block(
        _target_path(repo_root, "AI_TABLE_OF_CONTENTS.md"),
        "# AI Table Of Contents\n",
        TOC_BEGIN,
        TOC_END,
        _toc_body(),
    ):
        changed.append("AI_TABLE_OF_CONTENTS.md")

    hook = _target_path(repo_root, ".githooks/pre-push")
    if _write_text_if_changed(hook, _hook_text(hub_root, policy)):
        changed.append(".githooks/pre-push")
    try:
        hook.chmod(0o755)
    except OSError:
        pass
    if _write_text_if_changed(
        _target_path(repo_root, ".githooks/pre-push.ps1"),
        _ps_hook_text(hub_root, policy),
    ):
        changed.append(".githooks/pre-push.ps1")
    return changed


def _approval_error(policy: EnrollmentRepoPolicy, approval_id: str, *, update: bool) -> str | None:
    if not policy.enrollment_enabled:
        return f"Enrollment is disabled for repo policy: {policy.id}"
    allowed = policy.update_allowed if update else policy.apply_allowed
    if not allowed:
        operation = "update-apply" if update else "apply"
        return f"Enrollment {operation} is not allowed by reviewed policy: {policy.id}"
    if approval_id not in policy.approved_approval_ids:
        return f"Approval ID is not reviewed for repo policy {policy.id}: {approval_id}"
    return None


def _hold_error(policy: EnrollmentRepoPolicy) -> tuple[str | None, dict[str, Any], list[str]]:
    git_state = _repo_git_state(policy.path.resolve())
    hold_reasons = _policy_hold_reasons(policy, git_state)
    if hold_reasons:
        return (
            f"Enrollment is held for repo policy {policy.id}: "
            + "; ".join(hold_reasons),
            git_state,
            hold_reasons,
        )
    return None, git_state, hold_reasons


def apply_enrollment(
    hub_root: Path,
    policy: EnrollmentRepoPolicy,
    *,
    approval_id: str,
    update: bool = False,
) -> dict[str, Any]:
    hub_root = hub_root.resolve()
    error = _approval_error(policy, approval_id, update=update)
    if error:
        _append_audit(
            hub_root,
            {
                "event_type": "blocked",
                "operation": "update" if update else "enroll",
                "repo_id": policy.id,
                "repo_ref": _repo_ref(policy),
                "approval_id": approval_id,
                "reason": error,
            },
        )
        raise ValueError(error)

    error, git_state, hold_reasons = _hold_error(policy)
    if error:
        _append_audit(
            hub_root,
            {
                "event_type": "blocked",
                "operation": "update" if update else "enroll",
                "repo_id": policy.id,
                "repo_ref": _repo_ref(policy),
                "approval_id": approval_id,
                "reason": error,
                "git_state": git_state,
                "hold_reasons": hold_reasons,
            },
        )
        raise ValueError(error)

    try:
        changed_paths = _apply_payloads(policy, hub_root, approval_id, update=update)
    except ValueError as exc:
        _append_audit(
            hub_root,
            {
                "event_type": "failed",
                "operation": "update" if update else "enroll",
                "repo_id": policy.id,
                "repo_ref": _repo_ref(policy),
                "approval_id": approval_id,
                "reason": str(exc),
            },
        )
        raise
    event_type = "updated" if update else "applied"
    _append_audit(
        hub_root,
        {
            "event_type": event_type,
            "operation": "update" if update else "enroll",
            "repo_id": policy.id,
            "repo_ref": _repo_ref(policy),
            "approval_id": approval_id,
            "changed_paths": changed_paths,
            "approved_dad_managed_paths": APPROVED_RELATIVE_PATHS,
            "repo_local_only_paths": REPO_LOCAL_ONLY_PATHS,
            "repo_local_only_boundary": REPO_LOCAL_ONLY_BOUNDARY,
            "normal_operation_write_boundary": ".digital-asset/mail/**",
            "hook_install_disclosed": True,
            "git_state": git_state,
        },
    )
    return {
        "repo_id": policy.id,
        "repo_ref": _repo_ref(policy),
        "operation": "update" if update else "enroll",
        "changed_paths": changed_paths,
        "changed_count": len(changed_paths),
        "approval_id": approval_id,
        "hook_install_disclosed": True,
        "hook_activation_command": "git config core.hooksPath .githooks",
        "repo_local_only_paths": REPO_LOCAL_ONLY_PATHS,
        "repo_local_only_boundary": REPO_LOCAL_ONLY_BOUNDARY,
        "normal_operation_write_boundary": ".digital-asset/mail/**",
        "git_state": git_state,
        "audit_path": AUDIT_PATH.as_posix(),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def enrollment_status(
    policy: EnrollmentRepoPolicy, *, stale_hours: int = 24
) -> dict[str, Any]:
    repo_root = policy.path.resolve()
    contract_path = repo_root / ".digital-asset" / "dad-integration.json"
    contract: dict[str, Any] | None = None
    errors: list[str] = []
    if contract_path.exists():
        try:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            schema_path = Path(__file__).resolve().parents[2] / REPO_ENROLLMENT_SCHEMA
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            validator_cls = validator_for(schema)
            validator_cls.check_schema(schema)
            validator_cls(schema).validate(contract)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Invalid enrollment contract: {exc}")
        except ValidationError as exc:
            errors.append(f"Enrollment contract schema validation failed: {exc.message}")
    if contract:
        for rel in (
            ".digital-asset/exceptions/README.md",
            ".digital-asset/exceptions/.gitignore",
            ".digital-asset/exceptions/outbox.jsonl",
            ".digital-asset/exceptions/inbox.jsonl",
            ".digital-asset/exceptions/archive.jsonl",
        ):
            if not _target_path(repo_root, rel, allow_local_only=True).exists():
                errors.append(f"Missing repo-local exception surface path: {rel}")
    mail_status = mail_digest_status(repo_root, stale_hours=stale_hours)
    contract_version = (
        str(contract.get("enrollment", {}).get("version", "")) if contract else ""
    )
    transport_block = contract.get("transport", {}) if contract else {}
    transport_version = str(transport_block.get("surface_version", ""))
    transport_status = "missing"
    if contract and not isinstance(transport_block, dict):
        transport_status = "invalid"
        errors.append("Enrollment contract transport block is invalid")
    elif contract and not transport_version:
        transport_status = "contract_missing"
        errors.append("Enrollment contract missing transport.surface_version")
    elif contract and transport_version != TRANSPORT_SURFACE_VERSION:
        transport_status = "stale"
        errors.append(
            "Enrollment contract transport.surface_version "
            f"{transport_version} != {TRANSPORT_SURFACE_VERSION}"
        )
    elif contract:
        transport_status = "current"
    enabled_planes = contract.get("enabled_control_planes", []) if contract else []
    return {
        "repo_id": policy.id,
        "repo_ref": _repo_ref(policy),
        "configured": True,
        "enrolled": contract is not None,
        "contract_version": contract_version,
        "update_available": contract_version != ENROLLMENT_VERSION or bool(errors),
        "policy_wave": policy.wave,
        "mail_digest": mail_status,
        "weekly_check_stale": True,
        "transport": {
            "status": transport_status,
            "surface_version": transport_version,
            "expected_surface_version": TRANSPORT_SURFACE_VERSION,
        },
        "enabled_control_planes": enabled_planes,
        "repo_local_only_paths": REPO_LOCAL_ONLY_PATHS,
        "repo_local_only_boundary": REPO_LOCAL_ONLY_BOUNDARY,
        "errors": errors,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def enrollment_status_all(
    policies: Sequence[EnrollmentRepoPolicy], *, stale_hours: int = 24
) -> dict[str, Any]:
    rows = [enrollment_status(policy, stale_hours=stale_hours) for policy in policies]
    return {
        "repo_count": len(rows),
        "rows": rows,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
