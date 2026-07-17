"""Bounded, no-winner search over local continuity observations."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping

from .ids import stable_id
from .portfolio_continuity_inventory import (
    AUTHORITY_BOUNDARY as INVENTORY_AUTHORITY_BOUNDARY,
    GitRunner,
    _collect_ref_observations,
    _collect_worktree_observations,
    _digest,
    _ref_id,
    _repository_identity,
    _run,
    _tokenize,
)
from .portfolio_related_work import search_related_work


SCHEMA_VERSION = "dad.portfolio_continuity_search.v1"
AUTHORITY_BOUNDARY = (
    "Continuity search is bounded local retrieval evidence only. It selects no "
    "identity winner, persists no paths, snippets, subjects, task titles, or raw Git "
    "output, and cannot fetch, mutate Git, archive work, or authorize execution."
)


def _tree_terms(
    repo_root: Path,
    object_id: str,
    *,
    max_tree_entries: int,
    runner: GitRunner | None,
) -> tuple[list[tuple[frozenset[str], str]], bool]:
    args = ["ls-tree", "-r", "-z", "--name-only", object_id]
    if runner is not None:
        result = _run(runner, repo_root, args)
        if result.returncode != 0:
            return [], False
        raw_paths = [row for row in result.stdout.split(b"\0") if row]
        truncated = len(raw_paths) > max_tree_entries
    else:
        # Stream and stop after one look-ahead record.  This avoids materializing
        # a large historical tree merely to answer a bounded recovery query.
        try:
            process = subprocess.Popen(
                ["git", *args],
                cwd=repo_root,
                env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            return [], False
        raw_paths = []
        pending = b""
        truncated = False
        assert process.stdout is not None
        try:
            while len(raw_paths) <= max_tree_entries:
                chunk = process.stdout.read(8192)
                if not chunk:
                    break
                pending += chunk
                fields = pending.split(b"\0")
                pending = fields.pop()
                raw_paths.extend(field for field in fields if field)
                if len(raw_paths) > max_tree_entries:
                    truncated = True
                    break
            if pending and len(raw_paths) <= max_tree_entries:
                raw_paths.append(pending)
            if truncated and process.poll() is None:
                process.terminate()
            returncode = process.wait(timeout=5)
            if not truncated and returncode != 0:
                return [], False
        except (OSError, subprocess.SubprocessError):
            if process.poll() is None:
                process.kill()
            process.wait()
            return [], False
        finally:
            process.stdout.close()
    rows: list[tuple[frozenset[str], str]] = []
    for raw in raw_paths[:max_tree_entries]:
        path = raw.decode("utf-8", errors="replace")
        rows.append((_tokenize(path), _digest(path.replace("\\", "/").casefold())))
    return rows, truncated


def _score(shared: set[str], query_terms: frozenset[str]) -> float:
    return round(len(shared) / max(1, len(query_terms)), 6)


def _git_object_candidates(
    repo_root: Path,
    repository_id: str,
    query_terms: frozenset[str],
    *,
    max_refs: int,
    max_objects: int,
    max_worktrees: int,
    max_tree_entries: int,
    runner: GitRunner | None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    refs, refs_truncated = _collect_ref_observations(
        repo_root, max_refs=max_refs, runner=runner
    )
    worktrees, worktrees_truncated, worktree_gaps = _collect_worktree_observations(
        repo_root,
        repository_id,
        max_worktrees=max_worktrees,
        include_status=False,
        runner=runner,
    )
    by_object: dict[str, dict[str, Any]] = {}
    for ref in refs:
        row = by_object.setdefault(
            ref.object_id,
            {"refs": [], "terms": set(), "fields": set(), "committed_at": ""},
        )
        ref_terms = set(_tokenize(ref.ref_name))
        subject_terms = set(_tokenize(ref.subject))
        if ref_terms & query_terms:
            row["fields"].add("ref_name")
        if subject_terms & query_terms:
            row["fields"].add("commit_subject")
        row["terms"].update(ref_terms)
        row["terms"].update(subject_terms)
        row["refs"].append(_ref_id(repository_id, ref.ref_name))
        row["committed_at"] = max(row["committed_at"], ref.committed_at)
    for worktree in worktrees:
        if not worktree.head_id:
            continue
        row = by_object.setdefault(
            worktree.head_id,
            {"refs": [], "terms": set(), "fields": set(), "committed_at": ""},
        )
        branch_terms = set(_tokenize(worktree.branch_name))
        if branch_terms & query_terms:
            row["fields"].add("worktree_branch")
        row["terms"].update(branch_terms)
    object_ids = sorted(by_object)
    objects_truncated = len(object_ids) > max_objects
    candidates: list[dict[str, Any]] = []
    tree_entries_examined = 0
    tree_entries_truncated = 0
    for object_id in object_ids[:max_objects]:
        material = by_object[object_id]
        tree_rows, truncated = _tree_terms(
            repo_root,
            object_id,
            max_tree_entries=max_tree_entries,
            runner=runner,
        )
        tree_entries_examined += len(tree_rows)
        tree_entries_truncated += int(truncated)
        matching_tree_fingerprints: list[str] = []
        shared = set(material["terms"]) & set(query_terms)
        for terms, path_fingerprint in tree_rows:
            overlap = set(terms) & set(query_terms)
            if overlap:
                shared.update(overlap)
                matching_tree_fingerprints.append(path_fingerprint)
        fields = set(material["fields"])
        if matching_tree_fingerprints:
            fields.add("tree_path_name")
        if not shared:
            continue
        ref_ids = sorted(set(material["refs"]))
        evidence = {
            "object_id": object_id,
            "ref_ids": ref_ids,
            "matched_fields": sorted(fields),
            "tree_path_fingerprints": sorted(matching_tree_fingerprints),
        }
        candidates.append(
            {
                "candidate_id": stable_id(
                    "continuity-search-candidate", repository_id, "git_object", object_id
                ),
                "source_kind": "git_object",
                "repository_id": repository_id,
                "object_id": object_id,
                "ref_ids": ref_ids,
                "ref_count": len(ref_ids),
                "committed_at": material["committed_at"],
                "matched_fields": sorted(fields),
                "deterministic_score": _score(shared, query_terms),
                "evidence_fingerprint": _digest(evidence),
                "candidate_only": True,
                "execution_authorized": False,
            }
        )
    gaps = list(worktree_gaps)
    if refs_truncated:
        gaps.append("refs_truncated")
    if worktrees_truncated:
        gaps.append("worktrees_truncated")
    if objects_truncated:
        gaps.append("objects_truncated")
    if tree_entries_truncated:
        gaps.append("tree_entries_truncated")
    coverage = {
        "refs_examined": len(refs),
        "objects_available": len(object_ids),
        "objects_examined": min(len(object_ids), max_objects),
        "tree_entries_examined": tree_entries_examined,
        "tree_objects_truncated": tree_entries_truncated,
    }
    return candidates, coverage, sorted(set(gaps))


def _dirty_overlay_candidates(
    repo_root: Path,
    repository_id: str,
    query_terms: frozenset[str],
    *,
    max_worktrees: int,
    runner: GitRunner | None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    worktrees, truncated, gaps = _collect_worktree_observations(
        repo_root,
        repository_id,
        max_worktrees=max_worktrees,
        runner=runner,
    )
    candidates: list[dict[str, Any]] = []
    for worktree in worktrees:
        if worktree.status.dirty is not True:
            continue
        shared: set[str] = set()
        matched_path_fingerprints: list[str] = []
        for terms, fingerprint in zip(
            worktree.status.path_term_sets,
            worktree.status.path_fingerprints,
            strict=True,
        ):
            overlap = set(terms) & set(query_terms)
            if overlap:
                shared.update(overlap)
                matched_path_fingerprints.append(fingerprint)
        branch_overlap = set(_tokenize(worktree.branch_name)) & set(query_terms)
        shared.update(branch_overlap)
        if not shared:
            continue
        fields = []
        if matched_path_fingerprints:
            fields.append("dirty_path_name")
        if branch_overlap:
            fields.append("worktree_branch")
        evidence = {
            "worktree_id": worktree.worktree_id,
            "head_id": worktree.head_id,
            "overlay_fingerprint": worktree.status.fingerprint,
            "matched_path_fingerprints": sorted(matched_path_fingerprints),
            "matched_fields": fields,
        }
        candidates.append(
            {
                "candidate_id": stable_id(
                    "continuity-search-candidate",
                    repository_id,
                    "dirty_overlay",
                    worktree.worktree_id,
                    worktree.status.fingerprint,
                ),
                "source_kind": "dirty_overlay",
                "repository_id": repository_id,
                "worktree_id": worktree.worktree_id,
                "head_id": worktree.head_id,
                "detached": worktree.detached,
                "matched_fields": fields,
                "changes": {
                    "staged": worktree.status.staged,
                    "unstaged": worktree.status.unstaged,
                    "untracked": worktree.status.untracked,
                    "conflicted": worktree.status.conflicted,
                },
                "deterministic_score": _score(shared, query_terms),
                "evidence_fingerprint": _digest(evidence),
                "candidate_only": True,
                "execution_authorized": False,
            }
        )
    if truncated:
        gaps.append("worktrees_truncated")
    return candidates, {"worktrees_examined": len(worktrees)}, sorted(set(gaps))


def _codex_candidates(
    repository_id: str,
    query_terms: frozenset[str],
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        source_id = str(row.get("task_id") or row.get("id") or "").strip()
        title = str(row.get("title") or "")
        aliases = [str(value) for value in row.get("aliases", []) if isinstance(value, str)]
        if not source_id or not (title or aliases):
            continue
        shared = set(_tokenize(" ".join([title, *aliases]))) & set(query_terms)
        if not shared:
            continue
        opaque_id = stable_id(
            "continuity-codex-item", repository_id, _digest(source_id)
        )
        state = str(row.get("state") or "unknown").casefold().strip()
        safe_state_chars = "abcdefghijklmnopqrstuvwxyz0123456789_.:/-"
        if not state or len(state) > 64 or any(ch not in safe_state_chars for ch in state):
            state = "unknown"
        updated_at = str(row.get("updated_at") or "")
        if len(updated_at) > 64 or any(ch not in "0123456789T:Z+.-" for ch in updated_at):
            updated_at = ""
        evidence = {
            "codex_item_id": opaque_id,
            "source_fingerprint": _digest(source_id),
            "title_fingerprint": _digest(title),
            "alias_fingerprints": sorted(_digest(value) for value in aliases),
            "state": state,
            "updated_at": updated_at,
        }
        candidates.append(
            {
                "candidate_id": stable_id(
                    "continuity-search-candidate", repository_id, "codex_item", opaque_id
                ),
                "source_kind": "codex_item",
                "repository_id": repository_id,
                "codex_item_id": opaque_id,
                "state": state,
                "updated_at": updated_at,
                "matched_fields": ["codex_title_or_alias"],
                "deterministic_score": _score(shared, query_terms),
                "evidence_fingerprint": _digest(evidence),
                "candidate_only": True,
                "execution_authorized": False,
            }
        )
    return candidates


def search_continuity(
    repo_root: Path,
    query: str,
    *,
    codex_metadata: Iterable[Mapping[str, Any]] | None = None,
    max_candidates: int = 10,
    max_refs: int = 512,
    max_objects: int = 128,
    max_worktrees: int = 128,
    max_tree_entries: int = 5000,
    runner: GitRunner | None = None,
) -> dict[str, Any]:
    """Search local refs, linked worktrees, dirty overlays, and supplied task metadata.

    Search always returns candidates without choosing a primary identity.
    """

    if not 1 <= max_candidates <= 100:
        raise ValueError("max_candidates must be between 1 and 100")
    if not 1 <= max_objects <= 1000:
        raise ValueError("max_objects must be between 1 and 1000")
    if not 1 <= max_tree_entries <= 100_000:
        raise ValueError("max_tree_entries must be between 1 and 100000")
    query_terms = _tokenize(query)
    if not query_terms:
        raise ValueError("query must contain searchable terms")
    root = Path(repo_root)
    repository_id = _repository_identity(root, runner)
    git_candidates, git_coverage, git_gaps = _git_object_candidates(
        root,
        repository_id,
        query_terms,
        max_refs=max_refs,
        max_objects=max_objects,
        max_worktrees=max_worktrees,
        max_tree_entries=max_tree_entries,
        runner=runner,
    )
    overlay_candidates, overlay_coverage, overlay_gaps = _dirty_overlay_candidates(
        root,
        repository_id,
        query_terms,
        max_worktrees=max_worktrees,
        runner=runner,
    )
    codex_rows = list(codex_metadata or ())
    codex_candidates = _codex_candidates(repository_id, query_terms, codex_rows)
    deduped: dict[str, dict[str, Any]] = {}
    for candidate in [*git_candidates, *overlay_candidates, *codex_candidates]:
        current = deduped.get(candidate["candidate_id"])
        if current is None or candidate["deterministic_score"] > current["deterministic_score"]:
            deduped[candidate["candidate_id"]] = candidate
    ranked = sorted(
        deduped.values(),
        key=lambda row: (
            -float(row["deterministic_score"]),
            str(row["source_kind"]),
            str(row["candidate_id"]),
        ),
    )
    returned = ranked[:max_candidates]
    if not returned:
        classification = "insufficient_evidence"
    elif (
        len(returned) > 1
        and returned[0]["deterministic_score"] == returned[1]["deterministic_score"]
    ):
        classification = "ambiguous_no_winner"
    else:
        classification = "candidate_set_no_winner"
    gaps = sorted(set([*git_gaps, *overlay_gaps]))
    if codex_metadata is None:
        gaps.append("codex_metadata_not_supplied")
    gaps = sorted(set(gaps))
    return {
        "schema_version": SCHEMA_VERSION,
        "query_digest": _digest(sorted(query_terms)),
        "repository_id": repository_id,
        "classification": classification,
        "primary_candidate_id": "",
        "candidates": returned,
        "coverage": {
            **git_coverage,
            **overlay_coverage,
            "codex_items_examined": len(codex_rows),
            "candidates_before_limit": len(ranked),
            "candidates_returned": len(returned),
            "codex_source": (
                "explicit_supplied_metadata_only"
                if codex_metadata is not None
                else "not_supplied"
            ),
            "network_calls": 0,
            "git_writes": 0,
            "raw_output_persisted": False,
            "absolute_paths_persisted": False,
            "gaps": gaps,
        },
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inventory_authority_boundary": INVENTORY_AUTHORITY_BOUNDARY,
    }


def search_continuity_all_sources(
    repo_root: Path,
    hub_root: Path,
    query: str,
    *,
    codex_metadata: Iterable[Mapping[str, Any]] | None = None,
    max_candidates: int = 10,
    runner: GitRunner | None = None,
) -> dict[str, Any]:
    """Search Git, overlays, Codex metadata, and DAD durable identities together."""

    local = search_continuity(
        repo_root,
        query,
        codex_metadata=codex_metadata,
        max_candidates=max_candidates,
        runner=runner,
    )
    try:
        related = search_related_work(
            repo_root,
            hub_root,
            query,
            privacy_partition="private",
            limit=min(max_candidates, 5),
        )
    except (OSError, RuntimeError, ValueError):
        related = {
            "candidates": [],
            "coverage": {
                "returned_count": 0,
                "unavailable_sources": ["dad_durable_identity_surfaces"],
                "model_calls": 0,
            },
            "authority_boundary": "DAD related-work evidence was unavailable.",
        }
    candidates = list(local["candidates"])
    seen = {str(row["candidate_id"]) for row in candidates}
    for row in related.get("candidates", []):
        candidate_id = str(row.get("candidate_id", ""))
        if not candidate_id or candidate_id in seen:
            continue
        seen.add(candidate_id)
        candidates.append(
            {
                "candidate_id": candidate_id,
                "source_kind": "dad_" + str(row.get("candidate_kind", "unknown")),
                "title": str(row.get("title", "")),
                "matched_fields": ["dad_durable_metadata"],
                "deterministic_score": float(row.get("deterministic_score", 0.0)),
                "evidence_refs": list(row.get("evidence_refs", [])),
                "relation_candidate": str(row.get("relation_candidate", "")),
                "candidate_only": True,
                "execution_authorized": False,
            }
        )
    candidates.sort(
        key=lambda row: (
            -float(row.get("deterministic_score", 0.0)),
            str(row.get("source_kind", "")),
            str(row.get("candidate_id", "")),
        )
    )
    candidates = candidates[:max_candidates]
    if not candidates:
        classification = "insufficient_evidence"
    elif (
        len(candidates) > 1
        and candidates[0].get("deterministic_score")
        == candidates[1].get("deterministic_score")
    ):
        classification = "ambiguous_no_winner"
    else:
        classification = "candidate_set_no_winner"
    related_unavailable = list(
        related.get("coverage", {}).get("unavailable_sources", [])
    )
    return {
        "schema_version": "dad.portfolio_continuity_search.v2",
        "query_digest": local["query_digest"],
        "repository_id": local["repository_id"],
        "classification": classification,
        "primary_candidate_id": "",
        "candidates": candidates,
        "coverage": {
            "local": local["coverage"],
            "dad": related.get("coverage", {}),
            "gaps": sorted(
                {
                    *local["coverage"].get("gaps", []),
                    *(
                        f"dad_source_unavailable:{value}"
                        for value in related_unavailable
                    ),
                }
            ),
            "candidates_returned": len(candidates),
            "network_calls": 0,
            "git_writes": 0,
            "model_calls": 0,
        },
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inventory_authority_boundary": INVENTORY_AUTHORITY_BOUNDARY,
        "related_work_authority_boundary": related.get("authority_boundary", ""),
    }


search_repository_inventory = search_continuity


__all__ = [
    "AUTHORITY_BOUNDARY",
    "SCHEMA_VERSION",
    "search_continuity",
    "search_continuity_all_sources",
    "search_repository_inventory",
]
