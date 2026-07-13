from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from digital_asset_directory import cli


def test_approval_trust_and_attempts_cli_remain_non_authoritative(
    tmp_path: Path, monkeypatch
) -> None:
    runner = CliRunner()
    monkeypatch.setattr(
        cli,
        "_cfg",
        lambda *_args, **_kwargs: SimpleNamespace(repo_root=tmp_path),
    )

    trust = runner.invoke(cli.app, ["os", "approval-trust"])
    assert trust.exit_code == 0
    trust_payload = json.loads(trust.output)
    assert trust_payload["status"] == "candidate_deny_all"
    assert trust_payload["root_anchor_status"] == "unanchored_shadow"
    assert trust_payload["key_count"] == 0
    assert trust_payload["private_key_count"] == 0
    assert trust_payload["real_execution_authority"] is False

    attempts = runner.invoke(cli.app, ["os", "attempts"])
    assert attempts.exit_code == 0
    attempt_payload = json.loads(attempts.output)
    assert attempt_payload["status"] == "generated_candidate"
    assert attempt_payload["executor"]["available"] is False
    assert attempt_payload["executor"]["dispatch_allowed"] is False


def test_attempt_simulation_cli_selects_once_and_never_executes(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    candidates.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "attempt_id": "dad:portfolio-attempt:00000000-0000-0000-0000-000000000002",
                        "worker_revision_id": "worker:two",
                        "sequence": 2,
                    },
                    {
                        "attempt_id": "dad:portfolio-attempt:00000000-0000-0000-0000-000000000001",
                        "worker_revision_id": "worker:one",
                        "sequence": 1,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    result = CliRunner().invoke(cli.app, ["os", "attempt-simulate", str(candidates)])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert sum(row["claim_selected"] for row in payload["ordered_claims"]) == 1
    assert payload["execution_performed"] is False
