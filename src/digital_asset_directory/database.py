from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Any

from .models import (
    AssetRecord,
    AssetChunkRecord,
    AssetDeltaRecord,
    EdgeRecord,
    AlertRecord,
    DuplicateClusterRecord,
    LessonRecord,
    HandoffRecord,
    SynergyRecord,
    ActivationTrigger,
)
from .utils import utc_now


class CatalogDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "CatalogDB":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _init_schema(self) -> None:
        self.connection.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS assets (
          asset_id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, source_id TEXT NOT NULL,
          asset_type TEXT NOT NULL, title TEXT NOT NULL, logical_path TEXT NOT NULL,
          value_score REAL NOT NULL, freshness_status TEXT NOT NULL, last_seen_at TEXT NOT NULL,
          payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_assets_source ON assets(source_id);
        CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);
        CREATE INDEX IF NOT EXISTS idx_assets_value ON assets(value_score DESC);
        CREATE TABLE IF NOT EXISTS edges (
          edge_id TEXT PRIMARY KEY, edge_type TEXT NOT NULL, source_asset_id TEXT NOT NULL,
          target_asset_id TEXT NOT NULL, confidence REAL NOT NULL, scan_id TEXT NOT NULL,
          payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_asset_id);
        CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_asset_id);
        CREATE TABLE IF NOT EXISTS asset_chunks (
          chunk_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, revision_id TEXT NOT NULL,
          chunk_kind TEXT NOT NULL, scan_id TEXT NOT NULL, payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_asset_chunks_asset ON asset_chunks(asset_id);
        CREATE INDEX IF NOT EXISTS idx_asset_chunks_scan ON asset_chunks(scan_id);
        CREATE TABLE IF NOT EXISTS duplicate_clusters (
          cluster_id TEXT PRIMARY KEY, cluster_type TEXT NOT NULL, scan_id TEXT NOT NULL,
          payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_duplicate_clusters_scan ON duplicate_clusters(scan_id);
        CREATE TABLE IF NOT EXISTS asset_deltas (
          delta_id TEXT PRIMARY KEY, left_asset_id TEXT NOT NULL, right_asset_id TEXT NOT NULL,
          delta_type TEXT NOT NULL, scan_id TEXT NOT NULL, payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_asset_deltas_left ON asset_deltas(left_asset_id);
        CREATE INDEX IF NOT EXISTS idx_asset_deltas_right ON asset_deltas(right_asset_id);
        CREATE INDEX IF NOT EXISTS idx_asset_deltas_scan ON asset_deltas(scan_id);
        CREATE TABLE IF NOT EXISTS scans (
          scan_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, completed_at TEXT,
          status TEXT NOT NULL, summary_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS alerts (
          alert_id TEXT PRIMARY KEY, alert_type TEXT NOT NULL, severity TEXT NOT NULL,
          status TEXT NOT NULL, scan_id TEXT NOT NULL, payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS synergies (
          synergy_id TEXT PRIMARY KEY, score REAL NOT NULL, payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS activation_triggers (
          trigger_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, status TEXT NOT NULL, payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS lessons (
          lesson_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, repository TEXT NOT NULL, payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS handoffs (
          handoff_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, created_at TEXT NOT NULL, repository TEXT NOT NULL, payload_json TEXT NOT NULL
        );
        """)
        self.connection.commit()

    def replace_scan_identity_records(
        self,
        scan_id: str,
        chunks: Iterable[AssetChunkRecord],
        clusters: Iterable[DuplicateClusterRecord],
        deltas: Iterable[AssetDeltaRecord],
    ) -> None:
        self.connection.execute("DELETE FROM asset_chunks WHERE scan_id=?", (scan_id,))
        self.connection.execute("DELETE FROM duplicate_clusters WHERE scan_id=?", (scan_id,))
        self.connection.execute("DELETE FROM asset_deltas WHERE scan_id=?", (scan_id,))
        self.connection.executemany(
            "INSERT OR REPLACE INTO asset_chunks VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    c.chunk_id,
                    c.asset_id,
                    c.revision_id,
                    c.chunk_kind,
                    c.scan_id,
                    self._payload(c),
                )
                for c in chunks
            ],
        )
        self.connection.executemany(
            "INSERT OR REPLACE INTO duplicate_clusters VALUES (?, ?, ?, ?)",
            [
                (c.cluster_id, c.cluster_type, c.scan_id, self._payload(c))
                for c in clusters
            ],
        )
        self.connection.executemany(
            "INSERT OR REPLACE INTO asset_deltas VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    d.delta_id,
                    d.left_asset_id,
                    d.right_asset_id,
                    d.delta_type,
                    d.scan_id,
                    self._payload(d),
                )
                for d in deltas
            ],
        )
        self.connection.commit()

    @staticmethod
    def _payload(model: Any) -> str:
        return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)

    def start_scan(self, scan_id: str, summary: dict[str, Any] | None = None) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO scans VALUES (?, ?, NULL, ?, ?)",
            (scan_id, utc_now(), "running", json.dumps(summary or {})),
        )
        self.connection.commit()

    def complete_scan(self, scan_id: str, status: str, summary: dict[str, Any]) -> None:
        self.connection.execute(
            "UPDATE scans SET completed_at=?, status=?, summary_json=? WHERE scan_id=?",
            (utc_now(), status, json.dumps(summary, sort_keys=True), scan_id),
        )
        self.connection.commit()

    def upsert_assets(self, assets: Iterable[AssetRecord]) -> None:
        self.connection.executemany(
            "INSERT OR REPLACE INTO assets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    a.asset_id,
                    a.revision_id,
                    a.source_id,
                    a.asset_type,
                    a.title,
                    a.logical_path,
                    a.value_score,
                    a.freshness_status,
                    a.last_seen_at,
                    self._payload(a),
                )
                for a in assets
            ],
        )
        self.connection.commit()

    def replace_scan_edges(self, scan_id: str, edges: Iterable[EdgeRecord]) -> None:
        self.connection.execute("DELETE FROM edges WHERE scan_id=?", (scan_id,))
        self.connection.executemany(
            "INSERT OR REPLACE INTO edges VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    e.edge_id,
                    e.edge_type,
                    e.source_asset_id,
                    e.target_asset_id,
                    e.confidence,
                    e.scan_id,
                    self._payload(e),
                )
                for e in edges
            ],
        )
        self.connection.commit()

    def upsert_alerts(self, alerts: Iterable[AlertRecord]) -> None:
        self.connection.executemany(
            "INSERT OR REPLACE INTO alerts VALUES (?, ?, ?, ?, ?, ?)",
            [
                (a.alert_id, a.alert_type, a.severity, a.status, a.scan_id, self._payload(a))
                for a in alerts
            ],
        )
        self.connection.commit()

    def replace_scan_alerts(self, scan_id: str, alerts: Iterable[AlertRecord]) -> None:
        """Replace this scan's open alerts, mirroring ``replace_scan_edges``.

        Alerts are regenerated deterministically every scan, so appending them
        (the old ``upsert_alerts`` path) accumulated hundreds of thousands of
        rows across scans. Human-touched alerts (status != 'open') are preserved.
        """
        self.connection.execute(
            "DELETE FROM alerts WHERE scan_id=? AND status='open'", (scan_id,)
        )
        self.connection.executemany(
            "INSERT OR REPLACE INTO alerts VALUES (?, ?, ?, ?, ?, ?)",
            [
                (a.alert_id, a.alert_type, a.severity, a.status, a.scan_id, self._payload(a))
                for a in alerts
            ],
        )
        self.connection.commit()

    def prune_generated_records(self, keep_scan_id: str) -> dict[str, int]:
        """Drop per-scan generated rows that do not belong to the latest scan.

        ``edges``, ``asset_chunks``, ``asset_deltas``, ``duplicate_clusters`` and
        open ``alerts`` are keyed by ``scan_id`` and are only valid for the scan
        that produced them; older scans' rows are stale graph state that bloats
        the catalog. Assets persist (keyed by stable ``asset_id``). Non-open
        alerts (human-acknowledged/resolved) are preserved as a safety net.

        Assumes one scanner at a time (SQLite WAL single-writer): a concurrently
        running second scan's rows would be pruned as "not latest". Concurrent
        scans were already unsupported (assets upsert over each other); do not
        run two scans against one catalog.
        """
        removed: dict[str, int] = {}
        cur = self.connection.execute(
            "DELETE FROM edges WHERE scan_id != ?", (keep_scan_id,)
        )
        removed["edges"] = cur.rowcount
        cur = self.connection.execute(
            "DELETE FROM asset_chunks WHERE scan_id != ?", (keep_scan_id,)
        )
        removed["asset_chunks"] = cur.rowcount
        cur = self.connection.execute(
            "DELETE FROM asset_deltas WHERE scan_id != ?", (keep_scan_id,)
        )
        removed["asset_deltas"] = cur.rowcount
        cur = self.connection.execute(
            "DELETE FROM duplicate_clusters WHERE scan_id != ?", (keep_scan_id,)
        )
        removed["duplicate_clusters"] = cur.rowcount
        cur = self.connection.execute(
            "DELETE FROM alerts WHERE scan_id != ? AND status='open'", (keep_scan_id,)
        )
        removed["alerts"] = cur.rowcount
        self.connection.commit()
        return removed

    def prune_stale_running_scans(self, keep_scan_id: str) -> int:
        """Remove interrupted 'running' scan rows (crashed scans never completed)."""
        cur = self.connection.execute(
            "DELETE FROM scans WHERE status='running' AND scan_id != ?", (keep_scan_id,)
        )
        self.connection.commit()
        return cur.rowcount

    def vacuum(self) -> None:
        """Reclaim free pages after pruning. Must run outside an open transaction."""
        self.connection.execute("VACUUM")
        self.connection.commit()

    def table_counts(self) -> dict[str, int]:
        """Row counts per table for health/verification surfaces."""
        tables = [
            "assets", "edges", "alerts", "asset_chunks", "asset_deltas",
            "duplicate_clusters", "scans", "synergies", "activation_triggers",
            "lessons", "handoffs",
        ]
        counts: dict[str, int] = {}
        for table in tables:
            row = self.connection.execute(
                'SELECT COUNT(*) FROM "%s"' % table
            ).fetchone()
            counts[table] = int(row[0]) if row else 0
        return counts

    def upsert_synergies(self, records: Iterable[SynergyRecord]) -> None:
        self.connection.executemany(
            "INSERT OR REPLACE INTO synergies VALUES (?, ?, ?)",
            [(r.synergy_id, r.score, self._payload(r)) for r in records],
        )
        self.connection.commit()

    def upsert_triggers(self, records: Iterable[ActivationTrigger]) -> None:
        self.connection.executemany(
            "INSERT OR REPLACE INTO activation_triggers VALUES (?, ?, ?, ?)",
            [(r.trigger_id, r.asset_id, r.status, self._payload(r)) for r in records],
        )
        self.connection.commit()

    def add_lesson(self, record: LessonRecord) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO lessons VALUES (?, ?, ?, ?)",
            (record.lesson_id, record.created_at, record.repository, self._payload(record)),
        )
        self.connection.commit()

    def add_handoff(self, record: HandoffRecord) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO handoffs VALUES (?, ?, ?, ?, ?)",
            (
                record.handoff_id,
                record.session_id,
                record.created_at,
                record.repository,
                self._payload(record),
            ),
        )
        self.connection.commit()

    def assets(self) -> list[AssetRecord]:
        return [
            AssetRecord.model_validate_json(row["payload_json"])
            for row in self.connection.execute(
                "SELECT payload_json FROM assets ORDER BY value_score DESC, title"
            )
        ]

    def edges(self) -> list[EdgeRecord]:
        return [
            EdgeRecord.model_validate_json(row["payload_json"])
            for row in self.connection.execute("SELECT payload_json FROM edges")
        ]

    def alerts(self, open_only: bool = False) -> list[AlertRecord]:
        query = "SELECT payload_json FROM alerts" + (" WHERE status='open'" if open_only else "")
        return [
            AlertRecord.model_validate_json(row["payload_json"])
            for row in self.connection.execute(query)
        ]

    def synergies(self) -> list[SynergyRecord]:
        return [
            SynergyRecord.model_validate_json(row["payload_json"])
            for row in self.connection.execute(
                "SELECT payload_json FROM synergies ORDER BY score DESC, synergy_id"
            )
        ]

    def latest_scan(self) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM scans ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def latest_complete_scan(self) -> dict[str, Any] | None:
        """Most recent fully-successful scan (status 'complete').

        Retention/vacuum must key on this, not ``latest_scan``: if the most
        recent scan crashed ('running') or failed, its subset/empty rows are not
        a valid graph to prune everything else down to.
        """
        row = self.connection.execute(
            "SELECT * FROM scans WHERE status='complete' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
