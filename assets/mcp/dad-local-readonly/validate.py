"""Deterministically validate DAD's AI-agnostic MCP host adapter bundle."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from jsonschema.validators import validator_for


BUNDLE_ROOT = Path(__file__).resolve().parent
_PYTHON_SENTINEL = "DAD_PYTHON_EXECUTABLE"
_HUB_SENTINEL = "DAD_HUB_DIRECTORY"
_ABSOLUTE_WINDOWS = re.compile(r"(?:^|[^A-Za-z0-9])[A-Za-z]:[\\/]")
_SENSITIVE_KEY = re.compile(
    r"(?:authorization|api[_-]?key|password|secret|private[_-]?key|token)",
    re.IGNORECASE,
)
_SHELL_EXECUTABLES = {
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
_PLACEHOLDERS = {
    "render": {
        "{{DAD_PYTHON}}": _PYTHON_SENTINEL,
        "{{DAD_HUB}}": _HUB_SENTINEL,
    },
    "claude_env": {
        "${DAD_PYTHON}": _PYTHON_SENTINEL,
        "${DAD_HUB}": _HUB_SENTINEL,
    },
    "cursor_env": {
        "${env:DAD_PYTHON}": _PYTHON_SENTINEL,
        "${env:DAD_HUB}": _HUB_SENTINEL,
    },
    "vscode_env": {
        "${env:DAD_PYTHON}": _PYTHON_SENTINEL,
        "${env:DAD_HUB}": _HUB_SENTINEL,
    },
}


class BundleValidationError(ValueError):
    """Raised when a host adapter drifts from the canonical contract."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedAdapter:
    """Normalized host view used for cross-adapter parity checks."""

    adapter_id: str
    host: str
    logical_server_name: str
    command: str
    args: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    authority: tuple[tuple[str, Any], ...]


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BundleValidationError(f"{path.name}: expected one JSON object")
    return value


def _contained_template(root: Path, relative: str) -> Path:
    if "\\" in relative or relative.startswith(("/", "~")):
        raise BundleValidationError(f"unsafe template reference: {relative}")
    root_resolved = root.resolve()
    path = (root_resolved / relative).resolve()
    if root_resolved not in path.parents:
        raise BundleValidationError(f"template escapes bundle: {relative}")
    if not path.is_file():
        raise BundleValidationError(f"template missing: {relative}")
    return path


def _server_entry(
    template_path: Path,
    *,
    template_format: str,
    root_key: str,
    logical_name: str,
) -> dict[str, Any]:
    if template_format == "json":
        document = _load_json(template_path)
    elif template_format == "toml":
        document = tomllib.loads(template_path.read_text(encoding="utf-8"))
    else:
        raise BundleValidationError(f"unsupported format: {template_format}")

    if set(document) != {root_key}:
        raise BundleValidationError(f"{template_path.name}: unexpected top-level keys")
    servers = document.get(root_key)
    if not isinstance(servers, Mapping) or set(servers) != {logical_name}:
        raise BundleValidationError(f"{template_path.name}: canonical server name drift")
    server = servers[logical_name]
    if not isinstance(server, dict):
        raise BundleValidationError(f"{template_path.name}: server entry must be an object")
    return server


def _resolve_placeholder(value: Any, *, mode: str, field: str) -> str:
    if not isinstance(value, str):
        raise BundleValidationError(f"{field}: expected string")
    replacements = _PLACEHOLDERS.get(mode)
    if replacements is None or value not in replacements:
        raise BundleValidationError(f"{field}: unapproved machine-specific value")
    return replacements[value]


