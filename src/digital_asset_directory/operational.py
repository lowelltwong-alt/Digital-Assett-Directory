from __future__ import annotations

import json
import os
import copy
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from functools import lru_cache
from importlib import metadata
from pathlib import Path
from typing import Any

from .catalog import catalog_status
from .config import AppConfig, describe_hub_resolution, is_dad_hub_root, read_hub_locator
from .roadmap import check_roadmap
from .utils import atomic_write_text, json_dumps, utc_now
from .validation import validate_repo

CORE_SURFACES = [
    {
        "path": "AI_FRONT_DOOR.md",
        "purpose": "single AI entrypoint",
        "kind": "tracked",
        "required_for": "front_door",
    },
    {
        "path": "AI_TABLE_OF_CONTENTS.md",
        "purpose": "deterministic AI routing map",
        "kind": "tracked",
        "required_for": "front_door",
    },
    {
        "path": "MACHINE_NAVIGATION_MANIFEST.json",
        "purpose": "machine-readable navigation map",
        "kind": "tracked",
        "required_for": "front_door",
    },
    {
        "path": "state/catalog.sqlite3",
        "purpose": "local catalog database",
        "kind": "generated",
        "required_for": "catalog",
    },
    {
        "path": "processed/catalog/assets.jsonl",
        "purpose": "generated asset catalog",
        "kind": "generated",
        "required_for": "catalog",
    },
    {
        "path": "processed/graph/graph.json",
        "purpose": "generated candidate graph",
        "kind": "generated",
        "required_for": "knowledge_graph",
    },
    {
        "path": "processed/reports/scan_summary.md",
        "purpose": "latest local scan summary",
        "kind": "generated",
        "required_for": "scan_evidence",
    },
    {
        "path": "processed/alerts/alert_inbox.md",
        "purpose": "reviewable alert inbox",
        "kind": "generated",
        "required_for": "review_queue",
    },
    {
        "path": "processed/reports/workflow_part_usage_guidance.md",
        "purpose": "manual reviewed workflow-part guidance",
        "kind": "generated",
        "required_for": "workflow_part_guidance",
    },
    {
        "path": "roadmap/evidence/workflow-part-usage-guidance.md",
        "purpose": "tracked workflow-part guidance evidence",
        "kind": "tracked",
        "required_for": "workflow_part_guidance",
    },
]

VALIDATION_COMMANDS = [
    "python -m pytest",
    "python -m ruff check src tests scripts noxfile.py",
    "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate",
    "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update",
]

DOCTOR_CHILD_PROBE_ENV = "DAD_DOCTOR_CHILD_INVOCATION_PROBE"

UNAVAILABLE_HUB_POLICY = {
    "ordinary_local_coding": {
        "decision": "warn_and_continue",
        "logging_required": True,
        "reason": "Local source-authority work can continue when DAD is down, but agents must not pretend DAD context was available.",
    },
    "hard_gates": [
        "cross_repo_writes",
        "public_release",
        "enrollment_apply",
        "enrollment_update",
        "protected_repo_work",
        "mail_with_sensitive_payload",
    ],
    "hard_gate_decision": "fail_closed",
    "bypass": {
        "allowed": "named_human_acknowledgement_only",
        "command": (
            "asset-dir dad unavailable-ack --operation <operation> --reason <reason> "
            "--reviewed-by <human>"
        ),
        "fallback_audit": "~/.dad/audit/unavailable-acks.jsonl when the DAD hub cannot be resolved",
        "authority_boundary": "A bypass acknowledgement is an audit record, not blanket approval.",
    },
}

RECOVERY_GUIDANCE_MISSING_CODES = (
    "asset-dir-not-on-path",
    "user-shim-not-found",
    "external-invocation-not-verified",
    "hub-locator-missing-or-stale",
)

RECOVERY_GUIDANCE_PREFERRED_ACTIONS = (
    "none",
    "add_user_bin_to_path_or_use_direct_shim",
    "run_bootstrap_from_dad_hub",
)

