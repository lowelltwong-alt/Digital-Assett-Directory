from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..ids import stable_id
from ..models import MailMessageRecord
from ..utils import atomic_write_text, json_dumps, write_json
from .planner import build_rust_rollout_plan

RUST_ROLLOUT_PACKET_CREATED_AT = "2026-07-02T17:56:48.839505+00:00"


def build_rust_rollout_mail_packets(config_path: Path, out_dir: Path) -> dict[str, Any]:
    plan = build_rust_rollout_plan(config_path)
    logos_dir = out_dir / "logos"
    non_logos_dir = out_dir / "non_logos"
    expected_paths: set[Path] = {out_dir / "README.md"}
    for decision in plan["decisions"]:
        target_dir = logos_dir if decision["contains_logos"] else non_logos_dir
        expected_paths.add(target_dir / f"{_slug(decision['repo'])}.json")
    stale_paths = []
    if out_dir.exists():
        expected_resolved = {path.resolve(strict=False) for path in expected_paths}
        stale_paths = [
            path
            for path in sorted(out_dir.rglob("*.json"))
            if path.resolve(strict=False) not in expected_resolved
        ]
    if stale_paths:
        sample = ", ".join(_relative_to_out_dir(path, out_dir) for path in stale_paths[:5])
        raise ValueError(
            "stale Rust rollout packet files remain in output directory: "
            f"{sample}"
        )
    logos_dir.mkdir(parents=True, exist_ok=True)
    non_logos_dir.mkdir(parents=True, exist_ok=True)

    packets: list[dict[str, Any]] = []
    write_counts = {"written": 0, "unchanged": 0}
    for decision in plan["decisions"]:
        packet = _packet(decision)
        target_dir = logos_dir if decision["contains_logos"] else non_logos_dir
        path = target_dir / f"{_slug(decision['repo'])}.json"
        _write_json_if_changed(path, packet, write_counts)
        packets.append({**packet, "path": str(path)})

    readme = out_dir / "README.md"
    _write_text_if_changed(
        readme,
        "# DAD Rust Rollout Mail\n\n"
        "Deterministic local instruction packets only. These files do not send external\n"
        "email, mutate target repos, open GitHub PRs, authorize source changes, or clear\n"
        "public/private release gates.\n\n"
        "Every packet in this folder is staged candidate evidence with\n"
        "`delivery_status=staged_not_deliverable`,\n"
        "`requires_target_policy_review=true`, and\n"
        "`public_release_status=pending_human` until the target repo visibility and local\n"
        "policy are reviewed.\n\n"
        "Logos repos are instruction-mail-only.\n\n"
        "During concurrent Rust rollout work, run DAD's dirty-spool diagnostic before\n"
        "collecting, routing, or delivering mail:\n\n"
        "```powershell\n"
        "python -m digital_asset_directory.cli mail storm-gate\n"
        "python -m digital_asset_directory.cli mail doctor --repo all --summary-only --fail-on-dirty --fail-on-coverage-gap\n"
        "python -m digital_asset_directory.cli rust mail-spool-check\n"
        "```\n\n"
        "`mail storm-gate` is the first compact go/no-go answer for concurrent repo\n"
        "mail. `mail doctor` separates mailbox/staged-packet dirt from ordinary DAD git\n"
        "worktree dirt. If it reports `dirty=false` and `worktree_dirty=true`, mail\n"
        "collection/routing is not blocked by that fact alone; review the worktree with\n"
        "`git status` and use `--fail-on-worktree-dirty` only for scripts that require a\n"
        "clean DAD tree. The Rust probe is read-only, alias-only structural evidence;\n"
        "it does not authorize collect, route, deliver, public release, or adoption.\n\n"
        "Repo agents should write Rust lessons or rollout feedback to their own\n"
        "`.digital-asset/mail/outbox.jsonl`. Do not write directly to DAD's\n"
        "`processed/mail/inbox/*.jsonl` or a target repo's `.digital-asset/mail/inbox.jsonl`;\n"
        "DAD collection and delivery create those rows and the matching audit logs.\n\n"
        "Routine `asset-dir rust-rollout build-mail` output goes to ignored staging under\n"
        "`processed/mail/staged/rust_rollout/` by default. The tracked\n"
        "`mail/outbox/rust_rollout/` folder is a reference snapshot for review, not the\n"
        "write target every branch should churn.\n",
        write_counts,
    )
    return {
        "schema_version": "dad_rust_rollout_mail_build.v1",
        "packet_count": len(packets),
        "logos_packet_count": sum(1 for packet in packets if packet["payload"]["contains_logos"]),
        "non_logos_packet_count": sum(
            1 for packet in packets if not packet["payload"]["contains_logos"]
        ),
        "out_dir": str(out_dir),
        "write_counts": write_counts,
        "packets": packets,
    }


