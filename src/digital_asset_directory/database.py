from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Any

from .models import (
    AssetRecord,
    EdgeRecord,
    AlertRecord,
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
