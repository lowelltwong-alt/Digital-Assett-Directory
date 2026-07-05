from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from digital_asset_directory.cli import app
from digital_asset_directory.rust_bridge import (
    DadMailSpoolCheckResult,
    DadRepoInventoryProbeResult,
    DadScanCoreResult,
)
from digital_asset_directory.rust_bridge import dad_scan_core as bridge


RUNNER = CliRunner()


def _repo_probe_record(
    *,
    root_alias: str = "dad-local-source/workspace",
    logical_path: str = "dad-local-source/workspace/repo",
    contract_present: bool = False,
    contract_structural_pass: bool = False,
    contract_issue_codes: list[str] | None = None,
) -> dict[str, object]:
    if contract_issue_codes is None:
        if contract_structural_pass:
            contract_issue_codes = []
        elif contract_present:
            contract_issue_codes = ["contract_missing_schema_version"]
        else:
            contract_issue_codes = ["contract_missing"]
    return {
        "root_alias": root_alias,
        "logical_path": logical_path,
        "depth": 1,
        "git_marker_type": "directory",
        "contract_present": contract_present,
        "contract_parse_status": "present_parseable" if contract_present else "missing",
        "contract_schema_version_present": contract_structural_pass,
        "contract_repo_id_present": contract_structural_pass,
        "contract_capture_surface_version_present": contract_structural_pass,
        "contract_cli_fallback_present": contract_structural_pass,
        "contract_stable_user_shim_present": contract_structural_pass,
        "contract_windows_user_shim_present": contract_structural_pass,
        "contract_raw_checkout_fallback_present": contract_structural_pass,
        "contract_stable_shim_before_raw_checkout": contract_structural_pass,
        "contract_structural_pass": contract_structural_pass,
        "contract_issue_codes": contract_issue_codes,
        "no_mutation_performed": True,
    }


