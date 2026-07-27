"""Generated consumer-repo surfaces must never embed the local absolute hub path.

Consumer repos (some of which become public) receive DAD-managed surfaces:
the AGENTS.md governance block, `.githooks/pre-push` hooks,
`.digital-asset-directory.yml`, handoff/README files, and enrollment pointer
surfaces. Every one of them must reference the hub through `${DAD_HUB}` /
`$env:DAD_HUB` / `~/.dad/hub.json` indirection instead of a resolved absolute
path such as `C:\\Users\\...\\OneDrive\\Desktop\\...`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from digital_asset_directory.config import EnrollmentRepoPolicy
from digital_asset_directory.enrollment import (
    apply_enrollment,
    posix_pre_push_hook_text,
    powershell_pre_push_hook_text,
)
from digital_asset_directory.governance import (
    BEGIN,
    END,
    install_governance,
    scaffold_new_repo,
)

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]

WINDOWS_USERS_PATH = re.compile(r"[A-Za-z]:[\\/]Users[\\/]")
ONEDRIVE_DESKTOP = re.compile(r"OneDrive[\\/]Desktop")


def _assert_no_absolute_hub_path(surface: str, text: str, hub: Path) -> None:
    assert not WINDOWS_USERS_PATH.search(text), (
        f"{surface} embeds a local absolute path (drive:\\Users\\...)"
    )
    assert not ONEDRIVE_DESKTOP.search(text), (
        f"{surface} embeds an OneDrive/Desktop local path"
    )
    # Platform-independent leak check: the resolved hub path itself (native and
    # forward-slash spellings) must never appear in a consumer surface.
    resolved = str(hub.resolve())
    assert resolved not in text, f"{surface} embeds the resolved hub path"
    assert resolved.replace("\\", "/") not in text, (
        f"{surface} embeds the resolved hub path (forward-slash form)"
    )


def _assert_indirection(surface: str, text: str) -> None:
    assert "DAD_HUB" in text, f"{surface} does not reference DAD_HUB indirection"


def _fake_hub(tmp_path: Path) -> Path:
    hub = tmp_path / "hub"
    (hub / "scripts").mkdir(parents=True)
    (hub / "state" / "agent_sessions").mkdir(parents=True)
    return hub


def test_install_governance_surfaces_use_hub_indirection(tmp_path: Path) -> None:
    hub = _fake_hub(tmp_path)
    target = tmp_path / "consumer"
    target.mkdir()

    install_governance(target, hub)

    surfaces = {
        "AGENTS.md": target / "AGENTS.md",
        ".digital-asset-directory.yml": target / ".digital-asset-directory.yml",
        ".githooks/pre-push": target / ".githooks" / "pre-push",
        ".githooks/pre-push.ps1": target / ".githooks" / "pre-push.ps1",
        "DIGITAL_ASSET_DIRECTORY_HANDOFF.md": target / "DIGITAL_ASSET_DIRECTORY_HANDOFF.md",
        "CLAUDE.md": target / "CLAUDE.md",
    }
    for surface, path in surfaces.items():
        text = path.read_text(encoding="utf-8")
        _assert_no_absolute_hub_path(surface, text, hub)

    agents_text = surfaces["AGENTS.md"].read_text(encoding="utf-8")
    assert BEGIN in agents_text and END in agents_text
    _assert_indirection("AGENTS.md governance block", agents_text)
    assert "${DAD_HUB}" in agents_text

    yml_text = surfaces[".digital-asset-directory.yml"].read_text(encoding="utf-8")
    _assert_indirection(".digital-asset-directory.yml", yml_text)
    assert "hub_path: ${DAD_HUB}" in yml_text

    sh_hook = surfaces[".githooks/pre-push"].read_text(encoding="utf-8")
    _assert_indirection(".githooks/pre-push", sh_hook)
    assert "enforce_postflight.py" in sh_hook
    assert "~/.dad/hub.json" in sh_hook or ".dad" in sh_hook

    ps_hook = surfaces[".githooks/pre-push.ps1"].read_text(encoding="utf-8")
    _assert_indirection(".githooks/pre-push.ps1", ps_hook)
    assert "$env:DAD_HUB" in ps_hook
    assert "enforce_postflight.py" in ps_hook

    handoff = surfaces["DIGITAL_ASSET_DIRECTORY_HANDOFF.md"].read_text(encoding="utf-8")
    _assert_indirection("DIGITAL_ASSET_DIRECTORY_HANDOFF.md", handoff)


def test_install_governance_is_idempotent_with_indirection(tmp_path: Path) -> None:
    hub = _fake_hub(tmp_path)
    target = tmp_path / "consumer"
    target.mkdir()
    install_governance(target, hub)
    first = (target / "AGENTS.md").read_text(encoding="utf-8")
    install_governance(target, hub)
    second = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert first == second
    assert second.count(BEGIN) == 1


def test_scaffold_new_repo_readme_uses_hub_indirection(tmp_path: Path) -> None:
    hub = _fake_hub(tmp_path)
    target = tmp_path / "fresh"

    scaffold_new_repo(target, hub, name="Fresh Project")

    readme = (target / "README.md").read_text(encoding="utf-8")
    _assert_no_absolute_hub_path("README.md", readme, hub)
    _assert_indirection("README.md", readme)
    for rel in (
        "AGENTS.md",
        ".digital-asset-directory.yml",
        ".githooks/pre-push",
        ".githooks/pre-push.ps1",
        "DIGITAL_ASSET_DIRECTORY_HANDOFF.md",
    ):
        text = (target / rel).read_text(encoding="utf-8")
        _assert_no_absolute_hub_path(rel, text, hub)


def test_shared_pre_push_hook_texts_carry_no_absolute_path() -> None:
    sh_hook = posix_pre_push_hook_text()
    ps_hook = powershell_pre_push_hook_text()
    for surface, text in (("posix hook", sh_hook), ("powershell hook", ps_hook)):
        assert not WINDOWS_USERS_PATH.search(text)
        assert not ONEDRIVE_DESKTOP.search(text)
        _assert_indirection(surface, text)
        assert "~/.dad/hub.json" in text or "hub.json" in text
        assert "enforce_postflight.py" in text
    assert "$env:DAD_HUB" in ps_hook or "$DadHub" in ps_hook


def _enrollment_policy(
    repo: Path, *, visibility: str = "internal", public_facing: bool = False
) -> EnrollmentRepoPolicy:
    return EnrollmentRepoPolicy(
        id="repo-a",
        path=repo,
        alias="repo-a",
        visibility=visibility,
        public_facing=public_facing,
        enrollment_enabled=True,
        apply_allowed=True,
        update_allowed=True,
        active_hold=False,
        active_hold_reason="",
        allow_dirty_worktree=False,
        allow_non_main_branch=False,
        wave="wave-a",
        approved_approval_ids=["APPROVED-1"],
        local_paths_allowed=False,
        repo_type="application",
        languages=["python"],
        domains=["test"],
        context_tags=["persistent_repo"],
        validation_commands=["python -m pytest"],
    )


ENROLLMENT_CONSUMER_SURFACES = [
    "AGENTS.md",
    "CLAUDE.md",
    "AI_FRONT_DOOR.md",
    "AI_TABLE_OF_CONTENTS.md",
    ".githooks/pre-push",
    ".githooks/pre-push.ps1",
    ".ai-assets.json",
    ".digital-asset/dad-integration.json",
    ".digital-asset/context-map.json",
    ".digital-asset/skills/checkout.json",
    ".digital-asset/governance-map.yaml",
    ".digital-asset/data-map.yaml",
]


def _seed_enrollment_hub(tmp_path: Path) -> tuple[Path, Path]:
    hub = tmp_path / "hub"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    registry = hub / "registry" / "exception-capture-pattern-registry.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        (ROOT / "registry" / "exception-capture-pattern-registry.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    return hub, repo


def test_enrollment_apply_public_safe_surfaces_have_no_local_paths(
    tmp_path: Path,
) -> None:
    """A public-facing consumer repo must receive zero local absolute paths."""
    hub, repo = _seed_enrollment_hub(tmp_path)
    policy = _enrollment_policy(repo, visibility="public", public_facing=True)

    apply_enrollment(hub, policy, approval_id="APPROVED-1")

    for rel in ENROLLMENT_CONSUMER_SURFACES:
        text = (repo / rel).read_text(encoding="utf-8")
        _assert_no_absolute_hub_path(rel, text, hub)

    agents_text = (repo / "AGENTS.md").read_text(encoding="utf-8")
    _assert_indirection("enrollment AGENTS.md block", agents_text)
    for rel in (".githooks/pre-push", ".githooks/pre-push.ps1"):
        _assert_indirection(rel, (repo / rel).read_text(encoding="utf-8"))


def test_enrollment_apply_internal_policy_never_embeds_hub_path(
    tmp_path: Path,
) -> None:
    """Even internal repos never embed the private hub's absolute path.

    `dad-integration.json` may carry the consumer repo's OWN path when the
    reviewed policy allows local paths (`local_paths_included`), so the generic
    drive-letter regexes are only asserted on the other surfaces; the hub path
    itself must never appear anywhere.
    """
    hub, repo = _seed_enrollment_hub(tmp_path)

    apply_enrollment(hub, _enrollment_policy(repo), approval_id="APPROVED-1")

    resolved_hub = str(hub.resolve())
    for rel in ENROLLMENT_CONSUMER_SURFACES:
        text = (repo / rel).read_text(encoding="utf-8")
        assert resolved_hub not in text, f"{rel} embeds the resolved hub path"
        assert resolved_hub.replace("\\", "/") not in text, (
            f"{rel} embeds the resolved hub path (forward-slash form)"
        )
        if rel != ".digital-asset/dad-integration.json":
            _assert_no_absolute_hub_path(rel, text, hub)
