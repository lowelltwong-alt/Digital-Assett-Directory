from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

from digital_asset_directory.portfolio_continuity_codex_hook import (
    CodexHookInputError,
    build_codex_hook_receipt,
    hook_failure_ledger_path,
    ingest_codex_hook,
    read_codex_hook_failures,
    record_codex_hook_failure,
)
from digital_asset_directory.portfolio_continuity_events import (
    continuity_ledger_path,
    read_observation_events,
)
from digital_asset_directory.transport import init_data_root


def _input(event_name: str = "Stop") -> dict:
    payload = {
        "session_id": "session-private-identifier",
        "turn_id": "turn-private-identifier",
        "cwd": r"C:\\Users\\private\\repo",
        "transcript_path": r"C:\\Users\\private\\transcript.jsonl",
        "hook_event_name": event_name,
        "model": "private-model-label",
        "permission_mode": "default",
    }
    if event_name == "SessionStart":
        payload.pop("turn_id")
        payload["source"] = "resume"
    elif event_name in {"PreCompact", "PostCompact"}:
        payload["trigger"] = "auto"
    return payload


def _private_hub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    hub = tmp_path / "hub"
    hub.mkdir()
    data_root = tmp_path / "data"
    init_data_root(data_root, hub_root=hub)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))
    return hub


@pytest.mark.parametrize(
    ("event_name", "event_kind"),
    [
        ("SessionStart", "session_started"),
        ("PreCompact", "interruption_observed"),
        ("PostCompact", "resumption_observed"),
        ("Stop", "turn_stopped"),
    ],
)
def test_codex_events_map_to_minimized_receipts(event_name: str, event_kind: str) -> None:
    receipt = build_codex_hook_receipt(
        _input(event_name), observed_at="2026-07-17T00:00:00+00:00"
    )

    assert receipt["event_kind"] == event_kind
    rendered = json.dumps(receipt)
    for forbidden in (
        "session-private-identifier",
        "turn-private-identifier",
        "Users",
        "transcript",
        "private-model-label",
        "permission_mode",
    ):
        assert forbidden not in rendered


def test_failure_markers_are_concurrent_and_identity_validated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = _private_hub(tmp_path, monkeypatch)

    def record(index: int) -> dict:
        return record_codex_hook_failure(
            hub,
            {**_input(), "turn_id": f"private-failure-{index}"},
            repository_id="dad",
            reason_code="hook_ingest_failed",
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(record, range(8)))
    assert len(read_codex_hook_failures(hub)) == 8

    ledger = hook_failure_ledger_path(hub)
    rows = ledger.read_text(encoding="utf-8").splitlines()
    first = json.loads(rows[0])
    first["failure_id"] = "dad:hook-failure:" + "0" * 64
    rows[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    ledger.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(CodexHookInputError, match="identity"):
        read_codex_hook_failures(hub)


@pytest.mark.parametrize("root_state", ["uninitialized", "bound_to_other_hub"])
def test_failure_marker_never_falls_back_into_source_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    root_state: str,
) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    data_root = tmp_path / "data"
    if root_state == "bound_to_other_hub":
        other_hub = tmp_path / "other-hub"
        other_hub.mkdir()
        init_data_root(data_root, hub_root=other_hub)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))

    with pytest.raises(CodexHookInputError, match="initialized private DAD data root"):
        record_codex_hook_failure(
            hub,
            _input(),
            repository_id="dad",
            reason_code="hook_ingest_failed",
        )

    relative = Path("raw/portfolio/continuity-hook-failures.jsonl")
    assert not (hub / relative).exists()
    assert not (data_root / relative).exists()


