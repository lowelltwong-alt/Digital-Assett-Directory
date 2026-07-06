from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

DEFAULT_MAIL_MAX_JSONL_ROW_BYTES = 64_000
MAIL_SPOOL_CHECK_SCHEMA_VERSION = "dad_mail_spool_check.v0_1"
EVENT_LOG_CHECK_SCHEMA_VERSION = "dad_event_log_check.v0_1"
REPO_INVENTORY_PROBE_SCHEMA_VERSION = "dad_repo_inventory_probe.v0_2"


@dataclass(frozen=True)
class DadScanCoreResult:
    """Structured result from DAD's Rust scan core."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    cargo_found: bool
    source: str
    out: str
    summary_out: str
    quarantine_out: str
    display_command: list[str] | None = None
    timed_out: bool = False

    def to_dict(
        self, *, include_output: bool = False, include_local_paths: bool = False
    ) -> dict[str, object]:
        payload = asdict(self)
        if not include_local_paths and self.display_command is not None:
            payload["command"] = self.display_command
            payload["local_command_suppressed"] = True
        else:
            payload["local_command_suppressed"] = False
        if not include_output:
            payload["stdout"] = ""
            payload["stderr"] = ""
            payload["output_suppressed"] = True
        else:
            payload["output_suppressed"] = False
        return payload


@dataclass(frozen=True)
class DadMailSpoolCheckResult:
    """Structured result from DAD's Rust mail-spool probe."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    cargo_found: bool
    root_aliases: list[str]
    display_command: list[str] | None = None
    summary: dict[str, object] | None = None
    summary_valid: bool = False
    summary_validation_errors: list[str] | None = None
    timed_out: bool = False

    def to_dict(
        self, *, include_output: bool = False, include_local_paths: bool = False
    ) -> dict[str, object]:
        payload = asdict(self)
        if not include_local_paths and self.display_command is not None:
            payload["command"] = self.display_command
            payload["local_command_suppressed"] = True
        else:
            payload["local_command_suppressed"] = False
        if not include_local_paths and self.summary is not None and not self.summary_valid:
            payload["summary"] = None
            payload["summary_suppressed"] = True
        else:
            payload["summary_suppressed"] = False
        if not include_output:
            payload["stdout"] = ""
            payload["stderr"] = ""
            payload["output_suppressed"] = True
        else:
            payload["output_suppressed"] = False
        return payload


@dataclass(frozen=True)
class DadEventLogCheckResult:
    """Structured result from DAD's Rust event-log probe."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    cargo_found: bool
    root_aliases: list[str]
    display_command: list[str] | None = None
    summary: dict[str, object] | None = None
    summary_valid: bool = False
    summary_validation_errors: list[str] | None = None
    timed_out: bool = False

    def to_dict(
        self, *, include_output: bool = False, include_local_paths: bool = False
    ) -> dict[str, object]:
        payload = asdict(self)
        if not include_local_paths and self.display_command is not None:
            payload["command"] = self.display_command
            payload["local_command_suppressed"] = True
        else:
            payload["local_command_suppressed"] = False
        if not include_local_paths and self.summary is not None and not self.summary_valid:
            payload["summary"] = None
            payload["summary_suppressed"] = True
        else:
            payload["summary_suppressed"] = False
        if self.returncode != 0:
            payload["failure_summary"] = self._failure_summary()
        if not include_output:
            payload["stdout"] = ""
            payload["stderr"] = ""
            payload["output_suppressed"] = True
        else:
            payload["output_suppressed"] = False
        return payload

    def _failure_summary(self) -> str:
        if not self.cargo_found:
            return "cargo was not found on PATH. Install Rust via rustup."
        if self.timed_out:
            return "dad_scan_core event-log-check timed out."
        if self.summary_validation_errors:
            return "Rust event-log summary failed validation; see summary_validation_errors."
        return (
            "Rust event-log check failed; raw subprocess output is suppressed by "
            "default because it may contain local paths."
        )


@dataclass(frozen=True)
class DadRepoInventoryProbeResult:
    """Structured result from DAD's Rust repo-inventory probe."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    cargo_found: bool
    root_aliases: list[str]
    display_command: list[str] | None = None
    summary: dict[str, object] | None = None
    summary_valid: bool = False
    summary_validation_errors: list[str] | None = None
    timed_out: bool = False

    def to_dict(
        self, *, include_output: bool = False, include_local_paths: bool = False
    ) -> dict[str, object]:
        payload = asdict(self)
        if not include_local_paths and self.display_command is not None:
            payload["command"] = self.display_command
            payload["local_command_suppressed"] = True
        else:
            payload["local_command_suppressed"] = False
        if not include_local_paths and self.summary is not None and not self.summary_valid:
            payload["summary"] = None
            payload["summary_suppressed"] = True
        else:
            payload["summary_suppressed"] = False
        if self.returncode != 0:
            payload["failure_summary"] = self._failure_summary()
        if not include_output:
            payload["stdout"] = ""
            payload["stderr"] = ""
            payload["output_suppressed"] = True
        else:
            payload["output_suppressed"] = False
        return payload

    def _failure_summary(self) -> str:
        if not self.cargo_found:
            return "cargo was not found on PATH. Install Rust via rustup."
        if self.timed_out:
            return "dad_scan_core repo-inventory-probe timed out."
        if self.summary_validation_errors:
            return "Rust repo-inventory summary failed validation; see summary_validation_errors."
        return (
            "Rust repo-inventory probe failed; raw subprocess output is suppressed by "
            "default because it may contain local paths."
        )