def test_run_dad_scan_core_builds_cargo_command_and_captures_result(
    monkeypatch, tmp_path: Path
) -> None:
    completed = subprocess.CompletedProcess(
        args=["cargo"], returncode=0, stdout='{"included_count":1}\n', stderr=""
    )
    calls: list[dict[str, object]] = []

    def fake_run(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return completed

    monkeypatch.setattr(bridge.shutil, "which", lambda value: "C:/Rust/bin/cargo.exe")
    monkeypatch.setattr(bridge.subprocess, "run", fake_run)

    result = bridge.run_dad_scan_core(
        repo_root=tmp_path,
        source=Path("examples"),
        source_id="examples",
        path_alias="dad/examples",
        out=Path("raw/local/rust/examples.jsonl"),
        summary_out=Path("processed/reports/rust/examples-summary.json"),
        quarantine_out=Path("processed/quarantine/rust/examples-quarantine.json"),
        max_files=5,
        excludes=["**/*.tmp"],
    )

    assert result.returncode == 0
    assert result.cargo_found is True
    assert result.stdout == '{"included_count":1}\n'
    assert result.to_dict()["stdout"] == ""
    assert result.to_dict()["output_suppressed"] is True
    assert result.to_dict(include_output=True)["stdout"] == '{"included_count":1}\n'
    default_payload = result.to_dict()
    assert default_payload["local_command_suppressed"] is True
    assert default_payload["command"][:4] == [
        "cargo",
        "run",
        "--manifest-path",
        "tools/dad_scan_core/Cargo.toml",
    ]
    assert str(tmp_path) not in repr(default_payload)
    assert result.to_dict(include_local_paths=True)["local_command_suppressed"] is False
    command = calls[0]["command"]
    assert command[:4] == [
        "cargo",
        "run",
        "--manifest-path",
        str(tmp_path / "tools" / "dad_scan_core" / "Cargo.toml"),
    ]
    assert "--source-id" in command
    assert "examples" in command
    assert "--max-files" in command
    assert "--exclude" in command
    assert calls[0]["cwd"] == tmp_path
    assert calls[0]["capture_output"] is True


def test_run_dad_scan_core_reports_missing_cargo(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(bridge.shutil, "which", lambda value: None)

    result = bridge.run_dad_scan_core(
        repo_root=tmp_path,
        source=Path("examples"),
        source_id="examples",
        path_alias="dad/examples",
        out=Path("raw/local/rust/examples.jsonl"),
        summary_out=Path("processed/reports/rust/examples-summary.json"),
        quarantine_out=Path("processed/quarantine/rust/examples-quarantine.json"),
    )

    assert result.returncode == 127
    assert result.cargo_found is False
    assert "cargo was not found on PATH" in result.stderr
    assert result.source == "examples"


def test_run_dad_scan_core_reports_timeout(monkeypatch, tmp_path: Path) -> None:
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, timeout=1, output="building", stderr="hung")

    monkeypatch.setattr(bridge.shutil, "which", lambda value: "C:/Rust/bin/cargo.exe")
    monkeypatch.setattr(bridge.subprocess, "run", fake_run)

    result = bridge.run_dad_scan_core(
        repo_root=tmp_path,
        source=Path("examples"),
        source_id="examples",
        path_alias="dad/examples",
        out=Path("raw/local/rust/examples.jsonl"),
        summary_out=Path("processed/reports/rust/examples-summary.json"),
        quarantine_out=Path("processed/quarantine/rust/examples-quarantine.json"),
        timeout_seconds=1,
    )

    assert result.returncode == 124
    assert result.cargo_found is True
    assert result.timed_out is True
    assert result.stdout == "building"
    assert result.stderr == "hung"


def test_run_dad_mail_spool_check_builds_alias_only_command_and_summary(
    monkeypatch, tmp_path: Path
) -> None:
    summary = {
        "schema_version": "dad_mail_spool_check.v0_1",
        "root_count": 1,
        "checked_file_count": 0,
        "jsonl_file_count": 0,
        "lock_file_count": 0,
        "temp_fragment_count": 0,
        "rust_packet_count": 0,
        "malformed_jsonl_row_count": 0,
        "oversized_jsonl_row_count": 0,
        "issue_count": 0,
        "roots": [
            {
                "root_alias": "dad/central-mail",
                "status": "checked",
                "checked_file_count": 0,
                "jsonl_file_count": 0,
                "lock_file_count": 0,
                "temp_fragment_count": 0,
                "rust_packet_count": 0,
                "malformed_jsonl_row_count": 0,
                "oversized_jsonl_row_count": 0,
            }
        ],
        "issue_samples": [],
        "no_mutation_performed": True,
        "authority_boundary": "Python mail doctor remains authoritative.",
        "authoritative_gate": "mail doctor",
        "semantic_checks_not_performed": ["collection audit verification"],
    }
    completed = subprocess.CompletedProcess(
        args=["cargo"],
        returncode=0,
        stdout=json.dumps(summary) + "\n",
        stderr="",
    )
    calls: list[dict[str, object]] = []

    def fake_run(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return completed

    monkeypatch.setattr(bridge.shutil, "which", lambda value: "C:/Rust/bin/cargo.exe")
    monkeypatch.setattr(bridge.subprocess, "run", fake_run)

    result = bridge.run_dad_mail_spool_check(
        repo_root=tmp_path,
        roots=[Path("processed/mail")],
        root_aliases=["dad/central-mail"],
    )

    assert result.returncode == 0
    assert result.summary == summary
    assert result.summary_valid is True
    assert result.summary_validation_errors == []
    default_payload = result.to_dict()
    assert default_payload["stdout"] == ""
    assert default_payload["output_suppressed"] is True
    assert default_payload["command"][:5] == [
        "cargo",
        "run",
        "--manifest-path",
        "tools/dad_scan_core/Cargo.toml",
        "--",
    ]
    assert "mail-spool-check" in default_payload["command"]
    assert str(tmp_path) not in repr(default_payload)
    command = calls[0]["command"]
    assert "--root" in command
    assert str(tmp_path / "processed" / "mail") in command
    assert "--root-alias" in command
    assert "dad/central-mail" in command
    row_limit_index = command.index("--max-jsonl-row-bytes") + 1
    assert command[row_limit_index] == "64000"


def test_run_dad_mail_spool_check_rejects_invalid_summary_schema(
    monkeypatch, tmp_path: Path
) -> None:
    completed = subprocess.CompletedProcess(
        args=["cargo"],
        returncode=0,
        stdout='{"schema_version":"unexpected","issue_count":0}\n',
        stderr="",
    )
    monkeypatch.setattr(bridge.shutil, "which", lambda value: "C:/Rust/bin/cargo.exe")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *_args, **_kwargs: completed)

    result = bridge.run_dad_mail_spool_check(
        repo_root=tmp_path,
        roots=[Path("processed/mail")],
        root_aliases=["dad/central-mail"],
    )
    payload = result.to_dict()

    assert result.returncode == 2
    assert result.summary_valid is False
    assert any("schema_version" in error for error in result.summary_validation_errors or [])
    assert payload["summary"] is None
    assert payload["summary_suppressed"] is True


def test_run_dad_mail_spool_check_rejects_local_path_leaking_summary(
    monkeypatch, tmp_path: Path
) -> None:
    summary = {
        "schema_version": "dad_mail_spool_check.v0_1",
        "root_count": 1,
        "checked_file_count": 1,
        "jsonl_file_count": 1,
        "lock_file_count": 0,
        "temp_fragment_count": 0,
        "rust_packet_count": 0,
        "malformed_jsonl_row_count": 1,
        "oversized_jsonl_row_count": 0,
        "issue_count": 1,
        "roots": [
            {
                "root_alias": "C:/Users/lowel/mail",
                "status": "checked",
                "checked_file_count": 1,
                "jsonl_file_count": 1,
                "lock_file_count": 0,
                "temp_fragment_count": 0,
                "rust_packet_count": 0,
                "malformed_jsonl_row_count": 1,
                "oversized_jsonl_row_count": 0,
            }
        ],
        "issue_samples": [
            {
                "issue_type": "malformed_jsonl",
                "logical_path": "C:/Users/lowel/mail/outbox.jsonl",
                "line_number": 1,
                "detail": "row is not valid JSON",
            }
        ],
        "no_mutation_performed": True,
        "authority_boundary": "C:/Users/lowel/path leaked",
        "authoritative_gate": "mail doctor",
        "semantic_checks_not_performed": ["collection audit verification"],
    }
    completed = subprocess.CompletedProcess(
        args=["cargo"],
        returncode=0,
        stdout=json.dumps(summary) + "\n",
        stderr="",
    )
    monkeypatch.setattr(bridge.shutil, "which", lambda value: "C:/Rust/bin/cargo.exe")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *_args, **_kwargs: completed)

    result = bridge.run_dad_mail_spool_check(
        repo_root=tmp_path,
        roots=[Path("processed/mail")],
        root_aliases=["dad/central-mail"],
    )

    assert result.returncode == 2
    assert result.summary_valid is False
    errors = result.summary_validation_errors or []
    assert any("authority_boundary" in error for error in errors)
    assert any("root_alias" in error for error in errors)
    assert any("logical_path" in error for error in errors)


