from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

import digital_asset_directory.operational as operational
from digital_asset_directory.cli import app
from digital_asset_directory.config import (
    describe_hub_resolution,
    hub_locator_path,
    is_dad_hub_root,
    read_hub_locator,
    write_hub_locator,
)


RUNNER = CliRunner()
ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"


def _make_asset_dir_shim(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    python = str(Path(sys.executable).resolve())
    src = str(SRC_PATH.resolve())
    sh_src = src.replace("\\", "/")
    script = path / "asset-dir"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env sh",
                f'PYTHONPATH="{sh_src}${{PYTHONPATH:+:$PYTHONPATH}}" '
                f'exec "{python}" -m digital_asset_directory.cli "$@"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    (path / "asset-dir.cmd").write_text(
        f'@echo off\r\nset "PYTHONPATH={src};%PYTHONPATH%"\r\n"{python}" -m digital_asset_directory.cli %*\r\n',
        encoding="ascii",
    )


def _make_fake_asset_dir_shim(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    script = path / "asset-dir"
    script.write_text("#!/usr/bin/env sh\nprintf '{}\\n'\nexit 0\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    (path / "asset-dir.cmd").write_text("@echo off\r\necho {}\r\nexit /b 0\r\n", encoding="ascii")


def _make_false_green_asset_dir_shim(path: Path, hub: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    hub_path = str(hub.resolve())
    payload = json.dumps(
        {
            "schema": "deployment_readiness.v1",
            "deployment_ready": True,
            "deployment": {
                "ready": True,
                "hub_root_valid": True,
                "hub_resolution": {"hub_path": hub_path},
            },
        },
        sort_keys=True,
    )
    script = path / "asset-dir"
    script.write_text(f"#!/usr/bin/env sh\nprintf '%s\\n' '{payload}'\nexit 2\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    (path / "asset-dir.cmd").write_text(
        f"@echo off\r\necho {payload}\r\nexit /b 2\r\n",
        encoding="ascii",
    )


def _make_exit_zero_false_green_asset_dir_shim(path: Path, hub: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    hub_path = str(hub.resolve())
    payload = json.dumps(
        {
            "schema": "deployment_readiness.v1",
            "deployment_ready": True,
            "deployment": {
                "ready": True,
                "hub_root_valid": True,
                "hub_resolution": {"hub_path": hub_path},
            },
        },
        sort_keys=True,
    )
    script = path / "asset-dir"
    script.write_text(f"#!/usr/bin/env sh\nprintf '%s\\n' '{payload}'\nexit 0\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    (path / "asset-dir.cmd").write_text(
        f"@echo off\r\necho {payload}\r\nexit /b 0\r\n",
        encoding="ascii",
    )


def _make_probe_locator_writing_false_green_script(path: Path, hub: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    hub_path = str(hub.resolve())
    script = path / "fake_asset_dir.py"
    script.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "from pathlib import Path",
                f"HUB = {hub_path!r}",
                "locator = None",
                "for index, item in enumerate(sys.argv):",
                "    if item == '--locator' and index + 1 < len(sys.argv):",
                "        locator = Path(sys.argv[index + 1])",
                "if locator is not None:",
                "    locator.parent.mkdir(parents=True, exist_ok=True)",
                "    locator.write_text(json.dumps({",
                "        'schema_version': 'dad.hub-locator.v1',",
                "        'hub_path': HUB,",
                "        'hub_ref': 'dad://hub/Digital-Assett-Directory',",
                "    }), encoding='utf-8')",
                "print(json.dumps({",
                "    'schema': 'deployment_readiness.v1',",
                "    'deployment_ready': True,",
                "    'deployment': {",
                "        'ready': True,",
                "        'hub_root_valid': True,",
                "        'hub_resolution': {'hub_path': HUB},",
                "    },",
                "}))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return script


def _asset_dir_command(bin_dir: Path) -> list[str]:
    if os.name == "nt":
        return [str(bin_dir / "asset-dir.cmd")]
    return [str(bin_dir / "asset-dir")]


def _asset_dir_env(bin_dir: Path, home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["DAD_HUB"] = ""
    env["DAD_HUB_PATH"] = ""
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    return env


def _run_asset_dir(
    bin_dir: Path,
    home: Path,
    cwd: Path,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*_asset_dir_command(bin_dir), *args],
        cwd=cwd,
        env=_asset_dir_env(bin_dir, home),
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


def _run_bare_asset_dir(
    bin_dir: Path,
    home: Path,
    cwd: Path,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        " ".join(["asset-dir", *args]),
        cwd=cwd,
        env=_asset_dir_env(bin_dir, home),
        text=True,
        capture_output=True,
        check=False,
        shell=True,
        timeout=60,
    )


def _assert_no_target_dad_writes(repo: Path) -> None:
    assert not (repo / ".digital-asset").exists()
    assert not (repo / "processed").exists()
    assert not (repo / "state").exists()
    assert not (repo / "audit").exists()


def _tree_snapshot(root: Path) -> list[tuple[str, str, bytes]]:
    snapshot: list[tuple[str, str, bytes]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot.append(("dir", rel, b""))
        elif path.is_file():
            snapshot.append(("file", rel, path.read_bytes()))
        else:
            snapshot.append(("other", rel, b""))
    return snapshot


def _make_hub(path: Path) -> Path:
    (path / "registry").mkdir(parents=True)
    (path / "registry" / "source-of-truth.json").write_text("{}", encoding="utf-8")
    (path / "registry" / "design-authority.json").write_text("{}", encoding="utf-8")
    (path / "registry" / "schema-registry.json").write_text('{"schemas":{}}\n', encoding="utf-8")
    (path / "src" / "digital_asset_directory").mkdir(parents=True)
    (path / "src" / "digital_asset_directory" / "cli.py").write_text(
        "import typer\n\napp = typer.Typer()\n\ndef doctor():\n    pass\n",
        encoding="utf-8",
    )
    (path / "src" / "digital_asset_directory" / "config.py").write_text("", encoding="utf-8")
    (path / "src" / "digital_asset_directory" / "operational.py").write_text("", encoding="utf-8")
    (path / "AI_FRONT_DOOR.md").write_text("# AI Front Door\n", encoding="utf-8")
    (path / "AI_TABLE_OF_CONTENTS.md").write_text("# AI Table Of Contents\n", encoding="utf-8")
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


def _make_hollow_hub(path: Path) -> Path:
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


def test_hub_locator_path_defaults_to_user_dad_folder(tmp_path: Path) -> None:
    assert hub_locator_path(tmp_path) == tmp_path / ".dad" / "hub.json"


def test_write_and_read_hub_locator(tmp_path: Path) -> None:
    hub = _make_hub(tmp_path / "dad")
    locator = tmp_path / "home" / ".dad" / "hub.json"

    result = write_hub_locator(hub, locator)
    payload = json.loads(locator.read_text(encoding="utf-8"))
    readback = read_hub_locator(locator)

    assert result["written"] is True
    assert payload["hub_path"] == str(hub.resolve())
    assert readback["is_dad_hub"] is True
    assert readback["hub_path"] == str(hub.resolve())


def test_read_hub_locator_tolerates_utf8_bom(tmp_path: Path) -> None:
    hub = _make_hub(tmp_path / "dad")
    locator = tmp_path / "home" / ".dad" / "hub.json"
    locator.parent.mkdir(parents=True)
    locator.write_text(
        "\ufeff" + json.dumps({"hub_path": str(hub.resolve())}) + "\n",
        encoding="utf-8",
    )

    readback = read_hub_locator(locator)

    assert readback["error"] == ""
    assert readback["is_dad_hub"] is True
    assert readback["hub_path"] == str(hub.resolve())


def test_non_object_hub_locator_fails_closed(tmp_path: Path) -> None:
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    locator.parent.mkdir(parents=True)
    locator.write_text(json.dumps([{"hub_path": str(tmp_path / "dad")}]), encoding="utf-8")

    result = describe_hub_resolution(
        environ={},
        locator=locator,
        cwd=outside_repo,
        allow_current_fallback=False,
    )

    assert result["resolved"] is False
    assert "DAD hub unavailable" in result["error"]
    assert result["attempts"][0]["error"] == "invalid locator payload: expected JSON object"


def test_skeleton_directory_is_not_valid_dad_hub(tmp_path: Path) -> None:
    skeleton = tmp_path / "skeleton"
    (skeleton / "registry").mkdir(parents=True)
    (skeleton / "registry" / "source-of-truth.json").write_text("{}", encoding="utf-8")
    (skeleton / "src" / "digital_asset_directory").mkdir(parents=True)
    (skeleton / "src" / "digital_asset_directory" / "cli.py").write_text("", encoding="utf-8")

    assert not is_dad_hub_root(skeleton)


def test_deployment_doctor_rejects_hollow_hub_with_empty_cli(tmp_path: Path) -> None:
    hollow = _make_hollow_hub(tmp_path / "hollow")
    locator = tmp_path / "home" / ".dad" / "hub.json"

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--hub",
            str(hollow),
            "--scope",
            "deployment",
            "--locator",
            str(locator),
            "--write-hub-locator",
        ],
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["deployment_ready"] is False
    integrity = payload["deployment"]["install_integrity"]
    assert integrity["valid"] is False
    assert integrity["cli_entrypoint_valid"] is False
    assert "DAD hub install integrity check failed" in "\n".join(payload["deployment"]["warnings"])


def test_hub_resolution_prefers_explicit_hub(tmp_path: Path) -> None:
    explicit = _make_hub(tmp_path / "explicit")
    env_hub = _make_hub(tmp_path / "env")

    result = describe_hub_resolution(
        explicit_hub=explicit,
        environ={"DAD_HUB": str(env_hub)},
        locator=tmp_path / "missing" / "hub.json",
        cwd=tmp_path,
    )

    assert result["resolved"] is True
    assert result["source"] == "explicit_hub"
    assert result["hub_path"] == str(explicit.resolve())


def test_hub_resolution_uses_locator_outside_dad_repo(tmp_path: Path) -> None:
    hub = _make_hub(tmp_path / "dad")
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    write_hub_locator(hub, locator)

    result = describe_hub_resolution(
        environ={},
        locator=locator,
        cwd=outside_repo,
    )

    assert result["resolved"] is True
    assert result["source"] == "user_locator"
    assert result["hub_path"] == str(hub.resolve())


def test_hub_resolution_uses_dad_hub_env_outside_dad_repo(tmp_path: Path) -> None:
    hub = _make_hub(tmp_path / "dad")
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()

    result = describe_hub_resolution(
        environ={"DAD_HUB": str(hub), "DAD_HUB_PATH": ""},
        locator=tmp_path / "missing" / "hub.json",
        cwd=outside_repo,
    )

    assert result["resolved"] is True
    assert result["source"] == "DAD_HUB"
    assert result["hub_path"] == str(hub.resolve())


def test_hub_resolution_uses_dad_hub_path_when_dad_hub_unset(tmp_path: Path) -> None:
    hub = _make_hub(tmp_path / "dad")
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()

    result = describe_hub_resolution(
        environ={"DAD_HUB": "", "DAD_HUB_PATH": str(hub)},
        locator=tmp_path / "missing" / "hub.json",
        cwd=outside_repo,
    )

    assert result["resolved"] is True
    assert result["source"] == "DAD_HUB_PATH"
    assert result["hub_path"] == str(hub.resolve())


def test_invalid_env_hub_fails_closed_before_valid_locator(tmp_path: Path) -> None:
    valid_hub = _make_hub(tmp_path / "valid")
    not_hub = tmp_path / "not-dad"
    not_hub.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    write_hub_locator(valid_hub, locator)

    result = describe_hub_resolution(
        environ={"DAD_HUB": str(not_hub)},
        locator=locator,
        cwd=tmp_path,
    )

    assert result["resolved"] is False
    assert "DAD_HUB is set" in result["error"]


def test_invalid_dad_hub_path_fails_closed_before_valid_locator(tmp_path: Path) -> None:
    valid_hub = _make_hub(tmp_path / "valid")
    not_hub = tmp_path / "not-dad"
    not_hub.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    write_hub_locator(valid_hub, locator)

    result = describe_hub_resolution(
        environ={"DAD_HUB": "", "DAD_HUB_PATH": str(not_hub)},
        locator=locator,
        cwd=tmp_path,
    )

    assert result["resolved"] is False
    assert "DAD_HUB_PATH is set" in result["error"]


def test_hub_resolution_does_not_accept_non_dad_locator_target(tmp_path: Path) -> None:
    not_hub = tmp_path / "not-dad"
    not_hub.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    locator.parent.mkdir(parents=True)
    locator.write_text(json.dumps({"hub_path": str(not_hub)}) + "\n", encoding="utf-8")

    result = describe_hub_resolution(
        environ={},
        locator=locator,
        cwd=tmp_path,
        allow_current_fallback=False,
    )

    assert result["resolved"] is False
    assert result["hub_path"] == ""
    assert not is_dad_hub_root(not_hub)


def test_malformed_user_locator_outside_hub_fails_closed_without_current_fallback(
    tmp_path: Path,
) -> None:
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    locator.parent.mkdir(parents=True)
    locator.write_text("{not json", encoding="utf-8")

    result = describe_hub_resolution(
        environ={},
        locator=locator,
        cwd=outside_repo,
        allow_current_fallback=False,
    )

    assert result["resolved"] is False
    assert "DAD hub unavailable" in result["error"]
    assert result["attempts"][0]["error"].startswith("invalid JSON")


def test_doctor_can_write_custom_locator_for_deployment_scope(tmp_path: Path) -> None:
    locator = tmp_path / "home" / ".dad" / "hub.json"
    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--hub",
            ".",
            "--scope",
            "deployment",
            "--write-hub-locator",
            "--locator",
            str(locator),
        ],
    )

    assert result.exit_code in {0, 2}, result.output
    payload = json.loads(locator.read_text(encoding="utf-8"))
    assert payload["hub_path"] == str(ROOT.resolve())
    assert is_dad_hub_root(Path(payload["hub_path"]))
    assert '"schema": "deployment_readiness.v1"' in result.output


def test_doctor_locator_write_permission_error_fails_clean_without_target_write_or_path_leak(
    tmp_path: Path, monkeypatch
) -> None:
    outside_repo = tmp_path / "OneDrive" / "Desktop" / "Git Projects" / "caller repo"
    outside_repo.mkdir(parents=True)
    denied_path = tmp_path / "home" / ".dad" / "hub.json"

    def deny_locator_write(*_args, **_kwargs):
        raise PermissionError(f"access denied while writing {denied_path}")

    monkeypatch.setattr("digital_asset_directory.cli.write_hub_locator", deny_locator_write)
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--hub",
            str(ROOT),
            "--scope",
            "deployment",
            "--write-hub-locator",
            "--locator",
            str(denied_path),
        ],
        env={"DAD_HUB": "", "DAD_HUB_PATH": ""},
    )

    assert result.exit_code == 2
    assert "Traceback" not in result.output
    assert str(denied_path) not in result.output
    payload = json.loads(result.output)
    assert payload["deployment_ready"] is False
    assert payload["deployment"]["locator_write"]["written"] is False
    assert payload["deployment"]["locator_write"]["error_type"] == "PermissionError"
    assert payload["deployment"]["locator_write"]["error"] == "hub locator write failed: PermissionError"
    _assert_no_target_dad_writes(outside_repo)


def test_doctor_distinguishes_raw_checkout_from_external_invocation(
    tmp_path: Path, monkeypatch
) -> None:
    locator = tmp_path / "home" / ".dad" / "hub.json"
    monkeypatch.setattr(operational, "_user_shim_candidates", lambda: [])

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--hub",
            ".",
            "--scope",
            "deployment",
            "--write-hub-locator",
            "--locator",
            str(locator),
        ],
        env={"PATH": ""},
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    asset_dir = payload["deployment"]["asset_dir"]
    assert payload["deployment_ready"] is False
    assert asset_dir["external_invocation_ready"] is False
    assert asset_dir["module_fallback_available"] is True
    assert asset_dir["stable_invocation_available"] is True
    assert asset_dir["invocation_mode"] == "raw_checkout_fallback"
    guidance = asset_dir["recovery_guidance"]
    assert guidance["schema_version"] == "dad_deployment_recovery_guidance.v1"
    assert guidance["needed"] is True
    assert "asset-dir-not-on-path" in guidance["missing_or_unverified"]
    assert guidance["preferred_action"] == "run_bootstrap_from_dad_hub"
    assert guidance["raw_checkout_fallback_command"].endswith(
        "digital_asset_directory.cli doctor --scope deployment"
    )
    assert "PYTHONPATH" in guidance["raw_checkout_fallback_command"]
    assert "~/.dad/hub.json" in guidance["write_targets"]
    assert "raw source checkout fallback only" in "\n".join(payload["warnings"])


def test_doctor_recovery_guidance_for_non_dad_repo_without_asset_dir(
    tmp_path: Path, monkeypatch
) -> None:
    hub = _make_hub(tmp_path / "dad")
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    write_hub_locator(hub, locator)
    monkeypatch.setattr(operational, "_user_shim_candidates", lambda: [])
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--scope",
            "deployment",
            "--locator",
            str(locator),
        ],
        env={"PATH": "", "DAD_HUB": "", "DAD_HUB_PATH": ""},
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    asset_dir = payload["deployment"]["asset_dir"]
    guidance = asset_dir["recovery_guidance"]
    assert asset_dir["external_invocation_ready"] is False
    assert asset_dir["module_fallback_available"] is False
    assert guidance["needed"] is True
    assert guidance["preferred_action"] == "run_bootstrap_from_dad_hub"
    assert guidance["working_directory"] == str(hub.resolve())
    assert str(outside_repo) not in "\n".join(guidance["bootstrap_commands"].values())
    assert set(guidance["missing_or_unverified"]) == {
        "asset-dir-not-on-path",
        "user-shim-not-found",
        "external-invocation-not-verified",
    }
    assert guidance["raw_checkout_fallback_command"] == ""
    assert "bootstrap.ps1" in guidance["bootstrap_commands"]["windows_powershell"]
    assert "bootstrap.sh" in guidance["bootstrap_commands"]["posix_shell"]
    assert (
        "does not authorize writes to the caller repo" in guidance["non_target_repo_write_boundary"]
    )
    _assert_no_target_dad_writes(outside_repo)