def run_dad_scan_core(
    *,
    repo_root: Path,
    source: Path,
    source_id: str,
    path_alias: str,
    out: Path,
    summary_out: Path,
    quarantine_out: Path,
    max_files: int | None = None,
    max_content_hash_bytes: int = 10_485_760,
    follow_symlinks: bool = False,
    excludes: list[str] | None = None,
    cargo_bin: str = "cargo",
    manifest_path: Path | None = None,
    timeout_seconds: int = 300,
) -> DadScanCoreResult:
    """Run the Rust scanner through Cargo and return a structured subprocess result.

    The Rust scanner owns deterministic file walking and hashing only. Python keeps
    orchestration, policy, ingestion, and review authority.
    """

    repo_root = repo_root.resolve()
    source = _resolve(repo_root, source)
    out = _resolve(repo_root, out)
    summary_out = _resolve(repo_root, summary_out)
    quarantine_out = _resolve(repo_root, quarantine_out)
    manifest_path = (
        _resolve(repo_root, manifest_path)
        if manifest_path is not None
        else repo_root / "tools" / "dad_scan_core" / "Cargo.toml"
    )

    command = [
        cargo_bin,
        "run",
        "--manifest-path",
        str(manifest_path),
        "--",
        "scan-local",
        "--source",
        str(source),
        "--source-id",
        source_id,
        "--path-alias",
        path_alias,
        "--out",
        str(out),
        "--summary-out",
        str(summary_out),
        "--quarantine-out",
        str(quarantine_out),
        "--max-content-hash-bytes",
        str(max_content_hash_bytes),
    ]
    display_command = [
        cargo_bin,
        "run",
        "--manifest-path",
        _display_path(repo_root, manifest_path),
        "--",
        "scan-local",
        "--source",
        _display_path(repo_root, source),
        "--source-id",
        source_id,
        "--path-alias",
        path_alias,
        "--out",
        _display_path(repo_root, out),
        "--summary-out",
        _display_path(repo_root, summary_out),
        "--quarantine-out",
        _display_path(repo_root, quarantine_out),
        "--max-content-hash-bytes",
        str(max_content_hash_bytes),
    ]
    if max_files is not None:
        command.extend(["--max-files", str(max_files)])
        display_command.extend(["--max-files", str(max_files)])
    if follow_symlinks:
        command.append("--follow-symlinks")
        display_command.append("--follow-symlinks")
    for pattern in excludes or []:
        command.extend(["--exclude", pattern])
        display_command.extend(["--exclude", pattern])

    cargo_path = shutil.which(cargo_bin)
    if cargo_path is None:
        return DadScanCoreResult(
            command=command,
            returncode=127,
            stdout="",
            stderr=f"{cargo_bin} was not found on PATH. Install Rust via rustup.",
            cargo_found=False,
            source=_display_path(repo_root, source),
            out=_display_path(repo_root, out),
            summary_out=_display_path(repo_root, summary_out),
            quarantine_out=_display_path(repo_root, quarantine_out),
            display_command=display_command,
        )

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=timeout_seconds,
        )
        return DadScanCoreResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            cargo_found=True,
            source=_display_path(repo_root, source),
            out=_display_path(repo_root, out),
            summary_out=_display_path(repo_root, summary_out),
            quarantine_out=_display_path(repo_root, quarantine_out),
            display_command=display_command,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        return DadScanCoreResult(
            command=command,
            returncode=124,
            stdout=stdout,
            stderr=stderr or f"dad_scan_core timed out after {timeout_seconds} seconds.",
            cargo_found=True,
            source=_display_path(repo_root, source),
            out=_display_path(repo_root, out),
            summary_out=_display_path(repo_root, summary_out),
            quarantine_out=_display_path(repo_root, quarantine_out),
            display_command=display_command,
            timed_out=True,
        )


