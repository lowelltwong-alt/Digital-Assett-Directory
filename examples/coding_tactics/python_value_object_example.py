from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

AssetId = NewType("AssetId", str)


@dataclass(frozen=True, slots=True, kw_only=True)
class AssetRoute:
    asset_id: AssetId
    target_repo: str
    requires_human_review: bool = False


def route_label(route: AssetRoute) -> str:
    return f"{route.asset_id}->{route.target_repo}"