def test_doctor_recovery_guidance_prefers_path_when_verified_shim_not_on_path(
    tmp_path: Path, monkeypatch
) -> None:
    locator = tmp_path / "home" / ".dad" / "hub.json"
    bin_dir = tmp_path / "bin"
    _make_asset_dir_shim(bin_dir)
    shim = bin_dir / ("asset-dir.cmd" if os.name == "nt" else "asset-dir")
    real_which = operational.shutil.which

    def fake_which(name: str):
        if name == "asset-dir":
            return None
        return real_which(name)

    monkeypatch.setattr(operational.shutil, "which", fake_which)
    monkeypatch.setattr(operational, "_user_shim_candidates", lambda: [shim])

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--hub",
            ".",
            "--scope",
            "deployment",
            "--write-hub-locator",
            "--locator",
            str(locator),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    asset_dir = payload["deployment"]["asset_dir"]
    guidance = asset_dir["recovery_guidance"]
    assert asset_dir["on_path"] is False
    assert asset_dir["external_invocation_ready"] is True
    assert guidance["needed"] is True
    assert guidance["missing_or_unverified"] == ["asset-dir-not-on-path"]
    assert guidance["preferred_action"] == "add_user_bin_to_path_or_use_direct_shim"
    assert guidance["direct_shim_commands"]
    if os.name == "nt":
        assert any(
            command.startswith("& ") and "asset-dir.cmd" in command
            for command in guidance["direct_shim_commands"]
        )


