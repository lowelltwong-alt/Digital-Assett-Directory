"""Example boundary style for AI-generated Python.

This is intentionally small. It shows public API, private helpers, typed values,
pathlib, Protocol, StrEnum, and causal exception wrapping.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, auto
from pathlib import Path
from typing import NewType, Protocol

CustomerId = NewType("CustomerId", str)

__all__ = ["CustomerId", "ImportMode", "ImportResult", "CustomerImportService"]


class ImportMode(StrEnum):
    DRY_RUN = auto()
    APPLY = auto()


@dataclass(frozen=True, slots=True, kw_only=True)
class ImportResult:
    mode: ImportMode
    customer_count: int
    source_path: Path


class TextReader(Protocol):
    def read_text(self, path: Path) -> str:
        """Read text from path."""


class LocalTextReader:
    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")


class CustomerImportError(RuntimeError):
    """Raised when customer import fails."""


class CustomerImportService:
    def __init__(self, reader: TextReader | None = None) -> None:
        self._reader = reader or LocalTextReader()

    def import_customers(self, path: Path, *, mode: ImportMode) -> ImportResult:
        """Public entry point."""
        try:
            raw = self._reader.read_text(path)
            rows = self._parse_rows(raw)
            customers = self._validate_rows(rows)
        except OSError as exc:
            raise CustomerImportError(f"Could not read customer file: {path}") from exc

        if mode is ImportMode.APPLY:
            self._save_customers(customers)

        return ImportResult(mode=mode, customer_count=len(customers), source_path=path)

    def _parse_rows(self, raw: str) -> list[list[str]]:
        return [line.split(",") for line in raw.splitlines() if line.strip()]

    def _validate_rows(self, rows: list[list[str]]) -> list[tuple[CustomerId, str]]:
        customers: list[tuple[CustomerId, str]] = []
        for row in rows:
            if len(row) < 2:
                raise CustomerImportError("Expected at least customer_id,email")
            customers.append((CustomerId(row[0].strip()), row[1].strip()))
        return customers

    def _save_customers(self, customers: list[tuple[CustomerId, str]]) -> None:
        # Side-effect adapter would go here.
        return None