RECOVERY_GUIDANCE_LOCAL_PATH_FIELDS = (
    "bootstrap_commands",
    "working_directory",
    "dad_hub",
    "user_bin_dir",
    "path_entry",
    "add_to_path_hint",
    "direct_shim_commands",
    "raw_checkout_fallback_command",
)


def _recovery_guidance_contract() -> dict[str, Any]:
    return {
        "schema_version": "dad_deployment_recovery_guidance_contract.v1",
        "allowed_missing_or_unverified": list(RECOVERY_GUIDANCE_MISSING_CODES),
        "allowed_preferred_actions": list(RECOVERY_GUIDANCE_PREFERRED_ACTIONS),
        "local_path_fields": list(RECOVERY_GUIDANCE_LOCAL_PATH_FIELDS),
        "boundary_required": True,
        "authority_boundary": (
            "This contract describes local recovery-guidance shape only. It does not "
            "authorize target repo writes, enrollment, mail delivery, or public release."
        ),
    }


@lru_cache(maxsize=16)
def _command_version_cached(argv: tuple[str, ...]) -> dict[str, Any]:
    executable = shutil.which(argv[0])
    if not executable:
        return {"available": False, "argv": list(argv), "path": "", "version": "", "error": ""}
    try:
        completed = subprocess.run(
            list(argv),
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "argv": list(argv), "path": executable, "version": "", "error": str(exc)}
    output = (completed.stdout or completed.stderr).strip().splitlines()
    return {
        "available": completed.returncode == 0,
        "argv": list(argv),
        "path": executable,
        "version": output[0] if output else "",
        "returncode": completed.returncode,
        "error": "" if completed.returncode == 0 else (completed.stderr or completed.stdout).strip(),
    }


def _command_version(argv: list[str]) -> dict[str, Any]:
    return dict(_command_version_cached(tuple(argv)))


def _package_version() -> str:
    try:
        return metadata.version("digital-asset-directory")
    except metadata.PackageNotFoundError:
        return "editable-or-source-checkout"


def _policy_reachability(config: AppConfig) -> dict[str, Any]:
    return {
        "mail_repo_count": len(config.mail_repos),
        "exception_repo_count": len(config.exception_repos),
        "enrollment_repo_count": len(config.enrollment_repos),
        "mail_enabled_count": sum(1 for item in config.mail_repos if item.mail_enabled),
        "exception_enabled_count": sum(
            1 for item in config.exception_repos if item.exceptions_enabled
        ),
        "enrollment_enabled_count": sum(
            1 for item in config.enrollment_repos if item.enrollment_enabled
        ),
    }


def _hub_install_integrity(repo_root: Path) -> dict[str, Any]:
    required_files = [
        "AI_FRONT_DOOR.md",
        "AI_TABLE_OF_CONTENTS.md",
        "MACHINE_NAVIGATION_MANIFEST.json",
        "registry/source-of-truth.json",
        "registry/design-authority.json",
        "registry/schema-registry.json",
        "src/digital_asset_directory/cli.py",
        "src/digital_asset_directory/config.py",
        "src/digital_asset_directory/operational.py",
    ]
    missing = [rel for rel in required_files if not (repo_root / rel).is_file()]
    cli_path = repo_root / "src" / "digital_asset_directory" / "cli.py"
    cli_entrypoint_valid = False
    cli_error = ""
    try:
        cli_text = cli_path.read_text(encoding="utf-8")
        cli_entrypoint_valid = (
            "app = typer.Typer" in cli_text
            and "def doctor(" in cli_text
        )
    except OSError as exc:
        cli_error = str(exc)
    return {
        "valid": not missing and cli_entrypoint_valid,
        "required_files": required_files,
        "missing": missing,
        "cli_entrypoint_valid": cli_entrypoint_valid,
        "cli_error": cli_error,
        "authority_boundary": "Install integrity checks local DAD hub shape only; they do not execute target repo code or authorize cross-repo writes.",
    }


