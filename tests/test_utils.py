from __future__ import annotations

import os
from pathlib import Path

import pytest

import digital_asset_directory.utils as utils
from digital_asset_directory.utils import atomic_write_text


def test_atomic_write_text_retries_transient_replace_permission_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "last_checked.json"
    original_replace = os.replace
    attempts = {"count": 0}

    def flaky_replace(src: str, dst: str) -> None:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise PermissionError("temporary OneDrive lock")
        original_replace(src, dst)

    monkeypatch.setattr(utils.os, "replace", flaky_replace)
    monkeypatch.setattr(utils.time, "sleep", lambda _seconds: None)

    atomic_write_text(target, '{"ok": true}\n')

    assert attempts["count"] == 3
    assert target.read_text(encoding="utf-8") == '{"ok": true}\n'


def test_atomic_write_text_fails_closed_after_replace_permission_error_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "registry.json"
    replace_attempts = {"count": 0}

    def failing_replace(_src: str, _dst: str) -> None:
        replace_attempts["count"] += 1
        raise PermissionError("replace denied")

    monkeypatch.setattr(utils.os, "replace", failing_replace)
    monkeypatch.setattr(utils.time, "sleep", lambda _seconds: None)

    with pytest.raises(PermissionError, match="replace denied"):
        atomic_write_text(target, '{"ok": true}\n')

    assert replace_attempts["count"] == utils.ATOMIC_WRITE_REPLACE_ATTEMPTS
    assert not target.exists()
    assert not list(tmp_path.glob(".registry.json.*"))


def test_atomic_write_text_can_opt_into_direct_fallback_for_mail_availability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "last_checked.json"
    replace_attempts = {"count": 0}

    def failing_replace(_src: str, _dst: str) -> None:
        replace_attempts["count"] += 1
        raise PermissionError("replace denied")

    monkeypatch.setattr(utils.os, "replace", failing_replace)
    monkeypatch.setattr(utils.time, "sleep", lambda _seconds: None)

    atomic_write_text(target, '{"ok": true}\n', allow_direct_fallback=True)

    assert replace_attempts["count"] == utils.ATOMIC_WRITE_REPLACE_ATTEMPTS
    assert target.read_text(encoding="utf-8") == '{"ok": true}\n'
    assert not list(tmp_path.glob(".last_checked.json.*"))


def test_atomic_write_text_cleanup_permission_error_does_not_mask_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "last_checked.json"
    original_unlink = os.unlink
    cleanup_attempts = {"count": 0}

    def failing_replace(_src: str, _dst: str) -> None:
        raise PermissionError("replace denied")

    def failing_fallback(_path: Path, _text: str) -> None:
        raise PermissionError("fallback denied")

    def flaky_unlink(path: str) -> None:
        cleanup_attempts["count"] += 1
        if cleanup_attempts["count"] == 1:
            raise PermissionError("cleanup denied")
        original_unlink(path)

    monkeypatch.setattr(utils.os, "replace", failing_replace)
    monkeypatch.setattr(utils, "_direct_overwrite_text", failing_fallback)
    monkeypatch.setattr(utils.os, "unlink", flaky_unlink)
    monkeypatch.setattr(utils.time, "sleep", lambda _seconds: None)

    with pytest.raises(PermissionError, match="replace denied"):
        atomic_write_text(target, '{"ok": false}\n')

    assert cleanup_attempts["count"] == 2
    assert not list(tmp_path.glob(".last_checked.json.*"))
