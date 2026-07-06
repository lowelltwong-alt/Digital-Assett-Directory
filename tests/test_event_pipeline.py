from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from digital_asset_directory.cli import app
from digital_asset_directory.event_pipeline import (
    build_event_record,
    collect_events,
    record_repo_event,
)

RUNNER = CliRunner()


def _make_hub(path: Path) -> Path:
    (path / "registry").mkdir(parents=True)
    (path / "registry" / "source-of-truth.json").write_text("{}", encoding="utf-8")
    (path / "src" / "digital_asset_directory").mkdir(parents=True)
    (path / "src" / "digital_asset_directory" / "cli.py").write_text("", encoding="utf-8")
    (path / "AI_FRONT_DOOR.md").write_text("# AI Front Door\n", encoding="utf-8")
    (path / "MACHINE_NAVIGATION_MANIFEST.json").write_text(
        '{"manifest_version":"test"}\n', encoding="utf-8"
    )
    (path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "digital-asset-directory"',
                'version = "0.1.0"',
                "[project.scripts]",
                'asset-dir = "digital_asset_directory.cli:app"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (path / "config").mkdir()
    (path / "config" / "sources.example.yaml").write_text(
        "project:\n  database: state/catalog.sqlite3\n", encoding="utf-8"
    )
    return path


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def _repo_files(repo: Path) -> set[str]:
    return {path.relative_to(repo).as_posix() for path in repo.rglob("*") if path.is_file()}


def test_event_collect_dedupes_and_writes_explicit_response_state(tmp_path: Path) -> None:
    hub = _make_hub(tmp_path / "hub")
    repo = tmp_path / "repo-a"
    repo.mkdir()

    record_repo_event(
        repo,
        build_event_record(
            event_type="asset_used",
            source_repo="repo-a",
            source_visibility="internal",
            dedupe_key="repo-a|asset-used|rust-scan-core",
            payload={"summary": "Used Rust scan core guidance"},
            evidence=["dad://hub/tools/dad_scan_core"],
        ),
    )
    record_repo_event(
        repo,
        build_event_record(
            event_type="pipeline_health",
            source_repo="dad",
            source_visibility="internal",
            target_repo="repo-a",
            target_visibility="internal",
            notice_id="notice-1",
            actionable=True,
            dedupe_key="dad|notice-1|repo-a",
            payload={"summary": "DAD notice for repo A"},
        ),
    )
    record_repo_event(
        repo,
        build_event_record(
            event_type="dad_notice_implemented",
            source_repo="repo-a",
            source_visibility="internal",
            target_repo="dad",
            target_visibility="internal",
            notice_id="notice-1",
            dedupe_key="repo-a|notice-1|implemented",
            payload={"summary": "Implemented DAD notice"},
        ),
    )

    before = _repo_files(repo)
    first = collect_events(hub, [repo])
    after = _repo_files(repo)
    second = collect_events(hub, [repo])

    assert before == after
    assert first["collected_count"] == 3
    assert first["response_state_count"] == 1
    assert second["collected_count"] == 0
    assert second["duplicate_count"] == 3
    rows = _jsonl(hub / "processed" / "events" / "event_log.jsonl")
    responses = _jsonl(hub / "processed" / "events" / "response_state.jsonl")
    assert len(rows) == 3
    assert responses[0]["notice_id"] == "notice-1"
    assert responses[0]["response_state"] == "implemented"
    assert all(row["review_status"] == "collected_candidate" for row in rows)


def test_event_collect_quarantines_malformed_and_unsafe_rows_but_keeps_good_rows(
    tmp_path: Path,
) -> None:
    hub = _make_hub(tmp_path / "hub")
    repo = tmp_path / "repo-a"
    repo.mkdir()
    outbox = repo / ".digital-asset" / "events" / "outbox.jsonl"
    outbox.parent.mkdir(parents=True)
    outbox.write_bytes(b"{not json}\n\xff\xfe\xfa\n")
    record_repo_event(
        repo,
        build_event_record(
            event_type="lesson_found",
            source_repo="repo-a",
            dedupe_key="repo-a|lesson|safe",
            source_visibility="internal",
            payload={"summary": "A safe metadata-only lesson"},
        ),
    )
    unsafe = build_event_record(
        event_type="harness_needed",
        source_repo="repo-a",
        dedupe_key="repo-a|harness|unsafe",
        source_visibility="internal",
        payload={"summary": "safe before mutation"},
    ).model_dump(mode="json")
    unsafe["payload"]["summary"] = "token=SECRET12345678901234567890"
    with outbox.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(unsafe, sort_keys=True) + "\n")
    unsafe_csv = build_event_record(
        event_type="harness_needed",
        source_repo="repo-a",
        dedupe_key="repo-a|harness|csv",
        source_visibility="internal",
        payload={"summary": "safe before mutation"},
    ).model_dump(mode="json")
    unsafe_csv["payload"]["summary"] = "a,b,c,d,e\n1,2,3,4,5"
    with outbox.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(unsafe_csv, sort_keys=True) + "\n")

    result = collect_events(hub, [repo])

    assert result["collected_count"] == 1
    assert result["quarantined_count"] == 4
    assert len(_jsonl(hub / "processed" / "events" / "event_log.jsonl")) == 1
    malformed = (hub / "processed" / "events" / "quarantine" / "malformed_event_rows.jsonl")
    invalid = (hub / "processed" / "events" / "quarantine" / "invalid_event_rows.jsonl")
    assert malformed.exists()
    assert invalid.exists()
    assert "SECRET12345678901234567890" not in invalid.read_text(encoding="utf-8")
    assert "a,b,c,d,e" not in invalid.read_text(encoding="utf-8")


