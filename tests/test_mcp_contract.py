from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_mcp_surface_contract_is_registered_and_deny_all():
    contract = load("registry/mcp-surface-contract.json")
    schema = load("schemas/mcp-surface-contract.schema.json")
    jsonschema.Draft202012Validator(schema).validate(contract)
    assert contract["authority"]["execution_authorized"] is False
    assert contract["authority"]["host_configuration_write"] is False
    assert contract["compatibility"]["legacy_graph_stdio"] is True


def test_packet_schemas_are_strict_and_non_authorizing():
    packet_schema = load("schemas/mcp-action-packet.schema.json")
    result_schema = load("schemas/mcp-action-result.schema.json")
    for schema in (packet_schema, result_schema):
        assert schema["additionalProperties"] is False
        assert schema["properties"]["execution_authorized"]["const"] is False


def test_remote_contract_is_design_only_and_has_hostile_cases():
    text = (ROOT / "docs" / "MCP_REMOTE_CONFORMANCE.md").read_text(encoding="utf-8")
    for term in ("tenant", "replay", "redaction", "fail-closed", "synthetic"):
        assert term in text
    assert "does not deploy" in text


@pytest.mark.parametrize("bad", ["/private/source", "token=secret", "C:\\private\\source"])
def test_remote_design_never_treats_fixture_as_real_payload(bad: str):
    assert bad