def test_run_dad_mail_spool_check_rejects_mismatched_root_aliases_before_cargo(
    monkeypatch, tmp_path: Path
) -> None:
    def fail_run(*_args, **_kwargs):
        raise AssertionError("cargo should not run when root aliases are mismatched")

    monkeypatch.setattr(bridge.subprocess, "run", fail_run)

    with pytest.raises(ValueError, match="exactly one root_alias"):
        bridge.run_dad_mail_spool_check(
            repo_root=tmp_path,
            roots=[Path("processed/mail"), Path("processed/mail/staged/rust_rollout")],
            root_aliases=["dad/central-mail"],
        )


def test_run_dad_repo_inventory_probe_builds_alias_only_command_and_summary(
    monkeypatch, tmp_path: Path
) -> None:
    summary = {
        "schema_version": "dad_repo_inventory_probe.v0_2",
        "root_count": 1,
        "repo_count": 1,
        "skipped_dir_count": 0,
        "roots": [
            {
                "root_alias": "dad-local-source/workspace",
                "status": "checked",
                "repo_count": 1,
                "skipped_dir_count": 0,
            }
        ],
        "repos": [_repo_probe_record()],
        "skipped_dirs": [],
        "no_mutation_performed": True,
        "authority_boundary": "Rust repo-inventory probing is read-only structural evidence.",
    }
    completed = subprocess.CompletedProcess(
        args=["cargo"],
        returncode=0,
        stdout=json.dumps(summary) + "\n",
        stderr="",
    )
    calls: list[dict[str, object]] = []

    def fake_run(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return completed

    monkeypatch.setattr(bridge.shutil, "which", lambda value: "C:/Rust/bin/cargo.exe")
    monkeypatch.setattr(bridge.subprocess, "run", fake_run)

    result = bridge.run_dad_repo_inventory_probe(
        repo_root=tmp_path,
        roots=[Path("workspace")],
        root_aliases=["dad-local-source/workspace"],
        max_depth=6,
    )

    assert result.returncode == 0
    assert result.summary == summary
    assert result.summary_valid is True
    assert result.summary_validation_errors == []
    default_payload = result.to_dict()
    assert default_payload["stdout"] == ""
    assert default_payload["output_suppressed"] is True
    assert default_payload["command"][:5] == [
        "cargo",
        "run",
        "--manifest-path",
        "tools/dad_scan_core/Cargo.toml",
        "--",
    ]
    assert "repo-inventory-probe" in default_payload["command"]
    assert str(tmp_path) not in repr(default_payload)
    command = calls[0]["command"]
    assert "--root" in command
    assert str(tmp_path / "workspace") in command
    assert "--root-alias" in command
    assert "dad-local-source/workspace" in command


def test_run_dad_repo_inventory_probe_rejects_wrong_schema_summary(
    monkeypatch, tmp_path: Path
) -> None:
    completed = subprocess.CompletedProcess(
        args=["cargo"],
        returncode=0,
        stdout='{"schema_version":"old_probe","repo_count":0}\n',
        stderr="",
    )

    monkeypatch.setattr(bridge.shutil, "which", lambda value: "C:/Rust/bin/cargo.exe")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *_args, **_kwargs: completed)

    result = bridge.run_dad_repo_inventory_probe(
        repo_root=tmp_path,
        roots=[Path("workspace")],
        root_aliases=["dad-local-source/workspace"],
    )

    assert result.returncode == 2
    assert result.summary_valid is False
    assert any("schema_version" in issue for issue in result.summary_validation_errors or [])
    assert any("no_mutation_performed" in issue for issue in result.summary_validation_errors or [])
    default_payload = result.to_dict()
    assert default_payload["summary"] is None
    assert default_payload["summary_suppressed"] is True
    assert default_payload["failure_summary"].startswith("Rust repo-inventory summary failed")