def run_dad_mail_spool_check(
    *,
    repo_root: Path,
    roots: list[Path],
    root_aliases: list[str],
    max_jsonl_row_bytes: int = DEFAULT_MAIL_MAX_JSONL_ROW_BYTES,
    max_samples: int = 25,
    cargo_bin: str = "cargo",
    manifest_path: Path | None = None,
    timeout_seconds: int = 120,
) -> DadMailSpoolCheckResult:
    """Run the Rust read-only mail-spool probe through Cargo.

    The Rust probe finds deterministic file and row hazards only. Python's mail
    doctor remains the authority for collection, routing, delivery, and release
    decisions.
    """

    repo_root = repo_root.resolve()
    _validate_root_alias_cardinality(
        roots,
        root_aliases,
        command_name="mail-spool-check",
    )
    roots = [_resolve(repo_root, root) for root in roots]
    manifest_path = (
        _resolve(repo_root, manifest_path)
        if manifest_path is not None
        else repo_root / "tools" / "dad_scan_core" / "Cargo.toml"
    )

    command = [
        cargo_bin,
        "run",
        "--manifest-path",
        str(manifest_path),
        "--",
        "mail-spool-check",
        "--max-jsonl-row-bytes",
        str(max_jsonl_row_bytes),
        "--max-samples",
        str(max_samples),
    ]
    display_command = [
        cargo_bin,
        "run",
        "--manifest-path",
        _display_path(repo_root, manifest_path),
        "--",
        "mail-spool-check",
        "--max-jsonl-row-bytes",
        str(max_jsonl_row_bytes),
        "--max-samples",
        str(max_samples),
    ]
    for root, alias in zip(roots, root_aliases):
        command.extend(["--root", str(root), "--root-alias", alias])
        display_command.extend(["--root", _display_path(repo_root, root), "--root-alias", alias])

    cargo_path = shutil.which(cargo_bin)
    if cargo_path is None:
        return DadMailSpoolCheckResult(
            command=command,
            returncode=127,
            stdout="",
            stderr=f"{cargo_bin} was not found on PATH. Install Rust via rustup.",
            cargo_found=False,
            root_aliases=list(root_aliases),
            display_command=display_command,
        )

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=timeout_seconds,
        )
        summary = _parse_json_object(completed.stdout)
        summary_validation_errors = validate_mail_spool_check_summary(
            summary,
            root_aliases=root_aliases,
        )
        returncode = (
            2
            if completed.returncode == 0 and summary_validation_errors
            else completed.returncode
        )
        return DadMailSpoolCheckResult(
            command=command,
            returncode=returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            cargo_found=True,
            root_aliases=list(root_aliases),
            display_command=display_command,
            summary=summary,
            summary_valid=not summary_validation_errors,
            summary_validation_errors=summary_validation_errors,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        summary = _parse_json_object(stdout)
        summary_validation_errors = validate_mail_spool_check_summary(
            summary,
            root_aliases=root_aliases,
        )
        return DadMailSpoolCheckResult(
            command=command,
            returncode=124,
            stdout=stdout,
            stderr=stderr or f"dad_scan_core mail-spool-check timed out after {timeout_seconds} seconds.",
            cargo_found=True,
            root_aliases=list(root_aliases),
            display_command=display_command,
            summary=summary,
            summary_valid=False,
            summary_validation_errors=summary_validation_errors,
            timed_out=True,
        )


def run_dad_event_log_check(
    *,
    repo_root: Path,
    roots: list[Path],
    root_aliases: list[str],
    max_jsonl_row_bytes: int = DEFAULT_MAIL_MAX_JSONL_ROW_BYTES,
    max_samples: int = 25,
    cargo_bin: str = "cargo",
    manifest_path: Path | None = None,
    timeout_seconds: int = 120,
) -> DadEventLogCheckResult:
    """Run the Rust read-only event-log probe through Cargo.

    The Rust probe finds deterministic JSONL and structural hazards only. Python's
    event pipeline remains the authority for collection, public release, response
    state, and adoption decisions.
    """

    repo_root = repo_root.resolve()
    _validate_root_alias_cardinality(
        roots,
        root_aliases,
        command_name="event-log-check",
    )
    roots = [_resolve(repo_root, root) for root in roots]
    manifest_path = (
        _resolve(repo_root, manifest_path)
        if manifest_path is not None
        else repo_root / "tools" / "dad_scan_core" / "Cargo.toml"
    )

    command = [
        cargo_bin,
        "run",
        "--manifest-path",
        str(manifest_path),
        "--",
        "event-log-check",
        "--max-jsonl-row-bytes",
        str(max_jsonl_row_bytes),
        "--max-samples",
        str(max_samples),
    ]
    display_command = [
        cargo_bin,
        "run",
        "--manifest-path",
        _display_path(repo_root, manifest_path),
        "--",
        "event-log-check",
        "--max-jsonl-row-bytes",
        str(max_jsonl_row_bytes),
        "--max-samples",
        str(max_samples),
    ]
    for root, alias in zip(roots, root_aliases):
        command.extend(["--root", str(root), "--root-alias", alias])
        display_command.extend(["--root", _display_path(repo_root, root), "--root-alias", alias])

    cargo_path = shutil.which(cargo_bin)
    if cargo_path is None:
        return DadEventLogCheckResult(
            command=command,
            returncode=127,
            stdout="",
            stderr=f"{cargo_bin} was not found on PATH. Install Rust via rustup.",
            cargo_found=False,
            root_aliases=list(root_aliases),
            display_command=display_command,
        )

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=timeout_seconds,
        )
        summary = _parse_json_object(completed.stdout)
        summary_validation_errors = validate_event_log_check_summary(
            summary,
            root_aliases=root_aliases,
        )
        returncode = (
            2
            if completed.returncode == 0 and summary_validation_errors
            else completed.returncode
        )
        return DadEventLogCheckResult(
            command=command,
            returncode=returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            cargo_found=True,
            root_aliases=list(root_aliases),
            display_command=display_command,
            summary=summary,
            summary_valid=not summary_validation_errors,
            summary_validation_errors=summary_validation_errors,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        summary = _parse_json_object(stdout)
        summary_validation_errors = validate_event_log_check_summary(
            summary,
            root_aliases=root_aliases,
        )
        return DadEventLogCheckResult(
            command=command,
            returncode=124,
            stdout=stdout,
            stderr=stderr
            or f"dad_scan_core event-log-check timed out after {timeout_seconds} seconds.",
            cargo_found=True,
            root_aliases=list(root_aliases),
            display_command=display_command,
            summary=summary,
            summary_valid=False,
            summary_validation_errors=summary_validation_errors,
            timed_out=True,
        )


def run_dad_repo_inventory_probe(
    *,
    repo_root: Path,
    roots: list[Path],
    root_aliases: list[str],
    max_depth: int = 5,
    follow_symlinks: bool = False,
    cargo_bin: str = "cargo",
    manifest_path: Path | None = None,
    timeout_seconds: int = 120,
) -> DadRepoInventoryProbeResult:
    """Run the Rust read-only repo-inventory probe through Cargo."""

    repo_root = repo_root.resolve()
    _validate_root_alias_cardinality(
        roots,
        root_aliases,
        command_name="repo-inventory-probe",
    )
    roots = [_resolve(repo_root, root) for root in roots]
    manifest_path = (
        _resolve(repo_root, manifest_path)
        if manifest_path is not None
        else repo_root / "tools" / "dad_scan_core" / "Cargo.toml"
    )
    command = [
        cargo_bin,
        "run",
        "--manifest-path",
        str(manifest_path),
        "--",
        "repo-inventory-probe",
        "--max-depth",
        str(max_depth),
    ]
    display_command = [
        cargo_bin,
        "run",
        "--manifest-path",
        _display_path(repo_root, manifest_path),
        "--",
        "repo-inventory-probe",
        "--max-depth",
        str(max_depth),
    ]
    if follow_symlinks:
        command.append("--follow-symlinks")
        display_command.append("--follow-symlinks")
    for root, alias in zip(roots, root_aliases):
        command.extend(["--root", str(root), "--root-alias", alias])
        display_command.extend(["--root", _display_path(repo_root, root), "--root-alias", alias])

    cargo_path = shutil.which(cargo_bin)
    if cargo_path is None:
        return DadRepoInventoryProbeResult(
            command=command,
            returncode=127,
            stdout="",
            stderr=f"{cargo_bin} was not found on PATH. Install Rust via rustup.",
            cargo_found=False,
            root_aliases=list(root_aliases),
            display_command=display_command,
        )
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=timeout_seconds,
        )
        summary = _parse_json_object(completed.stdout)
        summary_validation_errors = validate_repo_inventory_probe_summary(
            summary,
            root_aliases=root_aliases,
        )
        returncode = (
            2
            if completed.returncode == 0 and summary_validation_errors
            else completed.returncode
        )
        return DadRepoInventoryProbeResult(
            command=command,
            returncode=returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            cargo_found=True,
            root_aliases=list(root_aliases),
            display_command=display_command,
            summary=summary,
            summary_valid=not summary_validation_errors,
            summary_validation_errors=summary_validation_errors,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        summary = _parse_json_object(stdout)
        summary_validation_errors = validate_repo_inventory_probe_summary(
            summary,
            root_aliases=root_aliases,
        )
        return DadRepoInventoryProbeResult(
            command=command,
            returncode=124,
            stdout=stdout,
            stderr=stderr
            or f"dad_scan_core repo-inventory-probe timed out after {timeout_seconds} seconds.",
            cargo_found=True,
            root_aliases=list(root_aliases),
            display_command=display_command,
            summary=summary,
            summary_valid=False,
            summary_validation_errors=summary_validation_errors,
            timed_out=True,
        )


def _parse_json_object(text: str) -> dict[str, object] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def validate_repo_inventory_probe_summary(
    summary: dict[str, object] | None,
    *,
    root_aliases: Sequence[str],
) -> list[str]:
    if summary is None:
        return ["stdout did not contain a JSON object summary"]
    errors: list[str] = []
    allowed_top_level_fields = {
        "schema_version",
        "root_count",
        "repo_count",
        "skipped_dir_count",
        "roots",
        "repos",
        "skipped_dirs",
        "no_mutation_performed",
        "authority_boundary",
    }
    unknown_top_level_fields = sorted(set(summary) - allowed_top_level_fields)
    if unknown_top_level_fields:
        errors.append(
            "summary contains unknown fields: " + ", ".join(unknown_top_level_fields)
        )
    if summary.get("schema_version") != REPO_INVENTORY_PROBE_SCHEMA_VERSION:
        errors.append(
            "schema_version must be "
            f"{REPO_INVENTORY_PROBE_SCHEMA_VERSION!r}; got {summary.get('schema_version')!r}"
        )
    if summary.get("no_mutation_performed") is not True:
        errors.append("no_mutation_performed must be true")
    authority_boundary = summary.get("authority_boundary")
    if not isinstance(authority_boundary, str) or not authority_boundary.strip():
        errors.append("authority_boundary must be a non-empty string")
    elif _contains_local_path_marker(authority_boundary):
        errors.append("authority_boundary must not contain local path markers")

    roots = summary.get("roots")
    repos = summary.get("repos")
    skipped_dirs = summary.get("skipped_dirs")
    if not isinstance(roots, list):
        errors.append("roots must be a list")
        roots = []
    if not isinstance(repos, list):
        errors.append("repos must be a list")
        repos = []
    if not isinstance(skipped_dirs, list):
        errors.append("skipped_dirs must be a list")
        skipped_dirs = []

    allowed_aliases = set(root_aliases)
    allowed_record_fields = {
        "roots": {"root_alias", "status", "repo_count", "skipped_dir_count"},
        "repos": {
            "root_alias",
            "logical_path",
            "depth",
            "git_marker_type",
            "contract_present",
            "contract_parse_status",
            "contract_schema_version_present",
            "contract_repo_id_present",
            "contract_capture_surface_version_present",
            "contract_cli_fallback_present",
            "contract_stable_user_shim_present",
            "contract_windows_user_shim_present",
            "contract_raw_checkout_fallback_present",
            "contract_stable_shim_before_raw_checkout",
            "contract_structural_pass",
            "contract_issue_codes",
            "no_mutation_performed",
        },
        "skipped_dirs": {"root_alias", "logical_path", "reason"},
    }
    for field, records in (
        ("roots", roots),
        ("repos", repos),
        ("skipped_dirs", skipped_dirs),
    ):
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                errors.append(f"{field}[{index}] must be an object")
                continue
            unknown_fields = sorted(set(record) - allowed_record_fields[field])
            if unknown_fields:
                errors.append(
                    f"{field}[{index}] contains unknown fields: "
                    + ", ".join(unknown_fields)
                )
            root_alias = record.get("root_alias")
            if not isinstance(root_alias, str) or not _is_public_safe_alias_path(root_alias):
                errors.append(f"{field}[{index}].root_alias must be a public-safe alias")
            elif root_alias not in allowed_aliases:
                errors.append(
                    f"{field}[{index}].root_alias {root_alias!r} was not requested"
                )
            logical_path = record.get("logical_path")
            if logical_path is not None and (
                not isinstance(logical_path, str)
                or not _is_public_safe_alias_path(logical_path)
            ):
                errors.append(f"{field}[{index}].logical_path must be a public-safe alias path")

    for index, record in enumerate(repos):
        if not isinstance(record, dict):
            continue
        if not isinstance(record.get("contract_present"), bool):
            errors.append(f"repos[{index}].contract_present must be a boolean")
        contract_statuses = {
            "missing",
            "oversized",
            "read_error",
            "malformed_json",
            "non_object_json",
            "present_parseable",
        }
        if record.get("contract_parse_status") not in contract_statuses:
            errors.append(
                f"repos[{index}].contract_parse_status must be one of "
                + ", ".join(sorted(contract_statuses))
            )
        contract_bool_fields = {
            "contract_schema_version_present",
            "contract_repo_id_present",
            "contract_capture_surface_version_present",
            "contract_cli_fallback_present",
            "contract_stable_user_shim_present",
            "contract_windows_user_shim_present",
            "contract_raw_checkout_fallback_present",
            "contract_stable_shim_before_raw_checkout",
            "contract_structural_pass",
        }
        for bool_field in sorted(contract_bool_fields):
            if not isinstance(record.get(bool_field), bool):
                errors.append(f"repos[{index}].{bool_field} must be a boolean")
        issue_codes = record.get("contract_issue_codes")
        allowed_issue_codes = {
            "contract_malformed_json",
            "contract_missing",
            "contract_missing_capture_surface_version",
            "contract_missing_cli_fallback",
            "contract_missing_raw_checkout_fallback",
            "contract_missing_repo_id",
            "contract_missing_schema_version",
            "contract_missing_stable_user_shim",
            "contract_missing_windows_user_shim",
            "contract_non_object_json",
            "contract_oversized",
            "contract_read_error",
            "contract_stable_shim_not_before_raw_checkout",
        }
        if not isinstance(issue_codes, list) or not all(
            isinstance(code, str) for code in issue_codes
        ):
            errors.append(f"repos[{index}].contract_issue_codes must be a list of strings")
        else:
            unknown_codes = sorted(set(issue_codes) - allowed_issue_codes)
            if unknown_codes:
                errors.append(
                    f"repos[{index}].contract_issue_codes contains unknown codes: "
                    + ", ".join(unknown_codes)
                )
            if issue_codes != sorted(issue_codes):
                errors.append(f"repos[{index}].contract_issue_codes must be sorted")
            if any(_contains_local_path_marker(code) for code in issue_codes):
                errors.append(
                    f"repos[{index}].contract_issue_codes must not contain local path markers"
                )
            required_fact_issue_by_field = {
                "contract_schema_version_present": "contract_missing_schema_version",
                "contract_repo_id_present": "contract_missing_repo_id",
                "contract_capture_surface_version_present": (
                    "contract_missing_capture_surface_version"
                ),
                "contract_cli_fallback_present": "contract_missing_cli_fallback",
                "contract_stable_user_shim_present": "contract_missing_stable_user_shim",
                "contract_windows_user_shim_present": (
                    "contract_missing_windows_user_shim"
                ),
                "contract_raw_checkout_fallback_present": (
                    "contract_missing_raw_checkout_fallback"
                ),
                "contract_stable_shim_before_raw_checkout": (
                    "contract_stable_shim_not_before_raw_checkout"
                ),
            }
            status_issue_codes = {
                "missing": "contract_missing",
                "oversized": "contract_oversized",
                "read_error": "contract_read_error",
                "malformed_json": "contract_malformed_json",
                "non_object_json": "contract_non_object_json",
            }
            status = record.get("contract_parse_status")
            status_issue = status_issue_codes.get(status)
            if status_issue and status_issue not in issue_codes:
                errors.append(
                    f"repos[{index}].contract_issue_codes must include {status_issue} "
                    f"when contract_parse_status is {status}"
                )
            if status != "present_parseable":
                for bool_field in sorted(required_fact_issue_by_field):
                    if record.get(bool_field) is True:
                        errors.append(
                            f"repos[{index}].{bool_field} must be false when "
                            f"contract_parse_status is {status}"
                        )
            else:
                parse_status_codes = set(status_issue_codes.values())
                unexpected_parse_codes = sorted(set(issue_codes) & parse_status_codes)
                if unexpected_parse_codes:
                    errors.append(
                        f"repos[{index}].contract_issue_codes contains parse-status codes "
                        "for a present_parseable contract: "
                        + ", ".join(unexpected_parse_codes)
                    )
                for bool_field, issue_code in sorted(required_fact_issue_by_field.items()):
                    if record.get(bool_field) is False and issue_code not in issue_codes:
                        errors.append(
                            f"repos[{index}].contract_issue_codes must include {issue_code} "
                            f"when {bool_field} is false"
                        )
                    if record.get(bool_field) is True and issue_code in issue_codes:
                        errors.append(
                            f"repos[{index}].contract_issue_codes must not include "
                            f"{issue_code} when {bool_field} is true"
                        )
            if record.get("contract_structural_pass") is True and issue_codes:
                errors.append(
                    f"repos[{index}].contract_structural_pass cannot be true with issue codes"
                )
            if record.get("contract_structural_pass") is True:
                if record.get("contract_present") is not True:
                    errors.append(
                        f"repos[{index}].contract_structural_pass requires contract_present"
                    )
                if record.get("contract_parse_status") != "present_parseable":
                    errors.append(
                        f"repos[{index}].contract_structural_pass requires "
                        "contract_parse_status present_parseable"
                    )
                for bool_field in sorted(required_fact_issue_by_field):
                    if record.get(bool_field) is not True:
                        errors.append(
                            f"repos[{index}].contract_structural_pass requires "
                            f"{bool_field}"
                        )
            if record.get("contract_structural_pass") is False and not issue_codes:
                errors.append(
                    f"repos[{index}].contract_structural_pass cannot be false without issue codes"
                )
            if record.get("contract_present") is False and "contract_missing" not in issue_codes:
                errors.append(
                    f"repos[{index}].contract_issue_codes must include contract_missing "
                    "when contract_present is false"
                )
            if record.get("contract_present") is True and "contract_missing" in issue_codes:
                errors.append(
                    f"repos[{index}].contract_issue_codes must not include contract_missing "
                    "when contract_present is true"
                )
            if record.get("contract_present") is False and record.get("contract_parse_status") != "missing":
                errors.append(
                    f"repos[{index}].contract_parse_status must be missing when "
                    "contract_present is false"
                )
            if record.get("contract_present") is True and record.get("contract_parse_status") == "missing":
                errors.append(
                    f"repos[{index}].contract_parse_status must not be missing when "
                    "contract_present is true"
                )
        if record.get("no_mutation_performed") is not True:
            errors.append(f"repos[{index}].no_mutation_performed must be true")
        if record.get("git_marker_type") not in {"directory", "file"}:
            errors.append(f"repos[{index}].git_marker_type must be directory or file")
        if not isinstance(record.get("depth"), int):
            errors.append(f"repos[{index}].depth must be an integer")

    allowed_skipped_reasons = {
        "repo discovery skip directory",
        "pytest temp workspace",
        "walk error",
    }
    for index, record in enumerate(skipped_dirs):
        if not isinstance(record, dict):
            continue
        reason = record.get("reason")
        if reason not in allowed_skipped_reasons:
            errors.append(
                f"skipped_dirs[{index}].reason must be one of "
                + ", ".join(sorted(allowed_skipped_reasons))
            )

    for index, record in enumerate(roots):
        if not isinstance(record, dict):
            continue
        if record.get("status") not in {"checked", "missing", "not_directory"}:
            errors.append(f"roots[{index}].status must be checked, missing, or not_directory")
        for count_field in ("repo_count", "skipped_dir_count"):
            if not isinstance(record.get(count_field), int):
                errors.append(f"roots[{index}].{count_field} must be an integer")

    for count_field, records in (
        ("root_count", roots),
        ("repo_count", repos),
        ("skipped_dir_count", skipped_dirs),
    ):
        if summary.get(count_field) != len(records):
            errors.append(f"{count_field} must equal len({count_field.removesuffix('_count')}s)")
    return errors


def validate_mail_spool_check_summary(
    summary: dict[str, object] | None,
    *,
    root_aliases: Sequence[str],
) -> list[str]:
    if summary is None:
        return ["stdout did not contain a JSON object summary"]
    errors: list[str] = []
    allowed_top_level_fields = {
        "schema_version",
        "root_count",
        "checked_file_count",
        "jsonl_file_count",
        "lock_file_count",
        "temp_fragment_count",
        "rust_packet_count",
        "malformed_jsonl_row_count",
        "oversized_jsonl_row_count",
        "issue_count",
        "roots",
        "issue_samples",
        "no_mutation_performed",
        "authority_boundary",
        "authoritative_gate",
        "semantic_checks_not_performed",
    }
    unknown_top_level_fields = sorted(set(summary) - allowed_top_level_fields)
    if unknown_top_level_fields:
        errors.append(
            "summary contains unknown fields: " + ", ".join(unknown_top_level_fields)
        )
    if summary.get("schema_version") != MAIL_SPOOL_CHECK_SCHEMA_VERSION:
        errors.append(
            "schema_version must be "
            f"{MAIL_SPOOL_CHECK_SCHEMA_VERSION!r}; got {summary.get('schema_version')!r}"
        )
    if summary.get("no_mutation_performed") is not True:
        errors.append("no_mutation_performed must be true")
    if summary.get("authoritative_gate") != "mail doctor":
        errors.append("authoritative_gate must be 'mail doctor'")
    authority_boundary = summary.get("authority_boundary")
    if not isinstance(authority_boundary, str) or not authority_boundary.strip():
        errors.append("authority_boundary must be a non-empty string")
    elif _contains_local_path_marker(authority_boundary):
        errors.append("authority_boundary must not contain local path markers")

    roots = summary.get("roots")
    issue_samples = summary.get("issue_samples")
    semantic_checks = summary.get("semantic_checks_not_performed")
    if not isinstance(roots, list):
        errors.append("roots must be a list")
        roots = []
    if not isinstance(issue_samples, list):
        errors.append("issue_samples must be a list")
        issue_samples = []
    if not isinstance(semantic_checks, list) or not all(
        isinstance(item, str) and item.strip() for item in semantic_checks
    ):
        errors.append("semantic_checks_not_performed must be a list of non-empty strings")

    for field in (
        "root_count",
        "checked_file_count",
        "jsonl_file_count",
        "lock_file_count",
        "temp_fragment_count",
        "rust_packet_count",
        "malformed_jsonl_row_count",
        "oversized_jsonl_row_count",
        "issue_count",
    ):
        if not isinstance(summary.get(field), int):
            errors.append(f"{field} must be an integer")

    allowed_aliases = set(root_aliases)
    allowed_root_fields = {
        "root_alias",
        "status",
        "checked_file_count",
        "jsonl_file_count",
        "lock_file_count",
        "temp_fragment_count",
        "rust_packet_count",
        "malformed_jsonl_row_count",
        "oversized_jsonl_row_count",
    }
    for index, record in enumerate(roots):
        if not isinstance(record, dict):
            errors.append(f"roots[{index}] must be an object")
            continue
        unknown_fields = sorted(set(record) - allowed_root_fields)
        if unknown_fields:
            errors.append(
                f"roots[{index}] contains unknown fields: " + ", ".join(unknown_fields)
            )
        root_alias = record.get("root_alias")
        if not isinstance(root_alias, str) or not _is_public_safe_alias_path(root_alias):
            errors.append(f"roots[{index}].root_alias must be a public-safe alias")
        elif root_alias not in allowed_aliases:
            errors.append(f"roots[{index}].root_alias {root_alias!r} was not requested")
        if record.get("status") not in {"checked", "missing", "not_directory"}:
            errors.append(f"roots[{index}].status must be checked, missing, or not_directory")
        for field in allowed_root_fields - {"root_alias", "status"}:
            if not isinstance(record.get(field), int):
                errors.append(f"roots[{index}].{field} must be an integer")

    allowed_issue_fields = {"issue_type", "logical_path", "line_number", "detail"}
    allowed_issue_types = {"jsonl_lock", "atomic_temp_fragment", "malformed_jsonl", "oversized_jsonl_record"}
    for index, record in enumerate(issue_samples):
        if not isinstance(record, dict):
            errors.append(f"issue_samples[{index}] must be an object")
            continue
        unknown_fields = sorted(set(record) - allowed_issue_fields)
        if unknown_fields:
            errors.append(
                f"issue_samples[{index}] contains unknown fields: "
                + ", ".join(unknown_fields)
            )
        if record.get("issue_type") not in allowed_issue_types:
            errors.append(f"issue_samples[{index}].issue_type is not recognized")
        logical_path = record.get("logical_path")
        if not isinstance(logical_path, str) or not _is_public_safe_alias_path(logical_path):
            errors.append(f"issue_samples[{index}].logical_path must be a public-safe alias path")
        line_number = record.get("line_number")
        if line_number is not None and not isinstance(line_number, int):
            errors.append(f"issue_samples[{index}].line_number must be an integer or null")
        detail = record.get("detail")
        if not isinstance(detail, str) or not detail.strip():
            errors.append(f"issue_samples[{index}].detail must be a non-empty string")

    if summary.get("root_count") != len(roots):
        errors.append("root_count must equal len(roots)")
    if summary.get("issue_count") != (
        int(summary.get("lock_file_count") or 0)
        + int(summary.get("temp_fragment_count") or 0)
        + int(summary.get("malformed_jsonl_row_count") or 0)
        + int(summary.get("oversized_jsonl_row_count") or 0)
    ):
        errors.append("issue_count must equal lock/temp/malformed/oversized counts")
    return errors


def validate_event_log_check_summary(
    summary: dict[str, object] | None,
    *,
    root_aliases: Sequence[str],
) -> list[str]:
    if summary is None:
        return ["stdout did not contain a JSON object summary"]
    errors: list[str] = []
    count_fields = {
        "root_count",
        "checked_file_count",
        "jsonl_file_count",
        "event_record_count",
        "malformed_jsonl_row_count",
        "invalid_utf8_row_count",
        "oversized_jsonl_row_count",
        "non_object_row_count",
        "missing_required_field_count",
        "invalid_field_value_count",
        "duplicate_event_id_count",
        "duplicate_dedupe_key_count",
        "unsafe_string_count",
        "issue_count",
    }
    allowed_top_level_fields = {
        "schema_version",
        *count_fields,
        "roots",
        "issue_samples",
        "no_mutation_performed",
        "authority_boundary",
        "authoritative_gate",
        "semantic_checks_not_performed",
    }
    unknown_top_level_fields = sorted(set(summary) - allowed_top_level_fields)
    if unknown_top_level_fields:
        errors.append(
            "summary contains unknown fields: " + ", ".join(unknown_top_level_fields)
        )
    if summary.get("schema_version") != EVENT_LOG_CHECK_SCHEMA_VERSION:
        errors.append(
            "schema_version must be "
            f"{EVENT_LOG_CHECK_SCHEMA_VERSION!r}; got {summary.get('schema_version')!r}"
        )
    if summary.get("no_mutation_performed") is not True:
        errors.append("no_mutation_performed must be true")
    if summary.get("authoritative_gate") != "events collect/report plus validate":
        errors.append("authoritative_gate must be 'events collect/report plus validate'")
    authority_boundary = summary.get("authority_boundary")
    if not isinstance(authority_boundary, str) or not authority_boundary.strip():
        errors.append("authority_boundary must be a non-empty string")
    elif _contains_local_path_marker(authority_boundary):
        errors.append("authority_boundary must not contain local path markers")

    roots = summary.get("roots")
    issue_samples = summary.get("issue_samples")
    semantic_checks = summary.get("semantic_checks_not_performed")
    if not isinstance(roots, list):
        errors.append("roots must be a list")
        roots = []
    if not isinstance(issue_samples, list):
        errors.append("issue_samples must be a list")
        issue_samples = []
    if not isinstance(semantic_checks, list) or not all(
        isinstance(item, str) and item.strip() for item in semantic_checks
    ):
        errors.append("semantic_checks_not_performed must be a list of non-empty strings")
    elif any(_contains_local_path_marker(item) for item in semantic_checks):
        errors.append("semantic_checks_not_performed must not contain local path markers")

    for field in count_fields:
        if not isinstance(summary.get(field), int):
            errors.append(f"{field} must be an integer")

    allowed_aliases = set(root_aliases)
    allowed_root_fields = {
        "root_alias",
        "status",
        "checked_file_count",
        "jsonl_file_count",
        "event_record_count",
        "malformed_jsonl_row_count",
        "invalid_utf8_row_count",
        "oversized_jsonl_row_count",
        "non_object_row_count",
        "missing_required_field_count",
        "invalid_field_value_count",
        "duplicate_event_id_count",
        "duplicate_dedupe_key_count",
        "unsafe_string_count",
    }
    for index, record in enumerate(roots):
        if not isinstance(record, dict):
            errors.append(f"roots[{index}] must be an object")
            continue
        unknown_fields = sorted(set(record) - allowed_root_fields)
        if unknown_fields:
            errors.append(
                f"roots[{index}] contains unknown fields: " + ", ".join(unknown_fields)
            )
        root_alias = record.get("root_alias")
        if not isinstance(root_alias, str) or not _is_public_safe_alias_path(root_alias):
            errors.append(f"roots[{index}].root_alias must be a public-safe alias")
        elif root_alias not in allowed_aliases:
            errors.append(f"roots[{index}].root_alias {root_alias!r} was not requested")
        if record.get("status") not in {"checked", "missing", "not_directory"}:
            errors.append(f"roots[{index}].status must be checked, missing, or not_directory")
        for field in allowed_root_fields - {"root_alias", "status"}:
            if not isinstance(record.get(field), int):
                errors.append(f"roots[{index}].{field} must be an integer")

    allowed_issue_fields = {"issue_type", "logical_path", "line_number", "detail"}
    allowed_issue_types = {
        "duplicate_dedupe_key",
        "duplicate_event_id",
        "invalid_field_value",
        "invalid_utf8_row",
        "malformed_jsonl",
        "missing_required_field",
        "non_object_jsonl_row",
        "oversized_jsonl_record",
        "unsafe_string",
    }
    for index, record in enumerate(issue_samples):
        if not isinstance(record, dict):
            errors.append(f"issue_samples[{index}] must be an object")
            continue
        unknown_fields = sorted(set(record) - allowed_issue_fields)
        if unknown_fields:
            errors.append(
                f"issue_samples[{index}] contains unknown fields: "
                + ", ".join(unknown_fields)
            )
        if record.get("issue_type") not in allowed_issue_types:
            errors.append(f"issue_samples[{index}].issue_type is not recognized")
        logical_path = record.get("logical_path")
        if not isinstance(logical_path, str) or not _is_public_safe_alias_path(logical_path):
            errors.append(f"issue_samples[{index}].logical_path must be a public-safe alias path")
        line_number = record.get("line_number")
        if line_number is not None and not isinstance(line_number, int):
            errors.append(f"issue_samples[{index}].line_number must be an integer or null")
        detail = record.get("detail")
        if not isinstance(detail, str) or not detail.strip():
            errors.append(f"issue_samples[{index}].detail must be a non-empty string")
        elif _contains_local_path_marker(detail):
            errors.append(f"issue_samples[{index}].detail must not contain local path markers")

    expected_issue_count = (
        int(summary.get("malformed_jsonl_row_count") or 0)
        + int(summary.get("invalid_utf8_row_count") or 0)
        + int(summary.get("oversized_jsonl_row_count") or 0)
        + int(summary.get("non_object_row_count") or 0)
        + int(summary.get("missing_required_field_count") or 0)
        + int(summary.get("invalid_field_value_count") or 0)
        + int(summary.get("duplicate_event_id_count") or 0)
        + int(summary.get("duplicate_dedupe_key_count") or 0)
        + int(summary.get("unsafe_string_count") or 0)
    )
    if summary.get("root_count") != len(roots):
        errors.append("root_count must equal len(roots)")
    if summary.get("issue_count") != expected_issue_count:
        errors.append("issue_count must equal structural issue counts")
    return errors


def _contains_local_path_marker(value: str) -> bool:
    normalized = value.replace("\\", "/")
    if "\\" in value or ":" in value:
        return True
    return normalized.startswith("/") or "/Users/" in normalized or "/OneDrive/" in normalized


def _is_public_safe_alias_path(value: str) -> bool:
    if not value or value.strip() != value:
        return False
    if "\\" in value or ":" in value or Path(value).is_absolute():
        return False
    for segment in value.split("/"):
        if segment in {"", ".", ".."}:
            return False
    return all(
        character.isascii() and (character.isalnum() or character in {"/", "-", "_", "."})
        for character in value
    )


def _resolve(repo_root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()


def _validate_root_alias_cardinality(
    roots: Sequence[Path],
    root_aliases: Sequence[str],
    *,
    command_name: str,
) -> None:
    if len(roots) != len(root_aliases):
        raise ValueError(
            f"{command_name} requires exactly one root_alias for each root "
            f"({len(roots)} roots, {len(root_aliases)} aliases)."
        )
    alias_counts: dict[str, int] = {}
    for alias in root_aliases:
        alias_counts[alias] = alias_counts.get(alias, 0) + 1
    duplicates = sorted(alias for alias, count in alias_counts.items() if count > 1)
    if duplicates:
        joined = ", ".join(duplicates)
        raise ValueError(f"{command_name} root_alias values must be unique: {joined}")


def _display_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return "<local-path-suppressed>"