def test_invocation_probe_scrubs_source_checkout_env_and_uses_non_dad_cwd(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("PYTHONPATH", str(SRC_PATH))
    monkeypatch.setenv("PYTHONHOME", "source-env-should-not-leak")

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["env"] = dict(kwargs["env"])
        captured["cwd"] = Path(kwargs["cwd"]).resolve()
        locator = Path(command[command.index("--locator") + 1])
        locator.parent.mkdir(parents=True, exist_ok=True)
        locator.write_text(
            json.dumps(
                {
                    "schema_version": "dad.hub-locator.v1",
                    "hub_path": str(ROOT.resolve()),
                    "hub_ref": "dad://hub/Digital-Assett-Directory",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        payload = {
            "schema": "deployment_readiness.v1",
            "deployment_ready": True,
            "deployment": {
                "ready": True,
                "hub_root_valid": True,
                "hub_resolution": {"hub_path": str(ROOT.resolve())},
                "python": {
                    "operational_module_file": str(
                        (ROOT / "src" / "digital_asset_directory" / "operational.py").resolve()
                    ),
                    "operational_module_points_to_hub": True,
                },
            },
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setattr(operational.subprocess, "run", fake_run)

    result = operational._probe_dad_invocation(["asset-dir"], ROOT.resolve())

    env = captured["env"]
    assert result["verified"] is True
    assert "PYTHONPATH" not in env
    assert "PYTHONHOME" not in env
    assert captured["cwd"] != ROOT.resolve()
    assert ROOT.resolve() not in Path(captured["cwd"]).parents


def test_doctor_recovery_guidance_contract_limits_codes_and_actions(
    tmp_path: Path, monkeypatch
) -> None:
    hub = _make_hub(tmp_path / "dad")
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    write_hub_locator(hub, locator)
    monkeypatch.setattr(operational, "_user_shim_candidates", lambda: [])
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--scope",
            "deployment",
            "--locator",
            str(locator),
        ],
        env={"PATH": "", "DAD_HUB": "", "DAD_HUB_PATH": ""},
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    guidance = payload["deployment"]["asset_dir"]["recovery_guidance"]
    contract = guidance["contract"]
    allowed_missing = set(contract["allowed_missing_or_unverified"])
    allowed_actions = set(contract["allowed_preferred_actions"])
    assert contract["schema_version"] == "dad_deployment_recovery_guidance_contract.v1"
    assert allowed_missing == set(operational.RECOVERY_GUIDANCE_MISSING_CODES)
    assert allowed_actions == set(operational.RECOVERY_GUIDANCE_PREFERRED_ACTIONS)
    assert set(guidance["missing_or_unverified"]).issubset(allowed_missing)
    assert guidance["preferred_action"] in allowed_actions
    assert "non_target_repo_write_boundary" in guidance
    assert contract["boundary_required"] is True


def test_doctor_uses_custom_locator_from_non_dad_repo(tmp_path: Path, monkeypatch) -> None:
    hub = _make_hub(tmp_path / "dad")
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    write_hub_locator(hub, locator)
    bin_dir = tmp_path / "bin"
    _make_asset_dir_shim(bin_dir)
    monkeypatch.setattr(operational, "_user_shim_candidates", lambda: [])
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--scope",
            "deployment",
            "--locator",
            str(locator),
        ],
        env={
            "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
            "DAD_HUB": "",
            "DAD_HUB_PATH": "",
        },
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["deployment_ready"] is True
    assert payload["deployment"]["hub_resolution"]["source"] == "user_locator"
    assert payload["deployment"]["hub_resolution"]["hub_path"] == str(hub.resolve())
    assert payload["deployment"]["caller_repo"]["inside_hub"] is False
    assert payload["deployment"]["asset_dir"]["on_path"] is True
    assert payload["deployment"]["asset_dir"]["stable_invocation_available"] is True
    assert payload["deployment"]["asset_dir"]["invocation_verified"] is True
    assert not (hub / "processed" / "reports" / "operational_readiness.json").exists()


def test_user_shim_doctor_runs_from_two_non_dad_repos_as_subprocess_without_dad_hub_env(
    tmp_path: Path,
) -> None:
    hub = _make_hub(tmp_path / "dad")
    home = tmp_path / "home"
    locator = home / ".dad" / "hub.json"
    write_hub_locator(hub, locator)
    bin_dir = tmp_path / "bin"
    _make_asset_dir_shim(bin_dir)
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()

    payloads = []
    for repo in [repo_a, repo_b]:
        completed = _run_asset_dir(bin_dir, home, repo, "doctor", "--scope", "deployment")
        assert completed.returncode == 0, completed.stderr or completed.stdout
        payload = json.loads(completed.stdout)
        payloads.append(payload)
        _assert_no_target_dad_writes(repo)

    assert {payload["deployment"]["hub_resolution"]["hub_path"] for payload in payloads} == {
        str(hub.resolve())
    }
    assert all(payload["deployment_ready"] is True for payload in payloads)
    assert all(
        payload["deployment"]["hub_resolution"]["source"] == "user_locator" for payload in payloads
    )
    assert all(payload["deployment"]["caller_repo"]["inside_hub"] is False for payload in payloads)
    assert all(
        payload["deployment"]["asset_dir"]["external_invocation_ready"] is True
        for payload in payloads
    )
    assert not (hub / "processed" / "reports" / "operational_readiness.json").exists()


def test_bare_asset_dir_runs_from_path_when_user_bin_is_on_path(tmp_path: Path) -> None:
    hub = _make_hub(tmp_path / "dad")
    home = tmp_path / "home"
    locator = home / ".dad" / "hub.json"
    write_hub_locator(hub, locator)
    bin_dir = tmp_path / "bin"
    _make_asset_dir_shim(bin_dir)
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()

    completed = _run_bare_asset_dir(
        bin_dir,
        home,
        outside_repo,
        "doctor",
        "--scope",
        "deployment",
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["deployment_ready"] is True
    assert payload["deployment"]["hub_resolution"]["source"] == "user_locator"
    assert payload["deployment"]["asset_dir"]["external_invocation_ready"] is True
    _assert_no_target_dad_writes(outside_repo)


def test_doctor_resolves_same_hub_from_two_non_dad_repos(tmp_path: Path, monkeypatch) -> None:
    hub = _make_hub(tmp_path / "dad")
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    write_hub_locator(hub, locator)
    bin_dir = tmp_path / "bin"
    _make_asset_dir_shim(bin_dir)
    monkeypatch.setattr(operational, "_user_shim_candidates", lambda: [])

    payloads = []
    for repo in [repo_a, repo_b]:
        monkeypatch.chdir(repo)
        result = RUNNER.invoke(
            app,
            [
                "doctor",
                "--scope",
                "deployment",
                "--locator",
                str(locator),
            ],
            env={
                "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                "DAD_HUB": "",
                "DAD_HUB_PATH": "",
            },
        )
        assert result.exit_code == 0, result.output
        payloads.append(json.loads(result.output))

    assert {payload["deployment"]["hub_resolution"]["hub_path"] for payload in payloads} == {
        str(hub.resolve())
    }
    assert all(payload["deployment_ready"] is True for payload in payloads)
    assert all(payload["deployment"]["caller_repo"]["inside_hub"] is False for payload in payloads)
    assert all(
        payload["deployment"]["asset_dir"]["invocation_verified"] is True for payload in payloads
    )
    assert not (hub / "processed" / "reports" / "operational_readiness.json").exists()


def test_doctor_rejects_fake_asset_dir_on_path_from_non_dad_repo(
    tmp_path: Path, monkeypatch
) -> None:
    hub = _make_hub(tmp_path / "dad")
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    write_hub_locator(hub, locator)
    bin_dir = tmp_path / "bin"
    _make_fake_asset_dir_shim(bin_dir)
    monkeypatch.setattr(operational, "_user_shim_candidates", lambda: [])
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--scope",
            "deployment",
            "--locator",
            str(locator),
        ],
        env={
            "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
            "DAD_HUB": "",
            "DAD_HUB_PATH": "",
        },
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["deployment_ready"] is False
    assert payload["deployment"]["asset_dir"]["on_path"] is True
    assert payload["deployment"]["asset_dir"]["invocation_verified"] is False
    assert "did not prove it invokes this DAD hub" in "\n".join(payload["deployment"]["warnings"])


def test_doctor_rejects_false_green_asset_dir_probe_returning_error(
    tmp_path: Path, monkeypatch
) -> None:
    hub = _make_hub(tmp_path / "dad")
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    write_hub_locator(hub, locator)
    bin_dir = tmp_path / "bin"
    _make_false_green_asset_dir_shim(bin_dir, hub)
    monkeypatch.setattr(operational, "_user_shim_candidates", lambda: [])
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--scope",
            "deployment",
            "--locator",
            str(locator),
        ],
        env={
            "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
            "DAD_HUB": "",
            "DAD_HUB_PATH": "",
        },
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    probe = payload["deployment"]["asset_dir"]["invocation_probes"][0]
    assert payload["deployment_ready"] is False
    assert probe["returncode"] == 2
    assert probe["verified"] is False
    assert "did not prove it invokes this DAD hub" in "\n".join(payload["deployment"]["warnings"])


def test_doctor_rejects_exit_zero_false_green_probe_without_locator_write(
    tmp_path: Path, monkeypatch
) -> None:
    hub = _make_hub(tmp_path / "dad")
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    write_hub_locator(hub, locator)
    bin_dir = tmp_path / "bin"
    _make_exit_zero_false_green_asset_dir_shim(bin_dir, hub)
    monkeypatch.setattr(operational, "_user_shim_candidates", lambda: [])
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--scope",
            "deployment",
            "--locator",
            str(locator),
        ],
        env={
            "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
            "DAD_HUB": "",
            "DAD_HUB_PATH": "",
        },
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    probe = payload["deployment"]["asset_dir"]["invocation_probes"][0]
    assert probe["available"] is True
    assert probe["returncode"] == 0
    assert probe["verified"] is False
    assert probe["probe_locator_written"] is False
    assert probe["probe_locator_points_to_hub"] is False
    assert payload["deployment_ready"] is False


def test_probe_rejects_false_green_even_when_probe_locator_is_written(tmp_path: Path) -> None:
    hub = ROOT
    fake = _make_probe_locator_writing_false_green_script(tmp_path / "bin", hub)

    probe = operational._probe_dad_invocation([sys.executable, str(fake)], hub)

    assert probe["available"] is True
    assert probe["returncode"] == 0
    assert probe["probe_locator_written"] is True
    assert probe["probe_locator_points_to_hub"] is True
    assert probe["operational_module_attested_to_hub"] is False
    assert probe["verified"] is False


def test_direct_skip_invocation_probes_does_not_fake_deployment_ready(
    tmp_path: Path, monkeypatch
) -> None:
    hub = _make_hub(tmp_path / "dad")
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    write_hub_locator(hub, locator)
    monkeypatch.setattr(operational, "_user_shim_candidates", lambda: [])
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--scope",
            "deployment",
            "--locator",
            str(locator),
            "--skip-invocation-probes",
        ],
        env={"PATH": "", "DAD_HUB": "", "DAD_HUB_PATH": ""},
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    asset_dir = payload["deployment"]["asset_dir"]
    assert payload["deployment_ready"] is False
    assert asset_dir["external_invocation_ready"] is False
    assert asset_dir["invocation_verified"] is False
    assert "restricted to child deployment probes" in asset_dir["invocation_probes"][0]["error"]


