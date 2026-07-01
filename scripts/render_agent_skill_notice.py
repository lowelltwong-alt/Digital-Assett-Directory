from __future__ import annotations

import argparse
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from render_agent_skill_checkout import find_skill, load_registry, pointer_payload


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = {
    "checkout": "templates/mail/skill-checkout-request.mail.template.json",
    "update": "templates/mail/skill-update-available.mail.template.json",
    "retirement": "templates/mail/skill-retirement-notice.mail.template.json",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_template(kind: str) -> dict[str, Any]:
    return json.loads((ROOT / TEMPLATES[kind]).read_text(encoding="utf-8"))


def stable_id(prefix: str, key: str) -> str:
    return f"{prefix}:{uuid.uuid5(uuid.NAMESPACE_URL, key)}"


def build_notice(
    *,
    kind: str,
    skill: dict[str, Any],
    target_repo: str,
    hub: str,
    created_at: str,
    from_version: str,
    to_version: str,
    replacement_skill: str,
    human_release_required: bool,
    include_local_paths: bool,
) -> dict[str, Any]:
    if kind == "retirement" and skill["status"] not in {"deprecated", "retired", "replaced"}:
        raise SystemExit(
            f"Refusing to render retirement notice for non-retired skill {skill['skill_id']}; "
            "mark the skill deprecated, retired, or replaced first."
        )
    template = load_template(kind)
    skill_id = skill["skill_id"]
    current_version = skill["version"]
    target_key = target_repo.strip()
    if kind == "checkout":
        dedupe_key = f"skill-checkout:{skill_id}:{current_version}:{target_key}"
    elif kind == "update":
        old = from_version or "<unknown>"
        new = to_version or current_version
        dedupe_key = f"skill-update:{skill_id}:{old}:{new}:{target_key}"
    else:
        dedupe_key = f"skill-retirement:{skill_id}:{current_version}:{target_key}"

    template["mail_id"] = stable_id("dad:mail", dedupe_key)
    template["thread_id"] = stable_id("dad:thread", f"skill:{skill_id}:{target_key}")
    template["target_repo"] = target_key
    template["created_at"] = created_at
    template["dedupe_key"] = dedupe_key

    pointer = pointer_payload(skill, hub, include_local_paths=include_local_paths)
    pointer_text = json.dumps(pointer, indent=2)
    payload = template["payload"]
    payload["source_skill"] = skill_id
    payload["summary"] = skill["description"]
    payload["exact_managed_block_or_pointer_content"] = pointer_text
    if kind == "checkout":
        payload["source_version"] = current_version
    elif kind == "update":
        payload["from_version"] = from_version or "<unknown>"
        payload["to_version"] = to_version or current_version
    else:
        payload["retired_version"] = current_version
        payload["replacement_skill"] = replacement_skill or skill["lifecycle"].get(
            "replacement_skill_id",
            "",
        )

    provenance = template["source_provenance"]
    provenance["canonical_source_repo"] = "dad://hub/Digital-Assett-Directory"
    provenance["composed_by"] = "render_agent_skill_notice.py"
    provenance["collected_at"] = created_at
    provenance["received_at"] = created_at

    release = template["public_release"]
    release["public_release_required"] = human_release_required
    release["public_release_status"] = "pending_human" if human_release_required else "not_required"
    release["release_reason"] = (
        "Human release required before public-facing delivery or until reviewed mail policy routes this packet."
        if human_release_required
        else ""
    )
    return template


def write_or_print(payload: dict[str, Any], output: Path | None, force: bool) -> None:
    content = json.dumps(payload, indent=2) + "\n"
    if output is None:
        print(content)
        return
    if output.exists() and not force:
        raise SystemExit(f"Refusing to overwrite existing output without --force: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render DAD agent skill lifecycle mail.")
    parser.add_argument("--notice-kind", choices=sorted(TEMPLATES), required=True)
    parser.add_argument("--skill-id", required=True)
    parser.add_argument("--target-repo", required=True)
    parser.add_argument("--hub", default="../Digital-Assett-Directory")
    parser.add_argument("--created-at", default=utc_now())
    parser.add_argument("--from-version", default="")
    parser.add_argument("--to-version", default="")
    parser.add_argument("--replacement-skill", default="")
    parser.add_argument(
        "--release-not-required",
        action="store_true",
        help="Mark public release not required; use only after reviewed internal target policy.",
    )
    parser.add_argument(
        "--human-release-required",
        action="store_true",
        help="Deprecated compatibility flag; notices require human release by default.",
    )
    parser.add_argument(
        "--include-local-paths",
        action="store_true",
        help="Include local filesystem paths in embedded pointer; use only for private/internal mail.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    registry = load_registry()
    skill = find_skill(registry, args.skill_id)
    payload = build_notice(
        kind=args.notice_kind,
        skill=skill,
        target_repo=args.target_repo,
        hub=args.hub,
        created_at=args.created_at,
        from_version=args.from_version,
        to_version=args.to_version,
        replacement_skill=args.replacement_skill,
        human_release_required=not args.release_not_required or args.human_release_required,
        include_local_paths=args.include_local_paths,
    )
    write_or_print(payload, args.output, args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
