from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from digital_asset_directory.cli import _json_command
from digital_asset_directory.test_parity import (
    compare_structured_reports,
    infer_native_authority,
    load_structured_observations,
    load_structured_report,
    run_test_parity,
)

pytestmark = pytest.mark.integration


def _python_exit(code: int) -> list[str]:
    return [sys.executable, "-c", f"import sys; sys.exit({code})"]


def _write_report_command(path: Path, *, outcome: str = "passed", duration: float = 0.01) -> list[str]:
    payload = json.dumps(
        {
            "tests": [
                {
                    "test_id": "tests/test_shadow.py::test_equivalent",
                    "outcome": outcome,
                    "duration_seconds": duration,
                }
            ]
        }
    )
    return [
        sys.executable,
        "-c",
        (
            "import pathlib; "
            f"pathlib.Path({json.dumps(str(path))}).write_text({json.dumps(payload)}, encoding='utf-8')"
        ),
    ]


def test_json_command_helper_accepts_windows_paths_with_spaces() -> None:
    command = _json_command(
        '["C:/Program Files/Python/python.exe","-m","pytest","tests/test file.py"]',
        "--native-command-json",
    )

    assert command == [
        "C:/Program Files/Python/python.exe",
        "-m",
        "pytest",
        "tests/test file.py",
    ]


def test_parity_passes_and_appends_audit_when_native_and_shadow_pass(tmp_path: Path) -> None:
    native_report = tmp_path / "native.json"
    shadow_report = tmp_path / "shadow.json"
    result = run_test_parity(
        tmp_path,
        native_command=_write_report_command(native_report),
        shadow_command=_write_report_command(shadow_report),
        timeout_seconds=10,
        native_report=native_report,
        shadow_report=shadow_report,
    )

    assert result["parity_status"] == "matched_pass"
    assert result["exit_code"] == 0
    assert result["candidate_only"] is True
    assert infer_native_authority([sys.executable, "-m", "pytest", "-q"]) == "pytest"
    assert infer_native_authority(["cargo", "test"]) == "native_command_candidate"
    audit_path = Path(result["audit_path"])
    assert audit_path.is_relative_to(tmp_path / "audit" / "events")
    event = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
    assert event["event_type"] == "test_parity_run"
    assert event["payload"]["native_authority"] == "native_command_candidate"
    assert event["payload"]["native"]["stdout_tail"] == "<omitted from audit>"
    assert event["payload"]["native"]["stderr_tail"] == "<omitted from audit>"


def test_parity_flags_shadow_false_green_when_native_fails(tmp_path: Path) -> None:
    result = run_test_parity(
        tmp_path,
        native_command=_python_exit(7),
        shadow_command=_python_exit(0),
        timeout_seconds=10,
        audit=False,
    )

    assert result["parity_status"] == "shadow_passed_native_failed"
    assert result["exit_code"] == 1
    assert result["native"]["exit_code"] == 7
    assert result["shadow"]["exit_code"] == 0
    assert result["native_authority"] == "native_command_candidate"


def test_parity_distinguishes_exit_code_only_from_verified_parity(tmp_path: Path) -> None:
    result = run_test_parity(
        tmp_path,
        native_command=_python_exit(0),
        shadow_command=_python_exit(0),
        timeout_seconds=10,
        audit=False,
    )

    assert result["parity_status"] == "exit_code_match_only"
    assert result["exit_code"] == 1
    assert result["structured_comparison"]["status"] == "not_provided"


def test_timing_analysis_reports_burn_in_cost_and_replacement_savings(
    tmp_path: Path,
) -> None:
    native_report = tmp_path / "native.json"
    shadow_report = tmp_path / "shadow.json"
    result = run_test_parity(
        tmp_path,
        native_command=[
            sys.executable,
            "-c",
            (
                "import pathlib, time; time.sleep(0.5); "
                f"pathlib.Path({json.dumps(str(native_report))}).write_text("
                f"{json.dumps(json.dumps({'tests': [{'test_id': 'tests/test_shadow.py::test_equivalent', 'outcome': 'passed', 'duration_seconds': 0.5}]}))}, "
                "encoding='utf-8')"
            ),
        ],
        shadow_command=[
            sys.executable,
            "-c",
            (
                "import pathlib, time; time.sleep(0.01); "
                f"pathlib.Path({json.dumps(str(shadow_report))}).write_text("
                f"{json.dumps(json.dumps({'tests': [{'test_id': 'tests/test_shadow.py::test_equivalent', 'outcome': 'passed', 'duration_seconds': 0.01}]}))}, "
                "encoding='utf-8')"
            ),
        ],
        timeout_seconds=10,
        native_report=native_report,
        shadow_report=shadow_report,
        audit=False,
    )

    timing = result["timing_analysis"]
    assert timing["measurement_mode"] == "sequential"
    assert timing["sequential_burn_in_seconds"] >= timing["native_seconds"]
    assert timing["sequential_burn_in_overhead_seconds"] == timing["shadow_seconds"]
    assert timing["replacement_estimate_status"] == "compared"
    assert timing["estimated_replacement_savings_seconds"] > 0
    assert timing["estimated_replacement_savings_percent"] > 0
    assert timing["replacement_would_be_faster"] is True


