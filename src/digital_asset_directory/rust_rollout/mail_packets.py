from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..ids import stable_id
from ..utils import write_json
from .planner import build_rust_rollout_plan


def build_rust_rollout_mail_packets(config_path: Path, out_dir: Path) -> dict[str, Any]:
    plan = build_rust_rollout_plan(config_path)
    logos_dir = out_dir / "logos"
    non_logos_dir = out_dir / "non_logos"
    logos_dir.mkdir(parents=True, exist_ok=True)
    non_logos_dir.mkdir(parents=True, exist_ok=True)

    packets: list[dict[str, Any]] = []
    for decision in plan["decisions"]:
        packet = _packet(decision)
        target_dir = logos_dir if decision["contains_logos"] else non_logos_dir
        path = target_dir / f"{_slug(decision['repo'])}.json"
        write_json(path, packet)
        packets.append({**packet, "path": str(path)})

    readme = out_dir / "README.md"
    readme.write_text(
        "# DAD Rust Rollout Mail\n\n"
        "Deterministic local instruction packets only. These files do not send "
        "external email, mutate target repos, open GitHub PRs, or authorize "
        "source changes. Logos repos are instruction-mail-only.\n",
        encoding="utf-8",
    )
    return {
        "schema_version": "dad_rust_rollout_mail_build.v1",
        "packet_count": len(packets),
        "logos_packet_count": sum(1 for packet in packets if packet["payload"]["contains_logos"]),
        "non_logos_packet_count": sum(
            1 for packet in packets if not packet["payload"]["contains_logos"]
        ),
        "out_dir": str(out_dir),
        "packets": packets,
    }


def _packet(decision: dict[str, Any]) -> dict[str, Any]:
    repo = str(decision["repo"])
    packet_type = (
        "rust_logos_instruction_only"
        if decision["contains_logos"]
        else "rust_forced_rollout_candidate"
    )
    return {
        "schema_version": "dad_rust_rollout_mail_packet.v1",
        "mail_id": stable_id("rust-rollout-mail", repo, packet_type),
        "message_type": "capability_suggestion",
        "source_repo": "Digital-Assett-Directory",
        "target_repo": repo,
        "dedupe_key": stable_id("rust-rollout-dedupe", repo, decision["rust_status"]),
        "sensitivity": "metadata_only",
        "review_status": "candidate",
        "payload": {
            "rust_rollout_packet_type": packet_type,
            "contains_logos": bool(decision["contains_logos"]),
            "rollout_mode": decision["rollout_mode"],
            "can_apply": bool(decision["can_apply"]),
            "block_reason": decision["block_reason"],
            "target_repo_owns_rust_files": True,
            "python_stays_orchestrator": True,
            "rust_boundary": "deterministic leaf tooling only",
            "recommended_first_rust_slice": decision["recommended_first_rust_slice"],
            "validation_commands": decision["validation_commands"],
            "external_send_performed": False,
            "github_write_performed": False,
            "destructive_write_authorized": False,
        },
        "suggested_actions": _suggested_actions(decision),
        "evidence": [
            "config/repo_rust_status.yaml",
            "docs/rust/DAD_RUST_SCAN_CORE.md",
            "lessons/rust_rollout/lesson_ledger.jsonl",
        ],
    }


def _suggested_actions(decision: dict[str, Any]) -> list[str]:
    if decision["contains_logos"]:
        return [
            "Do not accept DAD forced Rust writes.",
            "Review DAD lessons and implement any Rust slice inside Logos governance.",
            "Keep Rust as scanners, indexers, manifest validators, and JSONL validators only.",
        ]
    if decision["can_apply"]:
        return [
            "Review the DAD Rust rollout plan.",
            "Keep Python as orchestrator and target repo as owner of Rust files.",
            "Run the listed validation commands after any local apply.",
        ]
    return [
        "Keep this packet as a candidate notice.",
        f"Resolve the block before any local apply: {decision['block_reason']}",
    ]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "-", value.casefold()).strip("-") or "repo"
