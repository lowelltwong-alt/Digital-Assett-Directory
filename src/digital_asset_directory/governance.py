from __future__ import annotations

import os
from pathlib import Path
import subprocess
import yaml

from .learning import git_changed_files, open_sessions
from .logos_write_guard import assert_dad_write_allowed
from .mail_center import mail_gitignore_text, mail_readme_text
from .utils import atomic_write_text

BEGIN = "<!-- BEGIN DIGITAL_ASSET_DIRECTORY_GOVERNANCE -->"
END = "<!-- END DIGITAL_ASSET_DIRECTORY_GOVERNANCE -->"


def _managed_block(hub: Path) -> str:
    return f"""{BEGIN}
## Digital Asset Directory learning contract

Central hub: `{hub}`

Before material AI-assisted work:
1. Read this repository's own front door and authority surfaces.
2. Run: `asset-dir agent preflight --repo . --agent <agent> --task \"<task>\" --hub \"{hub}\"`
3. State scope, allowed/forbidden paths, validation plan, and stop conditions.
4. For load-bearing decisions that affect shared contracts, schemas, CI/hooks, governance,
   scoring/ranking, roadmap gates, source-boundary rules, dependencies, migrations, or
   future-agent defaults, classify high/medium/low risk before implementation. High-risk
   decisions require human attention, implementer red-team, premortem, rollback criteria,
   and fresh-eyes review.

For CI, test selection, path filters, required checks, module ownership, or
integration/release workflow changes, use the DAD CI module-boundary capability.
Ordinary PR checks must follow declared module ownership and dependency edges;
scheduled full-system regression stays separate. Never broaden one module's
workflow across the repository without an explicit reviewed exception.

If `asset-dir` is not available on `PATH`, use the stable user shim at
`~/.dad/bin/asset-dir` (POSIX shells) or `~/.dad/bin/asset-dir.ps1`
(PowerShell). If neither shim exists, run from the DAD checkout with
`PYTHONPATH=src python -m digital_asset_directory.cli agent preflight --repo . --agent <agent-id> --task "<task>"`
(POSIX) or `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli agent preflight --repo . --agent <agent-id> --task "<task>"`
(PowerShell).
A missing CLI does not relax local fail-closed boundaries.

Agent runtime policy: `AGENTS.md`, DAD CLI lifecycle commands, schemas, audit
records, deterministic hooks, and human gates are the durable contract. Runtime
files for Claude, Codex, Cursor, Copilot, or future agents are optional adapters
only and must not become the sole authority for DAD governance.

Before reporting completion or pushing material changes:
1. Run appropriate tests and report exact outcomes.
2. Run `asset-dir agent postflight --session <SESSION_ID> --repo . --summary \"<summary>\" --hub \"{hub}\"`.
3. Capture lessons, discoveries, failures, reusable patterns, missing capabilities, risks, and unknowns.

If work is PR-ready, an actual PR is open, or a branch is intentionally left after
a work session, record branch/PR status, owner or next reviewer, validation refs,
next action, and escalation date. Send metadata-only DAD mail for stuck,
superseded, duplicate, conflict-heavy, or stale PR/branch queues when local
policy allows.

The central directory catalogs evidence and candidates. It does not override this repository's local canon or authority boundaries.
{END}
"""