def test_structured_report_comparison_finds_missing_and_mismatched_tests(
    tmp_path: Path,
) -> None:
    native_report = tmp_path / "native.jsonl"
    shadow_report = tmp_path / "shadow.jsonl"
    native_report.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "test_id": "tests/test_a.py::test_one",
                        "outcome": "passed",
                        "duration_seconds": 1.5,
                    }
                ),
                json.dumps(
                    {
                        "test_id": "tests/test_b.py::test_two",
                        "outcome": "failed",
                        "duration_seconds": 2.0,
                    }
                ),
                json.dumps(
                    {
                        "test_id": "tests/test_c.py::test_three",
                        "outcome": "skipped",
                        "duration_seconds": 0.1,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    shadow_report.write_text(
        json.dumps(
            {
                "tests": [
                    {
                        "nodeid": "tests/test_a.py::test_one",
                        "outcome": "passed",
                        "duration_seconds": 0.5,
                    },
                    {
                        "nodeid": "tests/test_b.py::test_two",
                        "outcome": "passed",
                        "duration_seconds": 3.0,
                    },
                    {
                        "nodeid": "tests/test_d.py::test_four",
                        "outcome": "passed",
                        "duration_seconds": 0.2,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_structured_report(native_report)["tests/test_a.py::test_one"] == "passed"
    native = load_structured_observations(native_report)
    shadow = load_structured_observations(shadow_report)
    comparison = compare_structured_reports(native, shadow)

    assert comparison["status"] == "mismatch"
    assert comparison["native_only"] == ["tests/test_c.py::test_three"]
    assert comparison["shadow_only"] == ["tests/test_d.py::test_four"]
    assert comparison["outcome_mismatches"] == [
        {
            "test_id": "tests/test_b.py::test_two",
            "native_outcome": "failed",
            "shadow_outcome": "passed",
        }
    ]
    assert comparison["duration_comparison"]["used"] is True
    assert comparison["duration_comparison"]["shared_duration_count"] == 2
    assert comparison["duration_comparison"]["estimated_replacement_savings_seconds"] == 0.0



def test_parity_rejects_stale_empty_and_same_report_paths(tmp_path: Path) -> None:
    native_report = tmp_path / "native.jsonl"
    shadow_report = tmp_path / "shadow.jsonl"
    native_report.write_text("", encoding="utf-8")
    shadow_report.write_text("", encoding="utf-8")

    stale = run_test_parity(
        tmp_path,
        native_command=_python_exit(0),
        shadow_command=_python_exit(0),
        timeout_seconds=10,
        native_report=native_report,
        shadow_report=shadow_report,
        audit=False,
    )
    assert stale["parity_status"] == "structured_mismatch"
    assert stale["structured_comparison"]["status"] == "report_integrity_failed"

    same_path = tmp_path / "same.json"
    result = run_test_parity(
        tmp_path,
        native_command=_write_report_command(same_path),
        shadow_command=_write_report_command(same_path),
        timeout_seconds=10,
        native_report=same_path,
        shadow_report=same_path,
        audit=False,
    )
    assert result["parity_status"] == "structured_mismatch"
    assert "same path" in result["structured_comparison"]["integrity_errors"][0]


def test_parity_rejects_malformed_structured_report(tmp_path: Path) -> None:
    native_report = tmp_path / "native.jsonl"
    shadow_report = tmp_path / "shadow.json"

    result = run_test_parity(
        tmp_path,
        native_command=[
            sys.executable,
            "-c",
            (
                "import pathlib; "
                f"pathlib.Path({json.dumps(str(native_report))}).write_text("
                "'{not valid json', encoding='utf-8')"
            ),
        ],
        shadow_command=_write_report_command(shadow_report),
        timeout_seconds=10,
        native_report=native_report,
        shadow_report=shadow_report,
        audit=False,
    )

    assert result["parity_status"] == "structured_mismatch"
    assert result["structured_comparison"]["status"] == "report_integrity_failed"
    assert "parse failed" in result["structured_comparison"]["integrity_errors"][0]