def test_private_source_to_public_target_is_held_as_release_required(tmp_path: Path) -> None:
    hub = _make_hub(tmp_path / "hub")
    repo = tmp_path / "repo-a"
    repo.mkdir()
    record_repo_event(
        repo,
        build_event_record(
            event_type="governance_drift",
            source_repo="repo-a",
            source_visibility="private",
            target_repo="public-target",
            target_visibility="public",
            dedupe_key="repo-a|governance-drift|public-target",
            payload={"summary": "Pointer-safe governance drift metadata"},
        ),
    )

    collect_events(hub, [repo])

    row = _jsonl(hub / "processed" / "events" / "event_log.jsonl")[0]
    assert row["source_visibility"] == "unknown"
    assert row["public_release"]["public_release_required"] is True
    assert row["public_release"]["public_release_status"] == "pending_human"


def test_source_claimed_public_to_public_target_still_requires_release(
    tmp_path: Path,
) -> None:
    hub = _make_hub(tmp_path / "hub")
    repo = tmp_path / "repo-a"
    repo.mkdir()
    record_repo_event(
        repo,
        build_event_record(
            event_type="asset_used",
            source_repo="repo-a",
            source_visibility="public",
            target_repo="public-target",
            target_visibility="public",
            dedupe_key="repo-a|asset-used|public-claim",
            payload={"summary": "Source-authored public claim should not decide release"},
        ),
    )

    collect_events(hub, [repo])

    row = _jsonl(hub / "processed" / "events" / "event_log.jsonl")[0]
    assert row["source_visibility"] == "unknown"
    assert row["collection_provenance"]["source_claimed_visibility"] == "public"
    assert row["public_release"]["public_release_required"] is True
    assert row["public_release"]["public_release_status"] == "pending_human"


def test_notice_response_transitions_are_append_only(tmp_path: Path) -> None:
    hub = _make_hub(tmp_path / "hub")
    repo = tmp_path / "repo-a"
    repo.mkdir()
    for event_type, dedupe_key in [
        ("pipeline_health", "dad|notice-2|repo-a"),
        ("dad_notice_ack", "repo-a|notice-2|ack"),
        ("dad_notice_implemented", "repo-a|notice-2|implemented"),
    ]:
        if event_type == "pipeline_health":
            source_repo = "dad"
            target_repo = "repo-a"
            payload_summary = "DAD notice for repo A"
            response_state = "not_applicable"
        else:
            source_repo = "repo-a"
            target_repo = "dad"
            payload_summary = f"{event_type} response"
            response_state = "not_applicable"
        record_repo_event(
            repo,
            build_event_record(
                event_type=event_type,
                source_repo=source_repo,
                source_visibility="internal",
                target_repo=target_repo,
                target_visibility="internal",
                notice_id="notice-2",
                actionable=event_type == "pipeline_health",
                dedupe_key=dedupe_key,
                response_state=response_state,
                payload={"summary": payload_summary},
            ),
        )

    result = collect_events(hub, [repo])

    responses = _jsonl(hub / "processed" / "events" / "response_state.jsonl")
    assert result["response_state_count"] == 2
    assert [row["response_state"] for row in responses] == ["acknowledged", "implemented"]


def test_fake_notice_response_is_quarantined(tmp_path: Path) -> None:
    hub = _make_hub(tmp_path / "hub")
    repo = tmp_path / "repo-a"
    repo.mkdir()
    record_repo_event(
        repo,
        build_event_record(
            event_type="dad_notice_ack",
            source_repo="repo-a",
            source_visibility="internal",
            target_repo="dad",
            target_visibility="internal",
            notice_id="never-issued",
            dedupe_key="repo-a|never-issued|ack",
            payload={"summary": "Fake response should not create confidence"},
        ),
    )

    result = collect_events(hub, [repo])

    assert result["collected_count"] == 0
    assert result["quarantined_count"] == 1
    assert not (hub / "processed" / "events" / "response_state.jsonl").exists()


def test_event_report_flags_actionable_notice_without_response(tmp_path: Path) -> None:
    hub = _make_hub(tmp_path / "hub")
    repo = tmp_path / "repo-a"
    repo.mkdir()
    record_repo_event(
        repo,
        build_event_record(
            event_type="harness_needed",
            source_repo="repo-a",
            source_visibility="internal",
            notice_id="notice-3",
            actionable=True,
            dedupe_key="repo-a|notice-3|harness-needed",
            payload={"summary": "Needs a new harness"},
        ),
    )

    collect_events(hub, [repo])

    report = json.loads(
        (hub / "processed" / "events" / "reports" / "event_pipeline.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["notice_without_response_state_count"] == 1
    assert report["notice_without_response_state_ids"] == ["notice-3"]


def test_event_cli_record_collect_and_report(tmp_path: Path) -> None:
    hub = _make_hub(tmp_path / "hub")
    repo = tmp_path / "repo-a"
    repo.mkdir()

    record = RUNNER.invoke(
        app,
        [
            "events",
            "record",
            "--hub",
            str(hub),
            "--repo",
            str(repo),
            "--type",
            "pipeline_health",
            "--summary",
            "Repo can emit event records",
            "--dedupe-key",
            "repo-a|pipeline-health|1",
            "--source-visibility",
            "internal",
        ],
    )
    assert record.exit_code == 0, record.output
    before_collect = _repo_files(repo)

    collect = RUNNER.invoke(
        app,
        ["events", "collect", "--hub", str(hub), "--repo", str(repo)],
    )
    report = RUNNER.invoke(app, ["events", "report", "--hub", str(hub)])

    assert collect.exit_code == 0, collect.output
    assert report.exit_code == 0, report.output
    assert _repo_files(repo) == before_collect
    assert (hub / "processed" / "events" / "reports" / "event_pipeline.json").exists()
