"""Retention/GC for per-scan generated catalog rows.

Regression coverage for the append-forever defect: alerts (and other per-scan
generated rows) used to accumulate across every scan, growing the catalog
without bound. See ``CatalogDB.replace_scan_alerts`` / ``prune_generated_records``.
"""

from pathlib import Path

import pytest
import yaml

from digital_asset_directory import database
from digital_asset_directory.catalog import run_scan
from digital_asset_directory.config import load_config
from digital_asset_directory.database import CatalogDB
from digital_asset_directory.models import AlertRecord, EdgeRecord

_TS = "2026-07-21T00:00:00+00:00"


def _alert(scan_id: str, asset_id: str, status: str = "open") -> AlertRecord:
    return AlertRecord(
        alert_id=f"alert:{scan_id}:{asset_id}",
        created_at=_TS,
        alert_type="orphan_asset",
        severity="low",
        title="orphan candidate",
        recommended_action="review",
        status=status,  # type: ignore[arg-type]
        scan_id=scan_id,
    )


def _edge(scan_id: str, i: int) -> EdgeRecord:
    return EdgeRecord(
        edge_id=f"edge:{scan_id}:{i}",
        edge_type="related_to",
        source_asset_id=f"a{i}",
        target_asset_id=f"b{i}",
        method="test",
        confidence=0.5,
        created_at=_TS,
        scan_id=scan_id,
    )


def test_prune_generated_records_keeps_only_latest_scan(tmp_path: Path) -> None:
    db = CatalogDB(tmp_path / "c.sqlite3")
    db.replace_scan_edges("s1", [_edge("s1", 1), _edge("s1", 2)])
    db.replace_scan_alerts("s1", [_alert("s1", "a1"), _alert("s1", "a2")])
    db.replace_scan_edges("s2", [_edge("s2", 1)])
    db.replace_scan_alerts("s2", [_alert("s2", "a1")])

    # Old and new scans coexist until retention runs (the accumulation bug).
    assert len(db.edges()) == 3
    assert len(db.alerts()) == 3

    removed = db.prune_generated_records("s2")
    assert removed["edges"] == 2
    assert removed["alerts"] == 2
    assert len(db.edges()) == 1
    assert len(db.alerts()) == 1
    db.close()


def test_replace_scan_alerts_does_not_accumulate_within_a_scan(tmp_path: Path) -> None:
    db = CatalogDB(tmp_path / "c.sqlite3")
    db.replace_scan_alerts("s1", [_alert("s1", "a1"), _alert("s1", "a2")])
    # Re-running the same scan must replace, not append.
    db.replace_scan_alerts("s1", [_alert("s1", "a1"), _alert("s1", "a2")])
    assert len(db.alerts()) == 2
    db.close()


def test_prune_preserves_human_touched_alerts(tmp_path: Path) -> None:
    db = CatalogDB(tmp_path / "c.sqlite3")
    db.upsert_alerts([_alert("s1", "a1", status="acknowledged")])
    db.replace_scan_alerts("s2", [_alert("s2", "a1")])
    db.prune_generated_records("s2")
    statuses = sorted(a.status for a in db.alerts())
    # Acknowledged alert from an old scan survives; latest open alert stays.
    assert statuses == ["acknowledged", "open"]
    db.close()


def test_prune_stale_running_scans(tmp_path: Path) -> None:
    db = CatalogDB(tmp_path / "c.sqlite3")
    db.start_scan("s1")
    db.start_scan("s2")
    db.complete_scan("s2", "complete", {"scan_id": "s2"})
    db.start_scan("s3")  # crashed/interrupted, stays 'running'
    removed = db.prune_stale_running_scans("s1")
    assert removed == 1  # only s3 (running, != keep); s1 kept, s2 complete
    db.close()


# --- P0-2: retention must key on the latest COMPLETE scan, not latest scan ---


def test_latest_complete_scan_ignores_failed_and_running(tmp_path: Path) -> None:
    db = CatalogDB(tmp_path / "c.sqlite3")
    db.start_scan("s1")
    db.complete_scan("s1", "complete", {"scan_id": "s1"})
    db.start_scan("s2")
    db.complete_scan("s2", "failed", {"scan_id": "s2"})
    db.start_scan("s3")  # newest, but still running (crashed)
    assert db.latest_scan()["scan_id"] == "s3"  # naive pick would be wrong
    assert db.latest_complete_scan()["scan_id"] == "s1"
    db.close()


