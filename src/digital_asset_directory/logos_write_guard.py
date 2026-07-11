from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


POLICY_RELATIVE_PATH = Path(".digital-asset") / "dad-write-policy.json"
LOGOS_REPO_NAMES = {
    "logos-governance-architecture",
    "logos-scripture-graph",
    "logos-scripture-graph-repo",
    "logos-boundary-literature",
    "logos-doctrine-genealogy",
}
LOGOS_REMOTE_SLUGS = {
    "lowelltwong-alt/logos-governance-architecture",
    "lowelltwong-alt/logos-scripture-graph",
    "lowelltwong-alt/logos-boundary-literature",
    "lowelltwong-alt/logos-doctrine-genealogy",
}
AUTHORITY_REGISTRY = Path(__file__).resolve().parents[2] / "registry/logos-repo-authority.json"


class LogosWriteBlocked(PermissionError):
    """Raised before DAD creates or changes anything under a protected Logos repo."""


def authority_registry() -> dict[str, Any]:
    try:
        value = json.loads(AUTHORITY_REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _reviewed_identities() -> tuple[set[str], set[str]]:
    names = set(LOGOS_REPO_NAMES)
    remotes = set(LOGOS_REMOTE_SLUGS)
    for row in authority_registry().get("repos", []):
        if not isinstance(row, dict) or row.get("dad_write_mode") != "deny":
            continue
        names.update(str(value).lower() for value in row.get("aliases", []) if value)
        if row.get("remote_slug"):
            remotes.add(str(row["remote_slug"]).lower())
    return names, remotes


def _policy_for_path(path: Path) -> tuple[Path, dict[str, Any]] | None:
    resolved = path.resolve(strict=False)
    current = resolved if resolved.is_dir() else resolved.parent
    for parent in (current, *current.parents):
        policy_path = parent / POLICY_RELATIVE_PATH
        if not policy_path.is_file():
            continue
        try:
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LogosWriteBlocked(
                f"DAD write blocked: unreadable Logos policy at {policy_path}"
            ) from exc
        if not isinstance(policy, dict):
            raise LogosWriteBlocked(
                f"DAD write blocked: invalid Logos policy at {policy_path}"
            )
        return parent, policy
    return None


def _path_ancestors(path: Path) -> tuple[Path, ...]:
    resolved = path.resolve(strict=False)
    current = resolved if resolved.is_dir() else resolved.parent
    return (current, *current.parents)


def _git_roots_for_path(path: Path) -> list[Path]:
    return [parent for parent in _path_ancestors(path) if (parent / ".git").exists()]


def _normalized_remote_slug(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    remote = result.stdout.strip().replace("\\", "/").lower()
    if remote.endswith(".git"):
        remote = remote[:-4]
    if ":" in remote and not remote.startswith(("http://", "https://")):
        remote = remote.split(":", 1)[1]
    if "github.com/" in remote:
        remote = remote.split("github.com/", 1)[1]
    return remote.strip("/")


def _logos_identity(path: Path) -> tuple[Path, str] | None:
    names, remotes = _reviewed_identities()
    for parent in _path_ancestors(path):
        if parent.name.lower() in names:
            return parent, parent.name.lower()
    for repo_root in _git_roots_for_path(path):
        remote = _normalized_remote_slug(repo_root)
        if remote in remotes:
            return repo_root, remote
    return None


def assert_dad_write_allowed(path: Path, *, approval_id: str | None = None) -> None:
    """Fail closed for a path below a Logos DAD write-policy marker.

    A human must first add a scoped approval ID to the repo-owned marker. DAD
    cannot edit that marker because this same guard protects it.
    """

    marker = _policy_for_path(path)
    identity = _logos_identity(path)
    if marker is None and identity is None:
        return
    repo_root = marker[0] if marker else identity[0]
    policy = marker[1] if marker else {}
    repo_id = str(policy.get("repo_id") or (identity[1] if identity else repo_root.name))
    raise LogosWriteBlocked(
        f"DAD write blocked for protected Logos repo {repo_id}: {path}. "
        "No standing or environment approval is accepted. A future owner-approved "
        "write must use a separately implemented foreground, scoped, single-use grant."
    )
