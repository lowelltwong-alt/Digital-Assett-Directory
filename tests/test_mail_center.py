from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner

import digital_asset_directory.cli as cli_module
from digital_asset_directory.cli import (
    app,
    _discover_mail_repos,
    _mail_repo_candidates,
    _mailbox_coverage_summary,
)
from digital_asset_directory.config import MailRepoPolicy
from digital_asset_directory.mail_center import (
    central_inbox_path,
    collect_mail,
    compose_mail,
    deliver_mail,
    diagnose_mail_dirty_state,
    digest_mail,
    mail_digest_status,
    release_mail,
    review_central_mail,
    route_mail,
    review_mail,
    triage_mail,
)
from digital_asset_directory.rust_bridge import DadMailSpoolCheckResult
import digital_asset_directory.mail_center as mail_center

pytestmark = pytest.mark.integration
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


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "dad-test@example.invalid"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "DAD Test"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    (path / ".gitignore").write_text("processed/mail/staged/\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "baseline"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _repo_relative_files(repo: Path) -> set[str]:
    return {path.relative_to(repo).as_posix() for path in repo.rglob("*") if path.is_file()}


def _policy(
    repo: Path,
    repo_id: str,
    *,
    visibility: str = "internal",
    public_facing: bool = False,
    delivery_allowed: bool = True,
    write_protected: bool = False,
    write_protection_reason: str = "",
) -> MailRepoPolicy:
    return MailRepoPolicy(
        id=repo_id,
        path=repo,
        alias=repo_id,
        visibility=visibility,
        public_facing=public_facing,
        mail_enabled=True,
        delivery_allowed=delivery_allowed,
        write_protected=write_protected,
        write_protection_reason=write_protection_reason,
    )


def test_compose_redacts_secret_like_payload_and_rejects_restricted_mail(tmp_path: Path):
    repo = tmp_path / "repo-a"
    repo.mkdir()

    result = compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Share daily digest guidance.",
        payload={
            "note": (
                "api_key=super-secret-value AWS AKIAABCDEFGHIJKLMNOP JWT "
                "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.abcdefghijkl "
                "db postgres://user:pass@example.com/db email test@example.com "
                "phone 555-123-4567 ssn 123-45-6789 should never persist"
            )
        },
        evidence=["generated unit test"],
        suggested_actions=["Review locally before adopting."],
    )

    assert result["appended"] is True
    readme_text = (repo / ".digital-asset" / "mail" / "README.md").read_text(encoding="utf-8")
    assert "dad_cli_unavailable" in readme_text
    assert "$HOME/.dad/bin/asset-dir" in readme_text
    assert "$HOME\\.dad\\bin\\asset-dir.ps1" in readme_text
    assert "append pointer-safe JSONL to this repo's" in readme_text
    assert "outbox.jsonl" in readme_text
    assert "Do not include raw logs, secrets" in readme_text
    assert (repo / ".digital-asset" / "mail" / ".gitignore").read_text(
        encoding="utf-8"
    ) == "*.jsonl\nlast_checked.json\n"
    records = _jsonl(repo / ".digital-asset" / "mail" / "outbox.jsonl")
    assert len(records) == 1
    serialized = json.dumps(records[0])
    assert "super-secret-value" not in serialized
    assert "AKIAABCDEFGHIJKLMNOP" not in serialized
    assert "eyJhbGciOiJIUzI1NiJ9" not in serialized
    assert "postgres://user:pass@example.com/db" not in serialized
    assert "test@example.com" not in serialized
    assert "555-123-4567" not in serialized
    assert "123-45-6789" not in serialized
    assert records[0]["payload"]["redaction_count"] >= 7
    assert "Best-effort credential/PII screening" in records[0]["payload"]["redaction_note"]

    with pytest.raises(ValueError, match="confidential or restricted"):
        compose_mail(
            repo,
            message_type="lesson_suggestion",
            target_repo="central_only",
            summary="Rejected",
            sensitivity="restricted",
        )


def test_compose_warns_when_source_repo_is_not_in_reviewed_mail_policy(tmp_path: Path):
    repo = tmp_path / "seed-clean-clone"
    repo.mkdir()

    result = compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="A clone outbox should warn when DAD will not collect it by --repo all.",
        repo_policies=[],
    )

    assert result["source_policy_status"] == "unreviewed_source_repo"
    assert "will not collect it via --repo all" in result["collection_warning"]


def test_compose_reviewed_source_repo_has_no_collection_warning(tmp_path: Path):
    repo = tmp_path / "repo-a"
    repo.mkdir()

    result = compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="A reviewed source repo can be collected by policy.",
        repo_policies=[_policy(repo, "repo-a")],
    )

    assert result["source_policy_status"] == "reviewed_mail_repo"
    assert result["collection_warning"] == ""


def test_cli_mail_compose_payload_file_round_trips_structured_json_with_bom_and_equals(
    tmp_path: Path,
):
    hub = _make_hub(tmp_path / "dad")
    repo = tmp_path / "repo-a"
    repo.mkdir()
    payload_file = tmp_path / "lesson-pack.json"
    payload = {
        "lesson_pack_json": {
            "kernel_lessons": [
                {
                    "lesson_id": "lesson:fable-payload-file",
                    "fix": "preserve a=b inside structured JSON",
                }
            ],
            "flags": {"candidate_only": True},
        },
        "supersedes_reason": "corrected structured payload delivery path",
    }
    payload_file.write_bytes(
        b"\xef\xbb\xbf" + json.dumps(payload, sort_keys=True).encode("utf-8")
    )

    result = RUNNER.invoke(
        app,
        [
            "mail",
            "compose",
            "--hub",
            str(hub),
            "--repo",
            str(repo),
            "--type",
            "lesson_suggestion",
            "--summary",
            "Structured lesson pack delivery should not use key-value mode.",
            "--payload-file",
            str(payload_file),
            "--evidence",
            "synthetic Fable payload-file regression",
        ],
    )

    assert result.exit_code == 0, result.output
    rows = _jsonl(repo / ".digital-asset" / "mail" / "outbox.jsonl")
    assert rows[0]["payload"]["lesson_pack_json"]["kernel_lessons"][0]["fix"] == (
        "preserve a=b inside structured JSON"
    )
    assert rows[0]["payload"]["supersedes_reason"] == (
        "corrected structured payload delivery path"
    )


def test_cli_mail_compose_rejects_raw_json_in_key_value_payload_mode(tmp_path: Path):
    hub = _make_hub(tmp_path / "dad")
    repo = tmp_path / "repo-a"
    repo.mkdir()

    result = RUNNER.invoke(
        app,
        [
            "mail",
            "compose",
            "--hub",
            str(hub),
            "--repo",
            str(repo),
            "--type",
            "lesson_suggestion",
            "--summary",
            "Raw JSON in --payload should fail closed.",
            "--payload",
            '{"lesson_pack_json":{"fix":"a=b"}}',
        ],
    )

    assert result.exit_code == 2
    assert "--payload is key=value convenience mode only" in result.output
    assert not (repo / ".digital-asset" / "mail" / "outbox.jsonl").exists()


def test_cli_mail_compose_payload_json_path_round_trips_and_rejects_raw_json_payload(
    tmp_path: Path,
):
    hub = _make_hub(tmp_path / "hub")
    repo = tmp_path / "repo-a"
    repo.mkdir()
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(
        json.dumps(
            {
                "lesson_pack": {
                    "lessons": ["use payload-json for structured mail"],
                    "flags": {"candidate_only": True},
                },
                "applies_when": ["mail payload is already a JSON object"],
            }
        ),
        encoding="utf-8",
    )

    composed = RUNNER.invoke(
        app,
        [
            "mail",
            "compose",
            "--repo",
            str(repo),
            "--type",
            "lesson_suggestion",
            "--target-repo",
            "central_only",
            "--summary",
            "Share structured mail payload guidance.",
            "--payload-json",
            str(payload_path),
            "--hub",
            str(hub),
        ],
    )

    assert composed.exit_code == 0, composed.output
    record = json.loads(composed.output)["record"]
    assert record["payload"]["summary"] == "Share structured mail payload guidance."
    assert record["payload"]["lesson_pack"]["lessons"] == ["use payload-json for structured mail"]
    assert record["payload"]["lesson_pack"]["flags"]["candidate_only"] is True

    outbox_check = RUNNER.invoke(
        app,
        [
            "mail",
            "outbox-check",
            "--repo",
            str(repo),
            "--type",
            "lesson_suggestion",
            "--summary",
            "Share structured mail payload guidance.",
            "--payload-json",
            str(payload_path),
            "--hub",
            str(hub),
        ],
    )

    assert outbox_check.exit_code == 0, outbox_check.output
    assert json.loads(outbox_check.output)["sent_count"] == 1

    with pytest.raises(typer.BadParameter, match="key=value convenience mode"):
        cli_module._key_value_payload(['{"lesson_pack_json":{"lessons":["split risk"]}}'])

    json_value_payload = RUNNER.invoke(
        app,
        [
            "mail",
            "outbox-check",
            "--repo",
            str(repo),
            "--summary",
            "Key-value payloads may still carry JSON-looking values.",
            "--payload",
            'data={"x":1}',
            "--payload",
            "[legacy]=value",
            "--hub",
            str(hub),
        ],
    )

    assert json_value_payload.exit_code == 0, json_value_payload.output

    mixed_payload_modes = RUNNER.invoke(
        app,
        [
            "mail",
            "outbox-check",
            "--repo",
            str(repo),
            "--summary",
            "Mixed payload options should fail.",
            "--payload",
            "note=value",
            "--payload-json",
            str(payload_path),
            "--hub",
            str(hub),
        ],
    )

    assert mixed_payload_modes.exit_code == 2
    with pytest.raises(typer.BadParameter, match="Use only one payload source"):
        cli_module._mail_payload_options(["note=value"], payload_json=str(payload_path))

    list_payload_path = tmp_path / "payload-list.json"
    list_payload_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    non_object_payload_json = RUNNER.invoke(
        app,
        [
            "mail",
            "outbox-check",
            "--repo",
            str(repo),
            "--summary",
            "Non-object payload JSON should fail.",
            "--payload-json",
            str(list_payload_path),
            "--hub",
            str(hub),
        ],
    )

    assert non_object_payload_json.exit_code == 2
    with pytest.raises(typer.BadParameter, match="JSON object"):
        cli_module._parse_payload_json(
            cli_module._payload_json_text(str(list_payload_path)),
            option_name="--payload-json",
        )


def test_cli_mail_outbox_check_accepts_payload_file_for_structured_novelty(
    tmp_path: Path,
):
    hub = _make_hub(tmp_path / "dad")
    repo = tmp_path / "repo-a"
    repo.mkdir()
    payload_file = tmp_path / "lesson-pack.json"
    payload_file.write_text(
        json.dumps(
            {
                "lesson_pack_json": {
                    "lesson_id": "lesson:fable-outbox-check",
                    "fix": "check the same structured payload before compose",
                }
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    result = RUNNER.invoke(
        app,
        [
            "mail",
            "outbox-check",
            "--hub",
            str(hub),
            "--repo",
            str(repo),
            "--type",
            "lesson_suggestion",
            "--summary",
            "Structured novelty check should use the same payload file.",
            "--payload-file",
            str(payload_file),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["verdict"] == "new"

def test_bom_prefixed_jsonl_reads_and_reports_nonblocking_observation(tmp_path: Path):
    hub = _make_hub(tmp_path / "hub")
    repo = tmp_path / "repo-a"
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Share BOM-safe mailbox handling.",
    )
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    outbox.write_bytes(b"\xef\xbb\xbf" + outbox.read_bytes())

    novelty = mail_center.check_outbox_novelty(
        repo,
        message_type="lesson_suggestion",
        summary="Share BOM-safe mailbox handling.",
    )
    assert novelty["sent_count"] == 1

    report = diagnose_mail_dirty_state(hub, [repo])

    assert report["dirty"] is False
    assert report["summary"]["bom_jsonl_count"] == 1
    assert report["summary"]["embedded_bom_jsonl_count"] == 0
    observations = [
        item for item in report["observations"] if item["observation_type"] == "jsonl_utf8_bom"
    ]
    assert observations
    assert observations[0]["status"] == "report_only"
    assert observations[0]["line_numbers"] == [1]

    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Second row with embedded BOM.",
        allow_similar=True,
    )
    rows = outbox.read_bytes().splitlines()
    outbox.write_bytes(rows[0] + b"\n" + b"\xef\xbb\xbf" + rows[1] + b"\n")
    embedded_report = diagnose_mail_dirty_state(hub, [repo])

    assert embedded_report["dirty"] is False
    assert embedded_report["summary"]["bom_jsonl_count"] == 1
    assert embedded_report["summary"]["embedded_bom_jsonl_count"] == 1
    embedded_observation = next(
        item
        for item in embedded_report["observations"]
        if item["observation_type"] == "jsonl_utf8_bom"
    )
    assert embedded_observation["line_numbers"] == [1, 2]
    assert embedded_observation["embedded_bom_line_numbers"] == [2]


def test_agent_cli_success_paths_exit_zero(tmp_path: Path):
    hub = _make_hub(tmp_path / "hub")
    repo = tmp_path / "repo-a"
    repo.mkdir()

    preflight_result = RUNNER.invoke(
        app,
        [
            "agent",
            "preflight",
            "--repo",
            str(repo),
            "--agent",
            "codex",
            "--task",
            "rename a local variable",
            "--hub",
            str(hub),
        ],
    )

    assert preflight_result.exit_code == 0, preflight_result.output
    session_id = json.loads(preflight_result.output)["session_id"]

    midflight_result = RUNNER.invoke(
        app,
        [
            "agent",
            "midflight",
            "--session",
            session_id,
            "--context",
            "rename a local variable",
            "--hub",
            str(hub),
        ],
    )

    assert midflight_result.exit_code == 0, midflight_result.output
    assert json.loads(midflight_result.output)["status"] == "ok"

    postflight_result = RUNNER.invoke(
        app,
        [
            "agent",
            "postflight",
            "--session",
            session_id,
            "--repo",
            str(repo),
            "--summary",
            "done",
            "--hub",
            str(hub),
        ],
    )

    assert postflight_result.exit_code == 0, postflight_result.output


def test_collect_canonicalizes_source_identity_and_redaction(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Original summary",
    )
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    spoofed = _jsonl(outbox)[0]
    spoofed["source_repo"] = "C:/pretend/source"
    spoofed["mail_id"] = "dad:mail:spoofed"
    spoofed["dedupe_key"] = "spoofed-key"
    spoofed["payload"]["note"] = "token=very-secret-value"
    outbox.write_text(json.dumps(spoofed) + "\n", encoding="utf-8")

    result = collect_mail(hub, [repo])

    assert result["collected_count"] == 1
    central = _jsonl(central_inbox_path(hub, repo))
    assert central[0]["source_repo"].startswith("repo-path-sha256:")
    assert central[0]["source_provenance"]["canonical_source_repo"].startswith("repo-path-sha256:")
    assert central[0]["mail_id"] != "dad:mail:spoofed"
    assert central[0]["dedupe_key"] != "spoofed-key"
    central_text = json.dumps(central[0])
    assert "very-secret-value" not in central_text
    assert str(repo.resolve()).replace("\\", "/") not in central_text.replace("\\", "/")


def test_collect_sanitizes_local_paths_inside_mail_content(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    local_ref = "C:/Users/lowel/OneDrive/Desktop/Git Projects/private-repo/docs/review.md"
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Local path refs should be hashed before central storage.",
        payload={"note": f"See {local_ref}"},
        evidence=[local_ref],
        suggested_actions=[f"Review {local_ref} locally."],
    )

    result = collect_mail(hub, [repo])
    central = _jsonl(central_inbox_path(hub, repo))
    central_text = json.dumps(central, sort_keys=True).replace("\\", "/")

    assert result["collected_count"] == 1
    assert "C:/Users" not in central_text
    assert "OneDrive" not in central_text
    assert "Git Projects" not in central_text
    assert "repo-path-sha256:" in central_text


def test_collect_rejects_unstable_source_outbox_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="A concurrently written outbox should wait for the next collect pass.",
    )
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    original_signature = mail_center._jsonl_file_signature
    calls = 0

    def unstable_signature(path: Path):
        nonlocal calls
        if path == outbox:
            calls += 1
            return (100 + calls, 200 + calls)
        return original_signature(path)

    monkeypatch.setattr(mail_center, "_jsonl_file_signature", unstable_signature)

    result = collect_mail(hub, [repo])

    assert result["collected_count"] == 0
    assert result["error_count"] == 1
    assert result["errors"][0]["error_type"] == "source_outbox_unstable"
    assert "retry collection" in result["errors"][0]["recommendation"]
    assert not central_inbox_path(hub, repo).exists()


def test_collect_rechecks_source_outbox_before_central_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="A post-read append should block central promotion for this pass.",
    )
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    original_snapshot = mail_center._read_stable_jsonl_snapshot
    appended = False

    def append_after_snapshot(path: Path):
        nonlocal appended
        result = original_snapshot(path)
        if path == outbox and not appended:
            appended = True
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    json.dumps(
                        {
                            "message_id": "legacy-after-snapshot",
                            "message_type": "lesson_and_asset_candidate",
                            "summary": "Concurrent append after DAD read the source snapshot.",
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        return result

    monkeypatch.setattr(mail_center, "_read_stable_jsonl_snapshot", append_after_snapshot)

    result = collect_mail(hub, [repo])

    assert result["collected_count"] == 0
    assert result["error_count"] == 1
    assert result["errors"][0]["error_type"] == "source_outbox_unstable"
    assert "changed after snapshot" in result["errors"][0]["error"]
    assert not central_inbox_path(hub, repo).exists()


def test_collect_duplicate_retry_repairs_missing_collection_audit_for_stored_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Retry should repair collection audit for the row already written.",
    )
    original_audit = mail_center._append_collection_audit
    calls = 0

    def flaky_audit(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("simulated collection audit timeout")
        return original_audit(*args, **kwargs)

    monkeypatch.setattr(mail_center, "_append_collection_audit", flaky_audit)

    first = collect_mail(hub, [repo])
    second = collect_mail(hub, [repo])
    central_rows = _jsonl(central_inbox_path(hub, repo))
    audit_rows = _jsonl(hub / "processed" / "mail" / "archive" / "collection_log.jsonl")
    doctor = diagnose_mail_dirty_state(hub, [repo])

    assert first["collected_count"] == 1
    assert first["error_count"] == 1
    assert "simulated collection audit timeout" in first["errors"][0]["error"]
    assert second["duplicate_count"] == 1
    assert len(central_rows) == 1
    assert any(
        row["record_hash"] == mail_center._mail_record_hash(central_rows[0]) for row in audit_rows
    )
    assert doctor["summary"]["central_inbox_missing_collection_audit_count"] == 0
    assert doctor["dirty"] is False


def test_collect_accepts_metadata_only_legacy_fallback_outbox_packet(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "logos-scripture-graph-repo"
    hub.mkdir()
    repo.mkdir()
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    _append_jsonl(
        outbox,
        {
            "message_id": "msg-20260704-t423-scratch-delta-isolation-lesson",
            "direction": "outbound",
            "from_repo": "logos-scripture-graph",
            "to_hub": "dad://hub/Digital-Assett-Directory",
            "message_type": "lesson_and_asset_candidate",
            "trust_zone": "candidate",
            "timestamp": "2026-07-04T00:00:00Z",
            "subject": "T423 scratch-pad delta isolation pattern for hard corpus chunking",
            "summary": "Independent scratch passes become delta-isolation triage evidence.",
            "task_id": "T423",
            "context_map_entry": "ctx-t423-scratch-delta-isolation-pattern",
            "lesson_learned_slot": ".digital-asset/lessons/t423.yaml",
            "asset_candidates": ["asset-candidate:multi-model-scratch-delta-isolation"],
            "artifacts": ["scripts/compare_multi_model_bible_chunk_maps.py"],
            "non_authorizations": ["agreement_as_reviewed_gold"],
        },
    )
    policies = [_policy(repo, "logos-scripture-graph", visibility="public", public_facing=True)]

    result = collect_mail(hub, [repo], repo_policies=policies)
    duplicate = collect_mail(hub, [repo], repo_policies=policies)
    central = _jsonl(central_inbox_path(hub, repo, policies))

    assert result["collected_count"] == 1
    assert result["error_count"] == 0
    assert duplicate["duplicate_count"] == 1
    assert central[0]["message_type"] == "lesson_suggestion"
    assert central[0]["target_repo"] == "dad"
    assert central[0]["dedupe_key"].startswith("dad:mail-dedupe:")
    assert (
        central[0]["source_provenance"]["original_mail_id"]
        == "msg-20260704-t423-scratch-delta-isolation-lesson"
    )
    assert central[0]["source_provenance"]["canonical_source_repo"] == "repo:logos-scripture-graph"
    assert central[0]["source_provenance"]["source_visibility"] == "public"
    assert central[0]["payload"]["legacy_fallback_mail"] is True
    assert "agreement_as_reviewed_gold" in central[0]["payload"]["non_authorizations"]
    assert any(
        item.endswith("scripts/compare_multi_model_bible_chunk_maps.py")
        for item in central[0]["evidence"]
    )


def test_collect_dedupes_same_content_with_changed_packet_ids(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="asset_suggestion",
        target_repo="central_only",
        summary="Same content should dedupe.",
    )
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    duplicate = _jsonl(outbox)[0]
    duplicate["mail_id"] = "dad:mail:changed"
    duplicate["dedupe_key"] = "changed"
    _append_jsonl(outbox, duplicate)

    result = collect_mail(hub, [repo])

    assert result["collected_count"] == 1
    assert result["duplicate_count"] == 1


def test_collect_dedupes_same_original_mail_from_two_worktrees(tmp_path: Path):
    hub = tmp_path / "dad"
    worktree_a = tmp_path / "repo-worktree-a"
    worktree_b = tmp_path / "repo-worktree-b"
    hub.mkdir()
    worktree_a.mkdir()
    worktree_b.mkdir()
    compose_mail(
        worktree_a,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Copied branch worktrees should not fan out one logical mail item.",
        payload={"asset_id": "dad:asset:rust-storm-lesson"},
    )
    packet = _jsonl(worktree_a / ".digital-asset" / "mail" / "outbox.jsonl")[0]
    outbox_b = worktree_b / ".digital-asset" / "mail" / "outbox.jsonl"
    _append_jsonl(outbox_b, packet)

    result = collect_mail(hub, [worktree_a, worktree_b])
    central_rows = [
        row
        for path in (hub / "processed" / "mail" / "inbox").glob("*.jsonl")
        for row in _jsonl(path)
    ]
    audit_rows = _jsonl(hub / "processed" / "mail" / "archive" / "collection_log.jsonl")

    assert result["collected_count"] == 1
    assert result["duplicate_count"] == 1
    assert result["error_count"] == 0
    assert len(central_rows) == 1
    assert {row["event_type"] for row in audit_rows} == {"collected", "duplicate_seen"}


def test_doctor_reports_and_collect_quarantines_valid_json_invalid_mail_packet(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Good row should still collect while bad row is quarantined.",
    )
    invalid_row = {
        "mail_id": "dad:mail:invalid",
        "thread_id": "dad:thread:invalid",
        "message_type": "not_registered",
        "source_repo": "repo-a",
        "target_repo": "central_only",
        "created_at": "2026-07-05T00:00:00+00:00",
        "dedupe_key": "invalid",
        "payload": {"note": "metadata only"},
    }
    _append_jsonl(repo / ".digital-asset" / "mail" / "outbox.jsonl", invalid_row)

    doctor = diagnose_mail_dirty_state(hub, [repo])

    assert doctor["dirty"] is True
    assert doctor["summary"]["invalid_mail_packet_count"] == 1
    issue = next(item for item in doctor["issues"] if item["issue_type"] == "invalid_mail_packet")
    assert issue["mail_id"] == "dad:mail:invalid"
    assert issue["record_hash"].startswith("sha256:")
    assert not (hub / "processed" / "mail" / "quarantine" / "invalid_mail_packet.jsonl").exists()

    result = collect_mail(hub, [repo])
    central = _jsonl(central_inbox_path(hub, repo))
    quarantine = _jsonl(hub / "processed" / "mail" / "quarantine" / "invalid_mail_packet.jsonl")

    assert result["collected_count"] == 1
    assert result["error_count"] == 1
    assert result["errors"][0]["error_type"] == "invalid_mail_packet"
    assert len(central) == 1
    assert len(quarantine) == 1
    assert quarantine[0]["mail_id"] == "dad:mail:invalid"
    assert quarantine[0]["raw_payload_copied"] is False
    assert "payload" not in quarantine[0]

    after_quarantine = diagnose_mail_dirty_state(hub, [repo])

    assert after_quarantine["dirty"] is False
    assert after_quarantine["status"] == "clean_with_quarantine_observations"
    assert after_quarantine["summary"]["invalid_mail_packet_count"] == 0
    assert after_quarantine["summary"]["invalid_mail_packet_quarantine_count"] == 1
    assert any(
        item["observation_type"] == "invalid_source_outbox_packet_quarantined"
        for item in after_quarantine["observations"]
    )


def test_cli_mail_doctor_quarantines_invalid_source_outbox_rows_by_hash(
    tmp_path: Path,
):
    hub = _make_hub(tmp_path / "dad")
    repo = tmp_path / "repo-a"
    repo.mkdir()
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    invalid_row = {
        "mail_id": "dad:mail:invalid",
        "thread_id": "dad:thread:invalid",
        "message_type": "not_registered",
        "source_repo": "repo-a",
        "target_repo": "central_only",
        "created_at": "2026-07-05T00:00:00+00:00",
        "dedupe_key": "invalid",
        "payload": {"note": "metadata only"},
    }
    _append_jsonl(outbox, invalid_row)

    blocked = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--repo",
            str(repo),
            "--summary-only",
            "--fail-on-dirty",
            "--hub",
            str(hub),
        ],
    )
    missing_ack = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--repo",
            str(repo),
            "--summary-only",
            "--quarantine-invalid-packets",
            "--hub",
            str(hub),
        ],
    )
    quarantined = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--repo",
            str(repo),
            "--summary-only",
            "--fail-on-dirty",
            "--quarantine-invalid-packets",
            "--invalid-quarantine-ack",
            "reviewed invalid source-outbox row during mail storm",
            "--hub",
            str(hub),
        ],
    )

    assert blocked.exit_code == 1
    assert json.loads(blocked.output)["summary"]["invalid_mail_packet_count"] == 1
    assert missing_ack.exit_code == 2
    assert quarantined.exit_code == 0, quarantined.output
    payload = json.loads(quarantined.output)
    assert payload["status"] == "clean_with_quarantine_observations"
    assert payload["summary"]["invalid_mail_packet_count"] == 0
    assert payload["summary"]["invalid_mail_packet_quarantine_count"] == 1
    assert payload["invalid_quarantine_result"]["quarantined_count"] == 1
    quarantine_rows = _jsonl(
        hub / "processed" / "mail" / "quarantine" / "invalid_mail_packet.jsonl"
    )
    assert quarantine_rows[0]["raw_payload_copied"] is False
    assert "payload" not in quarantine_rows[0]

    invalid_row["payload"]["note"] = "changed after quarantine"
    outbox.write_text(json.dumps(invalid_row, sort_keys=True) + "\n", encoding="utf-8")
    changed = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--repo",
            str(repo),
            "--summary-only",
            "--fail-on-dirty",
            "--hub",
            str(hub),
        ],
    )

    assert changed.exit_code == 1
    assert json.loads(changed.output)["summary"]["invalid_mail_packet_count"] == 1