def test_run_dad_repo_inventory_probe_suppresses_external_root_basename(
    monkeypatch, tmp_path: Path
) -> None:
    repo_root = tmp_path / "dad"
    sensitive_root = tmp_path / "SensitiveClient"
    repo_root.mkdir()
    sensitive_root.mkdir()
    summary = {
        "schema_version": "dad_repo_inventory_probe.v0_2",
        "root_count": 1,
        "repo_count": 0,
        "skipped_dir_count": 0,
        "roots": [
            {
                "root_alias": "dad-local-source/client",
                "status": "checked",
                "repo_count": 0,
                "skipped_dir_count": 0,
            }
        ],
        "repos": [],
        "skipped_dirs": [],
        "no_mutation_performed": True,
        "authority_boundary": "Rust repo-inventory probing is read-only structural evidence.",
    }
    completed = subprocess.CompletedProcess(
        args=["cargo"],
        returncode=0,
        stdout=json.dumps(summary) + "\n",
        stderr="",
    )
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return completed

    monkeypatch.setattr(bridge.shutil, "which", lambda value: "C:/Rust/bin/cargo.exe")
    monkeypatch.setattr(bridge.subprocess, "run", fake_run)

    result = bridge.run_dad_repo_inventory_probe(
        repo_root=repo_root,
        roots=[sensitive_root],
        root_aliases=["dad-local-source/client"],
    )
    default_payload = result.to_dict()
    local_payload = result.to_dict(include_local_paths=True)

    assert result.returncode == 0
    assert "<local-path-suppressed>" in default_payload["command"]
    assert "SensitiveClient" not in repr(default_payload)
    assert str(sensitive_root) in " ".join(calls[0])
    assert "SensitiveClient" in repr(local_payload)


