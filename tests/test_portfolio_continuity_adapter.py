from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory import portfolio_continuity_adapter as adapter
from digital_asset_directory.portfolio_continuity_events import (
    ContinuityConflictError,
    ContinuityIntegrityError,
)
from digital_asset_directory.transport import init_data_root


def _receipt() -> dict:
    return {
        "schema_version": "dad.portfolio_continuity_adapter_receipt.v1",
        "request_id": "adapter-receipt-1",
        "adapter_id": "adapter:runtime-shadow",
        "adapter_revision_id": "adapter-revision:runtime-shadow:0.1.0",
        "source_kind": "runtime_hook",
        "source_id": "session:opaque-1",
        "source_revision": "event:4",
        "event_kind": "interruption_observed",
        "observed_at": "2026-07-16T12:00:00+00:00",
        "privacy_partition": "private:personal",
        "payload": {
            "interrupted_entity_id": "entity:one",
            "new_entity_id": "entity:two",
            "reason_code": "task_switch",
            "recommended_action": "inspect",
        },
    }


def _private_hub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    hub = tmp_path / "hub"
    hub.mkdir()
    data_root = tmp_path / "data"
    init_data_root(data_root, hub_root=hub)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))
    return hub


def test_silent_adapter_returns_no_receipt_content_or_action_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = adapter.ingest_receipt(_private_hub(tmp_path, monkeypatch), _receipt())

    assert result["status"] == "appended"
    assert result["silent"] is True
    assert result["execution_authorized"] is False
    for counter in (
        "model_calls",
        "network_calls",
        "notifications_attempted",
        "scheduler_actions",
        "git_actions",
        "task_mutations",
    ):
        assert result[counter] == 0
    rendered = json.dumps(result)
    assert "entity:one" not in rendered
    assert "task_switch" not in rendered
    assert "payload" not in result


def test_adapter_file_replay_is_idempotent_and_conflict_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = _private_hub(tmp_path, monkeypatch)
    receipt_file = tmp_path / "receipt.json"
    receipt_file.write_text(json.dumps(_receipt()), encoding="utf-8")

    assert adapter.ingest_receipt_file(hub, receipt_file)["status"] == "appended"
    assert adapter.ingest_receipt_file(hub, receipt_file)["status"] == "deduplicated"

    changed = _receipt()
    changed["payload"]["reason_code"] = "different"
    receipt_file.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ContinuityConflictError):
        adapter.ingest_receipt_file(hub, receipt_file)


def test_adapter_fails_closed_without_private_data_root(tmp_path: Path) -> None:
    with pytest.raises(ContinuityIntegrityError, match="initialized DAD_DATA_ROOT"):
        adapter.ingest_receipt(tmp_path, _receipt())


def test_adapter_module_has_no_action_or_integration_imports() -> None:
    source = Path(adapter.__file__).read_text(encoding="utf-8")
    forbidden = (
        "import subprocess",
        "import socket",
        "import requests",
        "import httpx",
        "import git",
        "from .daemon",
        "notification",
        "scheduler",
    )
    imports = "\n".join(
        line.strip() for line in source.splitlines() if line.startswith(("import ", "from "))
    )
    for token in forbidden:
        assert token not in imports.casefold()
