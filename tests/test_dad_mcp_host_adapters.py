from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "assets" / "mcp" / "dad-local-readonly"
VALIDATOR_PATH = BUNDLE / "validate.py"
SPEC = importlib.util.spec_from_file_location("dad_mcp_host_adapter_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


def _contract(root: Path = BUNDLE) -> dict:
    return json.loads((root / "contract.json").read_text(encoding="utf-8"))


def _evidence_capture_time(root: Path = BUNDLE) -> datetime:
    evidence = json.loads(
        (root / "installed-host-evidence.json").read_text(encoding="utf-8")
    )
    return datetime.fromisoformat(str(evidence["captured_at"]).replace("Z", "+00:00"))


def _template_document(adapter: dict) -> dict:
    path = BUNDLE / adapter["template"]
    if adapter["format"] == "json":
        return json.loads(path.read_text(encoding="utf-8"))
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_contract_matches_schema_and_has_non_authorizing_boundary():
    contract = _contract()
    schema = json.loads((BUNDLE / "contract.schema.json").read_text(encoding="utf-8"))

    jsonschema.Draft202012Validator(schema).validate(contract)

    assert contract["logical_server_name"] == "dad-local-graph-surfaces"
    assert contract["authority"] == {
        "transport": "stdio",
        "local_only": True,
        "read_only": True,
        "remote_enabled": False,
        "vendor_sdk_required": False,
        "execution_authority": False,
        "installation_policy": "explicit_human_approval",
    }
    assert contract["installation"]["authorized_by_bundle"] is False
    assert contract["installation"]["overwrite_existing_config"] is False
    assert contract["binding_policy"]["DAD_PYTHON"] == {
        "kind": "direct_python_executable",
        "windows_basename": "python.exe",
        "absolute_at_install": True,
        "shell_wrapper_allowed": False,
    }


def test_all_host_templates_resolve_to_one_entrypoint_and_authority():
    contract = _contract()

    resolved = [
        VALIDATOR.resolve_adapter(contract, adapter, root=BUNDLE)
        for adapter in contract["adapters"]
    ]

    assert len(resolved) == 7
    assert {item.logical_server_name for item in resolved} == {"dad-local-graph-surfaces"}
    assert {item.command for item in resolved} == {"DAD_PYTHON_EXECUTABLE"}
    assert {item.args for item in resolved} == {
        (
            "-m",
            "digital_asset_directory.cli",
            "mcp",
            "graph-stdio",
            "--hub",
            "DAD_HUB_DIRECTORY",
        )
    }
    assert len({item.allowed_tools for item in resolved}) == 1
    assert len({item.authority for item in resolved}) == 1

    report = VALIDATOR.validate_bundle(BUNDLE, now=_evidence_capture_time())
    assert report["status"] == "valid"
    assert report["adapter_count"] == 7
    assert report["installation_authorized"] is False


def test_templates_use_official_host_roots_and_no_unknown_top_level_metadata():
    contract = _contract()
    expected_roots = {
        "codex_project": "mcp_servers",
        "codex_global": "mcp_servers",
        "claude_code_project": "mcpServers",
        "claude_desktop": "mcpServers",
        "cursor": "mcpServers",
        "vscode_github_copilot": "servers",
        "github_copilot_cli": "mcpServers",
    }

    for adapter in contract["adapters"]:
        document = _template_document(adapter)
        assert set(document) == {expected_roots[adapter["adapter_id"]]}
        server = document[adapter["root_key"]][contract["logical_server_name"]]
        assert "url" not in server
        assert "headers" not in server
        assert server.get("type", "stdio") in {"stdio", "local"}
        assert server.get("env", {}) == {}


def test_templates_contain_no_secrets_absolute_paths_or_shell_wrappers():
    forbidden_fields = re.compile(
        r'"(?:authorization|api[_-]?key|password|secret|private[_-]?key|token)"\s*:',
        re.IGNORECASE,
    )
    absolute_windows = re.compile(r"[A-Za-z]:[\\/]")
    shell_wrappers = {
        "bash",
        "bash.exe",
        "cmd",
        "cmd.exe",
        "powershell",
        "powershell.exe",
        "pwsh",
        "pwsh.exe",
        "sh",
        "sh.exe",
    }
    contract = _contract()

    for adapter in contract["adapters"]:
        path = BUNDLE / adapter["template"]
        text = path.read_text(encoding="utf-8")
        assert not forbidden_fields.search(text)
        assert not absolute_windows.search(text)
        document = _template_document(adapter)
        server = document[adapter["root_key"]][contract["logical_server_name"]]
        assert not str(server["command"]).startswith(("/", "\\\\"))
        assert Path(str(server["command"])).name.lower() not in shell_wrappers


def test_validator_fails_closed_on_entrypoint_or_template_set_drift(tmp_path: Path):
    copy = tmp_path / "bundle"
    shutil.copytree(BUNDLE, copy)
    contract = _contract(copy)
    adapter = next(item for item in contract["adapters"] if item["format"] == "json")
    path = copy / adapter["template"]
    document = json.loads(path.read_text(encoding="utf-8"))
    document[adapter["root_key"]][contract["logical_server_name"]]["args"][3] = "write-server"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(VALIDATOR.BundleValidationError, match="entry-point args drift"):
        VALIDATOR.validate_bundle(copy, now=_evidence_capture_time(copy))

    path.write_text(
        (BUNDLE / adapter["template"]).read_text(encoding="utf-8"), encoding="utf-8"
    )
    (copy / "templates" / "undeclared.json").write_text("{}", encoding="utf-8")
    with pytest.raises(VALIDATOR.BundleValidationError, match="declared template set"):
        VALIDATOR.validate_bundle(copy, now=_evidence_capture_time(copy))


def test_host_evidence_exact_age_boundary_and_future_rejection(tmp_path: Path):
    now = datetime(2026, 7, 13, 21, 0, tzinfo=timezone.utc)
    cases = [
        ("boundary", now - timedelta(days=7), None),
        ("late", now - timedelta(days=7, hours=1), "stale"),
        ("future", now + timedelta(days=30), "from the future"),
    ]
    for name, captured, error in cases:
        copy = tmp_path / name
        shutil.copytree(BUNDLE, copy)
        path = copy / "installed-host-evidence.json"
        evidence = json.loads(path.read_text(encoding="utf-8"))
        evidence["captured_at"] = captured.isoformat().replace("+00:00", "Z")
        path.write_text(json.dumps(evidence), encoding="utf-8")
        if error is None:
            assert VALIDATOR.validate_bundle(copy, now=now)["status"] == "valid"
        else:
            with pytest.raises(VALIDATOR.BundleValidationError, match=error):
                VALIDATOR.validate_bundle(copy, now=now)
