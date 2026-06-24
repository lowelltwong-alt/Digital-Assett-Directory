from __future__ import annotations

import uuid

NAMESPACE = uuid.UUID("d7d89920-42cf-4c2d-9b7b-cfa3b7b33a24")


def stable_id(kind: str, *parts: str) -> str:
    canonical = "|".join(str(part).strip().replace("\\", "/") for part in parts)
    return f"dad:{kind}:{uuid.uuid5(NAMESPACE, f'{kind}|{canonical}')}"


def asset_id(source_id: str, logical_path: str) -> str:
    return stable_id("asset", source_id, logical_path.casefold())


def revision_id(asset_identifier: str, content_hash: str) -> str:
    return stable_id("revision", asset_identifier, content_hash)


def edge_id(edge_type: str, source_asset_id: str, target_asset_id: str) -> str:
    return stable_id("edge", edge_type, source_asset_id, target_asset_id)


def scan_id() -> str:
    return f"dad:scan:{uuid.uuid4()}"


def session_id() -> str:
    return f"dad:session:{uuid.uuid4()}"
