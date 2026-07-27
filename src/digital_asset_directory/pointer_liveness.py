"""Pointer liveness validator for navigation and registry path declarations.

Why this exists (incident 2026-07-10, lesson dad:lesson:0cf6def7-acf4-5824-b465-c2f9bfe5d305):
the multi-agent orchestration layer was checkpointed onto a preserve branch and
never integrated. For 16 days front doors, registries, and agent memory kept
citing ``orchestration/`` as a live path while the default branch — what every
other clone and agent actually sees — had nothing there. Nothing validated that
declared paths resolve, and critically nothing validated that they resolve ON
THE DEFAULT BRANCH.

Two modes, both read-only:

- ``worktree``: each declared path must exist in the working tree.
- ``default-branch``: each declared path must exist in ``git ls-tree -r
  <default-branch>``. A pointer that resolves in the worktree but not here is
  the exact signature of the incident class: present locally, invisible to
  everyone else.

Scoping rationale (kept deliberately narrow so the validator stays quiet and
therefore stays enabled):

- Only declared *repo content* pointers are checked. Refs are skipped when they
  are commands (contain whitespace), ``dad://`` logical URIs (deliberately not
  local paths; see validation.py pointer-template checks), URLs, ``planned:``
  markers, absolute paths, globs, or template placeholders.
- Data-plane refs (``raw/``, ``processed/``, ``state/``, ``audit/``,
  ``private/`` — the ``ALL_RUNTIME_DATA_PATHS`` families) are skipped in both
  modes: they are generated runtime artifacts that live under the active data
  root, are gitignored by design, and are already covered by graph-surface
  freshness and report-staleness validators. Checking them here would make
  every fresh clone red.
- Graph-surface ``manifest_logical_path``/``body_logical_path`` outputs are
  checked for *resolvability* (a known logical prefix) only, never existence,
  for the same reason.
- ``recent_changes[].paths`` in the navigation registry are a historical
  changelog and are intentionally not checked.

Issue codes (stable, convention per mcp_dependency_map):

- ``pointer_target_missing_in_worktree``
- ``pointer_target_missing_on_default_branch``  (headline: the incident class)
- ``pointer_target_untracked``  (exists locally, never committed — "someone
  forgot to commit", kept separate from "someone deleted it from main")
- ``pointer_registry_unparseable``

This module never mutates git state; all git access goes through the budgeted
read-only wrapper in portfolio_convergence_git with an explicit subcommand
allowlist.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from .portfolio_convergence_git import (
    GitConvergenceSettings,
    _GitCounter,
    _GitObservationError,
    _git_worktree,
)
from .transport import ALL_RUNTIME_DATA_PATHS

ISSUE_MISSING_WORKTREE = "pointer_target_missing_in_worktree"
ISSUE_MISSING_DEFAULT_BRANCH = "pointer_target_missing_on_default_branch"
ISSUE_NOT_IN_VALIDATED_TREE = "pointer_target_not_in_validated_tree"
ISSUE_UNTRACKED = "pointer_target_untracked"
ISSUE_UNPARSEABLE = "pointer_registry_unparseable"

# "auto" is the validate_repo default: on the default branch it behaves like
# "both"; on any other branch the tree comparison runs against HEAD's own tree
# (same-tree semantics) instead of the default branch. Rationale: a feature
# branch that adds a file and its registry pointer in the same commit is
# correct work and must not fail — pointer and target travel together and
# merge together. Checking such a branch against the default branch would
# error on every legitimate addition and get this validator muted.
POINTER_MODES = ("worktree", "default-branch", "both", "auto")

_DATA_PLANE_PREFIXES = tuple(
    sorted({value.split("/", 1)[0] + "/" for value in ALL_RUNTIME_DATA_PATHS.values()})
)

# Read-only git subcommands this validator is allowed to run. Enforced at the
# call site so a future edit cannot silently gain write behavior.
_READ_ONLY_GIT_SUBCOMMANDS = frozenset(
    {"ls-tree", "ls-files", "show-ref", "symbolic-ref"}
)

_TOC_PATH_HEADER = re.compile(r"^\|\s*Path\s*\|")
_BACKTICK_TOKEN = re.compile(r"`([^`]+)`")


def _read_only_git(
    repo_root: Path,
    args: tuple[str, ...],
    *,
    settings: GitConvergenceSettings,
    counter: _GitCounter,
) -> tuple[int, str]:
    if args[0] not in _READ_ONLY_GIT_SUBCOMMANDS:
        raise ValueError(f"Blocked non-read-only git subcommand: {args[0]}")
    result = _git_worktree(
        worktree=repo_root, args=args, settings=settings, counter=counter
    )
    return result.returncode, result.stdout.decode("utf-8", errors="replace")


def resolve_default_branch(
    repo_root: Path,
    *,
    settings: GitConvergenceSettings,
    counter: _GitCounter,
) -> str | None:
    """Resolve the default branch without network access.

    A locally recorded ``refs/remotes/<remote>/HEAD`` wins; otherwise a local
    ``main`` then ``master``. Returns None when the root is not a usable git
    repository (fixtures, exports), which degrades the check to a warning.
    """
    try:
        code, out = _read_only_git(
            repo_root,
            ("symbolic-ref", "--short", "refs/remotes/origin/HEAD"),
            settings=settings,
            counter=counter,
        )
        if code == 0 and out.strip():
            return out.strip().split("/", 1)[-1]
        for candidate in ("main", "master"):
            code, _ = _read_only_git(
                repo_root,
                ("show-ref", "--verify", "--quiet", f"refs/heads/{candidate}"),
                settings=settings,
                counter=counter,
            )
            if code == 0:
                return candidate
    except (OSError, _GitObservationError):
        return None
    return None


def _is_checkable_repo_path(ref: str) -> tuple[bool, str]:
    """Classify one declared ref. Returns (checkable, skip_reason)."""
    value = str(ref).strip()
    if not value:
        return False, "empty"
    if any(ch.isspace() for ch in value):
        return False, "command_or_prose"
    lowered = value.casefold()
    if lowered.startswith(("dad://", "http://", "https://", "planned:", "mailto:")):
        return False, "logical_uri"
    if value.startswith(("~", "$", "<", "-")):
        return False, "placeholder"
    if "*" in value or "?" in value:
        return False, "glob"
    if re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith(("/", "\\")):
        return False, "absolute_path"
    if "/" not in value and "." not in value:
        return False, "bare_token"
    normalized = value.replace("\\", "/")
    if normalized.startswith(_DATA_PLANE_PREFIXES):
        return False, "data_plane"
    if normalized.startswith(".digital-asset/"):
        # Repo-local enrollment runtime surface (mail spools, asset memory);
        # generated per-repo and legitimately absent from fresh clones.
        return False, "repo_local_runtime"
    return True, ""


def _normalize_ref(ref: str) -> str:
    value = str(ref).strip().replace("\\", "/")
    value = value.split("#", 1)[0]
    return value.rstrip("/")


def _pointer(surface: str, field: str, ref: str) -> dict[str, str]:
    return {"surface": surface, "field": field, "ref": _normalize_ref(ref)}


def _iter_refs(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                yield item


def _collect_navigation_registry(
    repo_root: Path, pointers: list[dict[str, str]], errors: list[str]
) -> bool:
    rel = "registry/ai-navigation-registry.json"
    path = repo_root / rel
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{ISSUE_UNPARSEABLE}: {rel}: {exc}")
        return True
    entry = payload.get("singular_entrypoint", {})
    if isinstance(entry, dict):
        for ref in _iter_refs(entry.get("path")):
            pointers.append(_pointer(rel, "singular_entrypoint.path", ref))
    for row in payload.get("branch_map", []):
        if not isinstance(row, dict):
            continue
        branch_id = str(row.get("branch_id", "branch"))
        for field in ("path", "paths", "route_after"):
            for ref in _iter_refs(row.get(field)):
                pointers.append(_pointer(rel, f"branch_map[{branch_id}].{field}", ref))
    return True


def _collect_graph_surface_registry(
    repo_root: Path, pointers: list[dict[str, str]], errors: list[str]
) -> bool:
    rel = "registry/graph-surface-registry.json"
    path = repo_root / rel
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{ISSUE_UNPARSEABLE}: {rel}: {exc}")
        return True
    for surface in payload.get("surfaces", []):
        if not isinstance(surface, dict):
            continue
        surface_id = str(surface.get("surface_id", "surface"))
        for source_input in surface.get("source_inputs", []):
            if not isinstance(source_input, dict):
                continue
            # data_surface refs are logical names validated elsewhere.
            if source_input.get("kind") not in {"registry_path", "schema_path", "source_path"}:
                continue
            for ref in _iter_refs(source_input.get("ref")):
                pointers.append(_pointer(rel, f"surfaces[{surface_id}].source_inputs", ref))
        builder = surface.get("builder", {})
        if isinstance(builder, dict):
            module_ref = str(builder.get("module", ""))
            if module_ref and not module_ref.startswith("planned:"):
                pointers.append(
                    {
                        "surface": rel,
                        "field": f"surfaces[{surface_id}].builder.module",
                        "ref": module_ref,
                        "kind": "module",
                    }
                )
        outputs = surface.get("outputs", {})
        if isinstance(outputs, dict):
            from .graph_surfaces import resolve_graph_surface_path

            for key in ("manifest_logical_path", "body_logical_path"):
                value = str(outputs.get(key, ""))
                if not value:
                    continue
                # Resolvability only: outputs are generated data-plane files.
                try:
                    resolve_graph_surface_path(repo_root, value)
                except ValueError as exc:
                    errors.append(
                        f"{ISSUE_UNPARSEABLE}: {rel} surfaces[{surface_id}].{key}: {exc}"
                    )
    return True


def _collect_offerings_registry(
    repo_root: Path, pointers: list[dict[str, str]], errors: list[str]
) -> bool:
    rel = "registry/dad-offerings-registry.json"
    path = repo_root / rel
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{ISSUE_UNPARSEABLE}: {rel}: {exc}")
        return True
    for offering in payload.get("offerings", []):
        if not isinstance(offering, dict):
            continue
        offering_id = str(offering.get("offering_id", "offering"))
        for field in ("path", "source_refs", "validation_refs", "harness_registry_ref"):
            value = offering.get(field)
            if value is None:
                continue
            for ref in _iter_refs(value):
                pointers.append(_pointer(rel, f"offerings[{offering_id}].{field}", ref))
    return True


def _collect_template_registry(
    repo_root: Path, pointers: list[dict[str, str]], errors: list[str]
) -> bool:
    rel = "registry/template-registry.json"
    path = repo_root / rel
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{ISSUE_UNPARSEABLE}: {rel}: {exc}")
        return True
    for template in payload.get("templates", []):
        if not isinstance(template, dict):
            continue
        template_id = str(template.get("template_id", "template"))
        for ref in _iter_refs(template.get("path")):
            pointers.append(_pointer(rel, f"templates[{template_id}].path", ref))
        for ref in _iter_refs(template.get("depends_on_contracts")):
            pointers.append(
                _pointer(rel, f"templates[{template_id}].depends_on_contracts", ref)
            )
    return True


def _collect_machine_manifest(
    repo_root: Path, pointers: list[dict[str, str]], errors: list[str]
) -> bool:
    rel = "MACHINE_NAVIGATION_MANIFEST.json"
    path = repo_root / rel
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{ISSUE_UNPARSEABLE}: {rel}: {exc}")
        return True
    standards = payload.get("navigation_standards", {})
    if isinstance(standards, dict):
        for field in ("single_ai_entrypoint", "navigation_registry"):
            for ref in _iter_refs(standards.get(field)):
                pointers.append(_pointer(rel, f"navigation_standards.{field}", ref))
    return True


def _collect_ai_toc(
    repo_root: Path, pointers: list[dict[str, str]], errors: list[str]
) -> bool:
    rel = "AI_TABLE_OF_CONTENTS.md"
    path = repo_root / rel
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{ISSUE_UNPARSEABLE}: {rel}: {exc}")
        return True
    in_path_table = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_path_table = False
            continue
        if _TOC_PATH_HEADER.match(stripped):
            in_path_table = True
            continue
        if not in_path_table or set(stripped) <= {"|", "-", " ", ":"}:
            continue
        first_cell = stripped.strip("|").split("|", 1)[0]
        for token in _BACKTICK_TOKEN.findall(first_cell):
            pointers.append(_pointer(rel, f"line {line_number}", token))
    return True


_SURFACE_COLLECTORS = (
    _collect_navigation_registry,
    _collect_graph_surface_registry,
    _collect_offerings_registry,
    _collect_template_registry,
    _collect_machine_manifest,
    _collect_ai_toc,
)


def collect_declared_pointers(
    repo_root: Path,
) -> tuple[list[dict[str, str]], list[str], list[str]]:
    """Return (pointers, unparseable_errors, surfaces_present)."""
    pointers: list[dict[str, str]] = []
    errors: list[str] = []
    surfaces: list[str] = []
    for collector in _SURFACE_COLLECTORS:
        if collector(repo_root, pointers, errors):
            surfaces.append(collector.__name__.removeprefix("_collect_"))
    return pointers, errors, surfaces


def _module_tree_candidates(module_ref: str) -> list[str]:
    module_name = module_ref.rpartition(".")[0]
    if not module_name:
        return []
    module_path = module_name.replace(".", "/")
    return [f"src/{module_path}.py", f"src/{module_path}/__init__.py"]


def _tree_has(tree_paths: set[str], tree_dirs: set[str], ref: str) -> bool:
    return ref in tree_paths or ref in tree_dirs


def _paths_and_dirs(paths: Iterable[str]) -> tuple[set[str], set[str]]:
    files: set[str] = set()
    dirs: set[str] = set()
    for raw in paths:
        if not raw:
            continue
        value = raw.replace("\\", "/")
        files.add(value)
        parts = value.split("/")
        for index in range(1, len(parts)):
            dirs.add("/".join(parts[:index]))
    return files, dirs


def validate_pointer_liveness(
    repo_root: Path,
    *,
    mode: str = "worktree",
    default_branch: str | None = None,
    settings: GitConvergenceSettings | None = None,
) -> dict[str, Any]:
    """Validate that declared pointers resolve. Read-only; never mutates git."""
    if mode not in POINTER_MODES:
        raise ValueError(f"mode must be one of {POINTER_MODES}, got {mode!r}")
    settings = settings or GitConvergenceSettings()
    counter = _GitCounter()
    errors: list[str] = []
    warnings: list[str] = []
    issue_codes: set[str] = set()

    pointers, unparseable, surfaces = collect_declared_pointers(repo_root)
    for message in unparseable:
        errors.append(message)
        issue_codes.add(ISSUE_UNPARSEABLE)

    checkable: list[dict[str, str]] = []
    skipped: dict[str, int] = {}
    for pointer in pointers:
        if pointer.get("kind") == "module":
            checkable.append(pointer)
            continue
        ok, reason = _is_checkable_repo_path(pointer["ref"])
        if ok:
            checkable.append(pointer)
        else:
            skipped[reason] = skipped.get(reason, 0) + 1

    want_worktree = mode in {"worktree", "both", "auto"}
    want_default_branch = mode in {"default-branch", "both", "auto"}

    resolved_default_branch: str | None = None
    tree_ref: str | None = None
    missing_tree_code = ISSUE_MISSING_DEFAULT_BRANCH
    tree_files: set[str] = set()
    tree_dirs: set[str] = set()
    index_files: set[str] = set()
    index_dirs: set[str] = set()
    if want_default_branch and not (repo_root / ".git").exists():
        # Not a git repository (fixtures, exports): nothing to compare against,
        # so skip silently rather than warn on every synthetic hub.
        want_default_branch = False
    if want_default_branch:
        resolved_default_branch = default_branch or resolve_default_branch(
            repo_root, settings=settings, counter=counter
        )
        if resolved_default_branch is None:
            warnings.append(
                "pointer_liveness_default_branch_unavailable: repository has no "
                "resolvable default branch here; default-branch mode skipped"
            )
            want_default_branch = False
        else:
            tree_ref = f"refs/heads/{resolved_default_branch}"
            if mode == "auto":
                try:
                    head_code, head_out = _read_only_git(
                        repo_root,
                        ("symbolic-ref", "--short", "HEAD"),
                        settings=settings,
                        counter=counter,
                    )
                except (OSError, _GitObservationError):
                    head_code, head_out = 1, ""
                current_branch = head_out.strip() if head_code == 0 else None
                if current_branch != resolved_default_branch:
                    # Same-tree semantics off the default branch (see
                    # POINTER_MODES note): validate this commit's registry
                    # against this commit's own tree.
                    tree_ref = "HEAD"
                    missing_tree_code = ISSUE_NOT_IN_VALIDATED_TREE
            try:
                code, out = _read_only_git(
                    repo_root,
                    (
                        "ls-tree",
                        "-r",
                        "--name-only",
                        "-z",
                        tree_ref,
                    ),
                    settings=settings,
                    counter=counter,
                )
                index_code, index_out = _read_only_git(
                    repo_root,
                    ("ls-files", "-z"),
                    settings=settings,
                    counter=counter,
                )
            except (OSError, _GitObservationError) as exc:
                warnings.append(
                    "pointer_liveness_default_branch_unavailable: "
                    f"git observation failed ({exc}); default-branch mode skipped"
                )
                want_default_branch = False
                code = index_code = 1
                out = index_out = ""
            if want_default_branch:
                if code != 0:
                    warnings.append(
                        "pointer_liveness_default_branch_unavailable: ls-tree "
                        f"failed for {resolved_default_branch}; default-branch mode skipped"
                    )
                    want_default_branch = False
                else:
                    tree_files, tree_dirs = _paths_and_dirs(out.split("\0"))
                    if index_code == 0:
                        index_files, index_dirs = _paths_and_dirs(index_out.split("\0"))

    checked = 0
    for pointer in checkable:
        surface = pointer["surface"]
        field = pointer["field"]
        ref = pointer["ref"]
        is_module = pointer.get("kind") == "module"
        checked += 1
        if want_worktree and not is_module:
            if not (repo_root / ref).exists():
                errors.append(f"{ISSUE_MISSING_WORKTREE}: {surface} {field} -> {ref}")
                issue_codes.add(ISSUE_MISSING_WORKTREE)
        if want_default_branch:
            if is_module:
                candidates = _module_tree_candidates(ref)
                if candidates and not any(
                    _tree_has(tree_files, tree_dirs, candidate) for candidate in candidates
                ):
                    errors.append(
                        f"{missing_tree_code}: {surface} {field} -> {ref}"
                    )
                    issue_codes.add(missing_tree_code)
                continue
            if _tree_has(tree_files, tree_dirs, ref):
                continue
            exists_locally = (repo_root / ref).exists()
            tracked_locally = _tree_has(index_files, index_dirs, ref)
            if exists_locally and not tracked_locally:
                errors.append(f"{ISSUE_UNTRACKED}: {surface} {field} -> {ref}")
                issue_codes.add(ISSUE_UNTRACKED)
            else:
                errors.append(
                    f"{missing_tree_code}: {surface} {field} -> {ref}"
                )
                issue_codes.add(missing_tree_code)

    return {
        "valid": not errors,
        "mode": mode,
        "default_branch": resolved_default_branch,
        "tree_ref": tree_ref,
        "errors": errors,
        "warnings": warnings,
        "issue_codes": sorted(issue_codes),
        "pointer_count": len(pointers),
        "checked_pointer_count": checked,
        "skipped": dict(sorted(skipped.items())),
        "surfaces": surfaces,
        "authority_boundary": (
            "Pointer liveness findings are deterministic repo-content evidence. "
            "They never merge, delete, or rewrite anything; resolving a finding "
            "is a human decision."
        ),
    }