def test_hook_bootstrap_failure_is_silent(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    isolated_hook = tmp_path / ".codex" / "hooks" / "intent_continuity_shadow.py"
    isolated_hook.parent.mkdir(parents=True)
    shutil.copy2(root / ".codex/hooks/intent_continuity_shadow.py", isolated_hook)

    completed = subprocess.run(
        [sys.executable, str(isolated_hook)],
        input=json.dumps(_input()),
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
        env={**os.environ, "PYTHONPATH": ""},
    )

    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""


def test_exact_hook_retry_is_idempotent_despite_process_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = _private_hub(tmp_path, monkeypatch)

    assert ingest_codex_hook(hub, _input())["status"] == "appended"
    assert ingest_codex_hook(hub, _input())["status"] == "deduplicated"
    assert len(read_observation_events(continuity_ledger_path(hub))) == 1


def test_stop_is_turn_activity_and_repository_binding_is_non_path_metadata() -> None:
    receipt = build_codex_hook_receipt(
        _input("Stop"),
        observed_at="2026-07-17T00:00:00+00:00",
        repository_id="dad",
    )

    assert receipt["event_kind"] == "turn_stopped"
    assert receipt["payload"]["repository_id"] == "dad"
    assert "repository_enrollment_id_not_supplied" not in receipt["payload"]["coverage_gaps"]


def test_turn_scoped_event_without_turn_id_fails_closed() -> None:
    payload = _input()
    payload.pop("turn_id")
    with pytest.raises(CodexHookInputError, match="turn_id"):
        build_codex_hook_receipt(payload)


def test_user_prompt_submit_is_not_supported() -> None:
    with pytest.raises(CodexHookInputError, match="Unsupported"):
        build_codex_hook_receipt(_input("UserPromptSubmit"))


def test_repo_hook_definition_excludes_prompt_capture_and_visible_output() -> None:
    root = Path(__file__).resolve().parents[1]
    hooks = json.loads((root / ".codex/hooks.json").read_text(encoding="utf-8"))["hooks"]
    assert set(hooks) == {"SessionStart", "PreCompact", "PostCompact", "Stop"}
    assert "UserPromptSubmit" not in hooks
    assert "statusMessage" not in json.dumps(hooks)
    assert all(
        handler["timeout"] == 5
        for groups in hooks.values()
        for group in groups
        for handler in group["hooks"]
    )


@pytest.mark.skipif(sys.platform != "win32", reason="validates commandWindows exactly")
def test_windows_hook_command_is_silent_and_persists_minimized_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).resolve().parents[1]
    hub = tmp_path / "hub"
    for relative in (
        "AI_FRONT_DOOR.md",
        "MACHINE_NAVIGATION_MANIFEST.json",
        "registry/source-of-truth.json",
        "pyproject.toml",
        "src/digital_asset_directory/cli.py",
    ):
        target = hub / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, target)
    data_root = tmp_path / "data"
    init_data_root(data_root, hub_root=hub)
    hooks = json.loads((root / ".codex/hooks.json").read_text(encoding="utf-8"))["hooks"]
    command = hooks["Stop"][0]["hooks"][0]["commandWindows"]
    assert command == (
        'python "$(git rev-parse --show-toplevel)/.codex/hooks/'
        'intent_continuity_shadow.py"'
    )
    command_args = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        command,
    ]
    monkeypatch.setenv("DAD_HUB", str(hub))
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))
    env = os.environ.copy()

    completed = subprocess.run(
        command_args,
        cwd=root / "tests",
        input=json.dumps(_input()),
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
        env=env,
    )

    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""
    events = read_observation_events(continuity_ledger_path(hub))
    assert len(events) == 1
    rendered = json.dumps(events[0])
    for forbidden in (
        "session-private-identifier",
        "turn-private-identifier",
        "Users",
        "transcript",
        "private-model-label",
        "permission_mode",
    ):
        assert forbidden not in rendered

    ledger = continuity_ledger_path(hub)
    lock_path = ledger.with_suffix(ledger.suffix + ".lock")
    lock_path.write_text("held-for-timeout-test", encoding="utf-8")
    started = time.monotonic()
    blocked = subprocess.run(
        command_args,
        cwd=root,
        input=json.dumps({**_input(), "turn_id": "another-private-turn"}),
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
        env=env,
    )
    elapsed = time.monotonic() - started
    lock_path.unlink()

    assert blocked.returncode == 0
    assert blocked.stdout == ""
    assert blocked.stderr == ""
    assert elapsed < 4.5
    assert len(read_observation_events(ledger)) == 1
    failures = read_codex_hook_failures(hub)
    assert len(failures) == 1
    assert failures[0]["reason_code"] == "hook_ingest_failed"
    assert "another-private-turn" not in json.dumps(failures)

    def invoke(turn: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command_args,
            cwd=root,
            input=json.dumps({**_input(), "turn_id": f"concurrent-turn-{turn}"}),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            env=env,
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        concurrent_results = list(executor.map(invoke, range(4)))
    assert all(
        result.returncode == 0 and not result.stdout and not result.stderr
        for result in concurrent_results
    )
    assert len(read_observation_events(ledger)) == 5