def test_doctor_refuses_locator_write_inside_caller_repo_without_mutating_tree(
    tmp_path: Path, monkeypatch
) -> None:
    hub = _make_hub(tmp_path / "dad")
    target_repo = tmp_path / "target-repo"
    (target_repo / ".digital-asset" / "mail").mkdir(parents=True)
    (target_repo / ".digital-asset" / "mail" / "inbox.jsonl").write_text(
        '{"mail_id":"existing"}\n', encoding="utf-8"
    )
    (target_repo / "processed").mkdir()
    (target_repo / "processed" / "sentinel.txt").write_text("keep\n", encoding="utf-8")
    (target_repo / "AGENTS.md").write_text("local authority\n", encoding="utf-8")
    before = _tree_snapshot(target_repo)
    locator = target_repo / ".digital-asset" / "hub.json"
    monkeypatch.chdir(target_repo)

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--hub",
            str(hub),
            "--scope",
            "deployment",
            "--locator",
            str(locator),
            "--write-hub-locator",
        ],
        env={"DAD_HUB": "", "DAD_HUB_PATH": ""},
    )

    assert result.exit_code == 2
    assert "Refusing to write a DAD hub locator inside the caller repository" in result.output
    assert not locator.exists()
    assert _tree_snapshot(target_repo) == before