def test_run_dad_repo_inventory_probe_rejects_local_path_leak_in_summary(
    monkeypatch, tmp_path: Path
) -> None:
    leaked_path = str(tmp_path / "workspace" / "repo").replace("\\", "/")
    summary = {
        "schema_version": "dad_repo_inventory_probe.v0_2",
        "root_count": 1,
        "repo_count": 1,
        "skipped_dir_count": 0,
        "roots": [
            {
                "root_alias": "dad-local-source/workspace",
                "status": "checked",
                "repo_count": 1,
                "skipped_dir_count": 0,
            }
        ],
        "repos": [_repo_probe_record(logical_path=leaked_path)],
        "skipped_dirs": [],
        "no_mutation_performed": True,
        "authority_boundary": "Rust repo-inventory probing is read-only structural evidence.",
    }
    completed = subprocess.CompletedProcess(
        args=["cargo"],
        returncode=0,
        stdout=json.dumps(summary) + "\n",
        stderr="",
    )

    monkeypatch.setattr(bridge.shutil, "which", lambda value: "C:/Rust/bin/cargo.exe")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *_args, **_kwargs: completed)

    result = bridge.run_dad_repo_inventory_probe(
        repo_root=tmp_path,
        roots=[Path("workspace")],
        root_aliases=["dad-local-source/workspace"],
    )

    assert result.returncode == 2
    assert result.summary_valid is False
    assert any("logical_path" in issue for issue in result.summary_validation_errors or [])
    default_payload = result.to_dict()
    assert default_payload["summary"] is None
    assert default_payload["summary_suppressed"] is True
    assert leaked_path not in repr(default_payload)


def test_run_dad_repo_inventory_probe_rejects_unknown_fields_and_unsafe_reason(
    monkeypatch, tmp_path: Path
) -> None:
    summary = {
        "schema_version": "dad_repo_inventory_probe.v0_2",
        "root_count": 1,
        "repo_count": 0,
        "skipped_dir_count": 1,
        "roots": [
            {
                "root_alias": "dad-local-source/workspace",
                "status": "checked",
                "repo_count": 0,
                "skipped_dir_count": 1,
            }
        ],
        "repos": [],
        "skipped_dirs": [
            {
                "root_alias": "dad-local-source/workspace",
                "logical_path": "dad-local-source/workspace/repo",
                "reason": f"walk error: {tmp_path}",
                "raw_error": str(tmp_path),
            }
        ],
        "unexpected": str(tmp_path),
        "no_mutation_performed": True,
        "authority_boundary": "Rust repo-inventory probing is read-only structural evidence.",
    }
    completed = subprocess.CompletedProcess(
        args=["cargo"],
        returncode=0,
        stdout=json.dumps(summary) + "\n",
        stderr="",
    )

    monkeypatch.setattr(bridge.shutil, "which", lambda value: "C:/Rust/bin/cargo.exe")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *_args, **_kwargs: completed)

    result = bridge.run_dad_repo_inventory_probe(
        repo_root=tmp_path,
        roots=[Path("workspace")],
        root_aliases=["dad-local-source/workspace"],
    )

    assert result.returncode == 2
    assert result.summary_valid is False
    assert any("unknown fields" in issue for issue in result.summary_validation_errors or [])
    assert any("reason" in issue for issue in result.summary_validation_errors or [])
    default_payload = result.to_dict()
    assert default_payload["summary"] is None
    assert str(tmp_path) not in repr(default_payload)


def test_run_dad_repo_inventory_probe_rejects_unsafe_contract_issue_codes(
    monkeypatch, tmp_path: Path
) -> None:
    summary = {
        "schema_version": "dad_repo_inventory_probe.v0_2",
        "root_count": 1,
        "repo_count": 1,
        "skipped_dir_count": 0,
        "roots": [
            {
                "root_alias": "dad-local-source/workspace",
                "status": "checked",
                "repo_count": 1,
                "skipped_dir_count": 0,
            }
        ],
        "repos": [
            _repo_probe_record(
                contract_present=True,
                contract_structural_pass=False,
                contract_issue_codes=[
                    "contract_missing_schema_version",
                    "unknown_contract_problem",
                    "contract_missing_repo_id",
                ],
            )
        ],
        "skipped_dirs": [],
        "no_mutation_performed": True,
        "authority_boundary": "Rust repo-inventory probing is read-only structural evidence.",
    }
    completed = subprocess.CompletedProcess(
        args=["cargo"],
        returncode=0,
        stdout=json.dumps(summary) + "\n",
        stderr="",
    )

    monkeypatch.setattr(bridge.shutil, "which", lambda value: "C:/Rust/bin/cargo.exe")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *_args, **_kwargs: completed)

    result = bridge.run_dad_repo_inventory_probe(
        repo_root=tmp_path,
        roots=[Path("workspace")],
        root_aliases=["dad-local-source/workspace"],
    )

    assert result.returncode == 2
    assert result.summary_valid is False
    assert any("unknown codes" in issue for issue in result.summary_validation_errors or [])
    assert any("must be sorted" in issue for issue in result.summary_validation_errors or [])
    assert result.to_dict()["summary"] is None


