from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest
from jsonschema import FormatChecker
from jsonschema.validators import validator_for
from typer.testing import CliRunner

import digital_asset_directory.cli as cli_module
from digital_asset_directory.cli import app
from digital_asset_directory.portfolio_capture_inbox import (
    CaptureInboxError,
    CaptureInboxSettings,
    build_capture_inbox_report,
    candidate_ledger_path,
    report_path,
    write_capture_inbox_outputs,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 20, tzinfo=timezone.utc)


def _copy_schemas(hub: Path) -> None:
    target = hub / "schemas"
    target.mkdir(parents=True, exist_ok=True)
    for name in (
        "portfolio-capture-candidate.schema.json",
        "portfolio-capture-inbox-report.schema.json",
    ):
        (target / name).write_text(
            (ROOT / "schemas" / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _validate(report: dict[str, object]) -> None:
    schema = json.loads(
        (ROOT / "schemas/portfolio-capture-inbox-report.schema.json").read_text(encoding="utf-8")
    )
    cls = validator_for(schema)
    cls.check_schema(schema)
    cls(schema, format_checker=FormatChecker()).validate(report)


def test_adapter_preserves_source_and_appends_redacted_candidates(tmp_path: Path) -> None:
    _copy_schemas(tmp_path)
    synthetic_token = "gh" + "p_" + "abcdefghijklmnopqrstuvwxyz0123456789"
    inbox = tmp_path / "outside-inbox.md"
    inbox.write_text(
        f"Build the cockpit from C:\\Users\\Lowell\\private\\notes.md\ntoken {synthetic_token}\n",
        encoding="utf-8",
    )
    before = _digest(inbox)
    report = build_capture_inbox_report(tmp_path, inbox, now=NOW)
    after = _digest(inbox)
    _validate(report)
    assert before == after
    assert report["source"]["mutated"] is False
    assert report["summary"]["redaction_count"] >= 2
    assert str(inbox) not in json.dumps(report)
    ledger_text = candidate_ledger_path(tmp_path).read_text(encoding="utf-8")
    assert synthetic_token not in ledger_text
    assert "C:\\\\Users\\\\Lowell" not in ledger_text


def test_repeated_import_is_idempotent_and_source_stays_unchanged(tmp_path: Path) -> None:
    _copy_schemas(tmp_path)
    inbox = tmp_path / "inbox.md"
    inbox.write_text("one thought\ntwo thoughts\n", encoding="utf-8")
    before = inbox.read_bytes()
    first = build_capture_inbox_report(tmp_path, inbox, now=NOW)
    second = build_capture_inbox_report(tmp_path, inbox, now=NOW)
    rows = candidate_ledger_path(tmp_path).read_text(encoding="utf-8").splitlines()
    assert first["summary"]["new_candidate_count"] == 2
    assert second["summary"]["new_candidate_count"] == 0
    assert second["summary"]["duplicate_candidate_count"] == 2
    assert len(rows) == 2
    assert inbox.read_bytes() == before


def test_oversized_input_writes_partial_report_but_no_candidate_ledger(tmp_path: Path) -> None:
    _copy_schemas(tmp_path)
    inbox = tmp_path / "inbox.md"
    inbox.write_bytes(b"x" * 1_025)
    result = write_capture_inbox_outputs(
        tmp_path,
        inbox,
        settings=CaptureInboxSettings(max_inbox_bytes=1_024),
        now=NOW,
    )
    assert result["status"] == "partial_candidate"
    assert result["coverage"]["problems"] == ["byte_budget_exhausted"]
    assert report_path(tmp_path).is_file()
    assert not candidate_ledger_path(tmp_path).exists()


def test_missing_input_does_not_create_any_output(tmp_path: Path) -> None:
    _copy_schemas(tmp_path)
    with pytest.raises(CaptureInboxError, match="does not exist"):
        write_capture_inbox_outputs(tmp_path, tmp_path / "missing.md", now=NOW)
    assert not report_path(tmp_path).exists()
    assert not candidate_ledger_path(tmp_path).exists()


@pytest.mark.parametrize("output_factory", [report_path, candidate_ledger_path])
def test_source_cannot_alias_capture_outputs(tmp_path: Path, output_factory: object) -> None:
    _copy_schemas(tmp_path)
    output = output_factory(tmp_path)  # type: ignore[operator]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("source bytes must remain unchanged\n", encoding="utf-8")
    before = output.read_bytes()
    with pytest.raises(CaptureInboxError, match="must not alias"):
        write_capture_inbox_outputs(tmp_path, output, now=NOW)
    assert output.read_bytes() == before


def test_source_symlink_to_capture_output_is_rejected_when_supported(tmp_path: Path) -> None:
    _copy_schemas(tmp_path)
    output = report_path(tmp_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("source bytes must remain unchanged\n", encoding="utf-8")
    alias = tmp_path / "capture-output-alias.md"
    try:
        alias.symlink_to(output)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks are unavailable in this environment")
    before = output.read_bytes()
    with pytest.raises(CaptureInboxError, match="must not alias"):
        write_capture_inbox_outputs(tmp_path, alias, now=NOW)
    assert output.read_bytes() == before


def test_invalid_utf8_writes_partial_report_without_candidates(tmp_path: Path) -> None:
    _copy_schemas(tmp_path)
    inbox = tmp_path / "invalid-utf8.md"
    inbox.write_bytes(b"valid prefix\n\xff\xfe")
    result = write_capture_inbox_outputs(tmp_path, inbox, now=NOW)
    assert result["status"] == "partial_candidate"
    assert result["coverage"]["problems"] == ["invalid_utf8"]
    assert not candidate_ledger_path(tmp_path).exists()


def test_line_budget_exhaustion_discards_the_whole_adapter_batch(tmp_path: Path) -> None:
    _copy_schemas(tmp_path)
    inbox = tmp_path / "too-many-lines.md"
    inbox.write_text("first\nsecond\n", encoding="utf-8")
    result = write_capture_inbox_outputs(
        tmp_path,
        inbox,
        settings=CaptureInboxSettings(max_lines=1),
        now=NOW,
    )
    assert result["status"] == "partial_candidate"
    assert result["coverage"]["problems"] == ["line_budget_exhausted"]
    assert result["summary"]["candidate_count"] == 0
    assert not candidate_ledger_path(tmp_path).exists()


def test_malformed_existing_ledger_blocks_append_and_preserves_source(tmp_path: Path) -> None:
    _copy_schemas(tmp_path)
    ledger = candidate_ledger_path(tmp_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("{malformed}\n", encoding="utf-8")
    inbox = tmp_path / "inbox.md"
    inbox.write_text("safe candidate\n", encoding="utf-8")
    before = inbox.read_bytes()
    with pytest.raises(CaptureInboxError, match="malformed"):
        build_capture_inbox_report(tmp_path, inbox, now=NOW)
    assert inbox.read_bytes() == before
    assert ledger.read_text(encoding="utf-8") == "{malformed}\n"


def test_cli_supports_raw_alias_and_explicit_dormant_inbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _copy_schemas(tmp_path)
    monkeypatch.setattr(
        cli_module, "_cfg", lambda *_args, **_kwargs: type("Cfg", (), {"repo_root": tmp_path})()
    )
    runner = CliRunner()
    raw = runner.invoke(
        app,
        ["os", "capture", "--raw", "cockpit needs a bounded capture lane", "--hub", str(tmp_path)],
    )
    assert raw.exit_code == 0, raw.output
    assert json.loads(raw.output)["captured_count"] == 1

    inbox = tmp_path / "inbox.md"
    inbox.write_text("review the dormant capture lane\n", encoding="utf-8")
    imported = runner.invoke(
        app,
        ["os", "capture-inbox", "--inbox", str(inbox), "--hub", str(tmp_path)],
    )
    assert imported.exit_code == 0, imported.output
    payload = json.loads(imported.output)
    assert payload["source_mutated"] is False
    assert payload["execution_authorized"] is False