def _packet(decision: dict[str, Any]) -> dict[str, Any]:
    repo = str(decision["repo"])
    packet_type = (
        "rust_logos_instruction_only"
        if decision["contains_logos"]
        else "rust_forced_rollout_candidate"
    )
    revision_basis = {
        "repo": repo,
        "packet_type": packet_type,
        "rust_status": decision["rust_status"],
        "rollout_mode": decision["rollout_mode"],
        "can_apply": bool(decision["can_apply"]),
        "block_reason": decision["block_reason"],
        "target_repo_owns_rust_files": bool(decision["target_repo_owns_rust_files"]),
        "recommended_first_rust_slice": decision["recommended_first_rust_slice"],
        "validation_commands": decision["validation_commands"],
    }
    revision_id = stable_id("rust-rollout-revision", json_dumps(revision_basis))
    dedupe_key = stable_id("rust-rollout-dedupe", repo, packet_type, revision_id)
    record = MailMessageRecord(
        mail_id=stable_id("rust-rollout-mail", repo, packet_type, revision_id),
        thread_id=stable_id("rust-rollout-thread", repo),
        message_type="capability_suggestion",
        source_repo="dad",
        target_repo=repo,
        created_at=RUST_ROLLOUT_PACKET_CREATED_AT,
        dedupe_key=dedupe_key,
        sensitivity="internal",
        review_status="generated_candidate",
        payload={
            "instruction_artifact_kind": "rust_rollout_local_instruction_packet",
            "rust_rollout_packet_type": packet_type,
            "rust_rollout_revision_id": revision_id,
            "contains_logos": bool(decision["contains_logos"]),
            "rollout_mode": decision["rollout_mode"],
            "can_apply": bool(decision["can_apply"]),
            "block_reason": decision["block_reason"],
            "target_repo_owns_rust_files": bool(decision["target_repo_owns_rust_files"]),
            "python_stays_orchestrator": True,
            "rust_boundary": "deterministic leaf tooling only",
            "recommended_first_rust_slice": decision["recommended_first_rust_slice"],
            "validation_commands": decision["validation_commands"],
            "external_send_performed": False,
            "github_write_performed": False,
            "destructive_write_authorized": False,
            "delivery_status": "staged_not_deliverable",
            "requires_target_policy_review": True,
            "packet_identity_basis": (
                "mail_id and dedupe_key include the Rust rollout revision hash; "
                "thread_id remains stable by repo so changed recommendations are "
                "upgrades, not duplicate resends."
            ),
        },
        suggested_actions=_suggested_actions(decision),
        evidence=[
            "config/repo_rust_status.yaml",
            "docs/rust/DAD_RUST_SCAN_CORE.md",
            "lessons/rust_rollout/lesson_ledger.jsonl",
        ],
        source_provenance={
            "canonical_source_repo": "dad://hub/Digital-Assett-Directory",
            "source_repo_id": "dad",
            "source_repo_alias": "dad",
            "source_visibility": "internal",
            "original_source_chain": ["dad://hub/Digital-Assett-Directory"],
            "return_address": "dad://rust-rollout/local-instruction-packets",
            "original_mail_id": "",
            "composed_by": "dad-rust-rollout",
            "collected_by": "",
            "collected_at": "",
            "received_at": RUST_ROLLOUT_PACKET_CREATED_AT,
        },
        public_release={
            "target_visibility": "unknown",
            "target_public_facing": False,
            "public_release_required": True,
            "public_release_status": "pending_human",
            "human_release_id": "",
            "release_reason": (
                "internal DAD-origin Rust rollout packet targets unknown repo visibility; "
                "keep staged until target policy and release posture are reviewed"
            ),
        },
    )
    return record.model_dump(mode="json")


def _suggested_actions(decision: dict[str, Any]) -> list[str]:
    gate = "Do not deliver or apply this packet until target visibility and local policy are reviewed."
    if decision["contains_logos"]:
        return [
            gate,
            "Do not accept DAD forced Rust writes.",
            "Review DAD lessons and implement any Rust slice inside Logos governance.",
            "Keep Rust as scanners, indexers, manifest validators, and JSONL validators only.",
        ]
    if decision["can_apply"]:
        return [
            gate,
            "Review the DAD Rust rollout plan.",
            "Keep Python as orchestrator and target repo as owner of Rust files.",
            "Run the listed validation commands after any local apply.",
        ]
    return [
        gate,
        "Keep this packet as a candidate notice.",
        f"Resolve the block before any local apply: {decision['block_reason']}",
    ]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "-", value.casefold()).strip("-") or "repo"


def _relative_to_out_dir(path: Path, out_dir: Path) -> str:
    try:
        return path.relative_to(out_dir).as_posix()
    except ValueError:
        return path.name


def _write_json_if_changed(path: Path, value: dict[str, Any], counts: dict[str, int]) -> None:
    text = json_dumps(value, pretty=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        counts["unchanged"] += 1
        return
    write_json(path, value)
    counts["written"] += 1


def _write_text_if_changed(path: Path, text: str, counts: dict[str, int]) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        counts["unchanged"] += 1
        return
    atomic_write_text(path, text)
    counts["written"] += 1