def _user_shim_candidates() -> list[Path]:
    bin_dir = Path.home() / ".dad" / "bin"
    if os.name == "nt":
        return [bin_dir / "asset-dir.ps1", bin_dir / "asset-dir.cmd"]
    return [bin_dir / "asset-dir"]


def _path_contains(path_value: str, target: Path) -> bool:
    target_resolved = target.resolve()
    target_text = str(target_resolved)
    if os.name == "nt":
        target_text = target_text.casefold()
    for item in path_value.split(os.pathsep):
        if not item.strip():
            continue
        try:
            candidate = Path(item).expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        candidate_text = str(candidate)
        if os.name == "nt":
            candidate_text = candidate_text.casefold()
        if candidate_text == target_text:
            return True
    return False


def _path_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _hub_requires_module_identity(repo_root: Path) -> bool:
    try:
        text = (
            repo_root
            / "src"
            / "digital_asset_directory"
            / "operational.py"
        ).read_text(encoding="utf-8")
    except OSError:
        return False
    return "def build_deployment_status" in text and "DOCTOR_CHILD_PROBE_ENV" in text


def _shim_command(path: Path) -> list[str]:
    if os.name == "nt" and path.suffix.lower() == ".ps1":
        powershell = shutil.which("powershell") or shutil.which("pwsh") or "powershell"
        return [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(path),
        ]
    return [str(path)]


def _deployment_recovery_guidance(
    *,
    repo_root: Path,
    asset_dir_on_path: bool,
    available_shims: list[Path],
    module_fallback_available: bool,
    external_invocation_ready: bool,
    locator_points_to_hub: bool,
) -> dict[str, Any]:
    bin_dir = Path.home() / ".dad" / "bin"
    bootstrap_ps1 = repo_root / "scripts" / "bootstrap.ps1"
    bootstrap_sh = repo_root / "scripts" / "bootstrap.sh"
    bootstrap_commands = {
        "windows_powershell": f"& '{bootstrap_ps1}'",
        "posix_shell": f"'{bootstrap_sh}'",
    }
    direct_shim_commands = []
    for path in available_shims:
        if os.name == "nt" and path.suffix.lower() in {".ps1", ".cmd", ".bat"}:
            direct_shim_commands.append(f"& '{path}' doctor --scope deployment")
        else:
            direct_shim_commands.append(f"'{path}' doctor --scope deployment")
    if not direct_shim_commands:
        if os.name == "nt":
            direct_shim_commands.extend(
                [
                    f"& '{bin_dir / 'asset-dir.ps1'}' doctor --scope deployment",
                    f"'{bin_dir / 'asset-dir.cmd'}' doctor --scope deployment",
                ]
            )
        else:
            direct_shim_commands.append(f"'{bin_dir / 'asset-dir'}' doctor --scope deployment")
    raw_checkout_fallback_command = ""
    if module_fallback_available:
        raw_checkout_fallback_command = (
            "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli doctor --scope deployment"
            if os.name == "nt"
            else "PYTHONPATH=src python -m digital_asset_directory.cli doctor --scope deployment"
        )
    missing_or_unverified: list[str] = []
    if not asset_dir_on_path:
        missing_or_unverified.append("asset-dir-not-on-path")
    if not available_shims:
        missing_or_unverified.append("user-shim-not-found")
    if not external_invocation_ready:
        missing_or_unverified.append("external-invocation-not-verified")
    if not locator_points_to_hub:
        missing_or_unverified.append("hub-locator-missing-or-stale")
    if not external_invocation_ready or not locator_points_to_hub:
        preferred_action = "run_bootstrap_from_dad_hub"
    elif not asset_dir_on_path:
        preferred_action = "add_user_bin_to_path_or_use_direct_shim"
    else:
        preferred_action = "none"
    return {
        "schema_version": "dad_deployment_recovery_guidance.v1",
        "contract": _recovery_guidance_contract(),
        "needed": bool(missing_or_unverified),
        "missing_or_unverified": missing_or_unverified,
        "preferred_action": preferred_action,
        "bootstrap_commands": bootstrap_commands,
        "working_directory": str(repo_root),
        "dad_hub": str(repo_root),
        "user_bin_dir": str(bin_dir),
        "path_entry": str(bin_dir),
        "add_to_path_hint": f"Add {bin_dir} to PATH for plain `asset-dir` from any repo.",
        "direct_shim_commands": direct_shim_commands,
        "raw_checkout_fallback_command": raw_checkout_fallback_command,
        "write_targets": [
            "~/.dad/hub.json",
            "~/.dad/bin/asset-dir",
            "~/.dad/bin/asset-dir.ps1",
            "~/.dad/bin/asset-dir.cmd",
        ],
        "non_target_repo_write_boundary": (
            "Deployment recovery writes only user-level DAD locator/shims and the DAD hub "
            "virtualenv. It does not authorize writes to the caller repo or other target repos."
        ),
    }