def _walk_no_sensitive_or_absolute(value: Any, *, trail: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if _SENSITIVE_KEY.search(key_text):
                raise BundleValidationError(
                    f"credential-like field in template: {'.'.join((*trail, key_text))}"
                )
            _walk_no_sensitive_or_absolute(child, trail=(*trail, key_text))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_no_sensitive_or_absolute(child, trail=(*trail, str(index)))
    elif isinstance(value, str):
        if _ABSOLUTE_WINDOWS.search(value) or value.startswith(("/", "\\\\")):
            raise BundleValidationError(
                f"absolute path in template: {'.'.join(trail) or '<value>'}"
            )


def resolve_adapter(
    contract: Mapping[str, Any], adapter: Mapping[str, Any], *, root: Path = BUNDLE_ROOT
) -> ResolvedAdapter:
    """Normalize one declared host template to the canonical contract."""

    logical_name = str(contract.get("logical_server_name", ""))
    server_contract = contract.get("server_contract")
    authority = contract.get("authority")
    if not logical_name or not isinstance(server_contract, Mapping):
        raise BundleValidationError("contract is missing canonical server data")
    if not isinstance(authority, Mapping):
        raise BundleValidationError("contract is missing authority metadata")

    template_path = _contained_template(root, str(adapter.get("template", "")))
    server = _server_entry(
        template_path,
        template_format=str(adapter.get("format", "")),
        root_key=str(adapter.get("root_key", "")),
        logical_name=logical_name,
    )
    _walk_no_sensitive_or_absolute(server)
    if "url" in server or "headers" in server:
        raise BundleValidationError(f"{template_path.name}: remote MCP fields are prohibited")
    if server.get("type", "stdio") not in {"stdio", "local"}:
        raise BundleValidationError(f"{template_path.name}: transport must be local stdio")
    if server.get("env", {}) != {}:
        raise BundleValidationError(f"{template_path.name}: environment must be empty")

    mode = str(adapter.get("placeholder_mode", ""))
    command = _resolve_placeholder(server.get("command"), mode=mode, field="command")
    raw_args = server.get("args")
    if not isinstance(raw_args, list) or not all(isinstance(arg, str) for arg in raw_args):
        raise BundleValidationError(f"{template_path.name}: args must be a string array")
    args = list(raw_args)
    if not args:
        raise BundleValidationError(f"{template_path.name}: args cannot be empty")
    args[-1] = _resolve_placeholder(args[-1], mode=mode, field="hub argument")

    expected_args = list(server_contract.get("args_template", []))
    if not expected_args:
        raise BundleValidationError("contract args_template cannot be empty")
    expected_args[-1] = _HUB_SENTINEL
    if args != expected_args:
        raise BundleValidationError(f"{template_path.name}: entry-point args drift")
    if Path(command).name.lower() in _SHELL_EXECUTABLES:
        raise BundleValidationError(f"{template_path.name}: shell wrapper is prohibited")

    allowed_tools = tuple(str(item) for item in server_contract.get("allowed_tools", []))
    configured_tools = server.get("enabled_tools", server.get("tools", list(allowed_tools)))
    if tuple(configured_tools) != allowed_tools:
        raise BundleValidationError(f"{template_path.name}: tool allowlist drift")

    return ResolvedAdapter(
        adapter_id=str(adapter.get("adapter_id", "")),
        host=str(adapter.get("host", "")),
        logical_server_name=logical_name,
        command=command,
        args=tuple(args),
        allowed_tools=allowed_tools,
        authority=tuple(sorted(authority.items())),
    )


def validate_bundle(
    root: Path = BUNDLE_ROOT, *, now: datetime | None = None
) -> dict[str, Any]:
    """Validate the bundle and return a privacy-safe categorical report."""

    contract = _load_json(root / "contract.json")
    contract_schema = _load_json(root / "contract.schema.json")
    contract_validator = validator_for(contract_schema)
    contract_validator.check_schema(contract_schema)
    contract_validator(contract_schema).validate(contract)
    installed_evidence = _load_json(root / "installed-host-evidence.json")
    evidence_schema = _load_json(root / "installed-host-evidence.schema.json")
    evidence_validator = validator_for(evidence_schema)
    evidence_validator.check_schema(evidence_schema)
    evidence_validator(evidence_schema).validate(installed_evidence)
    captured = datetime.fromisoformat(
        str(installed_evidence["captured_at"]).replace("Z", "+00:00")
    )
    clock = now or datetime.now(timezone.utc)
    age_seconds = (clock - captured.astimezone(timezone.utc)).total_seconds()
    max_age_seconds = int(installed_evidence["observation_max_age_days"]) * 86400
    future_skew_seconds = int(installed_evidence["future_skew_seconds"])
    if age_seconds < -future_skew_seconds:
        raise BundleValidationError("installed-host evidence is from the future")
    if age_seconds > max_age_seconds:
        raise BundleValidationError("installed-host evidence is stale")
    if contract.get("schema_version") != "dad.mcp.host_adapter_bundle.v1":
        raise BundleValidationError("unsupported contract schema_version")
    if contract.get("logical_server_name") != "dad-local-graph-surfaces":
        raise BundleValidationError("logical server name drift")

    authority = contract.get("authority")
    expected_authority = {
        "transport": "stdio",
        "local_only": True,
        "read_only": True,
        "remote_enabled": False,
        "vendor_sdk_required": False,
        "execution_authority": False,
        "installation_policy": "explicit_human_approval",
    }
    if authority != expected_authority:
        raise BundleValidationError("authority metadata drift")
    binding_policy = contract.get("binding_policy")
    expected_binding_policy = {
        "DAD_PYTHON": {
            "kind": "direct_python_executable",
            "windows_basename": "python.exe",
            "absolute_at_install": True,
            "shell_wrapper_allowed": False,
        },
        "DAD_HUB": {
            "kind": "initialized_local_directory",
            "absolute_at_install": True,
        },
    }
    if binding_policy != expected_binding_policy:
        raise BundleValidationError("binding policy drift")
    installation = contract.get("installation")
    if not isinstance(installation, Mapping) or installation.get("authorized_by_bundle") is not False:
        raise BundleValidationError("bundle must not authorize its own installation")

    adapters = contract.get("adapters")
    if not isinstance(adapters, list) or not adapters:
        raise BundleValidationError("contract must declare adapters")
    adapter_ids = [str(adapter.get("adapter_id", "")) for adapter in adapters]
    if len(adapter_ids) != len(set(adapter_ids)) or any(not item for item in adapter_ids):
        raise BundleValidationError("adapter IDs must be unique and non-empty")
    evidence_ids = [str(row.get("adapter_id", "")) for row in installed_evidence["hosts"]]
    if len(evidence_ids) != len(set(evidence_ids)) or set(evidence_ids) != set(adapter_ids):
        raise BundleValidationError("installed-host evidence must cover each adapter exactly once")
    source_hosts = {str(row.get("host", "")) for row in contract.get("first_party_sources", [])}
    adapter_hosts = {str(row.get("host", "")) for row in adapters}
    if not adapter_hosts.issubset(source_hosts):
        raise BundleValidationError("first-party sources do not cover every host")

    declared = {str(adapter.get("template", "")) for adapter in adapters}
    discovered = {
        path.relative_to(root).as_posix()
        for path in (root / "templates").iterdir()
        if path.is_file()
    }
    if declared != discovered:
        raise BundleValidationError("declared template set does not match bundle contents")

    resolved = [resolve_adapter(contract, adapter, root=root) for adapter in adapters]
    parity = {
        (
            item.logical_server_name,
            item.command,
            item.args,
            item.allowed_tools,
            item.authority,
        )
        for item in resolved
    }
    if len(parity) != 1:
        raise BundleValidationError("host adapters do not resolve to one contract")

    canonical = resolved[0]
    return {
        "status": "valid",
        "schema_version": str(contract["schema_version"]),
        "logical_server_name": canonical.logical_server_name,
        "adapter_count": len(resolved),
        "hosts": sorted(item.host for item in resolved),
        "entrypoint": {
            "command": canonical.command,
            "args": list(canonical.args),
        },
        "allowed_tools": list(canonical.allowed_tools),
        "authority": dict(canonical.authority),
        "installation_authorized": False,
    }


def main() -> int:
    try:
        report = validate_bundle()
    except (BundleValidationError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        print(json.dumps({"status": "invalid", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
