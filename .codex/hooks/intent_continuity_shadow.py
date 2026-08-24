"""Repo-local Codex command hook; success and failure are intentionally silent."""

from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
MAX_HOOK_INPUT_BYTES = 64 * 1024


def _runtime_enabled(event_name: str) -> bool:
    config = json.loads(
        (REPO_ROOT / "config/intent-continuity-shadow-hooks.json").read_text(
            encoding="utf-8"
        )
    )
    if config.get("status") != "supervised_silent_shadow":
        return False
    return any(
        trigger.get("runtime_event") == event_name and trigger.get("enabled") is True
        for trigger in config.get("triggers", [])
    )


def _repository_id() -> str:
    integration = json.loads(
        (REPO_ROOT / ".digital-asset/dad-integration.json").read_text(encoding="utf-8")
    )
    return str(integration.get("repo_id", ""))


def main() -> int:
    payload: object = {}
    hub_root: Path | None = None
    repository_id = ""
    record_failure = None
    try:
        raw = sys.stdin.buffer.read(MAX_HOOK_INPUT_BYTES + 1)
        if len(raw) > MAX_HOOK_INPUT_BYTES:
            return 0
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return 0
        event_name = payload.get("hook_event_name")
        if not isinstance(event_name, str) or not _runtime_enabled(event_name):
            return 0

        from digital_asset_directory.config import resolve_hub_root
        from digital_asset_directory.portfolio_continuity_codex_hook import (
            ingest_codex_hook,
            record_codex_hook_failure,
        )

        record_failure = record_codex_hook_failure
        hub_root = resolve_hub_root()
        repository_id = _repository_id()
        ingest_codex_hook(
            hub_root,
            payload,
            repository_id=repository_id,
        )
    except Exception:
        # Shadow observation must never block or add UI output. Reconciliation
        # reports missed coverage from authoritative local sources later.
        if hub_root is not None and isinstance(payload, dict) and record_failure is not None:
            try:
                record_failure(
                    hub_root,
                    payload,
                    repository_id=repository_id,
                    reason_code="hook_ingest_failed",
                )
            except Exception:
                pass
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
