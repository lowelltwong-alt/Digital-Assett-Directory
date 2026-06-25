from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml

from .models import AssetRecord

DEFAULT_WEIGHTS = {
    "reuse_potential": 0.18,
    "verification": 0.15,
    "provenance": 0.13,
    "composability": 0.15,
    "learning_loop_value": 0.15,
    "uniqueness": 0.08,
    "demand_signal": 0.08,
    "freshness": 0.08,
}


def load_scoring(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "config" / "scoring.yaml"
    return (
        yaml.safe_load(path.read_text(encoding="utf-8"))
        if path.exists()
        else {"weights": DEFAULT_WEIGHTS}
    )


def score_asset(
    asset: AssetRecord,
    scoring: dict[str, Any],
    duplicate_counts: dict[str, int] | None = None,
) -> AssetRecord:
    weights = scoring.get("weights", DEFAULT_WEIGHTS)
    learning_types = {
        "evaluation",
        "test",
        "lesson",
        "decision",
        "workflow",
        "schema",
        "ontology",
        "skill",
        "model",
        "algorithm",
        "forecaster",
    }
    reusable_types = {
        "code",
        "schema",
        "ontology",
        "taxonomy",
        "prompt",
        "skill",
        "workflow",
        "model",
        "algorithm",
        "forecaster",
        "adapter",
        "connector",
        "evaluation",
        "test",
        "decision",
        "lesson",
    }
    components = {
        "reuse_potential": min(
            1.0,
            0.45
            + 0.15 * len(asset.capabilities)
            + (0.25 if asset.asset_type in reusable_types else 0.0),
        ),
        "verification": min(
            1.0,
            0.25
            + (0.55 if asset.asset_type in {"test", "evaluation", "schema"} else 0.0)
            + (0.15 if "evaluation" in asset.tags else 0.0),
        ),
        "provenance": (
            0.95
            if asset.content_sha256
            else 0.55
            if (asset.source_provenance or asset.source_id)
            else 0.2
        ),
        "composability": min(
            1.0, 0.25 + 0.13 * len(asset.capabilities) + 0.08 * len(asset.outcomes)
        ),
        "learning_loop_value": min(
            1.0,
            0.30 + (0.45 if asset.asset_type in learning_types else 0.0) + 0.08 * len(asset.needs),
        ),
        "uniqueness": 1.0
        - min(0.6, 0.15 * max(0, (duplicate_counts or {}).get(asset.asset_id, 1) - 1)),
        "demand_signal": min(1.0, 0.30 + 0.15 * len(asset.needs) + 0.10 * len(asset.outcomes)),
        "freshness": {"current": 1.0, "watch": 0.65, "stale": 0.25, "unknown": 0.45}.get(
            asset.freshness_status, 0.45
        ),
    }
    raw = sum(float(weights.get(name, 0)) * value for name, value in components.items())
    penalties = scoring.get("risk_penalties", {})
    risk = 0.0
    if asset.sensitivity == "unknown":
        risk += float(penalties.get("sensitive_unclassified", 0.08))
    if not asset.content_sha256 and not asset.source_provenance:
        risk += float(penalties.get("no_provenance", 0.08))
    if (
        asset.source_kind == "github"
        and asset.asset_type == "repository"
        and not asset.metadata.get("license")
    ):
        risk += float(penalties.get("unknown_license", 0.04))
    raw *= max(0.0, 1.0 - min(0.85, risk))
    asset.value_components = {k: round(v * 100, 2) for k, v in components.items()}
    if risk:
        asset.value_components["risk_factor"] = round((1.0 - min(0.85, risk)) * 100, 2)
    asset.value_score = round(max(0.0, min(1.0, raw)) * 100, 2)
    return asset