def _probe_dad_invocation(argv: list[str], repo_root: Path) -> dict[str, Any]:
    if not argv:
        return {"available": False, "verified": False, "argv": [], "error": "missing command"}
    with tempfile.TemporaryDirectory(prefix="dad-doctor-probe-") as temp_dir:
        locator = Path(temp_dir) / "hub.json"
        env = dict(os.environ)
        env[DOCTOR_CHILD_PROBE_ENV] = "1"
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        command = [
            *argv,
            "doctor",
            "--hub",
            str(repo_root),
            "--scope",
            "deployment",
            "--locator",
            str(locator),
            "--write-hub-locator",
            "--skip-invocation-probes",
        ]
        try:
            completed = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
                env=env,
                cwd=temp_dir,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "available": False,
                "verified": False,
                "argv": argv,
                "error": str(exc),
            }
        locator_readback = read_hub_locator(locator)
        payload: dict[str, Any] = {}
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {}
        hub_path = (
            payload.get("deployment", {})
            .get("hub_resolution", {})
            .get("hub_path", "")
            if isinstance(payload, dict)
            else ""
        )
        deployment = payload.get("deployment", {}) if isinstance(payload, dict) else {}
        python_info = deployment.get("python", {}) if isinstance(deployment, dict) else {}
        module_file = str(python_info.get("operational_module_file", "")).strip()
        module_path = Path(module_file) if module_file else Path()
        module_attestation_verified = (
            bool(module_file)
            and python_info.get("operational_module_points_to_hub") is True
            and _path_within(module_path, repo_root)
        )
        module_identity_required = _hub_requires_module_identity(repo_root)
        locator_verified = (
            bool(locator_readback.get("is_dad_hub"))
            and locator_readback.get("hub_path") == str(repo_root)
        )
        verified = (
            completed.returncode == 0
            and payload.get("schema") == "deployment_readiness.v1"
            and payload.get("deployment_ready") is True
            and deployment.get("ready") is True
            and deployment.get("hub_root_valid") is True
            and hub_path == str(repo_root)
            and locator_verified
            and (not module_identity_required or module_attestation_verified)
        )
    return {
        "available": completed.returncode == 0
        and payload.get("schema") == "deployment_readiness.v1",
        "verified": verified,
        "argv": argv,
        "returncode": completed.returncode,
        "hub_path": hub_path,
        "probe_locator_written": bool(locator_readback.get("exists")),
        "probe_locator_points_to_hub": locator_verified,
        "operational_module_file": module_file,
        "operational_module_attested_to_hub": module_attestation_verified,
        "operational_module_attestation_required": module_identity_required,
        "error": "" if verified else (completed.stderr or completed.stdout).strip()[:1000],
    }


