from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from digital_asset_directory.lesson_automation_coverage import (
    build_weekly_asset_coverage,
    classify_weekly_asset_path,
    write_weekly_asset_coverage_outputs,
)

TIMESTAMP = "2026-07-09T00:00:00+00:00"


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_weekly_asset_coverage_flags_missing_high_signal_asset():
    result = build_weekly_asset_coverage(
        Path("hub"),
        changed_paths_by_repo={
            "mock-trial": [
                "scripts/process_new_case.py",
                "outputs/cases/private_case/reports/witness_packet.md",
            ]
        },
        generated_at=TIMESTAMP,
    )

    repo = result["repos"][0]
    assert repo["candidate_count"] == 1
    assert repo["missing_high_signal_count"] == 1
    assert repo["grade"] == "F"
    assert result["exception_candidates"][0]["candidate_exception_labels"] == [
        "asset_coverage_reporting_gap"
    ]
    assert result["exception_candidates"][0]["path_ref"] == "scripts/process_new_case.py"


def test_weekly_asset_coverage_marks_asset_covered_by_repo_outbox(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write_jsonl(
        repo / ".digital-asset" / "mail" / "outbox.jsonl",
        [
            {
                "mail_id": "dad:mail:simulator",
                "message_type": "lesson_suggestion",
                "created_at": TIMESTAMP,
                "asset_refs": ["simulation/run_layered_monte_carlo.py"],
            }
        ],
    )

    result = build_weekly_asset_coverage(
        tmp_path / "hub",
        changed_paths_by_repo={str(repo): ["simulation/run_layered_monte_carlo.py"]},
        generated_at=TIMESTAMP,
    )

    candidate = result["repos"][0]["candidates"][0]
    assert candidate["coverage_status"] == "covered"
    assert candidate["evidence_refs"] == ["mail_outbox:dad:mail:simulator"]
    assert result["summary"]["missing_high_signal_count"] == 0
    assert result["repos"][0]["grade"] == "A"


def test_weekly_asset_coverage_writer_reports_history_and_due_gate(tmp_path: Path):
    first = write_weekly_asset_coverage_outputs(
        tmp_path,
        changed_paths_by_repo={"repo-a": ["tests/test_intake_engine.py"]},
        generated_at=TIMESTAMP,
        force=True,
    )

    assert first["status"] == "ok"
    outputs = {key: Path(value) for key, value in first["outputs"].items()}
    assert outputs["report_json"].exists()
    assert outputs["report_markdown"].exists()
    assert outputs["snapshot"].exists()
    assert outputs["history"].exists()
    assert outputs["scan_cycle_events"].exists()

    report = json.loads(outputs["report_json"].read_text(encoding="utf-8"))
    assert report["summary"]["candidate_count"] == 1
    assert report["scan_cycle_event"]["pass_type"] == "weekly_asset_coverage"

    history = [
        json.loads(line)
        for line in outputs["history"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert history[0]["exception_candidate_count"] == 1

    second = write_weekly_asset_coverage_outputs(
        tmp_path,
        changed_paths_by_repo={"repo-a": ["tests/test_intake_engine.py"]},
        generated_at=TIMESTAMP,
    )
    assert second["status"] == "skipped"
    assert second["reason"] == "weekly_not_due"
    assert second["prior_findings_carried_forward"] is True
    assert second["summary"] == report["summary"]


def test_weekly_asset_coverage_ignores_disabled_and_unsafe_envelope_content(tmp_path: Path):
    enabled = tmp_path / "enabled"
    disabled = tmp_path / "disabled"
    enabled.mkdir()
    disabled.mkdir()
    write_jsonl(
        enabled / ".digital-asset" / "mail" / "outbox.jsonl",
        [
            {
                "mail_id": "dad:mail:unsafe-summary",
                "created_at": TIMESTAMP,
                "payload": {
                    "summary": "tests/test_private_case_engine.py includes private case facts"
                },
            }
        ],
    )
    policies = [
        SimpleNamespace(id="enabled", path=enabled, mail_enabled=True),
        SimpleNamespace(id="disabled", path=disabled, mail_enabled=False),
    ]

    result = build_weekly_asset_coverage(
        tmp_path / "hub",
        repo_policies=policies,
        changed_paths_by_repo={"enabled": ["tests/test_private_case_engine.py"]},
        generated_at=TIMESTAMP,
    )

    assert [repo["repo_key"] for repo in result["repos"]] == ["enabled"]
    assert result["repos"][0]["candidates"][0]["coverage_status"] == "missing"


def test_weekly_asset_coverage_real_git_policy_path(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "dad@example.test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "DAD Test"], check=True)
    test_path = repo / "tests" / "test_intake_engine.py"
    test_path.parent.mkdir()
    test_path.write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tests/test_intake_engine.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "Add intake engine test"], check=True)

    result = build_weekly_asset_coverage(
        tmp_path / "hub",
        repo_policies=[SimpleNamespace(id="repo-a", path=repo, mail_enabled=True)],
        generated_at=TIMESTAMP,
    )

    assert result["repo_count"] == 1
    assert result["repos"][0]["git_status"]["status"] == "ok"
    assert result["repos"][0]["candidate_count"] == 1


def test_weekly_asset_classifier_skips_private_outputs():
    assert classify_weekly_asset_path("outputs/cases/private/reports/witness_packet.md") is None
    assert classify_weekly_asset_path("source/raw/Exhibit_1.pdf") is None
    assert classify_weekly_asset_path("scripts/build_case_graphlite_kg.py")["categories"] == [
        "engine_or_workflow",
        "graph_or_kg",
    ]