def test_doctor_deployment_ready_with_dad_hub_env_from_non_dad_repo(
    tmp_path: Path, monkeypatch
) -> None:
    hub = _make_hub(tmp_path / "dad")
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()
    bin_dir = tmp_path / "bin"
    _make_asset_dir_shim(bin_dir)
    missing_locator = tmp_path / "missing" / "hub.json"
    monkeypatch.setattr(operational, "_user_shim_candidates", lambda: [])
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--scope",
            "deployment",
            "--locator",
            str(missing_locator),
        ],
        env={
            "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
            "DAD_HUB": str(hub),
            "DAD_HUB_PATH": "",
        },
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["deployment_ready"] is False
    assert payload["deployment"]["hub_resolution"]["source"] == "DAD_HUB"
    assert payload["deployment"]["hub_resolution_points_to_hub"] is True
    assert payload["deployment"]["locator_points_to_hub"] is False
    assert "~/.dad/hub.json" in "\n".join(payload["deployment"]["warnings"])
    assert not (hub / "processed" / "reports" / "operational_readiness.json").exists()


def test_doctor_dad_hub_env_can_repair_locator_for_deployment(tmp_path: Path, monkeypatch) -> None:
    hub = _make_hub(tmp_path / "dad")
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()
    locator = tmp_path / "home" / ".dad" / "hub.json"
    stale_hub = _make_hub(tmp_path / "old-dad")
    write_hub_locator(stale_hub, locator)
    bin_dir = tmp_path / "bin"
    _make_asset_dir_shim(bin_dir)
    monkeypatch.setattr(operational, "_user_shim_candidates", lambda: [])
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--scope",
            "deployment",
            "--locator",
            str(locator),
            "--write-hub-locator",
        ],
        env={
            "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
            "DAD_HUB": str(hub),
            "DAD_HUB_PATH": "",
        },
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["deployment_ready"] is True
    assert payload["deployment"]["hub_resolution"]["source"] == "DAD_HUB"
    assert payload["deployment"]["locator_points_to_hub"] is True
    assert json.loads(locator.read_text(encoding="utf-8"))["hub_path"] == str(hub.resolve())