def build_deployment_status(
    config: AppConfig,
    *,
    hub_resolution: dict[str, Any] | None = None,
    locator_write: dict[str, Any] | None = None,
    locator_path: Path | None = None,
    cwd: Path | None = None,
    skip_invocation_probes: bool = False,
) -> dict[str, Any]:
    repo_root = config.repo_root.resolve()
    resolution = hub_resolution or describe_hub_resolution(explicit_hub=repo_root)
    locator = read_hub_locator(locator_path)
    asset_dir = shutil.which("asset-dir")
    module_entrypoint_available = (repo_root / "src" / "digital_asset_directory" / "cli.py").exists()
    current = (cwd or Path.cwd()).resolve()
    caller_repo = current
    try:
        from .utils import find_repo_root

        caller_repo = find_repo_root(current).resolve()
    except Exception:
        caller_repo = current
    caller = {
        "inside_hub": caller_repo == repo_root or repo_root in caller_repo.parents,
        "has_dad_integration": (caller_repo / ".digital-asset" / "dad-integration.json").exists(),
        "has_mailbox": (caller_repo / ".digital-asset" / "mail").exists(),
    }
    install_integrity = _hub_install_integrity(repo_root)
    operational_module_identity_required = _hub_requires_module_identity(repo_root)
    operational_module_file = Path(__file__).resolve()
    operational_module_points_to_hub = _path_within(operational_module_file, repo_root)
    shim_candidates = _user_shim_candidates()
    available_shims = [path for path in shim_candidates if path.exists()]
    user_bin_dir = Path.home() / ".dad" / "bin"
    user_bin_on_path = _path_contains(os.environ.get("PATH", ""), user_bin_dir)
    invocation_probes: list[dict[str, Any]] = []
    if skip_invocation_probes and os.environ.get(DOCTOR_CHILD_PROBE_ENV) == "1":
        invocation_probes.append(
            {
                "available": True,
                "verified": True,
                "argv": [],
                "skipped": True,
                "reason": "skipped inside child invocation probe to avoid recursive doctor calls",
            }
        )
    elif skip_invocation_probes:
        invocation_probes.append(
            {
                "available": False,
                "verified": False,
                "argv": [],
                "skipped": False,
                "error": (
                    "--skip-invocation-probes is restricted to child deployment probes "
                    "launched by DAD doctor"
                ),
            }
        )
    else:
        if asset_dir:
            invocation_probes.append(_probe_dad_invocation(_shim_command(Path(asset_dir)), repo_root))
        for path in available_shims:
            invocation_probes.append(_probe_dad_invocation(_shim_command(path), repo_root))
    invocation_verified = any(probe.get("verified") for probe in invocation_probes)
    module_fallback_available = module_entrypoint_available and (
        caller_repo == repo_root or repo_root in caller_repo.parents
    )
    external_invocation_ready = invocation_verified
    stable_invocation_available = invocation_verified or module_fallback_available
    invocation_mode = (
        "external_invocation"
        if external_invocation_ready
        else "raw_checkout_fallback"
        if module_fallback_available
        else "unavailable"
    )
    hub_resolution_points_to_hub = (
        bool(resolution.get("resolved")) and resolution.get("hub_path") == str(repo_root)
    )
    locator_points_to_hub = bool(locator.get("is_dad_hub")) and locator.get("hub_path") == str(repo_root)
    ready = (
        bool(resolution.get("resolved"))
        and is_dad_hub_root(repo_root)
        and install_integrity["valid"]
        and external_invocation_ready
        and hub_resolution_points_to_hub
        and locator_points_to_hub
    )
    warnings: list[str] = []
    if not asset_dir:
        warnings.append(
            "asset-dir console script is not on PATH; use python -m digital_asset_directory.cli "
            "or a DAD wrapper until local install is complete."
        )
    if (asset_dir or available_shims) and not invocation_verified:
        warnings.append(
            "asset-dir command or user shim exists but did not prove it invokes this DAD hub."
        )
    if module_fallback_available and not external_invocation_ready:
        warnings.append(
            "DAD is callable through raw source checkout fallback only; this does not prove "
            "asset-dir or a user-level shim works from other repos."
        )
    if not install_integrity["valid"]:
        warnings.append("DAD hub install integrity check failed; deployment readiness is blocked.")
    if not locator_points_to_hub:
        warnings.append("~/.dad/hub.json is missing or does not point to this DAD hub.")
    recovery_guidance = _deployment_recovery_guidance(
        repo_root=repo_root,
        asset_dir_on_path=bool(asset_dir),
        available_shims=available_shims,
        module_fallback_available=module_fallback_available,
        external_invocation_ready=external_invocation_ready,
        locator_points_to_hub=locator_points_to_hub,
    )
    rust = {
        "cargo": _command_version(["cargo", "--version"]),
        "rustc": _command_version(["rustc", "--version"]),
    }
    return {
        "ready": ready,
        "hub_resolution": resolution,
        "hub_root_valid": is_dad_hub_root(repo_root),
        "install_integrity": install_integrity,
        "locator": locator,
        "locator_points_to_hub": locator_points_to_hub,
        "hub_resolution_points_to_hub": hub_resolution_points_to_hub,
        "locator_write": locator_write or {},
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "package_version": _package_version(),
            "module_entrypoint_available": module_entrypoint_available,
            "operational_module_file": str(operational_module_file),
            "operational_module_points_to_hub": operational_module_points_to_hub,
            "operational_module_attestation_required": operational_module_identity_required,
        },
        "asset_dir": {
            "on_path": bool(asset_dir),
            "path": asset_dir or "",
            "user_shim_available": bool(available_shims),
            "user_bin_dir": str(user_bin_dir),
            "user_bin_on_path": user_bin_on_path,
            "user_shim_paths": [str(path) for path in available_shims],
            "module_fallback_available": module_fallback_available,
            "external_invocation_ready": external_invocation_ready,
            "stable_invocation_available": stable_invocation_available,
            "invocation_mode": invocation_mode,
            "invocation_verified": invocation_verified,
            "invocation_probes": invocation_probes,
            "recovery_guidance": recovery_guidance,
        },
        "rust": rust,
        "caller_repo": caller,
        "repo_policy": _policy_reachability(config),
        "unavailable_hub_policy": UNAVAILABLE_HUB_POLICY,
        "warnings": warnings,
    }