def install_governance(target_repo: Path, hub_root: Path, force: bool = False) -> list[Path]:
    target_repo = target_repo.resolve()
    hub_root = hub_root.resolve()
    assert_dad_write_allowed(target_repo)
    target_repo.mkdir(parents=True, exist_ok=True)
    changed: list[Path] = []
    agents = target_repo / "AGENTS.md"
    existing = agents.read_text(encoding="utf-8") if agents.exists() else "# Agent Instructions\n\n"
    block = _managed_block(hub_root)
    if BEGIN in existing and END in existing:
        prefix, rest = existing.split(BEGIN, 1)
        _, suffix = rest.split(END, 1)
        new = prefix.rstrip() + "\n\n" + block + suffix.lstrip("\n")
    else:
        new = existing.rstrip() + "\n\n" + block
    if new != existing:
        atomic_write_text(agents, new)
        changed.append(agents)

    claude = target_repo / "CLAUDE.md"
    if not claude.exists() or force:
        content = (
            claude.read_text(encoding="utf-8")
            if claude.exists()
            else "# Claude Code Instructions\n\n"
        )
        if "@AGENTS.md" not in content:
            content = content.rstrip() + "\n\n@AGENTS.md\n"
        atomic_write_text(claude, content)
        changed.append(claude)

    config = target_repo / ".digital-asset-directory.yml"
    payload = {
        "version": "0.1.0",
        "hub_path": str(hub_root),
        "lessons_required": True,
        "handoff_required": True,
        "enforcement": "pre_push",
        "source_repo_authority_preserved": True,
        "load_bearing_decision_review": {
            "enabled": True,
            "high_risk_requires_human_gate": True,
            "fresh_eyes_review_template": "templates/load-bearing-decision-review.template.md",
        },
        "mail": {
            "enabled": True,
            "mailbox_path": ".digital-asset/mail",
            "digest_stale_after_hours": 24,
            "candidate_only": True,
        },
    }
    atomic_write_text(config, yaml.safe_dump(payload, sort_keys=False))
    changed.append(config)

    mailbox = target_repo / ".digital-asset" / "mail"
    mailbox.mkdir(parents=True, exist_ok=True)
    mail_readme = mailbox / "README.md"
    if not mail_readme.exists() or force:
        atomic_write_text(mail_readme, mail_readme_text())
        changed.append(mail_readme)
    mail_gitignore = mailbox / ".gitignore"
    if not mail_gitignore.exists() or force:
        atomic_write_text(mail_gitignore, mail_gitignore_text())
        changed.append(mail_gitignore)
    for name in ("inbox.jsonl", "outbox.jsonl", "archive.jsonl"):
        path = mailbox / name
        if not path.exists():
            atomic_write_text(path, "")
            changed.append(path)

    hook_dir = target_repo / ".githooks"
    hook_dir.mkdir(exist_ok=True)
    hook = hook_dir / "pre-push"
    hook_text = (
        "#!/usr/bin/env sh\n"
        "set -eu\n"
        f'HUB="{str(hub_root).replace(os.sep, "/")}"\n'
        'python "$HUB/scripts/enforce_postflight.py" --hub "$HUB" --repo "$(pwd)"\n'
    )
    atomic_write_text(hook, hook_text)
    try:
        hook.chmod(0o755)
    except OSError:
        pass
    changed.append(hook)

    ps_hook = hook_dir / "pre-push.ps1"
    atomic_write_text(
        ps_hook,
        f"$ErrorActionPreference='Stop'\npython '{hub_root / 'scripts' / 'enforce_postflight.py'}' --hub '{hub_root}' --repo (Get-Location).Path\n",
    )
    changed.append(ps_hook)

    instructions = target_repo / "DIGITAL_ASSET_DIRECTORY_HANDOFF.md"
    atomic_write_text(
        instructions,
        f"# Digital Asset Directory Handoff\n\nCentral hub: `{hub_root}`\n\nEnable the versioned hook for this clone:\n\n```powershell\ngit config core.hooksPath .githooks\n```\n\nUse the preflight/postflight commands in `AGENTS.md`.\n",
    )
    changed.append(instructions)
    return changed


STARTER_GITIGNORE = """__pycache__/
*.pyc
.venv/
venv/
.env
.env.*
*.pem
*.key
dist/
build/
"""

_DOWNSTREAM_REUSABLE_PREFIXES = (
    "src/",
    "lib/",
    "packages/",
    "apps/",
    "services/",
    "agents/",
    "skills/",
    "workflows/",
    "prompts/",
    "harnesses/",
    "schemas/",
    "registry/",
)