def test_agent_preflight_works_from_non_dad_repo_with_dad_hub_env(
    tmp_path: Path, monkeypatch
) -> None:
    hub = _make_hub(tmp_path / "dad")
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "agent",
            "preflight",
            "--repo",
            ".",
            "--agent",
            "codex",
            "--task",
            "deployment smoke from outside the DAD checkout",
        ],
        env={"DAD_HUB": str(hub), "DAD_HUB_PATH": ""},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["repository"] == str(outside_repo.resolve())
    assert payload["agent"] == "codex"
    assert payload["context_pack"]["warnings"]
    assert (hub / "state" / "agent_sessions").exists()


def test_agent_preflight_works_from_non_dad_repo_via_user_locator_and_user_shim_subprocess(
    tmp_path: Path,
) -> None:
    hub = _make_hub(tmp_path / "dad")
    home = tmp_path / "home"
    locator = home / ".dad" / "hub.json"
    write_hub_locator(hub, locator)
    bin_dir = tmp_path / "bin"
    _make_asset_dir_shim(bin_dir)
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()

    completed = _run_asset_dir(
        bin_dir,
        home,
        outside_repo,
        "agent",
        "preflight",
        "--repo",
        ".",
        "--agent",
        "codex",
        "--task",
        "deployment smoke from outside the DAD checkout via user locator",
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["repository"] == str(outside_repo.resolve())
    assert payload["agent"] == "codex"
    assert (hub / "state" / "agent_sessions").exists()
    _assert_no_target_dad_writes(outside_repo)


def test_doctor_fails_closed_when_hub_unavailable_from_non_dad_repo(
    tmp_path: Path, monkeypatch
) -> None:
    outside_repo = tmp_path / "other-repo"
    outside_repo.mkdir()
    not_hub = tmp_path / "not-dad"
    not_hub.mkdir()
    missing_locator = tmp_path / "home" / ".dad" / "hub.json"
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--hub",
            str(not_hub),
            "--scope",
            "deployment",
            "--locator",
            str(missing_locator),
        ],
        env={"DAD_HUB": "", "DAD_HUB_PATH": ""},
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["schema"] == "deployment_readiness.v1"
    assert payload["deployment_ready"] is False
    assert payload["deployment"]["hub_resolution"]["resolved"] is False
    assert payload["deployment"]["unavailable_hub_policy"]["hard_gate_decision"] == "fail_closed"
    assert "cross_repo_writes" in payload["deployment"]["unavailable_hub_policy"]["hard_gates"]
    assert (
        payload["deployment"]["unavailable_hub_policy"]["ordinary_local_coding"]["decision"]
        == "warn_and_continue"
    )
    assert not (outside_repo / "processed").exists()