def _deployment_for_operational_report(deployment: dict[str, Any]) -> dict[str, Any]:
    report_deployment = copy.deepcopy(deployment)
    asset_dir = report_deployment.get("asset_dir")
    if isinstance(asset_dir, dict) and isinstance(asset_dir.get("recovery_guidance"), dict):
        guidance = asset_dir["recovery_guidance"]
        asset_dir["recovery_guidance"] = {
            "schema_version": "dad_deployment_recovery_guidance.redacted.v1",
            "contract": guidance.get("contract", _recovery_guidance_contract()),
            "redacted": True,
            "available_in": "Run `asset-dir doctor --scope deployment` for local recovery commands.",
            "needed": bool(guidance.get("needed")),
            "missing_or_unverified": list(guidance.get("missing_or_unverified", [])),
            "preferred_action": str(guidance.get("preferred_action", "")),
            "authority_boundary": (
                "Operational readiness reports redact local recovery command paths. "
                "Recovery guidance remains advisory and does not authorize target repo writes."
            ),
        }
    return report_deployment


def _git_state(repo_root: Path) -> dict[str, Any]:
    try:
        status = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return {"available": False, "clean": False, "details": [str(exc)]}
    lines = [line for line in status.stdout.splitlines() if line.strip()]
    changed = [line for line in lines[1:] if not line.startswith("!! ")]
    return {
        "available": status.returncode == 0,
        "clean": status.returncode == 0 and not changed,
        "details": lines,
    }


def _surface_statuses(repo_root: Path) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for surface in CORE_SURFACES:
        path = repo_root / surface["path"]
        statuses.append(
            {
                **surface,
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() and path.is_file() else 0,
            }
        )
    return statuses


def _safe_validation(repo_root: Path) -> dict[str, Any]:
    try:
        return validate_repo(repo_root)
    except Exception as exc:
        return {"valid": False, "checked_count": 0, "errors": [str(exc)]}