def test_run_dad_repo_inventory_probe_rejects_impossible_contract_structural_pass(
    monkeypatch, tmp_path: Path
) -> None:
    record = _repo_probe_record(contract_present=True, contract_structural_pass=True)
    record["contract_windows_user_shim_present"] = False
    summary = {
        "schema_version": "dad_repo_inventory_probe.v0_2",
        "root_count": 1,
        "repo_count": 1,
        "skipped_dir_count": 0,
        "roots": [
            {
                "root_alias": "dad-local-source/workspace",
                "status": "checked",
                "repo_count": 1,
                "skipped_dir_count": 0,
            }
        ],
        "repos": [record],
        "skipped_dirs": [],
        "no_mutation_performed": True,
        "authority_boundary": "Rust repo-inventory probing is read-only structural evidence.",
    }
    completed = subprocess.CompletedProcess(
        args=["cargo"],
        returncode=0,
        stdout=json.dumps(summary) + "\n",
        stderr="",
    )

    monkeypatch.setattr(bridge.shutil, "which", lambda value: "C:/Rust/bin/cargo.exe")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *_args, **_kwargs: completed)

    result = bridge.run_dad_repo_inventory_probe(
        repo_root=tmp_path,
        roots=[Path("workspace")],
        root_aliases=["dad-local-source/workspace"],
    )

    assert result.returncode == 2
    assert result.summary_valid is False
    assert any(
        "contract_structural_pass requires contract_windows_user_shim_present" in issue
        for issue in result.summary_validation_errors or []
    )


def test_run_dad_repo_inventory_probe_rejects_malformed_status_without_issue_code(
    monkeypatch, tmp_path: Path
) -> None:
    record = _repo_probe_record(
        contract_present=True,
        contract_structural_pass=False,
        contract_issue_codes=["contract_missing_schema_version"],
    )
    record["contract_parse_status"] = "malformed_json"
    record["contract_repo_id_present"] = True
    summary = {
        "schema_version": "dad_repo_inventory_probe.v0_2",
        "root_count": 1,
        "repo_count": 1,
        "skipped_dir_count": 0,
        "roots": [
            {
                "root_alias": "dad-local-source/workspace",
                "status": "checked",
                "repo_count": 1,
                "skipped_dir_count": 0,
            }
        ],
        "repos": [record],
        "skipped_dirs": [],
        "no_mutation_performed": True,
        "authority_boundary": "Rust repo-inventory probing is read-only structural evidence.",
    }
    completed = subprocess.CompletedProcess(
        args=["cargo"],
        returncode=0,
        stdout=json.dumps(summary) + "\n",
        stderr="",
    )

    monkeypatch.setattr(bridge.shutil, "which", lambda value: "C:/Rust/bin/cargo.exe")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *_args, **_kwargs: completed)

    result = bridge.run_dad_repo_inventory_probe(
        repo_root=tmp_path,
        roots=[Path("workspace")],
        root_aliases=["dad-local-source/workspace"],
    )

    assert result.returncode == 2
    assert result.summary_valid is False
    assert any(
        "contract_malformed_json" in issue
        for issue in result.summary_validation_errors or []
    )
    assert any(
        "must be false when contract_parse_status is malformed_json" in issue
        for issue in result.summary_validation_errors or []
    )