def test_operational_report_redacts_deployment_recovery_guidance(
    tmp_path: Path, monkeypatch
) -> None:
    hub = _make_hub(tmp_path / "dad")
    locator = tmp_path / "home" / ".dad" / "hub.json"
    write_hub_locator(hub, locator)
    monkeypatch.setattr(operational, "_user_shim_candidates", lambda: [])
    monkeypatch.chdir(hub)

    result = RUNNER.invoke(
        app,
        [
            "doctor",
            "--hub",
            str(hub),
            "--scope",
            "operational",
            "--locator",
            str(locator),
        ],
        env={"PATH": "", "DAD_HUB": "", "DAD_HUB_PATH": ""},
    )

    assert result.exit_code == 2
    report_json = hub / "processed" / "reports" / "operational_readiness.json"
    assert report_json.exists()
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    guidance = payload["deployment"]["asset_dir"]["recovery_guidance"]
    guidance_text = json.dumps(guidance, sort_keys=True)
    assert guidance["redacted"] is True
    assert guidance["schema_version"] == "dad_deployment_recovery_guidance.redacted.v1"
    assert guidance["contract"]["schema_version"] == "dad_deployment_recovery_guidance_contract.v1"
    assert set(guidance["contract"]["local_path_fields"]) == set(
        operational.RECOVERY_GUIDANCE_LOCAL_PATH_FIELDS
    )
    assert str(hub.resolve()) not in guidance_text
    assert str(Path.home()) not in guidance_text
    assert "doctor --scope deployment" in guidance["available_in"]


def test_unavailable_hub_blocks_mail_deliver_before_target_write(
    tmp_path: Path, monkeypatch
) -> None:
    outside_repo = tmp_path / "other-repo"
    target_repo = tmp_path / "target-repo"
    not_hub = tmp_path / "not-dad"
    outside_repo.mkdir()
    target_repo.mkdir()
    not_hub.mkdir()
    sentinel = target_repo / "AGENTS.md"
    sentinel.write_text("local authority\n", encoding="utf-8")
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "mail",
            "deliver",
            "--repo",
            str(target_repo),
            "--hub",
            str(not_hub),
        ],
        env={"DAD_HUB": "", "DAD_HUB_PATH": ""},
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "FileNotFoundError" not in result.output
    assert str(tmp_path) not in result.output
    assert sentinel.read_text(encoding="utf-8") == "local authority\n"
    _assert_no_target_dad_writes(target_repo)


def test_unavailable_hub_blocks_enroll_apply_before_target_write(
    tmp_path: Path, monkeypatch
) -> None:
    outside_repo = tmp_path / "other-repo"
    target_repo = tmp_path / "target-repo"
    not_hub = tmp_path / "not-dad"
    outside_repo.mkdir()
    target_repo.mkdir()
    not_hub.mkdir()
    sentinel = target_repo / "AGENTS.md"
    sentinel.write_text("local authority\n", encoding="utf-8")
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "enroll",
            "apply",
            "--repo",
            str(target_repo),
            "--approval-id",
            "APPROVED",
            "--hub",
            str(not_hub),
        ],
        env={"DAD_HUB": "", "DAD_HUB_PATH": ""},
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "FileNotFoundError" not in result.output
    assert str(tmp_path) not in result.output
    assert sentinel.read_text(encoding="utf-8") == "local authority\n"
    _assert_no_target_dad_writes(target_repo)


