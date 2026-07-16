from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema.validators import validator_for

from digital_asset_directory.capability_os_cockpit import build_capability_os_cockpit, capability_os_cockpit_html
from digital_asset_directory.mcp_server import DADGraphMCPServer, MCPError
from digital_asset_directory.cli import app
from typer.testing import CliRunner


REPO = Path(__file__).resolve().parents[1]


def test_capability_cockpit_is_local_bounded_and_request_only(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DAD_DATA_ROOT", str(tmp_path / "uninitialized"))
    cockpit = build_capability_os_cockpit(
        REPO,
        REPO,
        today_items=[
            {"decision_key": str(i), "title": f"Decision {i}", "source_fingerprint": str(i)}
            for i in range(6)
        ],
    )
    schema = json.loads((REPO / "schemas/capability-os-cockpit.schema.json").read_text(encoding="utf-8"))
    validator_for(schema)(schema).validate(cockpit)
    assert len(cockpit["decisions"]) == 3
    assert cockpit["local_bind"] == "127.0.0.1"
    assert cockpit["external_javascript"] is False
    assert cockpit["execution_authorized"] is False
    assert all(row["behavior"] == "create_request_packet" for row in cockpit["controls"])
    html = capability_os_cockpit_html(cockpit).lower()
    assert "<script" not in html
    assert "<button" not in html


def test_mcp_exposes_read_only_plan_identity_and_recovery_resources(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DAD_DATA_ROOT", str(tmp_path / "uninitialized"))
    unapproved = DADGraphMCPServer(REPO)
    with pytest.raises(MCPError, match="not approved"):
        unapproved.read_resource("dad://plans/search")
    server = DADGraphMCPServer(REPO, approved_private_partitions=("private",))
    uris = {row["uri"] for row in server.list_resources()}
    assert "dad://plans/search" in uris
    assert "dad://recovery/candidates" in uris
    assert "dad://report/unfinished-intent" in uris
    search = json.loads(server.read_resource("dad://plans/search")["contents"][0]["text"])
    recovery = json.loads(server.read_resource("dad://recovery/candidates")["contents"][0]["text"])
    assert search["schema_version"] == "dad.plan_index.v1"
    assert recovery["execution_authorized"] is False
    assert recovery["model_calls"] == 0


def test_public_control_plane_command_families_are_discoverable() -> None:
    runner = CliRunner()
    for args in (
        ["os", "plan", "--help"],
        ["os", "recovery", "--help"],
        ["identity", "--help"],
        ["runtime", "--help"],
        ["harness", "--help"],
        ["autonomy", "--help"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.output