def test_prune_keyed_on_complete_scan_preserves_good_graph(tmp_path: Path) -> None:
    # Simulates the catalog-vacuum path when the newest scan failed: pruning must
    # key on the last complete scan so the good graph is not destroyed.
    db = CatalogDB(tmp_path / "c.sqlite3")
    db.start_scan("s1")
    db.replace_scan_edges("s1", [_edge("s1", 1), _edge("s1", 2)])
    db.complete_scan("s1", "complete", {"scan_id": "s1"})
    db.start_scan("s2")
    db.complete_scan("s2", "failed", {"scan_id": "s2"})
    keep = db.latest_complete_scan()["scan_id"]
    db.prune_generated_records(keep)
    assert {e.scan_id for e in db.edges()} == {"s1"}
    db.close()


def test_vacuum_runs_without_error(tmp_path: Path) -> None:
    db = CatalogDB(tmp_path / "c.sqlite3")
    db.replace_scan_edges("s1", [_edge("s1", 1)])
    db.vacuum()  # must not raise (VACUUM outside a transaction)
    assert db.table_counts()["edges"] == 1
    db.close()


def test_latest_complete_full_scope_scan_excludes_partial(tmp_path: Path) -> None:
    # Regression for the catalog-vacuum data-loss bug: a bounded scan also records
    # status 'complete', so keying retention on latest_complete_scan would prune
    # the full graph down to a partial one. The scope-aware query must skip it.
    db = CatalogDB(tmp_path / "c.sqlite3")
    db.start_scan("s_full")
    db.complete_scan("s_full", "complete", {"scan_id": "s_full", "full_scope": True})
    db.start_scan("s_partial")
    db.complete_scan("s_partial", "complete", {"scan_id": "s_partial", "full_scope": False})
    # Naive query would pick the newer partial scan...
    assert db.latest_complete_scan()["scan_id"] == "s_partial"
    # ...the scope-aware query keeps the last full-scope scan.
    assert db.latest_complete_full_scope_scan()["scan_id"] == "s_full"
    db.close()


def test_latest_scan_queries_break_timestamp_ties_by_insertion_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Windows system-clock granularity (~15.6ms) can stamp consecutive scans
    # with identical started_at values; 'latest' must then mean last-inserted,
    # not whichever row SQLite happens to scan first.
    monkeypatch.setattr(database, "utc_now", lambda: _TS)
    db = CatalogDB(tmp_path / "c.sqlite3")
    db.start_scan("s_older")
    db.complete_scan("s_older", "complete", {"scan_id": "s_older", "full_scope": True})
    db.start_scan("s_newer")
    db.complete_scan("s_newer", "complete", {"scan_id": "s_newer", "full_scope": True})
    assert db.latest_scan()["scan_id"] == "s_newer"
    assert db.latest_complete_scan()["scan_id"] == "s_newer"
    assert db.latest_complete_full_scope_scan()["scan_id"] == "s_newer"
    db.close()


def test_latest_complete_full_scope_scan_none_when_only_partial(tmp_path: Path) -> None:
    db = CatalogDB(tmp_path / "c.sqlite3")
    db.start_scan("s_partial")
    db.complete_scan("s_partial", "complete", {"scan_id": "s_partial", "full_scope": False})
    # No full-scope scan exists -> vacuum must NOT prune (returns None -> vacuum-only).
    assert db.latest_complete_full_scope_scan() is None


# --- P0-1: partial/bounded scans must NOT prune other scans' graph state ---