def test_collect_blocks_same_original_mail_from_different_reviewed_sources(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    compose_mail(
        repo_a,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Copied cross-repo packet identities should need provenance review.",
        payload={"asset_id": "dad:asset:rust-storm-lesson"},
    )
    packet = _jsonl(repo_a / ".digital-asset" / "mail" / "outbox.jsonl")[0]
    _append_jsonl(repo_b / ".digital-asset" / "mail" / "outbox.jsonl", packet)
    policies = [_policy(repo_a, "repo-a"), _policy(repo_b, "repo-b")]

    result = collect_mail(hub, [repo_a, repo_b], repo_policies=policies)
    central_rows = [
        row
        for path in (hub / "processed" / "mail" / "inbox").glob("*.jsonl")
        for row in _jsonl(path)
    ]

    assert result["collected_count"] == 1
    assert result["duplicate_count"] == 0
    assert result["error_count"] == 1
    assert result["errors"][0]["error_type"] == "cross_source_original_identity_conflict"
    assert result["errors"][0]["existing_source"] == "repo:repo-a"
    assert result["errors"][0]["incoming_source"] == "repo:repo-b"
    assert len(central_rows) == 1


def test_mail_doctor_blocks_cross_source_outbox_duplicate_identity(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    compose_mail(
        repo_a,
        message_type="asset_suggestion",
        target_repo="central_only",
        summary="Policy-known cross-source outbox duplicates should not look like retries.",
    )
    packet = _jsonl(repo_a / ".digital-asset" / "mail" / "outbox.jsonl")[0]
    _append_jsonl(repo_b / ".digital-asset" / "mail" / "outbox.jsonl", packet)
    policies = [_policy(repo_a, "repo-a"), _policy(repo_b, "repo-b")]

    result = diagnose_mail_dirty_state(hub, [repo_a, repo_b], repo_policies=policies)

    assert result["dirty"] is True
    assert result["status"] == "dirty_needs_review"
    assert result["action_summary"]["safe_to_collect"] is False
    assert result["summary"]["cross_source_outbox_duplicate_identity_count"] == 1
    assert "cross_source_outbox_duplicate_identity" in {
        item["issue_type"] for item in result["issues"]
    }


def test_mail_doctor_blocks_unknown_source_outbox_duplicate_identity(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    compose_mail(
        repo_a,
        message_type="asset_suggestion",
        target_repo="central_only",
        summary="Unreviewed duplicate outboxes need source classification.",
    )
    packet = _jsonl(repo_a / ".digital-asset" / "mail" / "outbox.jsonl")[0]
    _append_jsonl(repo_b / ".digital-asset" / "mail" / "outbox.jsonl", packet)

    result = diagnose_mail_dirty_state(hub, [repo_a, repo_b])

    assert result["dirty"] is True
    assert result["status"] == "dirty_needs_review"
    assert result["action_summary"]["safe_to_collect"] is False
    assert result["summary"]["unknown_source_outbox_duplicate_identity_count"] == 1
    assert "unknown_source_outbox_duplicate_identity" in {
        item["issue_type"] for item in result["issues"]
    }


def test_cli_mail_collect_allows_source_outbox_retry_duplicates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    repo = tmp_path / "repo-a"
    repo.mkdir()
    compose_mail(
        repo,
        message_type="asset_suggestion",
        target_repo="central_only",
        summary="Same source outbox row may be retried during a mail storm.",
    )
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    original = outbox.read_text(encoding="utf-8")
    outbox.write_text(original + original, encoding="utf-8")

    doctor = diagnose_mail_dirty_state(hub, [repo])
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(repo, "repo-a")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)
    result = RUNNER.invoke(app, ["mail", "collect", "--repo", str(repo), "--hub", str(hub)])

    assert doctor["dirty"] is False
    assert doctor["status"] == "clean_with_source_outbox_duplicates"
    assert doctor["summary"]["source_outbox_duplicate_identity_count"] == 1
    assert any(
        item["observation_type"] == "source_outbox_duplicate_identity"
        for item in doctor["observations"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["collected_count"] == 1
    assert payload["duplicate_count"] == 1

    after_collect = diagnose_mail_dirty_state(hub, [repo], repo_policies=cfg.mail_repos)
    assert after_collect["dirty"] is False
    assert after_collect["summary"]["unknown_source_outbox_duplicate_identity_count"] == 0
    assert after_collect["summary"]["source_outbox_duplicate_identity_count"] >= 1
    assert any(
        item["observation_type"]
        in {"source_outbox_duplicate_identity", "source_outbox_cross_file_duplicate_identity"}
        for item in after_collect["observations"]
    )


def test_collect_writes_collection_audit_for_central_inbox_rows(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Collection should leave a hash-backed audit row.",
    )

    result = collect_mail(hub, [repo])
    central = _jsonl(central_inbox_path(hub, repo))
    collection_log = _jsonl(hub / "processed" / "mail" / "archive" / "collection_log.jsonl")
    doctor = diagnose_mail_dirty_state(hub, [repo])

    assert result["collected_count"] == 1
    assert len(collection_log) == 1
    assert collection_log[0]["event_type"] == "collected"
    assert collection_log[0]["mail_id"] == central[0]["mail_id"]
    assert collection_log[0]["dedupe_key"] == central[0]["dedupe_key"]
    assert collection_log[0]["record_hash"] == mail_center._mail_record_hash(central[0])
    assert collection_log[0]["central_inbox"].startswith("processed/mail/inbox/")
    assert collection_log[0]["central_inbox"].endswith(".jsonl")
    assert doctor["summary"]["central_inbox_missing_collection_audit_count"] == 0
    assert doctor["dirty"] is False


def test_route_mail_requires_collection_audit_at_point_of_use(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="A wrong-box central inbox row must not be routable.",
    )
    packet = _jsonl(repo / ".digital-asset" / "mail" / "outbox.jsonl")[0]
    packet["review_status"] = "collected_candidate"
    packet["source_provenance"]["collected_at"] = "2026-07-05T01:00:00+00:00"
    central = hub / "processed" / "mail" / "inbox" / "repo-a.jsonl"
    central.parent.mkdir(parents=True)
    central.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    routed = route_mail(hub)

    assert routed["blocked"] is True
    assert routed["routed_count"] == 0
    assert routed["error_count"] == 1
    assert routed["errors"][0]["error_type"] == "missing_collection_audit"
    assert not (hub / "processed" / "mail" / "outbox" / "routed.jsonl").exists()
    assert not (hub / "processed" / "mail" / "archive" / "route_log.jsonl").exists()


def test_cli_mail_route_blocks_row_inserted_after_dirty_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    repo = tmp_path / "repo-a"
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Route must recheck rows that appear after the doctor gate.",
    )
    packet = _jsonl(repo / ".digital-asset" / "mail" / "outbox.jsonl")[0]
    packet["review_status"] = "collected_candidate"
    packet["source_provenance"]["collected_at"] = "2026-07-05T01:00:00+00:00"
    original_gate = cli_module._ensure_mail_clean_for_operation

    def inject_after_clean_gate(*args, **kwargs):
        result = original_gate(*args, **kwargs)
        central = hub / "processed" / "mail" / "inbox" / "repo-a.jsonl"
        central.parent.mkdir(parents=True, exist_ok=True)
        central.write_text(json.dumps(packet) + "\n", encoding="utf-8")
        return result

    monkeypatch.setattr(
        cli_module,
        "_ensure_mail_clean_for_operation",
        inject_after_clean_gate,
    )

    routed = RUNNER.invoke(app, ["mail", "route", "--hub", str(hub)])

    assert routed.exit_code == 2
    payload = json.loads(routed.output)
    assert payload["blocked"] is True
    assert payload["routed_count"] == 0
    assert payload["errors"][0]["error_type"] == "missing_collection_audit"
    assert not (hub / "processed" / "mail" / "outbox" / "routed.jsonl").exists()


def test_mail_doctor_flags_central_inbox_duplicate_logical_identity(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Central logical duplicates should be surfaced before routing.",
    )
    collect_mail(hub, [repo])
    central_path = central_inbox_path(hub, repo)
    original = _jsonl(central_path)[0]
    duplicate = dict(original)
    duplicate["mail_id"] = "dad:mail:logical-duplicate"
    duplicate["dedupe_key"] = "dad:dedupe:logical-duplicate"
    _append_jsonl(central_path, duplicate)

    doctor = diagnose_mail_dirty_state(hub, [repo])

    assert doctor["dirty"] is True
    assert doctor["summary"]["central_inbox_duplicate_logical_identity_count"] == 1
    assert "central_inbox_duplicate_logical_identity" in {
        item["issue_type"] for item in doctor["issues"]
    }


def test_collect_rejects_restricted_hand_written_outbox_packet(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    composed = compose_mail(
        repo,
        message_type="governance_notice",
        target_repo="central_only",
        summary="Rejected at collect.",
    )
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    packet = composed["record"]
    packet["sensitivity"] = "restricted"
    outbox.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    result = collect_mail(hub, [repo])

    assert result["collected_count"] == 0
    assert result["error_count"] == 1
    assert "confidential or restricted" in result["errors"][0]["error"]


def test_collect_route_deliver_dedupes_duplicate_deliveries(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()

    composed = compose_mail(
        repo_a,
        message_type="workflow_suggestion",
        target_repo=str(repo_b),
        summary="Repo B can use the mail digest workflow.",
        evidence=["repo-a/.digital-asset/mail/outbox.jsonl"],
        suggested_actions=["Run asset-dir mail digest once a day."],
    )

    collected = collect_mail(hub, [repo_a])
    routed = route_mail(hub)
    delivered = deliver_mail(hub, [repo_b])
    delivered_again = deliver_mail(hub, [repo_b])

    assert collected["collected_count"] == 1
    assert routed["routed_count"] == 1
    assert delivered["delivered_count"] == 1
    assert delivered_again["delivered_count"] == 0
    assert delivered_again["acknowledged_duplicate_count"] == 1
    inbox = _jsonl(repo_b / ".digital-asset" / "mail" / "inbox.jsonl")
    archive = _jsonl(repo_b / ".digital-asset" / "mail" / "archive.jsonl")
    assert [item["mail_id"] for item in inbox] == [composed["record"]["mail_id"]]
    assert [item["message_type"] for item in archive] == ["inbox_ack"]


def test_delivery_write_failure_records_central_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    compose_mail(
        repo_a,
        message_type="workflow_suggestion",
        target_repo=str(repo_b),
        summary="Repo B can use a DAD mailbox lesson.",
    )
    collect_mail(hub, [repo_a])
    route_mail(hub)
    original_append_unique = mail_center._append_unique

    def blocked_append_unique(path: Path, record):
        if path == repo_b / ".digital-asset" / "mail" / "inbox.jsonl":
            raise PermissionError("simulated sandbox denial")
        return original_append_unique(path, record)

    monkeypatch.setattr(mail_center, "_append_unique", blocked_append_unique)

    delivered = deliver_mail(hub, [repo_b])
    delivery_log = _jsonl(hub / "processed" / "mail" / "archive" / "delivery_log.jsonl")

    assert delivered["delivered_count"] == 0
    assert delivered["central_only_count"] == 1
    assert delivered["error_count"] == 0
    assert not (repo_b / ".digital-asset" / "mail" / "inbox.jsonl").exists()
    assert delivery_log[-1]["event_type"] == "central_only"
    assert "target repo inbox write failed" in delivery_log[-1]["reason"]


def test_delivery_log_binds_repo_inbox_row_hash(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    compose_mail(
        repo_a,
        message_type="workflow_suggestion",
        target_repo=str(repo_b),
        summary="Delivered rows should have hash-backed delivery evidence.",
    )

    collect_mail(hub, [repo_a])
    route_mail(hub)
    delivered = deliver_mail(hub, [repo_b])
    inbox_path = repo_b / ".digital-asset" / "mail" / "inbox.jsonl"
    inbox_rows = _jsonl(inbox_path)
    inbox_rows[0]["payload"]["summary"] = "Mutated after delivery."
    inbox_path.write_text(json.dumps(inbox_rows[0]) + "\n", encoding="utf-8")

    doctor = diagnose_mail_dirty_state(hub, [repo_b])
    delivery_log = _jsonl(hub / "processed" / "mail" / "archive" / "delivery_log.jsonl")

    assert delivered["delivered_count"] == 1
    assert delivery_log[0]["dedupe_key"] == inbox_rows[0]["dedupe_key"]
    assert delivery_log[0]["record_hash"].startswith("sha256:")
    assert doctor["dirty"] is True
    assert doctor["summary"]["repo_inbox_delivery_hash_mismatch_count"] == 1
    assert "repo_inbox_delivery_hash_mismatch" in {item["issue_type"] for item in doctor["issues"]}


def test_legacy_unhashed_delivery_log_does_not_verify_mutated_inbox_row(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    compose_mail(
        repo_a,
        message_type="workflow_suggestion",
        target_repo=str(repo_b),
        summary="Legacy delivery logs should not prove current inbox content.",
    )

    collect_mail(hub, [repo_a])
    route_mail(hub)
    deliver_mail(hub, [repo_b])
    inbox_path = repo_b / ".digital-asset" / "mail" / "inbox.jsonl"
    inbox_rows = _jsonl(inbox_path)
    inbox_rows[0]["dedupe_key"] = "dad:mail-dedupe:mutated"
    inbox_rows[0]["payload"]["summary"] = "Mutated after legacy delivery."
    inbox_path.write_text(json.dumps(inbox_rows[0]) + "\n", encoding="utf-8")
    legacy_log = hub / "processed" / "mail" / "archive" / "delivery_log.jsonl"
    legacy_log.write_text(
        json.dumps(
            {
                "event_type": "delivered",
                "mail_id": inbox_rows[0]["mail_id"],
                "target_repo": str(repo_b),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    doctor = diagnose_mail_dirty_state(hub, [repo_b])

    assert doctor["dirty"] is True
    assert doctor["summary"]["repo_inbox_without_delivery_log_count"] == 1
    assert doctor["summary"]["repo_inbox_legacy_delivery_log_count"] == 1
    assert "repo_inbox_without_delivery_log" in {item["issue_type"] for item in doctor["issues"]}
    assert any(
        item["observation_type"] == "repo_inbox_legacy_unhashed_delivery_log"
        for item in doctor["observations"]
    )


def test_cli_mail_doctor_can_allowlist_reviewed_legacy_repo_inbox_rows_hash_bound(
    tmp_path: Path,
):
    hub = _make_hub(tmp_path / "dad")
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    compose_mail(
        repo_a,
        message_type="workflow_suggestion",
        target_repo=str(repo_b),
        summary="Legacy repo inbox rows need explicit hash-bound review.",
    )

    collect_mail(hub, [repo_a])
    route_mail(hub)
    deliver_mail(hub, [repo_b])
    inbox_path = repo_b / ".digital-asset" / "mail" / "inbox.jsonl"
    inbox_rows = _jsonl(inbox_path)
    legacy_log = hub / "processed" / "mail" / "archive" / "delivery_log.jsonl"
    legacy_log.write_text(
        json.dumps(
            {
                "event_type": "delivered",
                "mail_id": inbox_rows[0]["mail_id"],
                "target_repo": str(repo_b),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    blocked = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--repo",
            str(repo_b),
            "--summary-only",
            "--fail-on-dirty",
            "--hub",
            str(hub),
        ],
    )
    repaired = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--repo",
            str(repo_b),
            "--summary-only",
            "--fail-on-dirty",
            "--allowlist-legacy-repo-inbox",
            "--legacy-allowlist-ack",
            "reviewed pre-enforcement repo inbox delivery row",
            "--hub",
            str(hub),
        ],
    )

    assert blocked.exit_code == 1
    assert repaired.exit_code == 0
    payload = json.loads(repaired.output)
    assert payload["status"] == "clean_with_legacy_observations"
    assert payload["action_summary"]["legacy_observation_count"] == 1
    assert payload["summary"]["repo_inbox_legacy_delivery_allowlist_count"] == 1
    assert payload["legacy_delivery_allowlist_result"]["allowlisted_count"] == 1
    assert (hub / "processed" / "mail" / "archive" / "legacy_delivery_allowlist.jsonl").exists()

    inbox_rows[0]["payload"]["summary"] = "Mutated after legacy allowlist."
    inbox_path.write_text(json.dumps(inbox_rows[0]) + "\n", encoding="utf-8")
    doctor_after_mutation = diagnose_mail_dirty_state(hub, [repo_b])

    assert doctor_after_mutation["dirty"] is True
    assert doctor_after_mutation["summary"]["repo_inbox_without_delivery_log_count"] == 1


def test_legacy_repo_inbox_allowlist_does_not_clear_wrong_target_row(
    tmp_path: Path,
):
    hub = _make_hub(tmp_path / "dad")
    source = tmp_path / "source"
    correct_target = tmp_path / "correct-target"
    wrong_target = tmp_path / "wrong-target"
    source.mkdir()
    correct_target.mkdir()
    wrong_target.mkdir()
    packet = compose_mail(
        source,
        message_type="workflow_suggestion",
        target_repo=str(correct_target),
        summary="A legacy allowlist must stay target-bound.",
    )["record"]
    inbox = wrong_target / ".digital-asset" / "mail" / "inbox.jsonl"
    inbox.parent.mkdir(parents=True)
    inbox.write_text(
        json.dumps({**packet, "review_status": "delivered_candidate"}) + "\n",
        encoding="utf-8",
    )
    delivery_log = hub / "processed" / "mail" / "archive" / "delivery_log.jsonl"
    delivery_log.parent.mkdir(parents=True)
    delivery_log.write_text(
        json.dumps(
            {
                "event_type": "delivered",
                "mail_id": packet["mail_id"],
                "target_repo": str(correct_target),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    attempted = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--repo",
            str(wrong_target),
            "--summary-only",
            "--fail-on-dirty",
            "--allowlist-legacy-repo-inbox",
            "--legacy-allowlist-ack",
            "attempted wrong-target legacy repair",
            "--hub",
            str(hub),
        ],
    )

    assert attempted.exit_code == 1
    payload = json.loads(attempted.output)
    assert payload["dirty"] is True
    assert payload["legacy_delivery_allowlist_result"]["allowlisted_count"] == 0
    assert payload["legacy_delivery_allowlist_result"]["skipped_non_legacy_count"] == 1
    assert payload["summary"]["repo_inbox_without_delivery_log_count"] == 1


def test_central_only_delivery_log_does_not_verify_dad_repo_inbox_row(tmp_path: Path):
    hub = _make_hub(tmp_path / "dad")
    source = tmp_path / "source"
    source.mkdir()
    packet = compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Central-only logs are not DAD repo-local inbox delivery proof.",
    )["record"]
    inbox = hub / ".digital-asset" / "mail" / "inbox.jsonl"
    inbox.parent.mkdir(parents=True)
    inbox.write_text(
        json.dumps({**packet, "review_status": "delivered_candidate"}) + "\n",
        encoding="utf-8",
    )
    delivery_log = hub / "processed" / "mail" / "archive" / "delivery_log.jsonl"
    delivery_log.parent.mkdir(parents=True)
    delivery_log.write_text(
        json.dumps(
            {
                "event_type": "delivered",
                "mail_id": packet["mail_id"],
                "target_repo": "central_only",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = diagnose_mail_dirty_state(hub, [hub])

    assert result["dirty"] is True
    assert result["summary"]["repo_inbox_without_delivery_log_count"] == 1
    issue = next(
        item for item in result["issues"] if item["issue_type"] == "repo_inbox_without_delivery_log"
    )
    assert issue["expected_target_repo"] != "central_only"


def test_legacy_unhashed_delivery_log_does_not_suppress_empty_inbox_delivery(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    composed = compose_mail(
        repo_a,
        message_type="workflow_suggestion",
        target_repo=str(repo_b),
        summary="Legacy delivery logs should not suppress real inbox writes.",
    )
    legacy_log = hub / "processed" / "mail" / "archive" / "delivery_log.jsonl"
    legacy_log.parent.mkdir(parents=True)
    legacy_log.write_text(
        json.dumps(
            {
                "event_type": "delivered",
                "mail_id": composed["record"]["mail_id"],
                "target_repo": str(repo_b),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    collect_mail(hub, [repo_a])
    route_mail(hub)
    delivered = deliver_mail(hub, [repo_b])

    assert delivered["delivered_count"] == 1
    assert delivered["acknowledged_duplicate_count"] == 0
    inbox_rows = _jsonl(repo_b / ".digital-asset" / "mail" / "inbox.jsonl")
    archive_rows = _jsonl(repo_b / ".digital-asset" / "mail" / "archive.jsonl")
    delivery_rows = _jsonl(legacy_log)
    assert [row["mail_id"] for row in inbox_rows] == [composed["record"]["mail_id"]]
    assert not archive_rows
    assert any(row.get("record_hash") for row in delivery_rows if row["event_type"] == "delivered")


def test_direct_central_outbox_write_blocks_doctor_and_delivery(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    target = tmp_path / "target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    packet = compose_mail(
        source,
        message_type="capability_suggestion",
        target_repo=str(target),
        summary="Rust feedback written directly to central outbox should not deliver.",
    )["record"]
    routed = hub / "processed" / "mail" / "outbox" / "routed.jsonl"
    routed.parent.mkdir(parents=True)
    routed.write_text(
        json.dumps({**packet, "review_status": "routed_candidate"}) + "\n",
        encoding="utf-8",
    )

    doctor = diagnose_mail_dirty_state(hub, [target])
    delivered = deliver_mail(hub, [target])

    assert doctor["dirty"] is True
    assert doctor["summary"]["central_outbox_missing_route_audit_count"] == 1
    assert "central_outbox_missing_route_audit" in {item["issue_type"] for item in doctor["issues"]}
    assert delivered["blocked"] is True
    assert delivered["route_block_count"] == 1
    assert delivered["delivered_count"] == 0
    assert not (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()


def test_route_log_binds_central_outbox_row_hash(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    target = tmp_path / "target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    compose_mail(
        source,
        message_type="capability_suggestion",
        target_repo=str(target),
        summary="Mutating a routed row should invalidate route evidence.",
    )

    collect_mail(hub, [source])
    routed = route_mail(hub)
    routed_path = hub / "processed" / "mail" / "outbox" / "routed.jsonl"
    rows = _jsonl(routed_path)
    rows[0]["payload"]["summary"] = "Mutated after route."
    routed_path.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")

    doctor = diagnose_mail_dirty_state(hub, [target])
    delivered = deliver_mail(hub, [target])
    route_log = _jsonl(hub / "processed" / "mail" / "archive" / "route_log.jsonl")

    assert routed["routed_count"] == 1
    assert route_log[0]["event_type"] == "routed"
    assert route_log[0]["routed_record_hash"].startswith("sha256:")
    assert doctor["dirty"] is True
    assert doctor["summary"]["central_outbox_route_hash_mismatch_count"] == 1
    assert "central_outbox_route_hash_mismatch" in {item["issue_type"] for item in doctor["issues"]}
    assert delivered["blocked"] is True
    assert delivered["delivered_count"] == 0


def test_route_log_requires_source_central_inbox_hash(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    target = tmp_path / "target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    compose_mail(
        source,
        message_type="capability_suggestion",
        target_repo=str(target),
        summary="Routed rows should retain source central inbox lineage.",
    )

    collect_mail(hub, [source])
    route_mail(hub)
    for path in (hub / "processed" / "mail" / "inbox").glob("*.jsonl"):
        path.unlink()

    doctor = diagnose_mail_dirty_state(hub, [target])
    delivered = deliver_mail(hub, [target])

    assert doctor["dirty"] is True
    assert doctor["summary"]["central_outbox_missing_source_inbox_count"] == 1
    assert "central_outbox_missing_source_inbox" in {
        item["issue_type"] for item in doctor["issues"]
    }
    assert delivered["blocked"] is True
    assert delivered["route_block_count"] == 1
    assert delivered["delivered_count"] == 0


def test_cli_mail_doctor_can_repair_legacy_route_audit_gap(tmp_path: Path):
    hub = _make_hub(tmp_path / "dad")
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    compose_mail(
        source,
        message_type="capability_suggestion",
        target_repo=str(target),
        summary="Pre-enforcement routed rows can receive exact route audit repair.",
    )
    collect_mail(hub, [source])
    route_mail(hub)
    route_log = hub / "processed" / "mail" / "archive" / "route_log.jsonl"
    route_log.unlink()
    routed_path = hub / "processed" / "mail" / "outbox" / "routed.jsonl"
    routed_rows = _jsonl(routed_path)
    routed_rows[0]["public_release"]["target_visibility"] = "unknown"
    routed_path.write_text(json.dumps(routed_rows[0], sort_keys=True) + "\n", encoding="utf-8")

    blocked = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--repo",
            str(source),
            "--summary-only",
            "--fail-on-dirty",
            "--hub",
            str(hub),
        ],
    )
    repaired = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--repo",
            str(source),
            "--summary-only",
            "--fail-on-dirty",
            "--repair-route-audit",
            "--route-audit-repair-ack",
            "reviewed pre-enforcement routed row lineage",
            "--hub",
            str(hub),
        ],
    )

    assert blocked.exit_code == 1
    blocked_payload = json.loads(blocked.output)
    assert blocked_payload["summary"]["central_outbox_missing_route_audit_count"] == 1
    assert repaired.exit_code == 0
    repaired_payload = json.loads(repaired.output)
    assert repaired_payload["dirty"] is False
    assert repaired_payload["route_audit_repair_result"]["repaired_count"] == 1
    rows = _jsonl(route_log)
    assert rows[0]["event_type"] == "legacy_route_audit_repaired"
    assert "pre-enforcement" in rows[0]["operator_ack"]


def test_phase10_two_repo_mail_trial_covers_message_types_digest_and_dedupe(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    policies = [
        _policy(repo_a, "repo-a", visibility="internal"),
        _policy(repo_b, "repo-b", visibility="internal"),
    ]
    packet_specs = [
        (
            "lesson_suggestion",
            "Lesson mail should move from repo A to repo B as candidate evidence.",
        ),
        (
            "asset_suggestion",
            "Asset mail should preserve source refs and local review boundaries.",
        ),
        (
            "workflow_suggestion",
            "Workflow mail should arrive without mutating source files.",
        ),
        (
            "governance_notice",
            "Governance mail should stay mailbox-only until reviewed locally.",
        ),
        (
            "capability_suggestion",
            "Exception-adjacent capability mail should be metadata-only.",
        ),
    ]
    for message_type, summary in packet_specs:
        compose_mail(
            repo_a,
            message_type=message_type,
            target_repo=str(repo_b),
            summary=summary,
            payload={
                "summary": summary,
                "source_asset_refs": [f"dad://phase10/{message_type}"],
                "update_channel": "dad://mail/phase10-synthetic-trial",
            },
            evidence=[f"synthetic-phase10:{message_type}"],
            suggested_actions=["Digest, triage, and decide locally before adopting."],
            repo_policies=policies,
        )

    collected = collect_mail(hub, [repo_a], repo_policies=policies)
    routed = route_mail(hub, repo_policies=policies)
    delivered = deliver_mail(hub, [repo_b], repo_policies=policies)
    delivered_again = deliver_mail(hub, [repo_b], repo_policies=policies)
    digest = digest_mail(repo_b, checked_at="2026-07-05T04:00:00+00:00")

    assert collected["collected_count"] == len(packet_specs)
    assert collected["duplicate_count"] == 0
    assert routed["routed_count"] == len(packet_specs)
    assert delivered["delivered_count"] == len(packet_specs)
    assert delivered["central_only_count"] == 0
    assert delivered_again["delivered_count"] == 0
    assert delivered_again["acknowledged_duplicate_count"] == len(packet_specs)
    assert digest["inbox_count"] == len(packet_specs)
    assert digest["unread_count"] == len(packet_specs)

    central_rows = _jsonl(hub / "processed" / "mail" / "inbox" / "repo-a.jsonl")
    inbox_rows = _jsonl(repo_b / ".digital-asset" / "mail" / "inbox.jsonl")
    delivery_log = _jsonl(hub / "processed" / "mail" / "archive" / "delivery_log.jsonl")
    archive_rows = _jsonl(repo_b / ".digital-asset" / "mail" / "archive.jsonl")
    assert {row["message_type"] for row in central_rows} == {spec[0] for spec in packet_specs}
    assert {row["message_type"] for row in inbox_rows} == {spec[0] for spec in packet_specs}
    assert all(
        row["source_provenance"]["return_address"].endswith(".digital-asset/mail/inbox.jsonl")
        for row in central_rows
    )
    assert sum(1 for row in delivery_log if row["event_type"] == "delivered") == len(packet_specs)
    assert sum(1 for row in delivery_log if row["event_type"] == "duplicate_ack") == len(
        packet_specs
    )
    assert sum(1 for row in archive_rows if row["message_type"] == "inbox_ack") == len(packet_specs)
    assert not (repo_b / "AGENTS.md").exists()


def test_phase10_agent_triage_does_not_release_unknown_origin_to_public_target(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    source = tmp_path / "unreviewed-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [_policy(target, "public-target", visibility="public", public_facing=True)]

    composed = compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo=str(target),
        summary="Unknown-origin mail must not reach a public-facing repo by agent triage.",
        payload={
            "summary": "Metadata-only public release gate synthetic case.",
            "source_ref": "dad://phase10/public-release-gate",
        },
        evidence=["synthetic-phase10:unknown-origin-public-target"],
        suggested_actions=["Hold centrally until a human release is recorded."],
        repo_policies=policies,
    )

    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    central_rows = _jsonl(next((hub / "processed" / "mail" / "inbox").glob("*.jsonl")))
    canonical_mail_id = central_rows[0]["mail_id"]
    assert central_rows[0]["source_provenance"]["source_visibility"] == "unknown"
    assert central_rows[0]["public_release"]["public_release_required"] is True

    held = deliver_mail(hub, [target], repo_policies=policies)
    central_review = review_central_mail(
        hub,
        mail_id=composed["record"]["mail_id"],
        decision="accept",
        decided_by="codex",
        human_verified=False,
        notes="Agent triage only; not a public release.",
        repo_policies=policies,
    )
    still_held = deliver_mail(hub, [target], repo_policies=policies)

    assert held["delivered_count"] == 0
    assert held["held_for_release_count"] == 1
    assert central_review["decision"]["review_status"] == "agent_triage"
    assert central_review["decision"]["public_release_gate_satisfied"] is False
    assert still_held["delivered_count"] == 0
    assert still_held["held_for_release_count"] == 1
    assert not (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()

    release = release_mail(
        hub,
        mail_id=canonical_mail_id,
        decision="approve",
        human_reviewed_by="Lowell",
        notes="Synthetic approval after provenance and public-safe payload review.",
        repo_policies=policies,
    )
    approved = deliver_mail(hub, [target], repo_policies=policies)
    inbox = _jsonl(target / ".digital-asset" / "mail" / "inbox.jsonl")

    assert release["release"]["decision"] == "approve"
    assert approved["delivered_count"] == 1
    assert inbox[0]["public_release"]["public_release_status"] == "approved"
    assert inbox[0]["public_release"]["human_release_id"] == release["release"]["release_id"]


def test_phase10_cli_reviewed_policy_path_delivers_only_mailbox_files(
    tmp_path: Path,
):
    hub = _make_hub(tmp_path / "dad")
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    (hub / "config" / "sources.example.yaml").write_text(
        "\n".join(
            [
                "project:",
                "  database: state/catalog.sqlite3",
                "mail:",
                "  repos:",
                "    - id: repo-a",
                f"      path: {repo_a.as_posix()}",
                "      alias: repo-a",
                "      visibility: internal",
                "      mail_enabled: true",
                "      delivery_allowed: true",
                "    - id: repo-b",
                f"      path: {repo_b.as_posix()}",
                "      alias: repo-b",
                "      visibility: internal",
                "      mail_enabled: true",
                "      delivery_allowed: true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    compose_mail(
        repo_a,
        message_type="governance_notice",
        target_repo=str(repo_b),
        summary="CLI policy path should deliver only mailbox files.",
        payload={
            "summary": "Synthetic Phase 10 CLI delivery proof.",
            "source_ref": "dad://phase10/cli-policy-path",
        },
        evidence=["synthetic-phase10:cli-reviewed-policy"],
        suggested_actions=["Digest and decide locally."],
    )
    before = _repo_relative_files(repo_b)

    collected = RUNNER.invoke(app, ["mail", "collect", "--repo", "all", "--hub", str(hub)])
    routed = RUNNER.invoke(app, ["mail", "route", "--hub", str(hub)])
    delivered = RUNNER.invoke(app, ["mail", "deliver", "--repo", "all", "--hub", str(hub)])

    assert collected.exit_code == 0, collected.output
    assert routed.exit_code == 0, routed.output
    assert delivered.exit_code == 0, delivered.output
    assert json.loads(collected.output)["collected_count"] == 1
    assert json.loads(routed.output)["routed_count"] == 1
    assert json.loads(delivered.output)["delivered_count"] == 1
    after = _repo_relative_files(repo_b)
    changed = after - before
    assert changed
    assert all(path.startswith(".digital-asset/mail/") for path in changed)
    assert ".digital-asset/mail/inbox.jsonl" in changed


@pytest.mark.parametrize("source_visibility", ["internal", "restricted"])
def test_phase10_non_public_visibility_to_public_target_requires_human_release(
    tmp_path: Path,
    source_visibility: str,
):
    hub = tmp_path / "dad"
    source = tmp_path / f"{source_visibility}-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, f"{source_visibility}-source", visibility=source_visibility),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]
    compose_mail(
        source,
        message_type="capability_suggestion",
        target_repo=str(target),
        summary=f"{source_visibility} source should require release to public target.",
        payload={
            "summary": "Metadata-only non-public visibility matrix case.",
            "source_ref": f"dad://phase10/{source_visibility}-to-public",
        },
        repo_policies=policies,
    )

    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    held = deliver_mail(hub, [target], repo_policies=policies)
    central = _jsonl(next((hub / "processed" / "mail" / "inbox").glob("*.jsonl")))[0]
    release_mail(
        hub,
        mail_id=central["mail_id"],
        decision="approve",
        human_reviewed_by="Lowell",
        notes="Synthetic approval after checking public-safe metadata.",
        repo_policies=policies,
    )
    approved = deliver_mail(hub, [target], repo_policies=policies)

    assert held["delivered_count"] == 0
    assert held["held_for_release_count"] == 1
    assert approved["delivered_count"] == 1
    inbox = _jsonl(target / ".digital-asset" / "mail" / "inbox.jsonl")
    assert inbox[0]["source_provenance"]["source_visibility"] == source_visibility


def test_deliver_requires_explicit_repo_allowlist(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    allowed_repo = tmp_path / "repo-allowed"
    outside_repo = tmp_path / "outside-existing-repo"
    hub.mkdir()
    repo_a.mkdir()
    allowed_repo.mkdir()
    outside_repo.mkdir()

    compose_mail(
        repo_a,
        message_type="workflow_suggestion",
        target_repo=str(outside_repo),
        summary="Should not be delivered without allowlist membership.",
    )
    collect_mail(hub, [repo_a])
    route_mail(hub)
    delivered = deliver_mail(hub, [allowed_repo])

    assert delivered["delivered_count"] == 0
    assert delivered["skipped"][0]["reason"] == "target repo is not in the allowed delivery list"
    assert not (outside_repo / ".digital-asset").exists()


def test_central_only_delivery_is_not_treated_as_filesystem_path(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()

    compose_mail(
        repo_a,
        message_type="taxonomy_suggestion",
        target_repo="central_only",
        summary="Candidate taxonomy note stays in the hub.",
    )

    collect_mail(hub, [repo_a])
    route_mail(hub)
    delivered = deliver_mail(hub, [repo_b])

    assert delivered["central_only_count"] == 1
    assert delivered["delivered_count"] == 0
    assert delivered["skipped"] == []
    assert not (tmp_path / "central_only").exists()


def test_malformed_central_outbox_quarantines_bad_row_and_continues(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    compose_mail(
        repo_a,
        message_type="workflow_suggestion",
        target_repo=str(repo_b),
        summary="Good row should still deliver.",
    )
    collect_mail(hub, [repo_a])
    route_mail(hub)
    outbox = hub / "processed" / "mail" / "outbox" / "routed.jsonl"
    with outbox.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("{not-json\n")

    delivered = deliver_mail(hub, [repo_b])

    assert delivered["blocked"] is False
    assert delivered["error_count"] == 1
    assert delivered["delivered_count"] == 1
    quarantine = _jsonl(hub / "processed" / "mail" / "quarantine" / "malformed_jsonl.jsonl")
    assert quarantine[0]["event_type"] == "malformed_jsonl"


def test_review_archive_digest_and_daily_freshness(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()

    composed = compose_mail(
        repo_a,
        message_type="capability_suggestion",
        target_repo=str(repo_b),
        summary="Add capability-matrix guidance to the repo front door.",
    )
    collect_mail(hub, [repo_a])
    route_mail(hub)
    deliver_mail(hub, [repo_b])

    decision = review_mail(
        repo_b,
        mail_id=composed["record"]["mail_id"],
        decision="reject",
        decided_by="unit-test",
        human_verified=True,
        notes="Not useful for this repo yet.",
    )
    digest = digest_mail(repo_b, checked_at="2026-06-30T10:00:00+00:00")
    fresh = mail_digest_status(repo_b, now="2026-06-30T11:00:00+00:00")
    stale = mail_digest_status(repo_b, now="2026-07-01T12:00:00+00:00")

    assert decision["appended"] is True
    assert digest["inbox_count"] == 1
    assert digest["unread_count"] == 0
    assert fresh["status"] == "fresh"
    assert fresh["stale"] is False
    assert stale["status"] == "stale"
    assert stale["stale"] is True


def test_central_review_handles_collected_mail_without_local_delivery(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "mock-trial"
    hub.mkdir()
    source.mkdir()
    composed = compose_mail(
        source,
        message_type="governance_notice",
        target_repo=str(hub),
        summary="Artifact registration drift should be triaged centrally by DAD.",
        payload={"safe_summary": "metadata-only registration drift"},
        evidence=["docs/artifact-registration-drift.md"],
        suggested_actions=["Review as candidate exception-lake signal."],
        allow_similar=True,
    )

    collected = collect_mail(hub, [source])
    central = _jsonl(central_inbox_path(hub, source))
    central_mail_id = central[0]["mail_id"]
    with pytest.raises(ValueError, match="No inbox mail found"):
        review_mail(hub, mail_id=central_mail_id, decision="accept")

    result = review_central_mail(
        hub,
        mail_id=composed["record"]["mail_id"],
        decision="accept",
        decided_by="codex",
        notes="DAD central triage only.",
    )

    assert collected["collected_count"] == 1
    assert result["appended"] is True
    assert result["decision"]["mail_id"] == central_mail_id
    assert result["decision"]["requested_mail_id"] == composed["record"]["mail_id"]
    assert result["decision"]["repository"] == "dad://central-mail"
    assert result["decision"]["review_status"] == "agent_triage"
    assert result["decision"]["public_release_gate_satisfied"] is False
    assert result["decision"]["target_repo_adoption_satisfied"] is False
    assert result["archive"] == "processed/mail/archive/central_review_decisions.jsonl"
    assert _jsonl(hub / result["archive"])[0]["decision_id"] == result["decision"]["decision_id"]
    archive_text = (hub / result["archive"]).read_text(encoding="utf-8")
    for fragment in [str(source), str(hub), "C:/Users", "C:\\Users", "OneDrive", "AppData"]:
        assert fragment.replace("\\", "/") not in archive_text.replace("\\", "/")
    assert not (hub / ".digital-asset" / "mail" / "archive.jsonl").exists()


def test_central_review_is_idempotent_and_not_public_release(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "private-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "private-source", visibility="private"),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]
    composed = compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo=str(target),
        summary="Private-origin mail must still need human release.",
        repo_policies=policies,
        allow_similar=True,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)

    first = review_central_mail(
        hub,
        mail_id=composed["record"]["mail_id"],
        decision="defer",
        decided_by="Lowell",
        human_verified=True,
        repo_policies=policies,
    )
    second = review_central_mail(
        hub,
        mail_id=composed["record"]["mail_id"],
        decision="defer",
        decided_by="Lowell",
        human_verified=True,
        repo_policies=policies,
    )
    delivered = deliver_mail(hub, [target], repo_policies=policies)

    assert first["appended"] is True
    assert second["appended"] is False
    assert first["decision"]["human_verified"] is True
    assert first["decision"]["source_repo"] == "repo:private-source"
    assert first["decision"]["target_repo"] == "repo:public-target"
    assert first["decision"]["public_release_gate_satisfied"] is False
    assert delivered["delivered_count"] == 0
    assert delivered["held_for_release_count"] == 1


def test_central_inbox_filename_uses_policy_id_or_hash_not_absolute_path(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "private source with spaces"
    hub.mkdir()
    source.mkdir()
    policies = [_policy(source, "private-source", visibility="private")]
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Central inbox filename should be policy based.",
        repo_policies=policies,
        allow_similar=True,
    )

    collect_mail(hub, [source], repo_policies=policies)
    central_path = central_inbox_path(hub, source, policies)
    inbox_files = sorted((hub / "processed" / "mail" / "inbox").glob("*.jsonl"))

    assert central_path.name == "private-source.jsonl"
    assert inbox_files == [central_path]
    assert str(source).replace("\\", "/") not in central_path.as_posix()


def test_reviewed_mail_is_not_redelivered_after_inbox_compaction(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    composed = compose_mail(
        repo_a,
        message_type="capability_suggestion",
        target_repo=str(repo_b),
        summary="Archive decisions should preserve duplicate detection.",
    )
    collect_mail(hub, [repo_a])
    route_mail(hub)
    deliver_mail(hub, [repo_b])
    review_mail(repo_b, mail_id=composed["record"]["mail_id"], decision="archive")
    (repo_b / ".digital-asset" / "mail" / "inbox.jsonl").write_text("", encoding="utf-8")

    delivered_again = deliver_mail(hub, [repo_b])

    assert delivered_again["delivered_count"] == 0
    assert delivered_again["acknowledged_duplicate_count"] == 1


def test_digest_ignores_forged_archive_decision_rows(tmp_path: Path):
    hub = tmp_path / "dad"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    composed = compose_mail(
        repo_a,
        message_type="lesson_suggestion",
        target_repo=str(repo_b),
        summary="Forged archive rows should not mark mail reviewed.",
    )
    collect_mail(hub, [repo_a])
    route_mail(hub)
    deliver_mail(hub, [repo_b])
    archive = repo_b / ".digital-asset" / "mail" / "archive.jsonl"
    _append_jsonl(archive, {"mail_id": composed["record"]["mail_id"], "decision": "reject"})

    digest = digest_mail(repo_b, checked_at="2026-06-30T10:00:00+00:00")

    assert digest["unread_count"] == 1


def test_private_source_to_internal_target_delivers_with_provenance(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "private-source"
    target = tmp_path / "internal-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "private-source", visibility="private"),
        _policy(target, "internal-target", visibility="internal"),
    ]

    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo=str(target),
        summary="Internal target may review private-origin candidate mail.",
        repo_policies=policies,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    delivered = deliver_mail(hub, [target], repo_policies=policies)

    assert delivered["delivered_count"] == 1
    assert delivered["held_for_release_count"] == 0
    inbox = _jsonl(target / ".digital-asset" / "mail" / "inbox.jsonl")
    assert inbox[0]["source_provenance"]["source_visibility"] == "private"
    assert inbox[0]["public_release"]["public_release_required"] is False


def test_private_source_to_public_target_is_held_until_human_release(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "private-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "private-source", visibility="private"),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]

    composed = compose_mail(
        source,
        message_type="workflow_suggestion",
        target_repo=str(target),
        summary="Public target should only see this after human release.",
        repo_policies=policies,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    held = deliver_mail(hub, [target], repo_policies=policies)

    assert held["delivered_count"] == 0
    assert held["held_for_release_count"] == 1
    assert not (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()
    holds = _jsonl(hub / "processed" / "mail" / "quarantine" / "public_release_holds.jsonl")
    assert holds[-1]["mail_id"] == composed["record"]["mail_id"]
    assert holds[-1]["public_release"]["public_release_status"] == "pending_human"

    release = release_mail(
        hub,
        mail_id=composed["record"]["mail_id"],
        decision="approve",
        human_reviewed_by="lowell",
        notes="Approved after checking source provenance and public-safe summary.",
    )
    approved = deliver_mail(hub, [target], repo_policies=policies)

    assert release["release"]["decision"] == "approve"
    assert approved["delivered_count"] == 1
    inbox = _jsonl(target / ".digital-asset" / "mail" / "inbox.jsonl")
    assert inbox[0]["public_release"]["public_release_status"] == "approved"
    assert inbox[0]["public_release"]["human_release_id"] == release["release"]["release_id"]
    inbox_text = (target / ".digital-asset" / "mail" / "inbox.jsonl").read_text(encoding="utf-8")
    assert str(source).replace("\\", "/") not in inbox_text.replace("\\", "/")
    assert inbox[0]["source_repo"] == "repo:private-source"


def test_source_authored_public_release_approval_is_not_trusted(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "unreviewed-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [_policy(target, "public-target", visibility="public", public_facing=True)]
    composed = compose_mail(
        source,
        message_type="workflow_suggestion",
        target_repo=str(target),
        summary="Spoofed release approval should be stripped.",
    )
    outbox = source / ".digital-asset" / "mail" / "outbox.jsonl"
    packet = composed["record"]
    packet["public_release"] = {
        "target_visibility": "public",
        "target_public_facing": True,
        "public_release_required": True,
        "public_release_status": "approved",
        "human_release_id": "dad:mail-release:forged",
        "release_reason": "forged by source packet",
    }
    outbox.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    delivered = deliver_mail(hub, [target], repo_policies=policies)

    assert delivered["delivered_count"] == 0
    assert delivered["held_for_release_count"] == 1
    assert not (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()
    central = _jsonl(next((hub / "processed" / "mail" / "inbox").glob("*.jsonl")))
    assert central[0]["public_release"]["public_release_status"] == "pending_human"
    assert central[0]["public_release"]["human_release_id"] == ""


def test_human_release_rejection_blocks_public_delivery(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "private-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "private-source", visibility="private"),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]

    composed = compose_mail(
        source,
        message_type="taxonomy_suggestion",
        target_repo=str(target),
        summary="Rejected private-origin public packet.",
        repo_policies=policies,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    release_mail(
        hub,
        mail_id=composed["record"]["mail_id"],
        decision="reject",
        human_reviewed_by="lowell",
        notes="Not suitable for a public-facing repo.",
    )

    delivered = deliver_mail(hub, [target], repo_policies=policies)

    assert delivered["delivered_count"] == 0
    assert delivered["rejected_release_count"] == 1
    assert not (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()
    log = _jsonl(hub / "processed" / "mail" / "archive" / "delivery_log.jsonl")
    assert log[-1]["event_type"] == "public_release_rejected"


def test_release_accepts_original_outbox_mail_id_after_canonical_collection(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "private-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "private-source", visibility="private"),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]
    composed = compose_mail(
        source,
        message_type="workflow_suggestion",
        target_repo=str(target),
        summary="Custom local dedupe key should not make release impossible.",
        repo_policies=policies,
        dedupe_key="local-outbox-key-that-will-be-canonicalized",
    )
    collect_mail(hub, [source], repo_policies=policies)
    central = _jsonl(next((hub / "processed" / "mail" / "inbox").glob("*.jsonl")))

    release = release_mail(
        hub,
        mail_id=composed["record"]["mail_id"],
        decision="approve",
        human_reviewed_by="lowell",
    )

    assert central[0]["mail_id"] != composed["record"]["mail_id"]
    assert central[0]["source_provenance"]["original_mail_id"] == composed["record"]["mail_id"]
    assert release["release"]["mail_id"] == central[0]["mail_id"]
    assert release["release"]["requested_mail_id"] == composed["record"]["mail_id"]


def test_agent_review_is_triage_not_human_review(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    target = tmp_path / "target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    composed = compose_mail(
        source,
        message_type="capability_suggestion",
        target_repo=str(target),
        summary="Agent triage should not clear unread mail.",
    )
    collect_mail(hub, [source])
    route_mail(hub)
    deliver_mail(hub, [target])

    review_mail(target, mail_id=composed["record"]["mail_id"], decision="defer")
    agent_digest = digest_mail(target, checked_at="2026-06-30T10:00:00+00:00")
    human_decision = review_mail(
        target,
        mail_id=composed["record"]["mail_id"],
        decision="defer",
        human_verified=True,
        decided_by="lowell",
    )
    human_digest = digest_mail(target, checked_at="2026-06-30T10:05:00+00:00")

    assert agent_digest["unread_count"] == 1
    assert agent_digest["agent_triage_count"] == 1
    assert human_decision["appended"] is True
    assert human_digest["unread_count"] == 0
    assert human_digest["reviewed_count"] == 1


def test_mail_triage_records_future_adoption_pointer(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    target = tmp_path / "target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    composed = compose_mail(
        source,
        message_type="asset_suggestion",
        target_repo=str(target),
        summary="Target may want to watch a Rust parity harness.",
        payload={
            "asset_id": "dad:offering:rust-shadow-parity-harness",
            "source_ref": "assets/coding-harnesses/rust-shadow-parity-harness",
        },
        evidence=["registry/dad-offerings-registry.json"],
    )
    collect_mail(hub, [source])
    route_mail(hub)
    deliver_mail(hub, [target])

    result = triage_mail(
        target,
        mail_id=composed["record"]["mail_id"],
        intake_decision="save_for_future",
        importance="future",
        planned_use="Watch for Python/Rust parity work.",
        implementation_plan=["Review when replacing slow pytest cases."],
        recorded_by="unit-test",
    )

    adoption = result["adoption"]
    assert adoption["intake_decision"] == "save_for_future"
    assert adoption["implementation_status"] == "watching"
    assert adoption["update_tracking"]["watch_source"] is True
    assert (
        adoption["update_tracking"]["upgrade_policy"] == "notify_via_dad_mail_before_local_change"
    )
    assert "dad:offering:rust-shadow-parity-harness" in adoption["source_asset_refs"]
    records = _jsonl(target / ".digital-asset" / "mail" / "adoption.jsonl")
    assert records[0]["adoption_id"] == adoption["adoption_id"]


def test_write_protected_mailbox_blocks_local_review_triage_and_digest(tmp_path: Path):
    repo = tmp_path / "logos"
    repo.mkdir()
    policies = [
        _policy(
            repo,
            "logos-scripture-graph",
            write_protected=True,
            write_protection_reason="explicit local-write approval required",
        )
    ]

    with pytest.raises(ValueError, match="write-protected"):
        compose_mail(
            repo,
            message_type="lesson_suggestion",
            target_repo="central_only",
            summary="Should remain central-only.",
            repo_policies=policies,
        )
    with pytest.raises(ValueError, match="write-protected"):
        review_mail(repo, mail_id="dad:mail:test", decision="defer", repo_policies=policies)
    with pytest.raises(ValueError, match="write-protected"):
        triage_mail(
            repo,
            mail_id="dad:mail:test",
            intake_decision="defer",
            repo_policies=policies,
        )
    with pytest.raises(ValueError, match="write-protected"):
        digest_mail(repo, repo_policies=policies)


def test_public_safe_payload_policy_rejects_raw_blob_to_public_target(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "public-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "public-source", visibility="public", public_facing=True),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]

    compose_mail(
        source,
        message_type="asset_suggestion",
        target_repo=str(target),
        summary="Raw table should not go to a public-facing mailbox.",
        payload={"raw_rows": "a,b,c,d,e\n1,2,3,4,5"},
        repo_policies=policies,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    delivered = deliver_mail(hub, [target], repo_policies=policies)

    assert delivered["delivered_count"] == 0
    assert delivered["held_for_release_count"] == 1
    assert delivered["skipped"][0]["reason"] == "public-safe payload violations"
    assert not (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()


def test_public_safe_payload_policy_rejects_raw_evidence_to_public_target(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "public-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "public-source", visibility="public", public_facing=True),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]

    compose_mail(
        source,
        message_type="asset_suggestion",
        target_repo=str(target),
        summary="Long raw evidence should not go to a public-facing mailbox.",
        evidence=["x" * 1000],
        repo_policies=policies,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    delivered = deliver_mail(hub, [target], repo_policies=policies)

    assert delivered["delivered_count"] == 0
    assert delivered["held_for_release_count"] == 1
    assert "payload_value_too_long:evidence" in delivered["skipped"][0]["violations"]


def test_public_safe_payload_policy_rejects_legacy_local_path_refs(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "public-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    policies = [
        _policy(source, "public-source", visibility="public", public_facing=True),
        _policy(target, "public-target", visibility="public", public_facing=True),
    ]
    compose_mail(
        source,
        message_type="asset_suggestion",
        target_repo=str(target),
        summary="Legacy routed mail should not leak local paths to public repos.",
        payload={"note": "metadata-only"},
        repo_policies=policies,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    routed_path = hub / "processed" / "mail" / "outbox" / "routed.jsonl"
    routed = _jsonl(routed_path)
    routed[0]["payload"]["note"] = (
        "See C:/Users/lowel/OneDrive/Desktop/Git Projects/private-repo/asset.json"
    )
    routed_path.write_text(json.dumps(routed[0], sort_keys=True) + "\n", encoding="utf-8")

    delivered = deliver_mail(hub, [target], repo_policies=policies)

    assert delivered["delivered_count"] == 0
    assert delivered["held_for_release_count"] == 0
    assert delivered["route_block_count"] == 1
    assert delivered["skipped"][0]["reason"] == "route_hash_mismatch"
    assert not (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()


def test_unreviewed_source_visibility_claim_is_downgraded_before_public_delivery(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    source = tmp_path / "unreviewed-source"
    target = tmp_path / "public-target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    target_policy = [_policy(target, "public-target", visibility="public", public_facing=True)]
    composed = compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo=str(target),
        summary="Spoofed public provenance must not clear the public release gate.",
    )
    outbox = source / ".digital-asset" / "mail" / "outbox.jsonl"
    packet = composed["record"]
    packet["source_provenance"]["source_visibility"] = "public"
    outbox.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    collect_mail(hub, [source], repo_policies=target_policy)
    route_mail(hub, repo_policies=target_policy)
    delivered = deliver_mail(hub, [target], repo_policies=target_policy)

    assert delivered["delivered_count"] == 0
    assert delivered["held_for_release_count"] == 1
    central = _jsonl(next((hub / "processed" / "mail" / "inbox").glob("*.jsonl")))
    assert central[0]["source_provenance"]["source_visibility"] == "unknown"


def test_same_basename_repo_targets_are_held_as_ambiguous(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    target_one = tmp_path / "one" / "shared"
    target_two = tmp_path / "two" / "shared"
    hub.mkdir()
    source.mkdir()
    target_one.mkdir(parents=True)
    target_two.mkdir(parents=True)
    policies = [
        _policy(source, "source", visibility="internal"),
        _policy(target_one, "shared-one", visibility="internal"),
        _policy(target_two, "shared-two", visibility="internal"),
    ]

    compose_mail(
        source,
        message_type="workflow_suggestion",
        target_repo="shared",
        summary="Bare basename target should not pick a repo arbitrarily.",
        repo_policies=policies,
    )
    collect_mail(hub, [source], repo_policies=policies)
    route_mail(hub, repo_policies=policies)
    delivered = deliver_mail(hub, [target_one, target_two], repo_policies=policies)

    assert delivered["delivered_count"] == 0
    assert delivered["skipped"][0]["reason"] == "target repo key is ambiguous"
    assert not (target_one / ".digital-asset" / "mail" / "inbox.jsonl").exists()
    assert not (target_two / ".digital-asset" / "mail" / "inbox.jsonl").exists()


def test_repo_all_uses_reviewed_config_allowlist_only(tmp_path: Path):
    hub = tmp_path / "dad"
    allowed = tmp_path / "allowed"
    stray = tmp_path / "stray"
    hub.mkdir()
    allowed.mkdir()
    stray.mkdir()
    (stray / ".digital-asset" / "mail").mkdir(parents=True)
    (stray / ".digital-asset" / "mail" / "inbox.jsonl").write_text("", encoding="utf-8")
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[SimpleNamespace(enabled=True, path=tmp_path)],
        mail_repos=[_policy(allowed, "allowed")],
    )

    assert _discover_mail_repos(["all"], cfg) == [allowed.resolve()]
    assert _discover_mail_repos(["all"], cfg, delivery=True) == [allowed.resolve()]


def test_mail_discovery_finds_nested_unreviewed_mailboxes_without_enrolling_them(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    allowed = tmp_path / "allowed"
    nested = tmp_path / "lawfirm-os" / "repos" / "intake-runtime"
    ignored = tmp_path / "project" / "target" / "build-copy"
    hub.mkdir()
    allowed.mkdir()
    nested.mkdir(parents=True)
    ignored.mkdir(parents=True)
    (nested / ".digital-asset" / "mail").mkdir(parents=True)
    (nested / ".digital-asset" / "mail" / "outbox.jsonl").write_text(
        '{"mail_id":"candidate"}\n',
        encoding="utf-8",
    )
    (ignored / ".digital-asset" / "mail").mkdir(parents=True)
    (ignored / ".digital-asset" / "mail" / "outbox.jsonl").write_text(
        '{"mail_id":"ignored-build-copy"}\n',
        encoding="utf-8",
    )
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[SimpleNamespace(enabled=True, path=tmp_path)],
        mail_repos=[_policy(allowed, "allowed")],
    )

    candidates = _mail_repo_candidates(cfg)
    nested_rows = [row for row in candidates if row["path"] == str(nested.resolve())]
    ignored_rows = [row for row in candidates if row["path"] == str(ignored.resolve())]

    assert len(nested_rows) == 1
    assert nested_rows[0]["configured"] is False
    assert nested_rows[0]["has_outbox"] is True
    assert nested_rows[0]["visibility"] == "unreviewed_candidate"
    assert ignored_rows == []
    assert _discover_mail_repos(["all"], cfg) == [allowed.resolve()]


def test_mail_discovery_ignores_dad_scratch_mailboxes(tmp_path: Path):
    hub = tmp_path / "dad"
    allowed = tmp_path / "allowed"
    scratch = hub / ".tmp" / "capture-emission" / "dad-capture-emission-abc123" / "lesson"
    hub.mkdir()
    allowed.mkdir()
    (scratch / ".digital-asset" / "mail").mkdir(parents=True)
    (scratch / ".digital-asset" / "mail" / "outbox.jsonl").write_text(
        '{"mail_id":"synthetic-scratch"}\n',
        encoding="utf-8",
    )
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[SimpleNamespace(enabled=True, path=hub)],
        mail_repos=[_policy(allowed, "allowed")],
    )

    candidates = _mail_repo_candidates(cfg)
    scratch_rows = [row for row in candidates if row["path"] == str(scratch.resolve())]
    coverage = _mailbox_coverage_summary(cfg, [allowed.resolve()], include_local_paths=True)

    assert scratch_rows == []
    assert coverage["unreviewed_mailbox_candidate_count"] == 0
    assert coverage["warning"] == ""


def test_mailbox_coverage_warns_about_nested_unreviewed_outboxes(tmp_path: Path):
    hub = tmp_path / "dad"
    allowed = tmp_path / "allowed"
    nested = tmp_path / "group" / "nested-repo"
    hub.mkdir()
    allowed.mkdir()
    nested.mkdir(parents=True)
    (nested / ".digital-asset" / "mail").mkdir(parents=True)
    (nested / ".digital-asset" / "mail" / "outbox.jsonl").write_text(
        '{"mail_id":"candidate"}\n',
        encoding="utf-8",
    )
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[SimpleNamespace(enabled=True, path=tmp_path)],
        mail_repos=[_policy(allowed, "allowed")],
    )

    coverage = _mailbox_coverage_summary(cfg, [allowed.resolve()])

    assert coverage["unreviewed_mailbox_candidate_count"] == 1
    assert coverage["reviewed_checked_count"] == 1
    assert "outside reviewed mail.repos" in coverage["warning"]
    sample = coverage["unreviewed_mailbox_candidate_samples"][0]
    assert sample["path_ref"].startswith("repo-path-sha256:")
    assert "path" not in sample
    local_coverage = _mailbox_coverage_summary(
        cfg,
        [allowed.resolve()],
        include_local_paths=True,
    )
    assert local_coverage["unreviewed_mailbox_candidate_samples"][0]["path"] == str(
        nested.resolve()
    )


def test_cli_mail_doctor_strict_coverage_gap_fails_for_unreviewed_nested_outbox(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    allowed = tmp_path / "allowed"
    nested = tmp_path / "lawfirm-os" / "repos" / "intake-runtime"
    allowed.mkdir()
    nested.mkdir(parents=True)
    (nested / ".digital-asset" / "mail").mkdir(parents=True)
    (nested / ".digital-asset" / "mail" / "outbox.jsonl").write_text("", encoding="utf-8")
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[SimpleNamespace(enabled=True, path=tmp_path)],
        mail_repos=[_policy(allowed, "allowed")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    default_result = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--repo",
            "all",
            "--summary-only",
            "--fail-on-dirty",
        ],
    )
    strict_result = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--repo",
            "all",
            "--summary-only",
            "--fail-on-dirty",
            "--fail-on-coverage-gap",
        ],
    )

    assert default_result.exit_code == 0
    payload = json.loads(default_result.output)
    assert payload["dirty"] is False
    assert payload["mailbox_coverage"]["unreviewed_mailbox_candidate_count"] == 1
    assert strict_result.exit_code == 1


def test_cli_mail_collect_repo_all_blocks_coverage_gap_unless_acknowledged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    allowed = tmp_path / "allowed"
    nested = tmp_path / "lawfirm-os" / "repos" / "intake-runtime"
    allowed.mkdir()
    nested.mkdir(parents=True)
    compose_mail(
        allowed,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Reviewed source mail should still collect when coverage is warning-only.",
    )
    compose_mail(
        nested,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Unreviewed source mail should trigger coverage warning.",
    )
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[SimpleNamespace(enabled=True, path=tmp_path)],
        mail_repos=[_policy(allowed, "allowed")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    blocked = RUNNER.invoke(
        app,
        [
            "mail",
            "collect",
            "--repo",
            "all",
        ],
    )
    acknowledged = RUNNER.invoke(
        app,
        [
            "mail",
            "collect",
            "--repo",
            "all",
            "--allow-coverage-gap-ack",
            "collect reviewed repos only after seeing one unreviewed mailbox",
        ],
    )

    assert blocked.exit_code == 1
    blocked_payload = json.loads(blocked.output)
    assert blocked_payload["schema_version"] == "dad_mailbox_coverage_gate.v1"
    assert blocked_payload["operation"] == "mail collect"
    assert blocked_payload["mailbox_coverage"]["unreviewed_mailbox_candidate_count"] == 1
    assert (
        "path" not in blocked_payload["mailbox_coverage"]["unreviewed_mailbox_candidate_samples"][0]
    )

    assert acknowledged.exit_code == 0
    payload = json.loads(acknowledged.output)
    assert payload["collected_count"] == 1
    assert payload["mailbox_coverage"]["unreviewed_mailbox_candidate_count"] == 1
    assert central_inbox_path(hub, allowed, cfg.mail_repos).exists()
    assert not central_inbox_path(hub, nested, cfg.mail_repos).exists()
    ack_log = _jsonl(hub / "processed" / "mail" / "archive" / "coverage_gap_ack.jsonl")
    assert ack_log[0]["operation"] == "mail collect"


def test_cli_mail_collect_repo_all_blocks_reviewed_enabled_unchecked_gap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    allowed = tmp_path / "allowed"
    missing = tmp_path / "missing"
    allowed.mkdir()
    missing.mkdir()
    compose_mail(
        allowed,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Reviewed source mail should not collect when coverage is inconsistent.",
    )
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(allowed, "allowed"), _policy(missing, "missing")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    def coverage_gap(*args, **kwargs):
        return {
            "schema_version": "dad_mailbox_coverage.v1",
            "candidate_count": 2,
            "reviewed_checked_count": 1,
            "unreviewed_mailbox_candidate_count": 0,
            "reviewed_enabled_not_checked_count": 1,
            "unreviewed_mailbox_candidate_samples": [],
            "reviewed_enabled_not_checked_samples": [
                {"path_ref": "repo-path-sha256:test", "repo_id": "missing"}
            ],
            "local_paths_included": False,
            "warning": "",
            "authority_boundary": "Mailbox discovery is read-only coverage evidence.",
        }

    monkeypatch.setattr(cli_module, "_mailbox_coverage_summary", coverage_gap)

    blocked = RUNNER.invoke(app, ["mail", "collect", "--repo", "all"])

    assert blocked.exit_code == 1
    blocked_payload = json.loads(blocked.output)
    assert blocked_payload["schema_version"] == "dad_mailbox_coverage_gate.v1"
    assert blocked_payload["mailbox_coverage"]["reviewed_enabled_not_checked_count"] == 1
    assert not central_inbox_path(hub, allowed, cfg.mail_repos).exists()


def test_cli_mail_deliver_repo_all_blocks_coverage_gap_before_inbox_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    allowed = tmp_path / "allowed"
    nested = tmp_path / "lawfirm-os" / "repos" / "intake-runtime"
    allowed.mkdir()
    nested.mkdir(parents=True)
    (nested / ".digital-asset" / "mail").mkdir(parents=True)
    (nested / ".digital-asset" / "mail" / "outbox.jsonl").write_text("", encoding="utf-8")
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[SimpleNamespace(enabled=True, path=tmp_path)],
        mail_repos=[_policy(allowed, "allowed")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    strict = RUNNER.invoke(
        app,
        [
            "mail",
            "deliver",
            "--repo",
            "all",
        ],
    )

    assert strict.exit_code == 1
    payload = json.loads(strict.output)
    assert payload["schema_version"] == "dad_mailbox_coverage_gate.v1"
    assert payload["operation"] == "mail deliver"
    assert payload["mailbox_coverage"]["unreviewed_mailbox_candidate_count"] == 1
    assert not (allowed / ".digital-asset" / "mail" / "inbox.jsonl").exists()


def test_cli_mail_deliver_repo_all_blocks_reviewed_enabled_unchecked_gap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    allowed = tmp_path / "allowed"
    missing = tmp_path / "missing"
    allowed.mkdir()
    missing.mkdir()
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(allowed, "allowed"), _policy(missing, "missing")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    def coverage_gap(*args, **kwargs):
        return {
            "schema_version": "dad_mailbox_coverage.v1",
            "candidate_count": 2,
            "reviewed_checked_count": 1,
            "unreviewed_mailbox_candidate_count": 0,
            "reviewed_enabled_not_checked_count": 1,
            "unreviewed_mailbox_candidate_samples": [],
            "reviewed_enabled_not_checked_samples": [
                {"path_ref": "repo-path-sha256:test", "repo_id": "missing"}
            ],
            "local_paths_included": False,
            "warning": "",
            "authority_boundary": "Mailbox discovery is read-only coverage evidence.",
        }

    monkeypatch.setattr(cli_module, "_mailbox_coverage_summary", coverage_gap)

    blocked = RUNNER.invoke(app, ["mail", "deliver", "--repo", "all"])

    assert blocked.exit_code == 1
    blocked_payload = json.loads(blocked.output)
    assert blocked_payload["schema_version"] == "dad_mailbox_coverage_gate.v1"
    assert blocked_payload["mailbox_coverage"]["reviewed_enabled_not_checked_count"] == 1
    assert not (allowed / ".digital-asset" / "mail" / "inbox.jsonl").exists()


def test_cli_mail_deliver_exits_nonzero_when_delivery_reports_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    target = tmp_path / "target"
    target.mkdir()
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(target, "target")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)
    monkeypatch.setattr(
        cli_module,
        "deliver_mail",
        lambda *args, **kwargs: {
            "delivered_count": 0,
            "error_count": 1,
            "errors": [{"error": "synthetic delivery failure"}],
            "blocked": False,
        },
    )

    result = RUNNER.invoke(app, ["mail", "deliver", "--repo", "target"])

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["error_count"] == 1


def test_cli_mail_deliver_exits_nonzero_when_delivery_reports_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    target = tmp_path / "target"
    target.mkdir()
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(target, "target")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)
    monkeypatch.setattr(
        cli_module,
        "deliver_mail",
        lambda *args, **kwargs: {
            "delivered_count": 0,
            "error_count": 0,
            "errors": [],
            "blocked": True,
            "route_block_count": 1,
        },
    )

    result = RUNNER.invoke(app, ["mail", "deliver", "--repo", "target"])

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["blocked"] is True
    assert payload["route_block_count"] == 1


def test_cli_mail_route_exits_nonzero_when_routing_reports_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    cfg = SimpleNamespace(repo_root=hub, local_sources=[], mail_repos=[])
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)
    monkeypatch.setattr(
        cli_module,
        "route_mail",
        lambda *args, **kwargs: {
            "routed_count": 0,
            "error_count": 1,
            "errors": [{"error": "synthetic route failure"}],
            "blocked": False,
        },
    )

    result = RUNNER.invoke(app, ["mail", "route"])

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["error_count"] == 1


def test_repo_option_resolves_reviewed_aliases_and_rejects_ambiguous_names(tmp_path: Path):
    hub = tmp_path / "dad"
    target = tmp_path / "logos-scripture-graph-repo"
    first_same_name = tmp_path / "one" / "shared-name"
    second_same_name = tmp_path / "two" / "shared-name"
    hub.mkdir()
    target.mkdir()
    first_same_name.mkdir(parents=True)
    second_same_name.mkdir(parents=True)
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[
            _policy(target, "logos-scripture-graph"),
            _policy(first_same_name, "first-shared"),
            _policy(second_same_name, "second-shared"),
        ],
    )

    assert _discover_mail_repos(["logos-scripture-graph"], cfg) == [target.resolve()]
    assert _discover_mail_repos(["logos-scripture-graph-repo"], cfg) == [target.resolve()]
    assert _discover_mail_repos([str(target)], cfg) == [target.resolve()]
    with pytest.raises(typer.BadParameter, match="ambiguous"):
        _discover_mail_repos(["shared-name"], cfg)


def test_explicit_delivery_path_requires_reviewed_mail_policy(tmp_path: Path):
    hub = tmp_path / "dad"
    allowed = tmp_path / "allowed"
    stray = tmp_path / "stray"
    hub.mkdir()
    allowed.mkdir()
    stray.mkdir()
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(allowed, "allowed")],
    )

    with pytest.raises(typer.BadParameter, match="reviewed mail.repos"):
        _discover_mail_repos([str(stray)], cfg, delivery=True)

    assert _discover_mail_repos([str(allowed)], cfg, delivery=True) == [allowed.resolve()]


def test_delivery_repo_all_blocks_when_any_reviewed_repo_is_delivery_held(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    allowed = tmp_path / "allowed"
    protected = tmp_path / "logos-scripture-graph"
    allowed.mkdir()
    protected.mkdir()
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[
            _policy(allowed, "allowed"),
            _policy(
                protected,
                "logos-scripture-graph",
                delivery_allowed=False,
                write_protected=True,
            ),
        ],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)
    deliver_called = False

    def fail_if_called(*args, **kwargs):
        nonlocal deliver_called
        deliver_called = True
        return {"delivered_count": 99}

    monkeypatch.setattr(cli_module, "deliver_mail", fail_if_called)

    with pytest.raises(typer.BadParameter, match="--repo all delivery is blocked"):
        _discover_mail_repos(["all"], cfg, delivery=True)
    assert _discover_mail_repos(["allowed"], cfg, delivery=True) == [allowed.resolve()]

    result = RUNNER.invoke(app, ["mail", "deliver", "--repo", "all"])

    assert result.exit_code == 2
    assert deliver_called is False
    assert not (allowed / ".digital-asset" / "mail" / "inbox.jsonl").exists()


def test_explicit_reviewed_operation_path_requires_reviewed_mail_policy(tmp_path: Path):
    hub = tmp_path / "dad"
    allowed = tmp_path / "allowed"
    stray = tmp_path / "stray"
    hub.mkdir()
    allowed.mkdir()
    stray.mkdir()
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(allowed, "allowed")],
    )

    with pytest.raises(typer.BadParameter, match="reviewed mail.repos"):
        _discover_mail_repos([str(stray)], cfg, reviewed=True)

    assert _discover_mail_repos([str(allowed)], cfg, reviewed=True) == [allowed.resolve()]


def test_cli_mail_collect_explicit_path_requires_reviewed_source_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    stray = tmp_path / "stray"
    stray.mkdir()
    compose_mail(
        stray,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Unreviewed explicit source path should not enter central DAD inbox.",
    )
    cfg = SimpleNamespace(repo_root=hub, local_sources=[], mail_repos=[])
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    result = RUNNER.invoke(app, ["mail", "collect", "--repo", str(stray)])

    assert result.exit_code == 2
    assert "reviewed mail.repos" in result.output
    assert not (hub / "processed" / "mail" / "inbox").exists()


def test_mail_discovery_reports_nested_configured_repos(tmp_path: Path):
    hub = tmp_path / "dad"
    nested = tmp_path / "group" / "nested-repo"
    hub.mkdir()
    nested.mkdir(parents=True)
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[SimpleNamespace(enabled=True, path=tmp_path)],
        mail_repos=[
            _policy(
                nested,
                "nested-repo",
                write_protected=True,
                write_protection_reason=(
                    r"C:\Users\lowel\OneDrive\Desktop\Git Projects"
                    r"\private\nested-repo"
                ),
            )
        ],
    )

    candidates = _mail_repo_candidates(cfg)

    nested_rows = [row for row in candidates if row["path"] == str(nested.resolve())]
    assert len(nested_rows) == 1
    assert nested_rows[0]["configured"] is True
    assert nested_rows[0]["visibility"] == "internal"
    assert str(nested_rows[0]["write_protection_reason"]).startswith("path-sha256:")


def test_strict_delivery_requires_reviewed_target_policy_for_explicit_paths(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    target = tmp_path / "target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    compose_mail(
        source,
        message_type="governance_notice",
        target_repo=str(target),
        summary="Explicit delivery still needs reviewed target policy in strict mode.",
    )
    collect_mail(hub, [source])
    route_mail(hub)

    delivered = deliver_mail(hub, [target], require_target_policy=True)

    assert delivered["delivered_count"] == 0
    assert delivered["skipped"][0]["reason"] == "target repo lacks reviewed mail policy"
    assert not (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()


def test_collect_mail_errors_use_safe_repo_refs(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "C__Users__lowel__OneDrive__Desktop__Git Projects__source"
    hub.mkdir()
    outbox = source / ".digital-asset" / "mail" / "outbox.jsonl"
    outbox.parent.mkdir(parents=True)
    outbox.write_text("{bad-json}\n", encoding="utf-8")

    result = collect_mail(hub, [source])
    result_text = json.dumps(result, sort_keys=True).replace("\\", "/")

    assert result["collected_count"] == 0
    assert result["error_count"] == 1
    assert result["errors"][0]["repo"].startswith("repo-path-sha256:")
    assert "C__Users" not in result_text
    assert "OneDrive" not in result_text
    assert "Git Projects" not in result_text


def test_malformed_jsonl_quarantine_uses_safe_path_refs(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "C__Users__lowel__OneDrive__Desktop__Git Projects__source"
    hub.mkdir()
    outbox = source / ".digital-asset" / "mail" / "outbox.jsonl"
    outbox.parent.mkdir(parents=True)
    outbox.write_text("{bad-json}\n", encoding="utf-8")

    collect_mail(hub, [source])

    quarantine_text = (
        hub / "processed" / "mail" / "quarantine" / "malformed_jsonl.jsonl"
    ).read_text(encoding="utf-8")
    assert "repo-path-sha256:" in quarantine_text
    assert "C__Users" not in quarantine_text
    assert "OneDrive" not in quarantine_text
    assert "Git Projects" not in quarantine_text


def test_collect_accepts_bom_prefixed_source_outbox(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="BOM-prefixed source outboxes should still collect.",
    )
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    outbox.write_bytes(b"\xef\xbb\xbf" + outbox.read_bytes())

    result = collect_mail(hub, [repo])

    assert result["collected_count"] == 1
    assert result["error_count"] == 0
    central = _jsonl(central_inbox_path(hub, repo))
    assert central[0]["payload"]["summary"] == "BOM-prefixed source outboxes should still collect."


def test_digest_tolerates_malformed_rows_and_updates_last_checked(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    mailbox = repo / ".digital-asset" / "mail"
    mailbox.mkdir(parents=True)
    (mailbox / "inbox.jsonl").write_text("{bad-json\n", encoding="utf-8")

    digest = digest_mail(repo, checked_at="2026-06-30T10:00:00+00:00")

    assert digest["parse_warning_count"] == 1
    assert digest["unread_count"] == 0
    assert (mailbox / "last_checked.json").exists()


def test_digest_tolerates_invalid_utf8_rows_and_updates_last_checked(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    mailbox = repo / ".digital-asset" / "mail"
    mailbox.mkdir(parents=True)
    (mailbox / "inbox.jsonl").write_bytes(b"\xff\n")

    digest = digest_mail(repo, checked_at="2026-06-30T10:00:00+00:00")

    assert digest["parse_warning_count"] == 1
    assert "Invalid UTF-8" in digest["parse_warnings"][0]["error"]
    assert digest["unread_count"] == 0
    assert (mailbox / "last_checked.json").exists()


def test_digest_tolerates_bom_prefixed_inbox_and_updates_last_checked(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    packet = compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo=str(repo),
        summary="BOM-prefixed inbox should still digest.",
    )["record"]
    inbox = repo / ".digital-asset" / "mail" / "inbox.jsonl"
    inbox.write_bytes(b"\xef\xbb\xbf" + json.dumps(packet).encode("utf-8") + b"\n")

    digest = digest_mail(repo, checked_at="2026-06-30T10:00:00+00:00")

    assert digest["parse_warning_count"] == 0
    assert digest["inbox_count"] == 1
    assert digest["unread_count"] == 1
    assert (repo / ".digital-asset" / "mail" / "last_checked.json").exists()


def test_stale_jsonl_lock_is_recovered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    hub.mkdir()
    source.mkdir()
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Stale lock should be removed.",
    )
    central = central_inbox_path(hub, source)
    central.parent.mkdir(parents=True)
    lock = central.with_name(f".{central.name}.lock")
    lock.write_text("stale", encoding="utf-8")
    old_time = os.path.getmtime(lock) - 1_000
    os.utime(lock, (old_time, old_time))
    monkeypatch.setattr(mail_center, "STALE_LOCK_SECONDS", 1.0)

    result = collect_mail(hub, [source])

    assert result["collected_count"] == 1
    assert not lock.exists()


def test_dead_pid_jsonl_lock_is_recovered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    hub.mkdir()
    source.mkdir()
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Dead PID lock should be removed.",
    )
    central = central_inbox_path(hub, source)
    central.parent.mkdir(parents=True)
    lock = central.with_name(f".{central.name}.lock")
    lock.write_text(json.dumps({"pid": 987654321, "created_at": "2026-07-04T00:00:00+00:00"}))
    monkeypatch.setattr(mail_center, "_jsonl_lock_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(mail_center, "LOCK_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(mail_center, "STALE_LOCK_SECONDS", 999.0)

    result = collect_mail(hub, [source])

    assert result["collected_count"] == 1
    assert result["error_count"] == 0
    assert not lock.exists()


def test_dead_pid_jsonl_lock_unlink_permission_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    hub.mkdir()
    source.mkdir()
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Dead PID lock cleanup should retry.",
    )
    central = central_inbox_path(hub, source)
    central.parent.mkdir(parents=True)
    lock = central.with_name(f".{central.name}.lock")
    lock.write_text(json.dumps({"pid": 987654321, "created_at": "2026-07-04T00:00:00+00:00"}))
    original_unlink = Path.unlink
    attempts = {"count": 0}

    def flaky_unlink(self: Path, *args, **kwargs):
        if self == lock and attempts["count"] == 0:
            attempts["count"] += 1
            raise PermissionError("temporary lock removal denial")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(mail_center.Path, "unlink", flaky_unlink)
    monkeypatch.setattr(mail_center, "_jsonl_lock_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(mail_center, "LOCK_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(mail_center, "STALE_LOCK_SECONDS", 999.0)
    monkeypatch.setattr(mail_center.time, "sleep", lambda _seconds: None)

    result = collect_mail(hub, [source])

    assert attempts["count"] == 1
    assert result["collected_count"] == 1
    assert result["error_count"] == 0
    assert not lock.exists()


def test_dead_pid_jsonl_lock_unlink_timeout_uses_tombstone_takeover(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    target = tmp_path / "archive.jsonl"
    lock = target.with_name(f".{target.name}.lock")
    lock.write_text(json.dumps({"pid": 987654321, "created_at": "2026-07-04T00:00:00+00:00"}))
    original_unlink = Path.unlink

    def blocked_unlink(self: Path, *args, **kwargs):
        if self == lock:
            raise PermissionError("persistent lock removal denial")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(mail_center.Path, "unlink", blocked_unlink)
    monkeypatch.setattr(mail_center, "_jsonl_lock_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(mail_center, "LOCK_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(mail_center, "STALE_LOCK_SECONDS", 999.0)
    monkeypatch.setattr(mail_center.time, "sleep", lambda _seconds: None)

    with mail_center._jsonl_lock(target):
        target.write_text('{"ok": true}\n', encoding="utf-8")

    assert target.read_text(encoding="utf-8") == '{"ok": true}\n'
    assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == 987654321


def test_dead_pid_jsonl_lock_unlink_timeout_with_stat_error_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    target = tmp_path / "archive.jsonl"
    lock = target.with_name(f".{target.name}.lock")
    lock.write_text(json.dumps({"pid": 987654321, "created_at": "2026-07-04T00:00:00+00:00"}))
    original_unlink = Path.unlink
    original_stat = Path.stat
    monotonic_values = iter([0.0, 0.02])

    def blocked_unlink(self: Path, *args, **kwargs):
        if self == lock:
            raise PermissionError("persistent lock removal denial")
        return original_unlink(self, *args, **kwargs)

    def flaky_stat(self: Path, *args, **kwargs):
        if self == lock:
            raise PermissionError("lock stat denied")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(mail_center.Path, "unlink", blocked_unlink)
    monkeypatch.setattr(mail_center.Path, "stat", flaky_stat)
    monkeypatch.setattr(mail_center, "_jsonl_lock_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(mail_center, "LOCK_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(mail_center, "STALE_LOCK_SECONDS", 999.0)
    monkeypatch.setattr(mail_center.time, "monotonic", lambda: next(monotonic_values, 0.02))
    monkeypatch.setattr(mail_center.time, "sleep", lambda _seconds: None)

    with pytest.raises(TimeoutError, match="Timed out waiting for JSONL lock"):
        with mail_center._jsonl_lock(target):
            target.write_text('{"ok": true}\n', encoding="utf-8")

    assert not target.exists()
    assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == 987654321


def test_same_process_leftover_jsonl_lock_unlink_timeout_uses_tombstone_takeover(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    target = tmp_path / "mail.jsonl"
    lock = target.with_name(f".{target.name}.lock")
    lock.write_text(json.dumps({"pid": os.getpid(), "created_at": "2026-07-04T00:00:00+00:00"}))
    original_unlink = Path.unlink
    monotonic_values = iter([0.0, 0.02])

    def blocked_unlink(self: Path, *args, **kwargs):
        if self == lock:
            raise PermissionError("same-process leftover lock cleanup denied")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(mail_center.Path, "unlink", blocked_unlink)
    monkeypatch.setattr(mail_center, "LOCK_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(mail_center, "STALE_LOCK_SECONDS", 999.0)
    monkeypatch.setattr(mail_center.time, "monotonic", lambda: next(monotonic_values, 0.02))
    monkeypatch.setattr(mail_center.time, "sleep", lambda _seconds: None)
    mail_center._ACTIVE_JSONL_LOCKS.discard(lock.resolve())

    with mail_center._jsonl_lock(target):
        target.write_text('{"ok": true}\n', encoding="utf-8")

    assert target.read_text(encoding="utf-8") == '{"ok": true}\n'
    assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == os.getpid()


def test_jsonl_lock_cleanup_permission_error_does_not_mask_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    target = tmp_path / "outbox.jsonl"
    lock = target.with_name(f".{target.name}.lock")
    original_unlink = Path.unlink
    attempts = {"count": 0}

    def flaky_unlink(self: Path, *args, **kwargs):
        if self == lock and attempts["count"] == 0:
            attempts["count"] += 1
            raise PermissionError("temporary lock cleanup denial")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(mail_center.Path, "unlink", flaky_unlink)
    monkeypatch.setattr(mail_center.time, "sleep", lambda _seconds: None)

    with mail_center._jsonl_lock(target):
        target.write_text('{"ok": true}\n', encoding="utf-8")

    assert attempts["count"] == 1
    assert target.read_text(encoding="utf-8") == '{"ok": true}\n'
    assert not lock.exists()


def test_active_jsonl_lock_timeout_is_reported_per_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    hub.mkdir()
    source.mkdir()
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Active lock should be reported.",
    )
    central = central_inbox_path(hub, source)
    central.parent.mkdir(parents=True)
    lock = central.with_name(f".{central.name}.lock")
    lock.write_text("active", encoding="utf-8")
    monkeypatch.setattr(mail_center, "LOCK_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(mail_center, "STALE_LOCK_SECONDS", 999.0)

    result = collect_mail(hub, [source])

    assert result["collected_count"] == 0
    assert result["error_count"] == 1
    assert "Timed out waiting for JSONL lock" in result["errors"][0]["error"]
    lock.unlink()


def test_collect_respects_active_repo_outbox_lock_and_skips_partial_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    hub.mkdir()
    source.mkdir()
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Active outbox writers should block collection.",
    )
    outbox = source / ".digital-asset" / "mail" / "outbox.jsonl"
    with outbox.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write('{"partial":')
    lock = outbox.with_name(f".{outbox.name}.lock")
    lock.write_text(json.dumps({"pid": os.getpid(), "created_at": "2026-07-04T00:00:00+00:00"}))
    monkeypatch.setattr(mail_center, "LOCK_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(mail_center, "STALE_LOCK_SECONDS", 999.0)
    monkeypatch.setattr(mail_center.time, "sleep", lambda _seconds: None)
    mail_center._ACTIVE_JSONL_LOCKS.add(lock.resolve())

    try:
        result = collect_mail(hub, [source])
    finally:
        mail_center._ACTIVE_JSONL_LOCKS.discard(lock.resolve())
        lock.unlink(missing_ok=True)

    assert result["collected_count"] == 0
    assert result["error_count"] == 1
    assert result["errors"][0]["error_type"] == "source_outbox_locked"
    assert "Timed out waiting for JSONL lock" in result["errors"][0]["error"]
    assert not central_inbox_path(hub, source).exists()
    assert not (hub / "processed" / "mail" / "quarantine" / "malformed_jsonl.jsonl").exists()


def test_mail_doctor_reports_dirty_spool_and_rust_packet_issues(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    hub.mkdir()
    source.mkdir()
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Dirty doctor should catch duplicate rows.",
    )
    outbox = source / ".digital-asset" / "mail" / "outbox.jsonl"
    original = outbox.read_text(encoding="utf-8")
    outbox.write_text(original + original, encoding="utf-8")

    central = hub / "processed" / "mail" / "inbox" / "source.jsonl"
    central.parent.mkdir(parents=True)
    central.write_text("{bad-json}\n", encoding="utf-8")
    direct = hub / "processed" / "mail" / "inbox" / "direct.jsonl"
    direct.write_text(original, encoding="utf-8")

    mail_dir = hub / ".digital-asset" / "mail"
    mail_dir.mkdir(parents=True)
    stale_lock = mail_dir / ".outbox.jsonl.lock"
    stale_lock.write_text(json.dumps({"pid": 987654321, "created_at": "2026-07-04T00:00:00+00:00"}))
    old_time = os.path.getmtime(stale_lock) - 1_000
    os.utime(stale_lock, (old_time, old_time))
    (mail_dir / ".outbox.jsonl.tmp").write_text("partial", encoding="utf-8")

    rust_packet = hub / "mail" / "outbox" / "rust_rollout" / "non_logos" / "bad.json"
    rust_packet.parent.mkdir(parents=True)
    rust_packet.write_text('{"not": "a mail packet"}\n', encoding="utf-8")

    result = diagnose_mail_dirty_state(
        hub,
        [source],
        stale_lock_seconds=1.0,
    )
    issue_types = {issue["issue_type"] for issue in result["issues"]}
    observation_types = {item["observation_type"] for item in result["observations"]}

    assert result["dirty"] is True
    assert result["status"] == "blocked"
    assert result["action_summary"]["status"] == "blocked"
    assert result["action_summary"]["safe_to_collect"] is False
    assert result["action_summary"]["severity_counts"]["critical"] >= 1
    assert result["action_summary"]["severity_counts"]["high"] >= 1
    assert any(
        "re-collect from the source repo outbox" in item
        for item in result["action_summary"]["next_actions"]
    )
    assert "jsonl_lock_tombstone" in observation_types
    assert result["summary"]["lock_tombstone_observation_count"] == 1
    assert "atomic_temp_fragment" in issue_types
    assert "malformed_jsonl" in issue_types
    assert result["summary"]["source_outbox_duplicate_identity_count"] == 1
    assert any(
        item["observation_type"] == "source_outbox_duplicate_identity"
        for item in result["observations"]
    )
    assert "central_inbox_uncollected_row" in issue_types
    assert "rust_rollout_packet_invalid" in issue_types
    assert (
        result["write_target_guidance"]["repo_agents_write"] == ".digital-asset/mail/outbox.jsonl"
    )


def test_mail_doctor_blocks_unstable_source_outbox_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Moving outboxes should block storm doctor safety.",
    )
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    original_signature = mail_center._jsonl_file_signature
    calls = 0

    def unstable_signature(path: Path):
        nonlocal calls
        signature = original_signature(path)
        if path == outbox and signature is not None:
            calls += 1
            if calls > 1:
                return (signature[0] + calls, signature[1])
        return signature

    monkeypatch.setattr(mail_center, "_jsonl_file_signature", unstable_signature)

    result = diagnose_mail_dirty_state(hub, [repo])

    assert result["dirty"] is True
    assert result["status"] == "dirty_needs_review"
    assert result["action_summary"]["safe_to_collect"] is False
    assert result["summary"]["source_outbox_unstable_count"] == 1
    assert "source_outbox_unstable" in {issue["issue_type"] for issue in result["issues"]}


def test_mail_doctor_treats_malformed_mail_backup_as_hygiene_observation(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Live outbox should collect even if a malformed backup exists.",
    )
    backup = repo / ".digital-asset" / "mail" / "outbox.malformed-backup-20260702T221700Z.jsonl"
    backup.write_text('{"partial": true}\nnot-json\n', encoding="utf-8")

    doctor = diagnose_mail_dirty_state(hub, [repo])
    collected = collect_mail(hub, [repo])

    assert doctor["dirty"] is False
    assert doctor["summary"]["unexpected_repo_mail_jsonl_count"] == 1
    assert doctor["action_summary"]["safe_to_collect"] is True
    assert any(
        item["observation_type"] == "unexpected_repo_mail_jsonl" and item["filename"] == backup.name
        for item in doctor["observations"]
    )
    assert "malformed_jsonl" not in {issue["issue_type"] for issue in doctor["issues"]}
    assert collected["collected_count"] == 1


def test_cli_mail_route_blocks_when_dirty_state_is_detected(tmp_path: Path):
    hub = _make_hub(tmp_path / "dad")
    source = tmp_path / "source"
    source.mkdir()
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Wrong-box central row should block routing.",
    )
    packet = json.loads(
        (source / ".digital-asset" / "mail" / "outbox.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    central = hub / "processed" / "mail" / "inbox" / "direct.jsonl"
    central.parent.mkdir(parents=True)
    central.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    result = RUNNER.invoke(app, ["mail", "route", "--hub", str(hub)])

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["schema_version"] == "dad_mail_dirty_gate.v1"
    assert payload["operation"] == "mail route"
    assert payload["blocked"] is True
    assert payload["action_summary"]["safe_to_route"] is False
    assert not (hub / "processed" / "mail" / "outbox" / "routed.jsonl").exists()


def test_cli_mail_collect_allows_clean_repo_outbox_backlog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    source = tmp_path / "source"
    source.mkdir()
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="A clean source outbox should be collected normally.",
    )
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(source, "source")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    result = RUNNER.invoke(app, ["mail", "collect", "--repo", str(source), "--hub", str(hub)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["collected_count"] == 1
    assert central_inbox_path(hub, source, cfg.mail_repos).exists()


def test_cli_mail_collect_exits_nonzero_on_partial_collection_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    repo = tmp_path / "repo"
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Partial collection failures should not look green at CLI boundary.",
    )
    original_audit = mail_center._append_collection_audit
    calls = 0

    def flaky_audit(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("simulated collection audit timeout")
        return original_audit(*args, **kwargs)

    monkeypatch.setattr(mail_center, "_append_collection_audit", flaky_audit)
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(repo, "repo")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    result = RUNNER.invoke(app, ["mail", "collect", "--repo", str(repo), "--hub", str(hub)])
    payload = json.loads(result.output)

    assert result.exit_code == 2
    assert payload["collected_count"] == 1
    assert payload["error_count"] == 1
    assert "simulated collection audit timeout" in payload["errors"][0]["error"]


def test_mail_doctor_treats_lifecycle_copies_as_observations(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Lifecycle copies should remain audit trail, not dirty state.",
    )
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    packet = json.loads(outbox.read_text(encoding="utf-8").splitlines()[0])
    collected_packet = {
        **packet,
        "review_status": "collected_candidate",
        "source_provenance": {
            **packet["source_provenance"],
            "collected_at": "2026-07-04T23:59:00+00:00",
        },
    }

    central_inbox = hub / "processed" / "mail" / "inbox" / "repo.jsonl"
    central_inbox.parent.mkdir(parents=True)
    central_inbox.write_text(
        json.dumps(collected_packet) + "\n",
        encoding="utf-8",
    )
    _append_jsonl(
        hub / "processed" / "mail" / "archive" / "legacy_collection_allowlist.jsonl",
        {
            "mail_id": collected_packet["mail_id"],
            "dedupe_key": collected_packet["dedupe_key"],
            "record_hash": mail_center._mail_record_hash(collected_packet),
            "review_status": "reviewed_legacy",
            "reviewed_by": "test",
            "reason": "Lifecycle fixture predates collection-audit enforcement.",
        },
    )
    old_time = 1_700_000_000
    os.utime(central_inbox, (old_time, old_time))
    route_mail(hub)
    inbox = hub / ".digital-asset" / "mail" / "inbox.jsonl"
    inbox.parent.mkdir(parents=True)
    delivered_packet = {**packet, "review_status": "delivered_candidate"}
    inbox.write_text(json.dumps(delivered_packet) + "\n", encoding="utf-8")
    archive = hub / "processed" / "mail" / "archive" / "central_review_decisions.jsonl"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text(
        json.dumps({**packet, "review_status": "archived"}) + "\n",
        encoding="utf-8",
    )
    delivery_log = hub / "processed" / "mail" / "archive" / "delivery_log.jsonl"
    delivery_log.write_text(
        json.dumps(
            {
                "event_type": "delivered",
                "mail_id": packet["mail_id"],
                "dedupe_key": packet["dedupe_key"],
                "record_hash": mail_center._mail_record_hash(delivered_packet),
                "target_repo": "dad",
                "created_at": "2026-07-04T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = diagnose_mail_dirty_state(hub, [repo])

    assert result["dirty"] is False
    assert result["action_summary"]["safe_to_collect"] is True
    assert result["action_summary"]["safe_to_route"] is True
    assert result["action_summary"]["safe_to_deliver"] is True
    assert any(
        item["observation_type"] == "mail_packet_lifecycle_identity"
        for item in result["observations"]
    )


def test_mail_doctor_flags_fresh_central_inbox_row_without_collection_audit(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="A direct central inbox write should not look collected.",
    )
    packet = json.loads(
        (repo / ".digital-asset" / "mail" / "outbox.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    packet["review_status"] = "collected_candidate"
    packet["source_provenance"]["collected_at"] = "2026-07-05T01:00:00+00:00"
    central = hub / "processed" / "mail" / "inbox" / "repo.jsonl"
    central.parent.mkdir(parents=True)
    central.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    result = diagnose_mail_dirty_state(hub, [repo])

    assert "central_inbox_missing_collection_audit" in {
        issue["issue_type"] for issue in result["issues"]
    }
    assert result["summary"]["central_inbox_missing_collection_audit_count"] == 1
    assert result["dirty"] is True


def test_mail_doctor_flags_backdated_central_inbox_row_without_allowlist(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Backdated central inbox rows should not rely on self-declared collected_at.",
    )
    packet = json.loads(
        (repo / ".digital-asset" / "mail" / "outbox.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    packet["review_status"] = "collected_candidate"
    packet["source_provenance"]["collected_at"] = "2026-07-04T23:59:00+00:00"
    central = hub / "processed" / "mail" / "inbox" / "repo.jsonl"
    central.parent.mkdir(parents=True)
    central.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    result = diagnose_mail_dirty_state(hub, [repo])

    assert "central_inbox_missing_collection_audit" in {
        issue["issue_type"] for issue in result["issues"]
    }
    assert result["summary"]["legacy_collection_audit_gap_count"] == 1
    assert result["action_summary"]["status"] == "blocked"
    assert result["dirty"] is True


def test_mail_doctor_keeps_legacy_central_inbox_audit_gaps_as_observations(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Legacy central rows predate collection audit enforcement.",
    )
    packet = json.loads(
        (repo / ".digital-asset" / "mail" / "outbox.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    packet["review_status"] = "collected_candidate"
    packet["source_provenance"]["collected_at"] = "2026-07-04T23:59:00+00:00"
    central = hub / "processed" / "mail" / "inbox" / "repo.jsonl"
    central.parent.mkdir(parents=True)
    central.write_text(json.dumps(packet) + "\n", encoding="utf-8")
    _append_jsonl(
        hub / "processed" / "mail" / "archive" / "legacy_collection_allowlist.jsonl",
        {
            "mail_id": packet["mail_id"],
            "dedupe_key": packet["dedupe_key"],
            "record_hash": mail_center._mail_record_hash(packet),
            "review_status": "reviewed_legacy",
            "reviewed_by": "test",
            "reason": "Known fixture row predates collection-audit enforcement.",
        },
    )
    old_time = 1_700_000_000
    os.utime(central, (old_time, old_time))
    backup = repo / ".digital-asset" / "mail" / "outbox.repair-backup.jsonl"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text('{"backup": true}\n', encoding="utf-8")

    result = diagnose_mail_dirty_state(hub, [repo])

    assert result["dirty"] is False
    assert result["action_summary"]["status"] == "clean_with_legacy_observations"
    assert result["action_summary"]["legacy_observation_count"] == 1
    assert result["action_summary"]["mailbox_hygiene_observation_count"] == 1
    assert result["action_summary"]["safe_to_collect"] is True
    assert any(
        "legacy central inbox rows" in item for item in result["action_summary"]["next_actions"]
    )
    assert any(
        "backup or repair JSONL files" in item for item in result["action_summary"]["next_actions"]
    )
    assert result["summary"]["legacy_collection_audit_gap_count"] == 1
    assert any(
        item["observation_type"] == "reviewed_legacy_central_inbox_without_collection_audit"
        for item in result["observations"]
    )


def test_mail_doctor_does_not_write_quarantine_for_malformed_helper_logs(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()
    route_log = hub / "processed" / "mail" / "archive" / "route_log.jsonl"
    route_log.parent.mkdir(parents=True)
    route_log.write_text("{bad-route-log}\n", encoding="utf-8")
    central_inbox = hub / "processed" / "mail" / "inbox" / "bad.jsonl"
    central_inbox.parent.mkdir(parents=True)
    central_inbox.write_text("{bad-central-inbox}\n", encoding="utf-8")

    result = diagnose_mail_dirty_state(hub, [repo])

    assert result["dirty"] is True
    assert result["summary"]["malformed_jsonl_count"] == 2
    assert not (hub / "processed" / "mail" / "quarantine").exists()


def test_cli_mail_doctor_can_allowlist_reviewed_legacy_central_rows(tmp_path: Path):
    hub = _make_hub(tmp_path / "dad")
    repo = tmp_path / "repo"
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Operator-reviewed legacy rows can be allowlisted explicitly.",
    )
    packet = _jsonl(repo / ".digital-asset" / "mail" / "outbox.jsonl")[0]
    packet["review_status"] = "collected_candidate"
    packet["source_provenance"]["collected_at"] = "2026-07-04T23:59:00+00:00"
    central = hub / "processed" / "mail" / "inbox" / "repo.jsonl"
    central.parent.mkdir(parents=True)
    central.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    blocked = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--repo",
            str(repo),
            "--summary-only",
            "--fail-on-dirty",
            "--hub",
            str(hub),
        ],
    )
    repaired = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--repo",
            str(repo),
            "--summary-only",
            "--fail-on-dirty",
            "--allowlist-legacy-central-inbox",
            "--legacy-allowlist-ack",
            "reviewed pre-enforcement fixture row",
            "--hub",
            str(hub),
        ],
    )

    assert blocked.exit_code == 1
    assert repaired.exit_code == 0
    payload = json.loads(repaired.output)
    assert payload["status"] == "clean_with_legacy_observations"
    assert payload["legacy_allowlist_result"]["allowlisted_count"] == 1
    assert (hub / "processed" / "mail" / "archive" / "legacy_collection_allowlist.jsonl").exists()


def test_mail_doctor_reports_git_worktree_dirt_separately_from_mail_dirt(tmp_path: Path):
    hub = _make_hub(tmp_path / "dad")
    _init_git_repo(hub)
    source = tmp_path / "source"
    source.mkdir()
    packet = compose_mail(
        source,
        message_type="capability_suggestion",
        target_repo="repo",
        summary="Valid staged Rust rollout reference packet.",
    )["record"]
    packet["payload"]["delivery_status"] = "staged_not_deliverable"
    rust_reference = hub / "mail" / "outbox" / "rust_rollout" / "non_logos" / "repo.json"
    rust_reference.parent.mkdir(parents=True)
    rust_reference.write_text(json.dumps(packet) + "\n", encoding="utf-8")
    (hub / "docs").mkdir(exist_ok=True)
    (hub / "docs" / "note.md").write_text("ordinary buildout work\n", encoding="utf-8")

    result = diagnose_mail_dirty_state(hub)

    assert result["dirty"] is False
    assert result["spool_dirty"] is False
    assert result["worktree_dirty"] is True
    assert result["worktree_dirty_does_not_change_mail_dirty"] is True
    assert result["action_summary"]["safe_to_collect"] is True
    assert result["worktree_state"]["counts_by_category"]["rust_rollout_reference_snapshot"] == 1
    assert result["worktree_state"]["counts_by_category"]["dad_source_or_governance"] == 1
    assert any("reference-snapshot churn" in item for item in result["worktree_state"]["guidance"])
    assert any(
        "rust_rollout_snapshot_promotion.jsonl" in item
        for item in result["worktree_state"]["guidance"]
    )


def test_cli_mail_doctor_worktree_dirty_has_separate_fail_flag(tmp_path: Path):
    hub = _make_hub(tmp_path / "dad")
    _init_git_repo(hub)
    (hub / "docs").mkdir(exist_ok=True)
    (hub / "docs" / "dirty.md").write_text("not mail corruption\n", encoding="utf-8")

    mail_only = RUNNER.invoke(
        app,
        ["mail", "doctor", "--summary-only", "--fail-on-dirty", "--hub", str(hub)],
    )

    assert mail_only.exit_code == 0
    mail_only_payload = json.loads(mail_only.output)
    assert mail_only_payload["dirty"] is False
    assert mail_only_payload["worktree_dirty"] is True

    worktree_required_clean = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--summary-only",
            "--fail-on-worktree-dirty",
            "--hub",
            str(hub),
        ],
    )

    assert worktree_required_clean.exit_code == 1
    worktree_payload = json.loads(worktree_required_clean.output)
    assert worktree_payload["dirty"] is False
    assert worktree_payload["worktree_dirty"] is True


def test_cli_mail_storm_gate_defaults_to_all_and_allows_worktree_dirt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    _init_git_repo(hub)
    (hub / "docs").mkdir(exist_ok=True)
    (hub / "docs" / "dirty.md").write_text("not mail corruption\n", encoding="utf-8")
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(allowed, "allowed")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    result = RUNNER.invoke(app, ["mail", "storm-gate"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "dad_mail_storm_gate.v1"
    assert payload["gate_status"] == "mail_safe_worktree_dirty"
    assert payload["requested_repos"] == ["all"]
    assert payload["safe_for_mail_storm_operations"] is True
    assert payload["safe_for_ingest_operations"] is True
    assert payload["safe_for_delivery_operations"] is True
    assert payload["safe_to_collect"] is True
    assert payload["safe_to_route"] is True
    assert payload["safe_to_deliver"] is True
    assert payload["blocked_operation_classes"] == []
    assert payload["blocking_reasons"] == []
    assert payload["spool_dirty"] is False
    assert payload["worktree_dirty"] is True
    assert payload["repo_scope"]["storm_scope_verified"] is True
    assert "dad_source_or_governance" in payload["worktree_state"]["counts_by_category"]


def test_cli_mail_storm_gate_blocks_unreviewed_mailbox_coverage_gap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    allowed = tmp_path / "allowed"
    nested = tmp_path / "lawfirm-os" / "repos" / "intake-runtime"
    allowed.mkdir()
    nested.mkdir(parents=True)
    (nested / ".digital-asset" / "mail").mkdir(parents=True)
    (nested / ".digital-asset" / "mail" / "outbox.jsonl").write_text("", encoding="utf-8")
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[SimpleNamespace(enabled=True, path=tmp_path)],
        mail_repos=[_policy(allowed, "allowed")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    result = RUNNER.invoke(app, ["mail", "storm-gate"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["gate_status"] == "blocked_coverage_gap"
    assert payload["safe_for_mail_storm_operations"] is False
    assert payload["safe_for_ingest_operations"] is False
    assert payload["safe_for_delivery_operations"] is False
    assert payload["safe_to_collect"] is False
    assert payload["blocked_operation_classes"] == ["collect", "route", "deliver"]
    assert payload["blocking_reasons"] == ["coverage_gap"]
    assert payload["mailbox_coverage"]["unreviewed_mailbox_candidate_count"] == 1
    sample = payload["mailbox_coverage"]["unreviewed_mailbox_candidate_samples"][0]
    assert sample["path_ref"].startswith("repo-path-sha256:")
    assert "path" not in sample


def test_cli_mail_storm_gate_blocks_unreviewed_inbox_only_coverage_gap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    allowed = tmp_path / "allowed"
    nested = tmp_path / "lawfirm-os" / "repos" / "inbox-only-runtime"
    allowed.mkdir()
    nested.mkdir(parents=True)
    (nested / ".digital-asset" / "mail").mkdir(parents=True)
    (nested / ".digital-asset" / "mail" / "inbox.jsonl").write_text("", encoding="utf-8")
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[SimpleNamespace(enabled=True, path=tmp_path)],
        mail_repos=[_policy(allowed, "allowed")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    result = RUNNER.invoke(app, ["mail", "storm-gate"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["gate_status"] == "blocked_coverage_gap"
    assert payload["mailbox_coverage"]["unreviewed_mailbox_candidate_count"] == 1
    sample = payload["mailbox_coverage"]["unreviewed_mailbox_candidate_samples"][0]
    assert sample["has_inbox"] is True
    assert sample["has_outbox"] is False
    assert sample["path_ref"].startswith("repo-path-sha256:")
    assert "path" not in sample


def test_cli_mail_storm_gate_holds_delivery_for_write_protected_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    protected = tmp_path / "protected"
    protected.mkdir()
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[
            _policy(
                protected,
                "logos-scripture-graph",
                write_protected=True,
                write_protection_reason=(
                    r"C:\Users\lowel\OneDrive\Desktop\Git Projects"
                    r"\03_World_View\logos-scripture-graph-repo"
                ),
            )
        ],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    result = RUNNER.invoke(app, ["mail", "storm-gate", "--no-fail-on-blocked"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["gate_status"] == "mail_safe_delivery_policy_hold"
    assert payload["requested_operation"] == "all"
    assert payload["selected_operation_safe"] is False
    assert payload["spool_dirty"] is False
    assert payload["safe_to_collect"] is True
    assert payload["safe_to_route"] is True
    assert payload["safe_to_deliver"] is False
    assert payload["safe_for_mail_storm_operations"] is False
    assert payload["safe_for_ingest_operations"] is True
    assert payload["safe_for_delivery_operations"] is False
    assert payload["blocked_operation_classes"] == ["deliver"]
    assert payload["blocking_reasons"] == ["delivery_policy_hold"]
    assert "Use safe_for_ingest_operations" in payload["operation_safety_contract"]
    assert payload["delivery_policy"]["blocked_delivery_repo_count"] == 1
    assert payload["delivery_policy"]["blocked_delivery_repos"][0]["repo_ref"] == (
        "repo:logos-scripture-graph"
    )
    assert payload["delivery_policy"]["blocked_delivery_repos"][0][
        "write_protection_reason"
    ].startswith("path-sha256:")
    assert r"C:\Users" not in result.output
    assert "OneDrive" not in result.output

    ingest_result = RUNNER.invoke(
        app,
        ["mail", "storm-gate", "--operation", "ingest"],
    )
    ingest_payload = json.loads(ingest_result.output)

    assert ingest_result.exit_code == 0
    assert ingest_payload["gate_status"] == "mail_safe_delivery_policy_hold"
    assert ingest_payload["requested_operation"] == "ingest"
    assert ingest_payload["selected_operation_safe"] is True
    assert ingest_payload["safe_for_ingest_operations"] is True
    assert ingest_payload["safe_for_delivery_operations"] is False


def test_cli_mail_ingest_collects_and_routes_without_protected_delivery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    source = tmp_path / "source"
    protected = tmp_path / "protected"
    source.mkdir()
    protected.mkdir()
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo=str(protected),
        summary="Rust rollout lesson should land centrally before protected delivery review.",
    )
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[
            _policy(source, "source"),
            _policy(
                protected,
                "logos-scripture-graph",
                write_protected=True,
                write_protection_reason="explicit local-write approval required",
            ),
        ],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    result = RUNNER.invoke(app, ["mail", "ingest"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "dad_mail_ingest_result.v1"
    assert payload["requested_repos"] == ["all"]
    assert payload["delivery_performed"] is False
    assert payload["collect"]["collected_count"] == 1
    assert payload["route"]["routed_count"] == 1
    assert payload["route"]["outbox"] == "processed/mail/outbox/routed.jsonl"
    assert payload["delivery_policy"]["blocked_delivery_repo_count"] == 1
    assert payload["delivery_policy"]["blocked_delivery_repos"][0]["repo_ref"] == (
        "repo:logos-scripture-graph"
    )
    assert not (protected / ".digital-asset" / "mail" / "inbox.jsonl").exists()
    assert (hub / "processed" / "mail" / "inbox").exists()
    assert (hub / "processed" / "mail" / "outbox" / "routed.jsonl").exists()
    assert str(tmp_path) not in result.output


def test_collect_mail_uses_read_only_snapshot_for_write_protected_source(tmp_path: Path):
    hub = tmp_path / "dad"
    source = tmp_path / "protected-source"
    target = tmp_path / "target"
    hub.mkdir()
    source.mkdir()
    target.mkdir()
    compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo=str(target),
        summary="Protected source outbox should be readable without local lock writes.",
    )
    policies = [
        _policy(
            source,
            "logos-scripture-graph",
            write_protected=True,
            write_protection_reason="read-only protected repo",
        ),
        _policy(target, "target"),
    ]

    result = collect_mail(hub, [source], repo_policies=policies)

    assert result["collected_count"] == 1
    assert not (source / ".digital-asset" / "mail" / ".outbox.jsonl.lock").exists()
    central_rows = _jsonl(central_inbox_path(hub, source, policies))
    assert central_rows[0]["source_repo"] == "repo:logos-scripture-graph"


def test_cli_mail_repair_plan_reports_delivery_policy_hold_lane(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    protected = tmp_path / "protected"
    protected.mkdir()
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[
            _policy(
                protected,
                "logos-scripture-graph",
                delivery_allowed=False,
                write_protection_reason="delivery paused",
            )
        ],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    result = RUNNER.invoke(app, ["mail", "repair-plan"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["gate_status"] == "mail_safe_delivery_policy_hold"
    assert payload["requested_operation"] == "all"
    assert payload["selected_operation_safe"] is False
    assert payload["safe_to_deliver"] is False
    assert payload["safe_for_ingest_operations"] is True
    assert payload["safe_for_delivery_operations"] is False
    assert payload["blocked_operation_classes"] == ["deliver"]
    assert payload["blocking_reasons"] == ["delivery_policy_hold"]
    assert payload["recommended_order"] == ["delivery-policy-hold-review"]
    lane = payload["repair_lanes"][0]
    assert lane["issue_type"] == "delivery_policy_hold"
    assert lane["samples"][0]["repo_ref"] == "repo:logos-scripture-graph"

    ingest_result = RUNNER.invoke(
        app,
        ["mail", "repair-plan", "--operation", "ingest", "--fail-on-blocked"],
    )
    ingest_payload = json.loads(ingest_result.output)

    assert ingest_result.exit_code == 0
    assert ingest_payload["requested_operation"] == "ingest"
    assert ingest_payload["selected_operation_safe"] is True
    assert ingest_payload["safe_for_ingest_operations"] is True
    assert ingest_payload["safe_for_delivery_operations"] is False


def test_mailbox_coverage_warns_when_reviewed_repo_was_not_checked(tmp_path: Path):
    hub = _make_hub(tmp_path / "dad")
    checked = tmp_path / "checked"
    omitted = tmp_path / "omitted"
    checked.mkdir()
    omitted.mkdir()
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(checked, "checked"), _policy(omitted, "omitted")],
    )

    coverage = _mailbox_coverage_summary(cfg, [checked])

    assert coverage["unreviewed_mailbox_candidate_count"] == 0
    assert coverage["reviewed_enabled_not_checked_count"] == 1
    assert coverage["warning"]
    sample = coverage["reviewed_enabled_not_checked_samples"][0]
    assert sample["path_ref"].startswith("repo-path-sha256:")
    assert "path" not in sample


def test_cli_mail_storm_gate_blocks_wrong_box_central_inbox_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    allowed = tmp_path / "allowed"
    source = tmp_path / "source"
    allowed.mkdir()
    source.mkdir()
    wrong_box_record = compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Repo agent wrote to the DAD central inbox directly.",
    )["record"]
    central_inbox = hub / "processed" / "mail" / "inbox" / "source.jsonl"
    central_inbox.parent.mkdir(parents=True)
    central_inbox.write_text(json.dumps(wrong_box_record) + "\n", encoding="utf-8")
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(allowed, "allowed")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    result = RUNNER.invoke(app, ["mail", "storm-gate"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["gate_status"] == "blocked_mail_dirty"
    assert payload["spool_dirty"] is True
    assert payload["requires_human_review"] is True
    assert payload["mail_summary"]["issue_count"] > 0
    assert payload["safe_for_mail_storm_operations"] is False


def test_cli_mail_repair_plan_reports_ordered_lanes_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    target_repo = tmp_path / "target"
    source_repo = tmp_path / "source"
    target_repo.mkdir()
    source_repo.mkdir()
    wrong_box_record = compose_mail(
        source_repo,
        message_type="lesson_suggestion",
        target_repo=str(target_repo),
        summary="Repo inbox direct write should be repair-planned, not trusted.",
    )["record"]
    target_inbox = target_repo / ".digital-asset" / "mail" / "inbox.jsonl"
    target_inbox.parent.mkdir(parents=True)
    target_inbox.write_text(
        json.dumps({**wrong_box_record, "review_status": "delivered_candidate"}) + "\n",
        encoding="utf-8",
    )
    rust_packet = compose_mail(
        source_repo,
        message_type="capability_suggestion",
        target_repo="repo:target",
        summary="Rust rollout tracked and staged packets have drifted.",
    )["record"]
    rust_packet["payload"]["delivery_status"] = "staged_not_deliverable"
    rust_packet["payload"]["rust_rollout_packet_type"] = "rust_buildout_notice"
    rust_packet["payload"]["rollout_mode"] = "staged_rollout"
    rust_packet["payload"]["rust_rollout_revision_id"] = "tracked-reference-revision"
    tracked_packet = hub / "mail" / "outbox" / "rust_rollout" / "non_logos" / "target.json"
    staged_packet = (
        hub / "processed" / "mail" / "staged" / "rust_rollout" / "non_logos" / "target.json"
    )
    tracked_packet.parent.mkdir(parents=True)
    staged_packet.parent.mkdir(parents=True)
    tracked_packet.write_text(json.dumps(rust_packet) + "\n", encoding="utf-8")
    staged_variant = {
        **rust_packet,
        "mail_id": "dad:mail:staged-rust-rollout-conflict",
        "dedupe_key": f"{rust_packet['dedupe_key']}:staged",
        "payload": {
            **rust_packet["payload"],
            "rust_rollout_revision_id": "ignored-staging-revision",
        },
    }
    staged_packet.write_text(json.dumps(staged_variant) + "\n", encoding="utf-8")
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(target_repo, "target")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    result = RUNNER.invoke(app, ["mail", "repair-plan"])

    assert result.exit_code == 0
    assert str(tmp_path) not in result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == "dad_mail_storm_repair_plan.v1"
    assert payload["status"] == "repair_plan_required"
    assert payload["gate_status"] == "blocked_mail_dirty"
    assert payload["dirty_state_fingerprint"].startswith("sha256:")
    assert payload["writes_performed"] is False
    assert payload["repair_execution_performed"] is False
    assert payload["repair_automation_allowed"] is False
    assert payload["safe_to_collect"] is False
    assert payload["safe_to_route"] is False
    assert payload["safe_to_deliver"] is False
    assert payload["operator_review_required"] is True
    assert payload["issue_counts_by_type"]["repo_inbox_without_delivery_log"] == 1
    assert payload["issue_counts_by_type"]["rust_rollout_semantic_identity_conflict"] == 1
    assert payload["recommended_order"][0] == "repo-inbox-delivery-audit-repair"
    assert "rust-rollout-packet-resync" in payload["recommended_order"]
    assert payload["review_queue"]["schema_version"] == "dad_mail_storm_repair_review_queue.v1"
    assert payload["review_queue"]["item_count"] == 2
    assert payload["review_queue"]["raw_payload_copied"] is False
    wrong_box_item = next(
        item
        for item in payload["review_queue"]["items"]
        if item["issue_type"] == "repo_inbox_without_delivery_log"
    )
    assert wrong_box_item["raw_payload_copied"] is False
    assert wrong_box_item["record_hash"]
    assert wrong_box_item["dedupe_key"] == wrong_box_record["dedupe_key"]
    assert wrong_box_item["message_type"] == "lesson_suggestion"
    rust_lane = next(
        lane for lane in payload["repair_lanes"] if lane["lane_id"] == "rust-rollout-packet-resync"
    )
    assert rust_lane["review_required_before_running_examples"] is True
    assert "suggested_review_commands" not in rust_lane
    assert "post_review_execution_examples" in rust_lane
    assert "diagnostic_doctor_summary_only_not_an_exit_gate" in payload["operator_commands"]
    assert "fail_closed_doctor" in payload["operator_commands"]
    assert not (hub / "processed" / "mail" / "quarantine").exists()
    assert not (hub / "processed" / "mail" / "archive" / "dirty_gate_bypass.jsonl").exists()

    blocked = RUNNER.invoke(app, ["mail", "repair-plan", "--fail-on-blocked"])
    assert blocked.exit_code == 1
    blocked_payload = json.loads(blocked.output)
    assert blocked_payload["safe_for_mail_storm_operations"] is False
    assert blocked_payload["writes_performed"] is False
    assert not (hub / "processed" / "mail" / "quarantine").exists()


def test_cli_mail_repair_plan_blocks_coverage_gap_without_local_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    reviewed = tmp_path / "reviewed"
    unreviewed = tmp_path / "nested" / "repo"
    reviewed.mkdir()
    unreviewed.mkdir(parents=True)
    (unreviewed / ".digital-asset" / "mail").mkdir(parents=True)
    (unreviewed / ".digital-asset" / "mail" / "outbox.jsonl").write_text("", encoding="utf-8")
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[SimpleNamespace(enabled=True, path=tmp_path)],
        mail_repos=[_policy(reviewed, "reviewed")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    result = RUNNER.invoke(app, ["mail", "repair-plan"])

    assert result.exit_code == 0
    assert str(tmp_path) not in result.output
    payload = json.loads(result.output)
    assert payload["gate_status"] == "blocked_coverage_gap"
    assert payload["safe_for_mail_storm_operations"] is False
    assert payload["recommended_order"][0] == "mailbox-coverage-review"
    sample = payload["repair_lanes"][0]["samples"]["unreviewed_mailbox_candidate_samples"][0]
    assert sample["path_ref"].startswith("repo-path-sha256:")
    assert "path" not in sample


def test_cli_mail_repair_plan_write_report_persists_operator_packet_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    reviewed = tmp_path / "reviewed"
    unreviewed = tmp_path / "nested" / "repo"
    reviewed.mkdir()
    unreviewed.mkdir(parents=True)
    (unreviewed / ".digital-asset" / "mail").mkdir(parents=True)
    (unreviewed / ".digital-asset" / "mail" / "outbox.jsonl").write_text("", encoding="utf-8")
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[SimpleNamespace(enabled=True, path=tmp_path)],
        mail_repos=[_policy(reviewed, "reviewed")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    result = RUNNER.invoke(app, ["mail", "repair-plan", "--write-report"])

    assert result.exit_code == 0
    assert str(tmp_path) not in result.output
    payload = json.loads(result.output)
    report_write = payload["report_write"]
    assert report_write["report_writes_performed"] is True
    assert report_write["repair_execution_performed"] is False
    assert report_write["json"].startswith("processed/reports/mail_storm_repair/")
    assert report_write["markdown"].startswith("processed/reports/mail_storm_repair/")
    assert report_write["latest_json"] == "processed/reports/mail_storm_repair/latest.json"
    assert report_write["latest_markdown"] == "processed/reports/mail_storm_repair/latest.md"

    json_path = hub / report_write["json"]
    markdown_path = hub / report_write["markdown"]
    latest_json_path = hub / report_write["latest_json"]
    latest_markdown_path = hub / report_write["latest_markdown"]
    assert json_path.exists()
    assert markdown_path.exists()
    assert latest_json_path.exists()
    assert latest_markdown_path.exists()
    stored = json.loads(json_path.read_text(encoding="utf-8"))
    latest = json.loads(latest_json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert stored["schema_version"] == "dad_mail_storm_repair_plan.v1"
    assert stored["dirty_state_fingerprint"].startswith("sha256:")
    assert latest["dirty_state_fingerprint"] == stored["dirty_state_fingerprint"]
    assert latest["latest_pointer"]["source_report"] == report_write["json"]
    assert stored["writes_performed"] is False
    assert stored["repair_execution_performed"] is False
    assert stored["review_queue"]["raw_payload_copied"] is False
    assert stored["report_packet"]["report_writes_performed"] is True
    assert "operator evidence only" in markdown
    assert "operator evidence only" in latest_markdown_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in json_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in markdown
    assert str(tmp_path) not in latest_json_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in latest_markdown_path.read_text(encoding="utf-8")
    assert not (hub / "processed" / "mail" / "quarantine").exists()
    assert not (hub / "processed" / "mail" / "outbox" / "routed.jsonl").exists()


def test_cli_mail_doctor_summary_reports_hub_only_scope(tmp_path: Path):
    hub = _make_hub(tmp_path / "dad")

    result = RUNNER.invoke(
        app,
        ["mail", "doctor", "--summary-only", "--fail-on-dirty", "--hub", str(hub)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["repo_scope"]["external_repo_mailboxes_checked"] is False
    assert payload["repo_scope"]["included_repo_count"] == 0
    assert payload["repo_scope"]["storm_scope_verified"] is False
    assert payload["action_summary"]["safe_for_mail_storm_operations"] is False
    assert "Pass --repo all" in payload["repo_scope"]["warning"]


def test_cli_mail_doctor_fail_on_coverage_gap_rejects_unchecked_reviewed_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _make_hub(tmp_path / "dad")
    checked = tmp_path / "checked"
    checked.mkdir()
    cfg = SimpleNamespace(
        repo_root=hub,
        local_sources=[],
        mail_repos=[_policy(checked, "checked")],
    )
    monkeypatch.setattr(cli_module, "_cfg", lambda *args, **kwargs: cfg)

    def fake_coverage(*args, **kwargs):
        return {
            "schema_version": "dad_mailbox_coverage.v1",
            "candidate_count": 1,
            "reviewed_checked_count": 0,
            "unreviewed_mailbox_candidate_count": 0,
            "reviewed_enabled_not_checked_count": 1,
            "unreviewed_mailbox_candidate_samples": [],
            "reviewed_enabled_not_checked_samples": [],
            "local_paths_included": False,
            "warning": "reviewed enabled mail.repos were not included",
            "authority_boundary": "test",
        }

    monkeypatch.setattr(cli_module, "_mailbox_coverage_summary", fake_coverage)

    result = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--repo",
            "all",
            "--summary-only",
            "--fail-on-coverage-gap",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["dirty"] is False
    assert payload["mailbox_coverage"]["reviewed_enabled_not_checked_count"] == 1


def test_mail_doctor_scope_counts_selected_repos(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()

    result = diagnose_mail_dirty_state(hub, [repo])

    assert result["repo_scope"]["external_repo_mailboxes_checked"] is True
    assert result["repo_scope"]["included_repo_count"] == 1
    assert result["repo_scope"]["warning"] == ""


def test_cli_mail_doctor_fail_on_worktree_dirty_fails_closed_without_git(tmp_path: Path):
    hub = _make_hub(tmp_path / "dad")

    result = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--summary-only",
            "--fail-on-worktree-dirty",
            "--hub",
            str(hub),
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["dirty"] is False
    assert payload["worktree_dirty"] is False
    assert payload["worktree_state"]["status"] == "not_git_worktree"


def test_mail_doctor_flags_wrong_target_inbox_even_when_mail_id_was_delivered(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    correct_target = tmp_path / "correct"
    wrong_target = tmp_path / "wrong"
    source = tmp_path / "source"
    hub.mkdir()
    correct_target.mkdir()
    wrong_target.mkdir()
    source.mkdir()
    packet = compose_mail(
        source,
        message_type="lesson_suggestion",
        target_repo=str(correct_target),
        summary="A copied inbox row should not be trusted in the wrong target.",
    )["record"]
    inbox = wrong_target / ".digital-asset" / "mail" / "inbox.jsonl"
    inbox.parent.mkdir(parents=True)
    inbox.write_text(
        json.dumps({**packet, "review_status": "delivered_candidate"}) + "\n",
        encoding="utf-8",
    )
    delivery_log = hub / "processed" / "mail" / "archive" / "delivery_log.jsonl"
    delivery_log.parent.mkdir(parents=True)
    delivery_log.write_text(
        json.dumps(
            {
                "event_type": "delivered",
                "mail_id": packet["mail_id"],
                "target_repo": str(correct_target),
                "created_at": "2026-07-05T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = diagnose_mail_dirty_state(hub, [correct_target, wrong_target])

    assert result["dirty"] is True
    issue = next(
        item for item in result["issues"] if item["issue_type"] == "repo_inbox_without_delivery_log"
    )
    assert issue["mail_id"] == packet["mail_id"]
    assert issue["expected_target_repo"]


def test_mail_doctor_treats_matching_rust_staging_and_reference_as_observation(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    hub.mkdir()
    source.mkdir()
    packet = compose_mail(
        source,
        message_type="capability_suggestion",
        target_repo="repo",
        summary="A staged Rust rollout packet may mirror a tracked reference snapshot.",
    )["record"]
    packet["payload"]["delivery_status"] = "staged_not_deliverable"
    packet["payload"]["rust_rollout_packet_type"] = "rust_buildout_notice"
    packet["payload"]["rollout_mode"] = "staged_rollout"
    tracked = hub / "mail" / "outbox" / "rust_rollout" / "non_logos" / "repo.json"
    staged = hub / "processed" / "mail" / "staged" / "rust_rollout" / "non_logos" / "repo.json"
    tracked.parent.mkdir(parents=True)
    staged.parent.mkdir(parents=True)
    tracked.write_text(json.dumps(packet) + "\n", encoding="utf-8")
    staged.write_text(
        json.dumps(
            {
                **packet,
                "mail_id": "dad:mail:staged-rust-rollout-observation",
                "dedupe_key": f"{packet['dedupe_key']}:staged",
                "payload": {
                    **packet["payload"],
                    "packet_identity_basis": "staged metadata differs from old snapshot",
                    "rust_rollout_revision_id": "dad:rust-rollout-revision:test",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = diagnose_mail_dirty_state(hub)

    assert result["dirty"] is False
    assert result["action_summary"]["safe_to_collect"] is True
    assert "rust_rollout_semantic_identity_conflict" not in {
        item["issue_type"] for item in result["issues"]
    }
    assert "rust_rollout_staged_reference_semantic_pair" in {
        item["observation_type"] for item in result["observations"]
    }


def test_mail_doctor_flags_divergent_rust_staging_and_reference_content(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    hub.mkdir()
    source.mkdir()
    packet = compose_mail(
        source,
        message_type="capability_suggestion",
        target_repo="repo",
        summary="A staged Rust rollout packet may diverge from a tracked snapshot.",
    )["record"]
    packet["payload"]["delivery_status"] = "staged_not_deliverable"
    packet["payload"]["rust_rollout_packet_type"] = "rust_buildout_notice"
    packet["payload"]["rollout_mode"] = "staged_rollout"
    tracked = hub / "mail" / "outbox" / "rust_rollout" / "non_logos" / "repo.json"
    staged = hub / "processed" / "mail" / "staged" / "rust_rollout" / "non_logos" / "repo.json"
    tracked.parent.mkdir(parents=True)
    staged.parent.mkdir(parents=True)
    tracked.write_text(json.dumps(packet) + "\n", encoding="utf-8")
    staged.write_text(
        json.dumps(
            {
                **packet,
                "mail_id": "dad:mail:staged-rust-rollout-divergent",
                "dedupe_key": f"{packet['dedupe_key']}:staged",
                "payload": {
                    **packet["payload"],
                    "summary": "Divergent staged payload with no revision marker.",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = diagnose_mail_dirty_state(hub)

    assert result["dirty"] is True
    issue = next(
        item
        for item in result["issues"]
        if item["issue_type"] == "rust_rollout_semantic_identity_conflict"
    )
    assert len(issue["revision_ids"]) == 0
    assert len(issue["semantic_content_hashes"]) == 2


def test_mail_doctor_duplicate_rust_rollout_packet_identity_is_not_clean(
    tmp_path: Path,
):
    hub = tmp_path / "dad"
    source = tmp_path / "source"
    hub.mkdir()
    source.mkdir()
    packet = compose_mail(
        source,
        message_type="capability_suggestion",
        target_repo="repo",
        summary="Duplicate Rust rollout packet identities should require review.",
    )["record"]
    packet["payload"]["delivery_status"] = "staged_not_deliverable"
    first = hub / "mail" / "outbox" / "rust_rollout" / "non_logos" / "one.json"
    second = hub / "mail" / "outbox" / "rust_rollout" / "non_logos" / "two.json"
    first.parent.mkdir(parents=True)
    first.write_text(json.dumps(packet) + "\n", encoding="utf-8")
    second.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    result = diagnose_mail_dirty_state(hub)

    assert result["dirty"] is True
    assert result["status"] == "dirty_needs_review"
    assert result["action_summary"]["safe_to_collect"] is False
    assert "rust_rollout_duplicate_packet_identity" in {
        item["issue_type"] for item in result["issues"]
    }


def test_rust_structural_clean_signal_does_not_override_mail_doctor_semantics(
    monkeypatch,
    tmp_path: Path,
):
    hub = _make_hub(tmp_path / "dad")
    source = tmp_path / "source"
    source.mkdir()
    packet = compose_mail(
        source,
        message_type="capability_suggestion",
        target_repo="repo",
        summary="Rust structural checks can be clean while mail semantics still block.",
    )["record"]
    packet["payload"]["delivery_status"] = "staged_not_deliverable"
    first = hub / "mail" / "outbox" / "rust_rollout" / "non_logos" / "one.json"
    second = hub / "mail" / "outbox" / "rust_rollout" / "non_logos" / "two.json"
    first.parent.mkdir(parents=True)
    first.write_text(json.dumps(packet) + "\n", encoding="utf-8")
    second.write_text(json.dumps(packet) + "\n", encoding="utf-8")

    rust_calls: list[dict[str, object]] = []

    def clean_rust_probe(**kwargs):
        rust_calls.append(kwargs)
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
                "issue_count": 0,
                "rust_packet_count": 2,
                "issue_samples": [],
                "no_mutation_performed": True,
                "authority_boundary": "Python mail doctor remains the authoritative gate.",
                "authoritative_gate": "mail doctor",
                "semantic_checks_not_performed": [
                    "delivery log hash verification",
                    "Rust rollout packet semantic identity comparison",
                ],
            },
            summary_valid=True,
            summary_validation_errors=[],
        )

    monkeypatch.setattr(cli_module, "run_dad_mail_spool_check", clean_rust_probe)

    rust_probe = RUNNER.invoke(app, ["rust", "mail-spool-check", "--hub", str(hub)])
    rust_payload = json.loads(rust_probe.output)
    doctor = diagnose_mail_dirty_state(hub)

    assert rust_probe.exit_code == 0
    assert rust_calls
    assert rust_calls[0]["roots"][2] == hub / "mail" / "outbox" / "rust_rollout"
    assert rust_payload["summary"]["issue_count"] == 0
    assert rust_payload["summary"]["mail_spool_structural_clean"] is True
    assert rust_payload["summary"]["structural_spool_check_only"] is True
    assert rust_payload["summary"]["mail_storm_gate_satisfied"] is False
    assert rust_payload["scope"]["structural_spool_check_only"] is True
    assert rust_payload["scope"]["mail_storm_gate_satisfied"] is False
    assert doctor["dirty"] is True
    assert doctor["action_summary"]["safe_to_route"] is False
    assert "rust_rollout_duplicate_packet_identity" in {
        item["issue_type"] for item in doctor["issues"]
    }


def test_mail_doctor_flags_external_repo_inbox_without_delivery_log(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "external" / "repo"
    hub.mkdir()
    repo.mkdir(parents=True)
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="External repo inbox writes should still be classified as inbox.",
    )
    packet = json.loads(
        (repo / ".digital-asset" / "mail" / "outbox.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    inbox = repo / ".digital-asset" / "mail" / "inbox.jsonl"
    inbox.write_text(
        json.dumps({**packet, "review_status": "delivered_candidate"}) + "\n",
        encoding="utf-8",
    )

    result = diagnose_mail_dirty_state(hub, [repo])

    assert "repo_inbox_without_delivery_log" in {issue["issue_type"] for issue in result["issues"]}
    assert result["summary"]["repo_inbox_without_delivery_log_count"] == 1


def test_mail_doctor_flags_repo_inbox_without_delivery_log(tmp_path: Path):
    hub = tmp_path / "dad"
    repo = tmp_path / "repo"
    hub.mkdir()
    repo.mkdir()
    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Direct inbox writes should be suspicious.",
    )
    packet = json.loads(
        (repo / ".digital-asset" / "mail" / "outbox.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    inbox = hub / ".digital-asset" / "mail" / "inbox.jsonl"
    inbox.parent.mkdir(parents=True)
    inbox.write_text(
        json.dumps({**packet, "review_status": "delivered_candidate"}) + "\n",
        encoding="utf-8",
    )

    result = diagnose_mail_dirty_state(hub, [repo])

    assert "repo_inbox_without_delivery_log" in {issue["issue_type"] for issue in result["issues"]}
    assert result["summary"]["repo_inbox_without_delivery_log_count"] == 1


def test_mail_doctor_repairs_only_stale_locks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hub = tmp_path / "dad"
    mailbox = hub / ".digital-asset" / "mail"
    mailbox.mkdir(parents=True)
    stale_lock = mailbox / ".outbox.jsonl.lock"
    stale_lock.write_text(json.dumps({"pid": 987654321, "created_at": "2026-07-04T00:00:00+00:00"}))
    active_lock = mailbox / ".inbox.jsonl.lock"
    active_lock.write_text(
        json.dumps({"pid": os.getpid(), "created_at": "2026-07-04T00:00:00+00:00"})
    )
    old_time = os.path.getmtime(stale_lock) - 1_000
    os.utime(stale_lock, (old_time, old_time))
    monkeypatch.setattr(mail_center, "_jsonl_lock_pid_is_alive", lambda pid: pid == os.getpid())
    mail_center._ACTIVE_JSONL_LOCKS.add(active_lock.resolve())

    try:
        result = diagnose_mail_dirty_state(
            hub,
            repair_stale_locks=True,
            stale_lock_seconds=1.0,
        )
    finally:
        mail_center._ACTIVE_JSONL_LOCKS.discard(active_lock.resolve())

    assert result["summary"]["repaired_count"] == 1
    assert result["summary"]["lock_issue_count"] == 1
    assert result["dirty"] is True
    assert not stale_lock.exists()
    assert active_lock.exists()


def test_mail_doctor_treats_unremovable_dead_lock_as_nonblocking_tombstone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = tmp_path / "dad"
    mailbox = hub / ".digital-asset" / "mail"
    mailbox.mkdir(parents=True)
    dead_lock = mailbox / ".outbox.jsonl.lock"
    dead_lock.write_text(
        json.dumps({"pid": 987654321, "created_at": "2026-07-04T00:00:00+00:00"}),
        encoding="utf-8",
    )
    original_unlink = Path.unlink

    def blocked_unlink(self: Path, *args, **kwargs):
        if self == dead_lock:
            raise PermissionError("persistent lock removal denial")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(mail_center.Path, "unlink", blocked_unlink)
    monkeypatch.setattr(mail_center, "_jsonl_lock_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(mail_center.time, "sleep", lambda _seconds: None)

    result = diagnose_mail_dirty_state(
        hub,
        repair_stale_locks=True,
        stale_lock_seconds=999.0,
    )

    assert result["dirty"] is False
    assert result["summary"]["lock_issue_count"] == 0
    assert result["summary"]["lock_tombstone_observation_count"] == 1
    assert result["summary"]["repaired_count"] == 1
    assert result["repaired"][0]["removed"] is False
    assert dead_lock.exists()
    observation = next(
        item
        for item in result["observations"]
        if item["observation_type"] == "jsonl_lock_tombstone"
    )
    assert observation["repair_attempted"] is True
    assert observation["repair_removed"] is False
    assert observation["status"] == "dead_owner"


def test_mail_doctor_repairs_stale_temp_fragments_only_when_requested(tmp_path: Path):
    hub = tmp_path / "dad"
    mailbox = hub / ".digital-asset" / "mail"
    mailbox.mkdir(parents=True)
    stale_temp = mailbox / ".outbox.jsonl.tmp"
    stale_temp.write_text("partial", encoding="utf-8")
    old_time = os.path.getmtime(stale_temp) - 1_000
    os.utime(stale_temp, (old_time, old_time))

    read_only = diagnose_mail_dirty_state(hub, stale_lock_seconds=1.0)

    assert read_only["summary"]["temp_fragment_count"] == 1
    assert stale_temp.exists()

    repaired = diagnose_mail_dirty_state(
        hub,
        repair_temp_fragments=True,
        stale_lock_seconds=1.0,
    )

    assert repaired["summary"]["repaired_count"] == 1
    assert repaired["summary"]["temp_fragment_count"] == 0
    assert repaired["dirty"] is False
    assert not stale_temp.exists()


def test_mail_doctor_treats_unremovable_stale_temp_as_nonblocking_tombstone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = tmp_path / "dad"
    mailbox = hub / ".digital-asset" / "mail"
    mailbox.mkdir(parents=True)
    stale_temp = mailbox / ".outbox.jsonl.tmp"
    stale_temp.write_text("partial", encoding="utf-8")
    old_time = os.path.getmtime(stale_temp) - 1_000
    os.utime(stale_temp, (old_time, old_time))
    original_unlink = Path.unlink

    def blocked_unlink(self: Path, *args, **kwargs):
        if self == stale_temp:
            raise PermissionError("persistent temp fragment removal denial")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(mail_center.Path, "unlink", blocked_unlink)

    result = diagnose_mail_dirty_state(
        hub,
        repair_temp_fragments=True,
        stale_lock_seconds=1.0,
    )

    assert result["dirty"] is False
    assert result["summary"]["temp_fragment_count"] == 0
    assert result["summary"]["repaired_count"] == 1
    assert stale_temp.exists()
    observation = next(
        item
        for item in result["observations"]
        if item["observation_type"] == "atomic_temp_fragment_tombstone"
    )
    assert observation["repair_attempted"] is True
    assert observation["repair_removed"] is False


def test_mail_doctor_treats_last_checked_temp_as_nonblocking_metadata(tmp_path: Path):
    hub = tmp_path / "dad"
    mailbox = hub / ".digital-asset" / "mail"
    mailbox.mkdir(parents=True)
    metadata_temp = mailbox / ".last_checked.json.tmp"
    metadata_temp.write_text("partial", encoding="utf-8")

    result = diagnose_mail_dirty_state(hub, stale_lock_seconds=1.0)

    assert result["dirty"] is False
    assert result["summary"]["temp_fragment_count"] == 0
    assert metadata_temp.exists()
    assert any(
        item["observation_type"] == "metadata_atomic_temp_fragment"
        and item["path"] == ".digital-asset/mail/.last_checked.json.tmp"
        for item in result["observations"]
    )


def test_cli_mail_doctor_repaired_stale_temp_can_pass_fail_on_dirty(tmp_path: Path):
    hub = _make_hub(tmp_path / "dad")
    mailbox = hub / ".digital-asset" / "mail"
    mailbox.mkdir(parents=True)
    stale_temp = mailbox / ".outbox.jsonl.tmp"
    stale_temp.write_text("partial", encoding="utf-8")
    old_time = os.path.getmtime(stale_temp) - 1_000
    os.utime(stale_temp, (old_time, old_time))

    repaired = RUNNER.invoke(
        app,
        [
            "mail",
            "doctor",
            "--summary-only",
            "--fail-on-dirty",
            "--repair-temp-fragments",
            "--stale-lock-seconds",
            "1",
            "--hub",
            str(hub),
        ],
    )

    assert repaired.exit_code == 0
    payload = json.loads(repaired.output)
    assert payload["dirty"] is False
    assert payload["summary"]["repaired_count"] == 1
    assert not stale_temp.exists()


def test_missing_digest_status_is_stale_without_writing(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    status = mail_digest_status(repo)

    assert status == {"status": "missing", "stale": True, "last_checked_at": None}
    assert not (repo / ".digital-asset").exists()


def test_invalid_naive_and_future_digest_status_are_stale(tmp_path: Path):
    repo = tmp_path / "repo"
    mailbox = repo / ".digital-asset" / "mail"
    mailbox.mkdir(parents=True)
    last_checked = mailbox / "last_checked.json"

    last_checked.write_text("not-json", encoding="utf-8")
    assert mail_digest_status(repo)["status"] == "invalid"
    assert mail_digest_status(repo)["stale"] is True

    last_checked.write_text('{"last_checked_at":"2026-06-30T10:00:00"}', encoding="utf-8")
    naive = mail_digest_status(repo, now="2026-06-30T11:00:00+00:00")
    assert naive["status"] == "invalid"
    assert naive["stale"] is True

    last_checked.write_text(
        '{"last_checked_at":"2026-07-01T10:00:00+00:00"}',
        encoding="utf-8",
    )
    future = mail_digest_status(repo, now="2026-06-30T11:00:00+00:00")
    assert future["status"] == "future"
    assert future["stale"] is True


def test_symlinked_mailbox_escape_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    outside = tmp_path / "outside-mail"
    repo.mkdir()
    outside.mkdir()
    (repo / ".digital-asset").mkdir()
    try:
        (repo / ".digital-asset" / "mail").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(ValueError, match="escapes repository boundary"):
        compose_mail(
            repo,
            message_type="lesson_suggestion",
            target_repo="central_only",
            summary="Should fail before writing outside repo.",
        )
