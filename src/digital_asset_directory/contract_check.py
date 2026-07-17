"""Deterministic DAD contract check for pushes and pull requests.

Verifies that changes touching protected paths carry a DAD lifecycle trace —
a ``DAD-Session:`` commit trailer (or PR-body line) produced by
``asset-dir agent postflight`` — or an explicit, logged ``DAD-Bypass:``.

Design constraints:

- Artifact-triggered, not behavior-triggered: the check keys on the diff, so
  it binds agents that never ran preflight (the ones advice cannot reach).
- Dependency-light on purpose: stdlib + PyYAML only, no package-relative
  imports, so CI can run it with ``pip install PyYAML`` and the pre-push hook
  can run it from a bare checkout.
- Protected paths derive from ``.ci/module-boundaries.yaml`` module roots plus
  policy extras; the policy file never becomes a second competing path list.
- Warn mode never fails; enforce mode is a reviewed policy flip
  (``registry/contract-check-policy.json``), not a code change.

A trailer's presence never proves the session was real or the work reviewed;
hub-side reconciliation audits trailer identifiers against the session store.
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from pathlib import Path
from typing import Any

POLICY_RELPATH = Path("registry") / "contract-check-policy.json"


def load_policy(hub_root: Path) -> dict[str, Any]:
    return json.loads((hub_root / POLICY_RELPATH).read_text(encoding="utf-8"))


def _load_manifest_roots(hub_root: Path, policy: dict[str, Any]) -> list[str]:
    source = policy.get("protected_paths_source", "")
    manifest_path = hub_root / source if source else None
    roots: list[str] = []
    if manifest_path and manifest_path.exists():
        import yaml

        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        for module in manifest.get("modules", []) or []:
            roots.extend(str(root) for root in module.get("roots", []) or [])
        roots.extend(str(path) for path in manifest.get("workflow_paths", []) or [])
    return roots


def protected_path_specs(hub_root: Path, policy: dict[str, Any]) -> list[str]:
    specs = _load_manifest_roots(hub_root, policy)
    specs.extend(str(glob) for glob in policy.get("extra_protected_globs", []) or [])
    return sorted(set(specs))


def _normalize(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def _matches(path: str, spec: str) -> bool:
    spec = _normalize(spec)
    path = _normalize(path)
    if fnmatch.fnmatch(path, spec):
        return True
    # A bare directory or file root protects everything beneath it.
    trimmed = spec[:-3] if spec.endswith("/**") else spec
    return path == trimmed or path.startswith(trimmed + "/")


def classify_paths(
    changed: list[str], specs: list[str], exempt: list[str]
) -> tuple[list[str], list[str]]:
    protected: list[str] = []
    unprotected: list[str] = []
    for path in changed:
        if any(_matches(path, glob) for glob in exempt):
            unprotected.append(path)
        elif any(_matches(path, spec) for spec in specs):
            protected.append(path)
        else:
            unprotected.append(path)
    return protected, unprotected


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return result.stdout


def changed_files(repo: Path, base: str, head: str = "HEAD") -> list[str]:
    output = _git(repo, "diff", "--name-only", f"{base}...{head}")
    return [line.strip() for line in output.splitlines() if line.strip()]


def _extract_trailers(
    text: str, key: str, pattern: str
) -> tuple[list[str], list[str]]:
    """Return (valid values, malformed values) for ``key:`` lines in text."""

    valid: list[str] = []
    malformed: list[str] = []
    matcher = re.compile(pattern)
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.lower().startswith(key.lower() + ":"):
            continue
        value = stripped[len(key) + 1 :].strip()
        if matcher.match(value):
            valid.append(value)
        else:
            malformed.append(value)
    return valid, malformed


def collect_traces(
    repo: Path,
    base: str,
    head: str,
    policy: dict[str, Any],
    extra_text: str = "",
) -> dict[str, Any]:
    messages = _git(repo, "log", "--format=%B%n", f"{base}..{head}")
    combined = messages + "\n" + (extra_text or "")
    sessions, malformed_sessions = _extract_trailers(
        combined, policy["trailer_key"], policy["trailer_pattern"]
    )
    bypasses, malformed_bypasses = _extract_trailers(
        combined, policy["bypass_key"], policy["bypass_pattern"]
    )
    return {
        "session_trailers": sorted(set(sessions)),
        "malformed_session_trailers": sorted(set(malformed_sessions)),
        "bypass_trailers": sorted(set(bypasses)),
        "malformed_bypass_trailers": sorted(set(malformed_bypasses)),
    }


def run_contract_check(
    repo: Path,
    hub_root: Path,
    base: str,
    head: str = "HEAD",
    *,
    extra_text: str = "",
    mode: str | None = None,
) -> dict[str, Any]:
    policy = load_policy(hub_root)
    effective_mode = mode or policy.get("mode", "warn")
    specs = protected_path_specs(hub_root, policy)
    exempt = [str(glob) for glob in policy.get("exempt_globs", []) or []]
    changed = changed_files(repo, base, head)
    protected, unprotected = classify_paths(changed, specs, exempt)
    traces = collect_traces(repo, base, head, policy, extra_text=extra_text)

    has_trace = bool(traces["session_trailers"])
    has_bypass = bool(traces["bypass_trailers"])
    violation = bool(protected) and not has_trace and not has_bypass

    report: dict[str, Any] = {
        "schema_version": "0.1.0",
        "policy_id": policy.get("policy_id", ""),
        "mode": effective_mode,
        "base": base,
        "head": head,
        "changed_count": len(changed),
        "protected_paths": protected,
        "unprotected_count": len(unprotected),
        **traces,
        "bypass_used": has_bypass and bool(protected) and not has_trace,
        "violation": violation,
        "status": (
            "not_applicable"
            if not protected
            else "traced"
            if has_trace
            else "bypassed"
            if has_bypass
            else "violation"
        ),
    }
    if violation or traces["malformed_session_trailers"]:
        report["remediation"] = policy.get("remediation", "")
    return report


def render_text(report: dict[str, Any]) -> str:
    lines = [
        f"DAD contract check [{report['mode']}] — {report['status']}",
        f"changed files: {report['changed_count']} "
        f"(protected: {len(report['protected_paths'])})",
    ]
    if report["protected_paths"]:
        for path in report["protected_paths"][:20]:
            lines.append(f"  protected: {path}")
        if len(report["protected_paths"]) > 20:
            lines.append(f"  ... and {len(report['protected_paths']) - 20} more")
    if report["session_trailers"]:
        lines.append("session trailers: " + ", ".join(report["session_trailers"]))
    if report["malformed_session_trailers"]:
        lines.append(
            "MALFORMED session trailers: "
            + ", ".join(report["malformed_session_trailers"])
        )
    if report["bypass_used"]:
        lines.append("BYPASS used: " + ", ".join(report["bypass_trailers"]))
    if report.get("remediation"):
        lines.append("")
        lines.append(report["remediation"])
    return "\n".join(lines)
