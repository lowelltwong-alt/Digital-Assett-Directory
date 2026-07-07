"""Registered graph surface helpers.

Graph surfaces are generated candidate projections. This module resolves their
registered logical paths through the DAD data plane and prepares data-only
journal snapshot plans. It does not make graph content authoritative.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

from .transport import data_path
from .utils import json_dumps, sha256_bytes, sha256_file, utc_now

GRAPH_SURFACE_REGISTRY = Path("registry") / "graph-surface-registry.json"
GRAPH_SNAPSHOT_ROOT = Path("graph-surfaces")
GRAPH_SURFACE_AUTHORITY_BOUNDARY = (
    "Graph surface checkpoint rows are data-plane replication evidence for "
    "generated candidate graph surfaces. They do not approve, rank, recommend, "
    "trust, or authorize any node, edge, asset, repo, or downstream write."
)

_LOGICAL_PREFIXES = {
    "learning": "learning",
    "research": "research",
    "reports": "central_reports",
    "exceptions": "exceptions",
}


def load_graph_surface_registry(hub_root: Path) -> dict[str, Any]:
    path = hub_root / GRAPH_SURFACE_REGISTRY
    if not path.exists():
        return {
            "registry_version": "",
            "status": "missing",
            "surfaces": [],
            "authority_boundary": GRAPH_SURFACE_AUTHORITY_BOUNDARY,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"surfaces": []}


def resolve_graph_surface_path(hub_root: Path, logical_path: str) -> Path:
    path = Path(logical_path)
    if path.is_absolute() or not path.parts:
        raise ValueError(f"Graph surface path must be a relative logical path: {logical_path}")
    prefix = path.parts[0]
    logical_surface = _LOGICAL_PREFIXES.get(prefix)
    if logical_surface is None:
        raise ValueError(f"Unknown graph surface logical prefix: {prefix}")
    return data_path(hub_root, logical_surface).joinpath(*path.parts[1:])


def _stable_gzip(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=9, mtime=0)


def _journal_surface_dir(surface_id: str) -> Path:
    return Path("data") / GRAPH_SNAPSHOT_ROOT / surface_id


def _snapshot_paths(surface_id: str, body_sha256: str) -> dict[str, str]:
    digest = body_sha256.removeprefix("sha256:")
    surface_dir = _journal_surface_dir(surface_id)
    return {
        "manifest_json_path": (surface_dir / "manifest.json").as_posix(),
        "body_gzip_path": (surface_dir / f"body-{digest}.json.gz").as_posix(),
        "index_jsonl_path": (Path("data") / GRAPH_SNAPSHOT_ROOT / "index.jsonl").as_posix(),
    }


def graph_surface_checkpoint_plan(
    hub_root: Path,
    journal_repo: Path | None = None,
) -> dict[str, Any]:
    registry = load_graph_surface_registry(hub_root)
    generated_at = utc_now()
    snapshots: list[dict[str, Any]] = []
    index_rows: list[dict[str, Any]] = []
    ready_count = 0
    skipped_unchanged_count = 0
    missing_count = 0

    for surface in registry.get("surfaces", []):
        surface_id = str(surface.get("surface_id", ""))
        outputs = surface.get("outputs", {})
        manifest_logical = str(outputs.get("manifest_logical_path", ""))
        body_logical = str(outputs.get("body_logical_path", ""))
        snapshot: dict[str, Any] = {
            "surface_id": surface_id,
            "surface_status": surface.get("status", ""),
            "review_status": surface.get("review_status", ""),
            "manifest_logical_path": manifest_logical,
            "body_logical_path": body_logical,
            "authority_boundary": surface.get(
                "authority_boundary", GRAPH_SURFACE_AUTHORITY_BOUNDARY
            ),
        }
        try:
            manifest_path = resolve_graph_surface_path(hub_root, manifest_logical)
            body_path = resolve_graph_surface_path(hub_root, body_logical)
        except ValueError as exc:
            snapshot.update(
                {
                    "status": "invalid_registry_path",
                    "error": str(exc),
                    "manifest_exists": False,
                    "body_exists": False,
                }
            )
            missing_count += 1
            snapshots.append(snapshot)
            continue

        snapshot.update(
            {
                "manifest_path": str(manifest_path),
                "body_path": str(body_path),
                "manifest_exists": manifest_path.exists(),
                "body_exists": body_path.exists(),
            }
        )
        if not manifest_path.exists() or not body_path.exists():
            snapshot["status"] = "missing_surface_files"
            missing_count += 1
            snapshots.append(snapshot)
            continue

        try:
            manifest_json = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            snapshot.update({"status": "invalid_manifest", "error": str(exc)})
            missing_count += 1
            snapshots.append(snapshot)
            continue

        body_bytes = body_path.read_bytes()
        body_sha256 = f"sha256:{sha256_file(body_path)}"
        body_gzip_sha256 = f"sha256:{sha256_bytes(_stable_gzip(body_bytes))}"
        paths = _snapshot_paths(surface_id, body_sha256)
        body_snapshot_exists = (
            bool(journal_repo)
            and (Path(journal_repo) / paths["body_gzip_path"]).exists()
        )
        body_upload_action = "skip_unchanged" if body_snapshot_exists else "write_gzip"
        if body_snapshot_exists:
            skipped_unchanged_count += 1
        ready_count += 1
        index_row = {
            "schema_version": "dad.graph_surface_checkpoint_index.v1",
            "surface_id": surface_id,
            "checkpointed_at": generated_at,
            "manifest_json_path": paths["manifest_json_path"],
            "body_gzip_path": paths["body_gzip_path"],
            "body_sha256": body_sha256,
            "body_gzip_sha256": body_gzip_sha256,
            "body_upload_action": body_upload_action,
            "review_status": surface.get("review_status", ""),
            "surface_status": surface.get("status", ""),
            "authority_boundary": GRAPH_SURFACE_AUTHORITY_BOUNDARY,
        }
        index_rows.append(index_row)
        snapshot.update(
            {
                "status": "ready",
                "manifest_json": manifest_json,
                "body_sha256": body_sha256,
                "body_gzip_sha256": body_gzip_sha256,
                "body_gzip_snapshot_path": paths["body_gzip_path"],
                "manifest_json_snapshot_path": paths["manifest_json_path"],
                "index_jsonl_path": paths["index_jsonl_path"],
                "body_snapshot_exists": body_snapshot_exists,
                "body_upload_action": body_upload_action,
                "index_row": index_row,
            }
        )
        snapshots.append(snapshot)

    return {
        "schema_version": "dad.graph_surface_checkpoint_plan.v1",
        "generated_at": generated_at,
        "registry_path": GRAPH_SURFACE_REGISTRY.as_posix(),
        "registry_version": registry.get("registry_version", ""),
        "surface_count": len(snapshots),
        "ready_count": ready_count,
        "missing_count": missing_count,
        "skipped_unchanged_body_count": skipped_unchanged_count,
        "snapshots": snapshots,
        "checkpoint_index_rows": index_rows,
        "authority_boundary": GRAPH_SURFACE_AUTHORITY_BOUNDARY,
    }


def write_graph_surface_checkpoint_artifacts(
    hub_root: Path,
    journal_repo: Path,
) -> dict[str, Any]:
    plan = graph_surface_checkpoint_plan(hub_root, journal_repo)
    index_rows: list[dict[str, Any]] = []
    written_manifest_count = 0
    written_body_count = 0
    skipped_body_count = 0
    for snapshot in plan["snapshots"]:
        if snapshot.get("status") != "ready":
            continue
        manifest_path = journal_repo / str(snapshot["manifest_json_snapshot_path"])
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json_dumps(snapshot["manifest_json"], pretty=True) + "\n",
            encoding="utf-8",
        )
        written_manifest_count += 1
        body_snapshot_path = journal_repo / str(snapshot["body_gzip_snapshot_path"])
        if snapshot["body_upload_action"] == "skip_unchanged" and body_snapshot_path.exists():
            skipped_body_count += 1
        else:
            body_bytes = Path(str(snapshot["body_path"])).read_bytes()
            body_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            body_snapshot_path.write_bytes(_stable_gzip(body_bytes))
            written_body_count += 1
        index_rows.append(snapshot["index_row"])

    if index_rows:
        index_path = journal_repo / "data" / GRAPH_SNAPSHOT_ROOT / "index.jsonl"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        existing = set()
        if index_path.exists():
            existing = set(index_path.read_text(encoding="utf-8").splitlines())
        with index_path.open("a", encoding="utf-8") as handle:
            for row in index_rows:
                line = json_dumps(row)
                if line in existing:
                    continue
                handle.write(line + "\n")
    plan.update(
        {
            "written_manifest_count": written_manifest_count,
            "written_body_count": written_body_count,
            "skipped_body_count": skipped_body_count,
        }
    )
    return plan
