from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from digital_asset_directory.cli import app
from digital_asset_directory.rust_bridge import DadScanCoreResult
from digital_asset_directory.rust_bridge import dad_scan_core as bridge


RUNNER = CliRunner()


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


def test_rust_scan_local_cli_prints_structured_result(monkeypatch, tmp_path: Path) -> None:
    def fake_scan(**kwargs):
        assert kwargs["source"] == Path("examples")
        assert kwargs["source_id"] == "examples"
        assert kwargs["path_alias"] == "dad/examples"
        return DadScanCoreResult(
            command=["cargo", "run"],
            returncode=0,
            stdout="ok",
            stderr="",
            cargo_found=True,
            source=str(tmp_path / "examples"),
            out=str(tmp_path / "out.jsonl"),
            summary_out=str(tmp_path / "summary.json"),
            quarantine_out=str(tmp_path / "quarantine.json"),
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
    assert payload["command"] == ["cargo", "run"]
    assert payload["returncode"] == 0
    assert payload["stdout"] == ""
    assert payload["output_suppressed"] is True