def test_run_dad_repo_inventory_probe_rejects_mismatched_root_aliases_before_cargo(
    monkeypatch, tmp_path: Path
) -> None:
    def fail_run(*_args, **_kwargs):
        raise AssertionError("cargo should not run when root aliases are mismatched")

    monkeypatch.setattr(bridge.subprocess, "run", fail_run)

    with pytest.raises(ValueError, match="exactly one root_alias"):
        bridge.run_dad_repo_inventory_probe(
            repo_root=tmp_path,
            roots=[Path("workspace"), Path("other-workspace")],
            root_aliases=["dad-local-source/workspace"],
        )


def test_run_dad_repo_inventory_probe_rejects_duplicate_root_aliases_before_cargo(
    monkeypatch, tmp_path: Path
) -> None:
    def fail_run(*_args, **_kwargs):
        raise AssertionError("cargo should not run when root aliases are duplicated")

    monkeypatch.setattr(bridge.subprocess, "run", fail_run)

    with pytest.raises(ValueError, match="root_alias values must be unique"):
        bridge.run_dad_repo_inventory_probe(
            repo_root=tmp_path,
            roots=[Path("workspace"), Path("other-workspace")],
            root_aliases=["dad-local-source/workspace", "dad-local-source/workspace"],
        )


def test_run_dad_repo_inventory_probe_missing_cargo_has_safe_failure_summary(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(bridge.shutil, "which", lambda value: None)

    result = bridge.run_dad_repo_inventory_probe(
        repo_root=tmp_path,
        roots=[Path("workspace")],
        root_aliases=["dad-local-source/workspace"],
    )

    payload = result.to_dict()
    assert result.returncode == 127
    assert payload["stderr"] == ""
    assert payload["failure_summary"] == "cargo was not found on PATH. Install Rust via rustup."


def test_rust_scan_local_cli_prints_structured_result(monkeypatch, tmp_path: Path) -> None:
    def fake_scan(**kwargs):
        assert kwargs["source"] == Path("examples")
        assert kwargs["source_id"] == "examples"
        assert kwargs["path_alias"] == "dad/examples"
        return DadScanCoreResult(
            command=["cargo", "run", "--manifest-path", str(tmp_path / "Cargo.toml")],
            returncode=0,
            stdout="ok",
            stderr="",
            cargo_found=True,
            source="examples",
            out="out.jsonl",
            summary_out="summary.json",
            quarantine_out="quarantine.json",
            display_command=["cargo", "run", "--manifest-path", "tools/dad_scan_core/Cargo.toml"],
        )

    monkeypatch.setattr("digital_asset_directory.cli.run_dad_scan_core", fake_scan)

    result = RUNNER.invoke(
        app,
        [
            "rust",
            "scan-local",
            "--source",
            "examples",
            "--source-id",
            "examples",
            "--path-alias",
            "dad/examples",
            "--out",
            "out.jsonl",
            "--summary-out",
            "summary.json",
            "--quarantine-out",
            "quarantine.json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == ["cargo", "run", "--manifest-path", "tools/dad_scan_core/Cargo.toml"]
    assert payload["returncode"] == 0
    assert payload["stdout"] == ""
    assert payload["output_suppressed"] is True
    assert payload["local_command_suppressed"] is True
    assert str(tmp_path) not in result.stdout


def test_rust_mail_spool_check_cli_uses_default_dad_roots(monkeypatch) -> None:
    def fake_check(**kwargs):
        assert kwargs["root_aliases"] == [
            "dad/repo-mail-mirror",
            "dad/central-mail",
            "dad/rust-rollout-reference",
            "dad/rust-rollout-staging",
        ]
        assert len(kwargs["roots"]) == 4
        assert kwargs["max_jsonl_row_bytes"] == 64_000
        return DadMailSpoolCheckResult(
            command=["cargo", "run", "--manifest-path", "C:/private/Cargo.toml"],
            returncode=0,
            stdout='{"issue_count":0}',
            stderr="",
            cargo_found=True,
            root_aliases=kwargs["root_aliases"],
            display_command=["cargo", "run", "--manifest-path", "tools/dad_scan_core/Cargo.toml"],
            summary={
                "schema_version": "dad_mail_spool_check.v0_1",
                "root_count": 4,
                "checked_file_count": 0,
                "jsonl_file_count": 0,
                "lock_file_count": 0,
                "temp_fragment_count": 0,
                "rust_packet_count": 0,
                "malformed_jsonl_row_count": 0,
                "oversized_jsonl_row_count": 0,
                "issue_count": 0,
                "roots": [
                    {
                        "root_alias": alias,
                        "status": "missing",
                        "checked_file_count": 0,
                        "jsonl_file_count": 0,
                        "lock_file_count": 0,
                        "temp_fragment_count": 0,
                        "rust_packet_count": 0,
                        "malformed_jsonl_row_count": 0,
                        "oversized_jsonl_row_count": 0,
                    }
                    for alias in kwargs["root_aliases"]
                ],
                "issue_samples": [],
                "no_mutation_performed": True,
                "authority_boundary": "Python mail doctor remains the authoritative gate.",
                "authoritative_gate": "mail doctor",
                "semantic_checks_not_performed": ["delivery log hash verification"],
            },
            summary_valid=True,
            summary_validation_errors=[],
        )

    monkeypatch.setattr("digital_asset_directory.cli.run_dad_mail_spool_check", fake_check)

    result = RUNNER.invoke(app, ["rust", "mail-spool-check"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["issue_count"] == 0
    assert payload["summary"]["authoritative_gate"] == "mail doctor"
    assert payload["summary"]["mail_spool_structural_clean"] is True
    assert payload["summary"]["structural_spool_check_only"] is True
    assert payload["summary"]["mail_storm_gate_satisfied"] is False
    assert payload["scope"]["hub_local_default_roots"] is True
    assert payload["scope"]["structural_spool_check_only"] is True
    assert payload["scope"]["mail_storm_gate_satisfied"] is False
    assert "delivery log hash verification" in payload["summary"]["semantic_checks_not_performed"]
    assert payload["stdout"] == ""
    assert payload["output_suppressed"] is True
    assert payload["local_command_suppressed"] is True


def test_rust_repo_inventory_probe_cli_accepts_explicit_roots(monkeypatch) -> None:
    def fake_probe(**kwargs):
        assert kwargs["roots"] == [Path("workspace")]
        assert kwargs["root_aliases"] == ["dad-local-source/workspace"]
        assert kwargs["max_depth"] == 6
        return DadRepoInventoryProbeResult(
            command=["cargo", "run", "--manifest-path", "C:/private/Cargo.toml"],
            returncode=0,
            stdout='{"repo_count":1}',
            stderr="",
            cargo_found=True,
            root_aliases=kwargs["root_aliases"],
            display_command=["cargo", "run", "--manifest-path", "tools/dad_scan_core/Cargo.toml"],
            summary={"schema_version": "dad_repo_inventory_probe.v0_2", "repo_count": 1},
            summary_valid=True,
            summary_validation_errors=[],
        )

    monkeypatch.setattr("digital_asset_directory.cli.run_dad_repo_inventory_probe", fake_probe)

    result = RUNNER.invoke(
        app,
        [
            "rust",
            "repo-inventory-probe",
            "--root",
            "workspace",
            "--root-alias",
            "dad-local-source/workspace",
            "--max-depth",
            "6",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["repo_count"] == 1
    assert payload["stdout"] == ""
    assert payload["local_command_suppressed"] is True


def test_rust_repo_inventory_parity_cli_rejects_invalid_probe_summary(monkeypatch) -> None:
    def fake_probe(**kwargs):
        return DadRepoInventoryProbeResult(
            command=["cargo", "run", "--manifest-path", "C:/private/Cargo.toml"],
            returncode=0,
            stdout='{"schema_version":"old_probe"}',
            stderr="",
            cargo_found=True,
            root_aliases=kwargs["root_aliases"],
            display_command=["cargo", "run", "--manifest-path", "tools/dad_scan_core/Cargo.toml"],
            summary={"schema_version": "old_probe"},
            summary_valid=False,
            summary_validation_errors=["schema_version must be dad_repo_inventory_probe.v0_2"],
        )

    monkeypatch.setattr("digital_asset_directory.cli.run_dad_repo_inventory_probe", fake_probe)

    result = RUNNER.invoke(
        app,
        [
            "rust",
            "repo-inventory-parity",
            "--root",
            "workspace",
            "--root-alias",
            "dad-local-source/workspace",
        ],
    )

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["summary"] is None
    assert payload["summary_suppressed"] is True
    assert payload["summary_validation_errors"]