def _write_minimal_dad_hub_markers(hub: Path) -> None:
    (hub / "AI_FRONT_DOOR.md").write_text("# AI Front Door\n", encoding="utf-8")
    (hub / "MACHINE_NAVIGATION_MANIFEST.json").write_text(
        '{"manifest_version":"test"}\n', encoding="utf-8"
    )
    (hub / "registry").mkdir(parents=True, exist_ok=True)
    (hub / "registry" / "source-of-truth.json").write_text("{}\n", encoding="utf-8")
    (hub / "src" / "digital_asset_directory").mkdir(parents=True, exist_ok=True)
    (hub / "src" / "digital_asset_directory" / "cli.py").write_text("", encoding="utf-8")
    (hub / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "digital-asset-directory"',
                'version = "0.1.0"',
                "[project.scripts]",
                'asset-dir = "digital_asset_directory.cli:app"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _setup_scan_hub(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    _write_minimal_dad_hub_markers(hub)
    for rel in [
        "config", "processed/catalog", "processed/graph",
        "processed/alerts", "processed/reports", "state",
    ]:
        (hub / rel).mkdir(parents=True, exist_ok=True)
    source = tmp_path / "source"
    source.mkdir()
    (source / ".git").mkdir()
    for i in range(6):
        (source / f"f{i}.md").write_text(
            f"# Asset {i}\nknowledge graph learning loop evaluation {i}", encoding="utf-8"
        )
    (hub / "config" / "scoring.yaml").write_text(
        "weights:\n  reuse_potential: 1.0\n", encoding="utf-8"
    )
    cfg = {
        "project": {"database": "state/catalog.sqlite3"},
        "sources": {
            "local": [
                {
                    "id": "local",
                    "path": str(source),
                    "path_alias": "source",
                    "exclude": ["**/.git/**"],
                }
            ],
            "github": [],
        },
        "settings": {"read_only": True},
    }
    (hub / "config" / "sources.local.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return hub


def _edge_scan_ids(database_path: Path) -> set[str]:
    with CatalogDB(database_path) as db:
        return {e.scan_id for e in db.edges()}


@pytest.mark.integration
def test_full_scope_scan_prunes_to_latest(tmp_path: Path) -> None:
    cfg = load_config(repo_root=_setup_scan_hub(tmp_path))
    s1 = run_scan(cfg, local=True, github=True)
    assert s1["retention_pruned"]["scope"] == "full"
    s2 = run_scan(cfg, local=True, github=True)
    assert s2["retention_pruned"]["scope"] == "full"
    # After two full scans, only the latest scan's edges survive.
    assert _edge_scan_ids(cfg.database_path) <= {s2["scan_id"]}


@pytest.mark.integration
def test_local_only_scan_does_not_prune(tmp_path: Path) -> None:
    cfg = load_config(repo_root=_setup_scan_hub(tmp_path))
    run_scan(cfg, local=True, github=True)  # full: populates
    # Seed an edge from a hypothetical other source/scan that a partial scan of
    # THIS source will not regenerate (re-scanning the same source only
    # overwrites its own edges, so a foreign edge is the real accumulation case).
    with CatalogDB(cfg.database_path) as db:
        db.replace_scan_edges("foreign-scan", [_edge("foreign-scan", 999)])
    s2 = run_scan(cfg, local=True, github=False)  # partial: must NOT prune
    assert s2["retention_pruned"]["scope"] == "partial"
    assert s2["retention_pruned"]["skipped"] == "prune_skipped_partial_scan"
    # The foreign edge survives because the partial scan did not prune.
    assert "foreign-scan" in _edge_scan_ids(cfg.database_path)


@pytest.mark.integration
def test_full_scope_scan_prunes_foreign_edges(tmp_path: Path) -> None:
    cfg = load_config(repo_root=_setup_scan_hub(tmp_path))
    run_scan(cfg, local=True, github=True)  # full: populates
    with CatalogDB(cfg.database_path) as db:
        db.replace_scan_edges("foreign-scan", [_edge("foreign-scan", 999)])
    s2 = run_scan(cfg, local=True, github=True)  # full: prunes foreign state
    assert s2["retention_pruned"]["scope"] == "full"
    assert "foreign-scan" not in _edge_scan_ids(cfg.database_path)


@pytest.mark.integration
def test_bounded_scan_does_not_prune(tmp_path: Path) -> None:
    cfg = load_config(repo_root=_setup_scan_hub(tmp_path))
    run_scan(cfg, local=True, github=True)  # full
    s2 = run_scan(cfg, local=True, github=True, max_files=2)  # bounded
    assert s2["retention_pruned"]["scope"] == "partial"
    assert s2["retention_pruned"]["max_files"] == 2