def _safe_roadmap(repo_root: Path) -> dict[str, Any]:
    try:
        return check_roadmap(repo_root, update=False)
    except Exception as exc:
        return {"error": str(exc), "phases": {}}


def _compact_catalog_status(status: dict[str, Any]) -> dict[str, Any]:
    latest = status.get("latest_scan")
    compact = {key: value for key, value in status.items() if key != "latest_scan"}
    if not latest:
        compact["latest_scan"] = None
        return compact
    latest_summary: dict[str, Any] = {}
    try:
        latest_summary = json.loads(latest.get("summary_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        latest_summary = {}
    compact["latest_scan"] = {
        "scan_id": latest.get("scan_id"),
        "started_at": latest.get("started_at"),
        "completed_at": latest.get("completed_at"),
        "status": latest.get("status"),
        "asset_count": latest_summary.get("asset_count"),
        "edge_count": latest_summary.get("edge_count"),
        "alert_count": latest_summary.get("alert_count"),
        "changed_during_scan_count": latest_summary.get("changed_during_scan_count"),
        "source_files_mutated": latest_summary.get("source_files_mutated"),
    }
    return compact


def build_operational_readiness(
    config: AppConfig,
    *,
    include_git: bool = True,
    hub_resolution: dict[str, Any] | None = None,
    locator_write: dict[str, Any] | None = None,
    locator_path: Path | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    repo_root = config.repo_root
    deployment = build_deployment_status(
        config,
        hub_resolution=hub_resolution,
        locator_write=locator_write,
        locator_path=locator_path,
        cwd=cwd,
    )
    report_deployment = _deployment_for_operational_report(deployment)
    validation = _safe_validation(repo_root)
    roadmap = _safe_roadmap(repo_root)
    try:
        catalog = _compact_catalog_status(catalog_status(config))
    except Exception as exc:
        catalog = {
            "database": str(config.database_path),
            "exists": False,
            "assets": 0,
            "edges": 0,
            "alerts": 0,
            "latest_scan": None,
            "error": str(exc),
        }
    surfaces = _surface_statuses(repo_root)
    missing_required = [surface for surface in surfaces if not surface["exists"]]
    phases = roadmap.get("phases", {}) if isinstance(roadmap, dict) else {}
    phase_status_counts = Counter(
        phase.get("computed_status", "unknown") for phase in phases.values()
    )
    unverified_phase_gates = {
        phase_id: phase.get("human_gate_ids_unverified", [])
        for phase_id, phase in phases.items()
        if phase.get("human_gate_ids_unverified")
    }
    github_enabled = [
        source.id for source in config.github_sources if getattr(source, "enabled", False)
    ]
    local_enabled = [
        source.id for source in config.local_sources if getattr(source, "enabled", False)
    ]
    git = _git_state(repo_root) if include_git else {"available": False, "clean": None, "details": []}

    warnings: list[str] = []
    if not validation.get("valid"):
        warnings.append("Repository contract validation is failing.")
    if not catalog.get("exists") or catalog.get("assets", 0) <= 0:
        warnings.append("Catalog database is missing or empty; run a bounded local scan.")
    if missing_required:
        warnings.append("One or more front-door or generated readiness surfaces are missing.")
    if unverified_phase_gates:
        warnings.append("Roadmap still has unverified human gates.")
    if github_enabled:
        warnings.append("One or more GitHub sources are enabled; confirm token scope before scanning.")
    if git.get("clean") is False:
        warnings.append("Git worktree has tracked changes.")
    for warning in deployment["warnings"]:
        warnings.append(f"Deployment: {warning}")

    core_ready = (
        deployment["ready"] is True
        and validation.get("valid") is True
        and bool(catalog.get("exists"))
        and catalog.get("assets", 0) > 0
        and not missing_required
        and not unverified_phase_gates
        and not github_enabled
        and (not include_git or git.get("clean") is True)
    )
    return {
        "schema": "operational_readiness.v1",
        "generated_at": utc_now(),
        "repo_root": str(repo_root),
        "ready": core_ready,
        "deployment_ready": deployment["ready"],
        "candidate_only": True,
        "authority_boundary": (
            "Operational readiness summarizes current local evidence. It does not scan, "
            "mutate source repositories, mark roadmap gates complete, or promote generated "
            "outputs to truth."
        ),
        "validation": validation,
        "deployment": report_deployment,
        "roadmap_phase_status_counts": dict(sorted(phase_status_counts.items())),
        "roadmap_unverified_phase_gates": unverified_phase_gates,
        "catalog": catalog,
        "configured_sources": {
            "local_enabled": local_enabled,
            "github_enabled": github_enabled,
        },
        "surfaces": surfaces,
        "missing_surfaces": missing_required,
        "git": git,
        "warnings": warnings,
        "validation_commands": VALIDATION_COMMANDS,
        "recommended_next_commands": [
            "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend workflow-part-guidance --limit 50",
            "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update",
        ],
    }


def operational_readiness_markdown(result: dict[str, Any]) -> str:
    ready = "yes" if result["ready"] else "no"
    lines = [
        "# Operational Readiness",
        "",
        f"Generated at: `{result['generated_at']}`",
        f"Ready: **{ready}**",
        "",
        result["authority_boundary"],
        "",
        "## Summary",
        "",
        f"- Catalog assets: **{result['catalog'].get('assets', 0)}**",
        f"- Catalog edges: **{result['catalog'].get('edges', 0)}**",
        f"- Open alerts: **{result['catalog'].get('alerts', 0)}**",
        f"- Validation valid: **{result['validation'].get('valid')}**",
        f"- Deployment ready: **{result.get('deployment_ready')}**",
        f"- Hub resolution: `{result.get('deployment', {}).get('hub_resolution', {}).get('source', '')}`",
        f"- asset-dir on PATH: **{result.get('deployment', {}).get('asset_dir', {}).get('on_path')}**",
        f"- Roadmap statuses: `{result['roadmap_phase_status_counts']}`",
        f"- Local sources enabled: `{result['configured_sources']['local_enabled']}`",
        f"- GitHub sources enabled: `{result['configured_sources']['github_enabled']}`",
        "",
        "## Warnings",
        "",
    ]
    if result["warnings"]:
        lines.extend(f"- {warning}" for warning in result["warnings"])
    else:
        lines.append("- No readiness warnings.")
    lines.extend(["", "## Required Surfaces", ""])
    lines.extend(
        [
            "| path | kind | purpose | exists |",
            "|---|---|---|---|",
        ]
    )
    for surface in result["surfaces"]:
        lines.append(
            f"| `{surface['path']}` | `{surface['kind']}` | {surface['purpose']} | "
            f"`{surface['exists']}` |"
        )
    lines.extend(["", "## Validation Commands", ""])
    lines.extend(f"- `{command}`" for command in result["validation_commands"])
    lines.extend(["", "## Recommended Next Commands", ""])
    lines.extend(f"- `{command}`" for command in result["recommended_next_commands"])
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This report is evidence for operating the DAD hub. It is not acceptance evidence "
            "for new source scopes, GitHub scanning, automatic workflow assembly, embeddings, "
            "scheduled scans, or external research.",
            "",
        ]
    )
    return "\n".join(lines)


def write_operational_readiness_report(
    config: AppConfig,
    *,
    hub_resolution: dict[str, Any] | None = None,
    locator_write: dict[str, Any] | None = None,
    locator_path: Path | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    result = build_operational_readiness(
        config,
        hub_resolution=hub_resolution,
        locator_write=locator_write,
        locator_path=locator_path,
        cwd=cwd,
    )
    report_path = config.repo_root / "processed" / "reports" / "operational_readiness.md"
    payload_path = config.repo_root / "processed" / "reports" / "operational_readiness.json"
    atomic_write_text(report_path, operational_readiness_markdown(result))
    atomic_write_text(payload_path, json_dumps(result, pretty=True) + "\n")
    return {**result, "report": str(report_path), "payload": str(payload_path)}
