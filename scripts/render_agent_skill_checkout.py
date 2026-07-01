from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_REL = "registry/agent-skill-library.json"
PUBLIC_HUB_REF = "dad://hub/Digital-Assett-Directory"
PUBLIC_REGISTRY_REF = "dad://registry/agent-skill-library"
PUBLIC_MAIL_REF = "dad://mail/outbox"


def load_registry() -> dict[str, Any]:
    return json.loads((ROOT / REGISTRY_REL).read_text(encoding="utf-8"))


def find_skill(registry: dict[str, Any], skill_id: str) -> dict[str, Any]:
    for skill in registry.get("skills", []):
        if skill["skill_id"] == skill_id:
            return skill
    raise SystemExit(f"Unknown skill_id: {skill_id}")


def pointer_payload(skill: dict[str, Any], hub: str, *, include_local_paths: bool = False) -> dict[str, Any]:
    hub_root = hub.rstrip("/").rstrip(chr(92))
    skill_ref = f"dad://skill/{skill['skill_id']}/{skill['version']}"
    skill_row: dict[str, Any] = {
        "skill_id": skill["skill_id"],
        "source": skill_ref,
        "entrypoint": f"{skill_ref}/SKILL.md",
        "version": skill["version"],
        "status": skill["status"],
        "skill_format": skill["skill_format"],
        "checkout_mode": "pointer",
        "return_address": PUBLIC_MAIL_REF,
        "update_channel": skill["update_policy"],
        "required_before": skill["trigger_examples"],
        "capabilities": skill["capabilities"],
    }
    if include_local_paths:
        skill_row.update(
            {
                "local_source_path": f"{hub_root}/{skill['path']}",
                "local_entrypoint": f"{hub_root}/{skill['entrypoint']}",
                "local_return_address": f"{hub_root}/processed/mail/outbox",
            }
        )
    payload: dict[str, Any] = {
        "schema_version": "0.1.0",
        "pointer_type": "dad_agent_skill_checkout",
        "hub": PUBLIC_HUB_REF,
        "source_provenance": {
            "source_repo_id": "dad",
            "source_repo_alias": "Digital-Assett-Directory",
            "source_visibility": "internal",
            "source_registry": PUBLIC_REGISTRY_REF,
            "return_address": PUBLIC_MAIL_REF,
            "local_paths_included": include_local_paths,
        },
        "authority_boundary": (
            "This checkout is advisory. The target repo decides whether to adopt, "
            "update, retire, replace, or remove the skill pointer."
        ),
        "daily_check": {
            "skill_digest_stale_after_hours": 24,
            "preflight_behavior": "warn_only_when_stale",
        },
        "checked_out_skills": [skill_row],
        "do_not_copy_full_skills_without_approval": True,
        "local_adoption_required": True,
    }
    if include_local_paths:
        payload["local_hub_path"] = hub_root
    return payload


def wrapper_text(skill: dict[str, Any], hub: str, *, include_local_paths: bool = False) -> str:
    pointer = pointer_payload(skill, hub, include_local_paths=include_local_paths)
    source = pointer["checked_out_skills"][0]
    lines = [
        "---",
        f"name: {skill['name'].lower().replace(' ', '-')}-checkout",
        (
            "description: Use when this repo needs the DAD-managed "
            f"{skill['name']} skill. This wrapper routes agents to DAD source "
            "metadata and keeps local adoption under repo authority."
        ),
        "---",
        "",
        f"# {skill['name']} Checkout",
        "",
        "This is a lightweight wrapper, not a full skill copy.",
        "",
        f"- Skill ID: `{skill['skill_id']}`",
        f"- Version: `{skill['version']}`",
        f"- DAD registry: `{pointer['source_provenance']['source_registry']}`",
        f"- DAD source ref: `{source['source']}`",
        f"- DAD entrypoint: `{source['entrypoint']}`",
        f"- Return address: `{source['return_address']}`",
        "",
        "Do not copy full DAD skills into this repo unless explicitly approved.",
        "Do not install plugins, hooks, MCP servers, or automation from this wrapper alone.",
        "Skill mail is candidate evidence only; local review decides adoption.",
        "",
        "Before material work, read the target repo authority files, then consult the DAD entrypoint above.",
    ]
    if include_local_paths:
        lines.extend(
            [
                "",
                "Local private/internal path hints:",
                "",
                f"- Local hub path: `{pointer['local_hub_path']}`",
                f"- Local source path: `{source['local_source_path']}`",
                f"- Local entrypoint: `{source['local_entrypoint']}`",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def write_or_print(content: str, output: Path | None, force: bool) -> None:
    if output is None:
        print(content)
        return
    if output.exists() and not force:
        raise SystemExit(f"Refusing to overwrite existing output without --force: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a DAD agent skill checkout pointer.")
    parser.add_argument("--skill-id", help="Skill ID from registry/agent-skill-library.json")
    parser.add_argument("--hub", default="../Digital-Assett-Directory", help="Path to the DAD hub")
    parser.add_argument("--mode", choices=["pointer", "wrapper"], default="pointer")
    parser.add_argument("--output", type=Path, help="Optional output path; stdout by default")
    parser.add_argument("--force", action="store_true", help="Overwrite output path if it exists")
    parser.add_argument(
        "--include-local-paths",
        action="store_true",
        help="Include local filesystem paths; use only for private/internal checkouts.",
    )
    parser.add_argument("--list", action="store_true", help="List available skills")
    args = parser.parse_args()

    registry = load_registry()
    if args.list:
        for skill in registry.get("skills", []):
            print(f"{skill['skill_id']}\t{skill['name']}\t{skill['version']}\t{skill['status']}")
        return 0
    if not args.skill_id:
        raise SystemExit("--skill-id is required unless --list is used")

    skill = find_skill(registry, args.skill_id)
    if args.mode not in skill["checkout_modes"]:
        raise SystemExit(f"{args.mode} checkout is not allowed for {args.skill_id}")

    if args.mode == "pointer":
        content = (
            json.dumps(
                pointer_payload(skill, args.hub, include_local_paths=args.include_local_paths),
                indent=2,
            )
            + "\n"
        )
    else:
        content = wrapper_text(skill, args.hub, include_local_paths=args.include_local_paths)
    write_or_print(content, args.output, args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
