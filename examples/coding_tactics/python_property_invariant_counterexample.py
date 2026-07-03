from __future__ import annotations

from urllib.parse import urlencode


def canonical_query(params: list[tuple[str, str]]) -> str:
    # Order-dependent output makes cache keys and dedupe records drift.
    return urlencode(params, doseq=True)