def scaffold_new_repo(target_repo: Path, hub_root: Path, name: str | None = None) -> list[Path]:
    """Create a new repository pre-wired to the hub: starter files + governance install.

    Git init and `core.hooksPath` are handled by `scripts/new_repo.ps1` so this stays
    import-safe and unit-testable without a git dependency.
    """
    target_repo = target_repo.resolve()
    hub_root = hub_root.resolve()
    assert_dad_write_allowed(target_repo)
    target_repo.mkdir(parents=True, exist_ok=True)
    project_name = name or target_repo.name
    changed: list[Path] = []

    readme = target_repo / "README.md"
    if not readme.exists():
        atomic_write_text(
            readme,
            f"# {project_name}\n\n"
            f"Connected to the Digital Asset Directory hub at `{hub_root}`.\n\n"
            "Before material AI work run the hub preflight; before reporting completion run "
            "the postflight. See `AGENTS.md` and `DIGITAL_ASSET_DIRECTORY_HANDOFF.md`.\n",
        )
        changed.append(readme)

    gitignore = target_repo / ".gitignore"
    if not gitignore.exists():
        atomic_write_text(gitignore, STARTER_GITIGNORE)
        changed.append(gitignore)

    ci_template = (
        hub_root
        / "templates"
        / "ci-module-boundary"
        / "monorepo"
        / "module-boundaries.yaml"
    )
    ci_manifest = target_repo / ".ci" / "module-boundaries.candidate.yaml"
    if ci_template.exists() and not ci_manifest.exists() and not (target_repo / ".ci" / "module-boundaries.yaml").exists():
        payload = yaml.safe_load(ci_template.read_text(encoding="utf-8"))
        payload["repository"]["repository_id"] = project_name.lower().replace(" ", "-")
        ci_manifest.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(ci_manifest, yaml.safe_dump(payload, sort_keys=False))
        changed.append(ci_manifest)
        adoption_source = hub_root / "templates" / "ci-module-boundary" / "ADOPTION.md"
        if adoption_source.exists():
            adoption_target = target_repo / ".ci" / "ADOPTION.md"
            atomic_write_text(adoption_target, adoption_source.read_text(encoding="utf-8"))
            changed.append(adoption_target)
        schema_source = hub_root / "schemas" / "ci-module-boundary.schema.json"
        if schema_source.exists():
            schema_target = target_repo / "schemas" / "ci-module-boundary.schema.json"
            schema_target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(schema_target, schema_source.read_text(encoding="utf-8"))
            changed.append(schema_target)

    changed.extend(install_governance(target_repo, hub_root))
    return changed


def enforce_postflight(hub_root: Path, target_repo: Path) -> tuple[bool, str]:
    pending = open_sessions(hub_root, target_repo)
    if pending:
        ids = ", ".join(item["session_id"] for item in pending)
        return False, f"Open AI work session(s) require postflight handoff: {ids}"
    hub_portability = hub_root / "registry" / "portable-capability-registry.json"
    local_portability = target_repo / "registry" / "portable-capability-registry.json"
    if hub_portability.exists() or local_portability.exists():
        from .portability_control import assess_lifecycle, classify_eligibility

        changed = git_changed_files(target_repo)
        try:
            upstream = subprocess.run(
                ["git", "-C", str(target_repo), "rev-parse", "--abbrev-ref", "@{upstream}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            comparison = upstream.stdout.strip() if upstream.returncode == 0 else "origin/main"
            committed = subprocess.run(
                ["git", "-C", str(target_repo), "diff", "--name-only", f"{comparison}...HEAD"],
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
            if committed.returncode == 0:
                changed.extend(committed.stdout.splitlines())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        changed = sorted({path.replace("\\", "/") for path in changed if path})
        enrolled = (target_repo / ".digital-asset" / "dad-integration.json").exists()
        downstream_reusable_changes = [
            path for path in changed if path.startswith(_DOWNSTREAM_REUSABLE_PREFIXES)
        ]
        if enrolled and not local_portability.exists() and downstream_reusable_changes:
            return False, (
                "Portability protected-release gate blocked: enrolled downstream code or "
                "reusable-asset changes require a reviewed local portability registry/path policy"
            )
        if (
            not local_portability.exists()
            and classify_eligibility("", changed)["applicability"] == "portable_required"
        ):
            return False, (
                "Portability protected-release gate blocked: downstream governed changes "
                "require a reviewed local portability disposition or adoption contract"
            )

        assessment = assess_lifecycle(
            target_repo if local_portability.exists() else hub_root,
            stage="release",
            paths=changed,
            protected_transition=True,
        )
        if assessment["gate_outcome"] == "block":
            return False, (
                "Portability protected-release gate blocked: "
                + ", ".join(assessment["finding_codes"])
            )
    return True, "No open Digital Asset Directory agent sessions for this repository."