def test_unavailable_hub_blocks_representative_hard_gate_commands_before_target_write(
    tmp_path: Path, monkeypatch
) -> None:
    outside_repo = tmp_path / "other-repo"
    target_repo = tmp_path / "target-repo"
    not_hub = tmp_path / "not-dad"
    outside_repo.mkdir()
    target_repo.mkdir()
    not_hub.mkdir()
    sentinel = target_repo / "AGENTS.md"
    sentinel.write_text("local authority\n", encoding="utf-8")
    monkeypatch.chdir(outside_repo)
    commands = [
        ["mail", "collect", "--repo", str(target_repo), "--hub", str(not_hub)],
        ["mail", "route", "--hub", str(not_hub)],
        ["mail", "deliver", "--repo", str(target_repo), "--hub", str(not_hub)],
        [
            "mail",
            "release",
            "--mail-id",
            "dad:mail:test",
            "--decision",
            "approve",
            "--human-reviewed-by",
            "Lowell",
            "--hub",
            str(not_hub),
        ],
        [
            "enroll",
            "apply",
            "--repo",
            str(target_repo),
            "--approval-id",
            "APPROVED",
            "--hub",
            str(not_hub),
        ],
        [
            "enroll",
            "update-apply",
            "--repo",
            str(target_repo),
            "--approval-id",
            "APPROVED",
            "--hub",
            str(not_hub),
        ],
    ]

    for command in commands:
        result = RUNNER.invoke(app, command, env={"DAD_HUB": "", "DAD_HUB_PATH": ""})
        assert result.exit_code != 0, command
        assert "Traceback" not in result.output, command
        assert "FileNotFoundError" not in result.output, command
        assert str(tmp_path) not in result.output, command
        assert sentinel.read_text(encoding="utf-8") == "local authority\n"
        _assert_no_target_dad_writes(target_repo)


def test_dad_unavailable_ack_records_user_local_audit_without_hub(
    tmp_path: Path, monkeypatch
) -> None:
    outside_repo = tmp_path / "other-repo"
    not_hub = tmp_path / "not-dad"
    audit_output = tmp_path / "user-local-audit" / "unavailable-acks.jsonl"
    outside_repo.mkdir()
    not_hub.mkdir()
    monkeypatch.chdir(outside_repo)

    result = RUNNER.invoke(
        app,
        [
            "dad",
            "unavailable-ack",
            "--operation",
            "cross_repo_writes",
            "--reason",
            "Lowell explicitly reviewed this blocked operation",
            "--reviewed-by",
            "Lowell",
            "--hub",
            str(not_hub),
            "--audit-output",
            str(audit_output),
        ],
        env={"DAD_HUB": "", "DAD_HUB_PATH": ""},
    )

    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    payload = json.loads(result.output)
    assert payload["event_type"] == "dad_unavailable_ack"
    assert payload["hub_available"] is False
    assert payload["audit_scope"] == "user_local"
    assert payload["reviewed_by"] == "Lowell"
    rows = [json.loads(line) for line in audit_output.read_text(encoding="utf-8").splitlines()]
    assert rows == [payload]


def test_dad_unavailable_ack_requires_named_human_without_writing_audit(
    tmp_path: Path, monkeypatch
) -> None:
    outside_repo = tmp_path / "other-repo"
    not_hub = tmp_path / "not-dad"
    audit_output = tmp_path / "user-local-audit" / "unavailable-acks.jsonl"
    outside_repo.mkdir()
    not_hub.mkdir()
    monkeypatch.chdir(outside_repo)

    for reviewed_by in ["", "human", "agent", "codex", "Claude", "unknown"]:
        command = [
            "dad",
            "unavailable-ack",
            "--operation",
            "cross_repo_writes",
            "--reason",
            "test bypass should not be accepted",
            "--hub",
            str(not_hub),
            "--audit-output",
            str(audit_output),
        ]
        if reviewed_by:
            command.extend(["--reviewed-by", reviewed_by])
        result = RUNNER.invoke(
            app,
            command,
            env={"DAD_HUB": "", "DAD_HUB_PATH": ""},
        )

        assert result.exit_code == 2
        assert "--reviewed-by must name the human" in result.output
        assert not audit_output.exists()


def test_bootstrap_scripts_prove_generated_shims() -> None:
    ps1 = Path("scripts/bootstrap.ps1").read_text(encoding="utf-8")
    sh = Path("scripts/bootstrap.sh").read_text(encoding="utf-8")

    assert "& $ShimPs1 doctor --hub $Root --scope deployment --write-hub-locator" in ps1
    assert '"$DAD_BIN/asset-dir" doctor --hub "$ROOT" --scope deployment --write-hub-locator' in sh
    assert ps1.index("$ShimPs1 = Join-Path $DadBin 'asset-dir.ps1'") < ps1.index(
        "& $ShimPs1 doctor --hub $Root --scope deployment --write-hub-locator"
    )
    assert sh.index('cat > "$DAD_BIN/asset-dir"') < sh.index(
        '"$DAD_BIN/asset-dir" doctor --hub "$ROOT" --scope deployment --write-hub-locator'
    )


def test_integration_contracts_try_stable_user_shims_before_raw_checkout_fallback() -> None:
    template_contract = json.loads(
        (ROOT / "templates" / "downstream" / "DAD_INTEGRATION.template.json").read_text(
            encoding="utf-8"
        )
    )
    local_contract_path = ROOT / ".digital-asset" / "dad-integration.json"
    contracts = [template_contract]
    if local_contract_path.exists():
        contracts.append(json.loads(local_contract_path.read_text(encoding="utf-8")))

    assert template_contract["agent_runtime_policy"] == {
        "core_contract": "AGENTS.md",
        "adapter_authority": "optional_wrapper_only",
        "agent_id_policy": "arbitrary_non_empty_string",
        "vendor_lock_in_prohibited": True,
    }
    for contract in contracts:
        fallback = contract["capture"]["cli_fallback"]
        assert "~/.dad/bin/asset-dir" in fallback
        assert "~/.dad/bin/asset-dir.ps1" in fallback
        assert "PYTHONPATH=src python -m digital_asset_directory.cli" in fallback
        assert fallback.index("~/.dad/bin/asset-dir") < fallback.index(
            "PYTHONPATH=src python -m digital_asset_directory.cli"
        )
        assert "dad_cli_unavailable" in fallback


def test_new_repo_script_uses_agent_id_placeholder() -> None:
    script = (ROOT / "scripts" / "new_repo.ps1").read_text(encoding="utf-8")
    assert "--agent <agent-id>" in script
    assert "--agent claude-code" not in script
