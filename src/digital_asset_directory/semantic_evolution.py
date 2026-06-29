from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path, PurePosixPath
from typing import Any

from .config import LocalSource
from .ids import stable_id
from .models import AssetRecord, SemanticEvolutionRecord
from .utils import atomic_write_text, sha256_bytes, sha256_file, utc_now, write_jsonl

METHODOLOGY_VERSION = "semantic-evolution-grading-v1"
COSMETIC_JSON_KEYS = {"$id", "$schema", "$comment", "title", "description", "examples"}
PATH_CLASS_LINEAGE_RANK = {
    "canonicalish_source": 0,
    "worktree": 10,
    "temp_fixture": 20,
    "archive": 30,
    "generated_or_processed": 40,
}
VERSION_CUE_RE = re.compile(
    r"(?:^|[-_/ .])(?:v|version|rev|revision|attempt|copy|pytest)[-_ .]?(\d+)(?:$|[-_/ .])",
    re.IGNORECASE,
)


def path_class(logical_path: str) -> str:
    lowered = logical_path.lower().replace("\\", "/")
    if ".pytest-tmp-root" in lowered or "/tmp/" in lowered or "/temp/" in lowered:
        return "temp_fixture"
    if "_codex_worktrees" in lowered:
        return "worktree"
    if "/archive/" in lowered or "/99_archive/" in lowered or "/zips/" in lowered:
        return "archive"
    if "processed/" in lowered or "raw/" in lowered:
        return "generated_or_processed"
    return "canonicalish_source"


def _path_version_cue(logical_path: str) -> int:
    matches = [int(match.group(1)) for match in VERSION_CUE_RE.finditer(logical_path)]
    return max(matches) if matches else 0


def _lineage_sort_key(item: dict[str, Any]) -> tuple[str, int, int, str]:
    asset: AssetRecord = item["asset"]
    path = asset.logical_path.lower().replace("\\", "/")
    modified = asset.modified_at or asset.first_seen_at or ""
    return (
        modified,
        PATH_CLASS_LINEAGE_RANK.get(path_class(path), 99),
        _path_version_cue(path),
        path,
    )


def _resolve_asset_path(asset: AssetRecord, local_sources: list[LocalSource]) -> Path | None:
    logical = asset.logical_path.replace("\\", "/")
    for source in local_sources:
        alias = source.path_alias.strip("/")
        if logical == alias:
            return source.path
        prefix = f"{alias}/"
        if logical.startswith(prefix):
            return source.path / logical[len(prefix) :]
    return None


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _strip_cosmetic_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_cosmetic_json(item)
            for key, item in sorted(value.items())
            if key not in COSMETIC_JSON_KEYS
        }
    if isinstance(value, list):
        return [_strip_cosmetic_json(item) for item in value]
    return value


def _load_json_asset(
    asset: AssetRecord,
    local_sources: list[LocalSource],
    *,
    max_read_bytes: int = 1_000_000,
) -> tuple[dict[str, Any] | None, str, str]:
    path = _resolve_asset_path(asset, local_sources)
    if not path or not path.exists() or not path.is_file():
        return None, "", "missing_file"
    try:
        if max_read_bytes > 0 and path.stat().st_size > max_read_bytes:
            return None, "", "skipped_too_large"
        text = path.read_text(encoding="utf-8")
        content_hash = sha256_file(path)
        payload = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "", "unreadable_or_not_json"
    if not isinstance(payload, dict):
        return None, content_hash, "json_not_object"
    return payload, content_hash, "json_object"


def _schema_features(payload: dict[str, Any]) -> dict[str, Any]:
    properties = payload.get("properties")
    if not isinstance(properties, dict):
        properties = {}
    required = payload.get("required")
    if not isinstance(required, list):
        required = []
    types: dict[str, str] = {}
    enums: dict[str, list[str]] = {}
    patterns: dict[str, str] = {}
    formats: dict[str, str] = {}
    for key, value in properties.items():
        if not isinstance(value, dict):
            continue
        if "type" in value:
            types[key] = _json_dumps(value["type"])
        if isinstance(value.get("enum"), list):
            enums[key] = sorted(str(item) for item in value["enum"])
        if "pattern" in value:
            patterns[key] = str(value["pattern"])
        if "format" in value:
            formats[key] = str(value["format"])
    return {
        "required": sorted(str(item) for item in required),
        "properties": sorted(str(key) for key in properties),
        "types": types,
        "enums": enums,
        "patterns": patterns,
        "formats": formats,
        "semantic_hash": sha256_bytes(_json_dumps(_strip_cosmetic_json(payload)).encode("utf-8")),
        "normalized_hash": sha256_bytes(_json_dumps(payload).encode("utf-8")),
    }


def _set_delta(left: list[str], right: list[str]) -> tuple[list[str], list[str]]:
    left_set, right_set = set(left), set(right)
    return sorted(right_set - left_set), sorted(left_set - right_set)


def _compare_feature_maps(
    left: dict[str, str] | dict[str, list[str]],
    right: dict[str, str] | dict[str, list[str]],
) -> dict[str, Any]:
    added_keys = sorted(set(right) - set(left))
    removed_keys = sorted(set(left) - set(right))
    changed: dict[str, dict[str, Any]] = {}
    for key in sorted(set(left) & set(right)):
        if left[key] != right[key]:
            changed[key] = {"left": left[key], "right": right[key]}
    return {"added": added_keys, "removed": removed_keys, "changed": changed}


def _compare_features(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    required_added, required_removed = _set_delta(left["required"], right["required"])
    properties_added, properties_removed = _set_delta(left["properties"], right["properties"])
    enums = _compare_feature_maps(left["enums"], right["enums"])
    enum_added_values: dict[str, list[str]] = {}
    enum_removed_values: dict[str, list[str]] = {}
    for key, values in enums["changed"].items():
        added, removed = _set_delta(values["left"], values["right"])
        if added:
            enum_added_values[key] = added
        if removed:
            enum_removed_values[key] = removed
    return {
        "required_added": required_added,
        "required_removed": required_removed,
        "properties_added": properties_added,
        "properties_removed": properties_removed,
        "types": _compare_feature_maps(left["types"], right["types"]),
        "enums": {
            **enums,
            "values_added": enum_added_values,
            "values_removed": enum_removed_values,
        },
        "patterns": _compare_feature_maps(left["patterns"], right["patterns"]),
        "formats": _compare_feature_maps(left["formats"], right["formats"]),
    }


def _merge_pair_changes(pair_changes: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "required_added": set(),
        "required_removed": set(),
        "properties_added": set(),
        "properties_removed": set(),
        "type_changed": set(),
        "type_added": set(),
        "type_removed": set(),
        "enum_changed": set(),
        "enum_added": set(),
        "enum_removed": set(),
        "enum_values_added": defaultdict(set),
        "enum_values_removed": defaultdict(set),
        "pattern_changed": set(),
        "pattern_added": set(),
        "pattern_removed": set(),
        "format_changed": set(),
    }
    for change in pair_changes:
        for key in ("required_added", "required_removed", "properties_added", "properties_removed"):
            merged[key].update(change[key])
        merged["type_added"].update(change["types"]["added"])
        merged["type_removed"].update(change["types"]["removed"])
        merged["type_changed"].update(change["types"]["changed"])
        merged["enum_added"].update(change["enums"]["added"])
        merged["enum_removed"].update(change["enums"]["removed"])
        merged["enum_changed"].update(change["enums"]["changed"])
        for field, values in change["enums"]["values_added"].items():
            merged["enum_values_added"][field].update(values)
        for field, values in change["enums"]["values_removed"].items():
            merged["enum_values_removed"][field].update(values)
        merged["pattern_added"].update(change["patterns"]["added"])
        merged["pattern_removed"].update(change["patterns"]["removed"])
        merged["pattern_changed"].update(change["patterns"]["changed"])
        merged["format_changed"].update(change["formats"]["changed"])
    return {
        key: sorted(value) if not isinstance(value, defaultdict) else {
            item_key: sorted(item_value) for item_key, item_value in sorted(value.items())
        }
        for key, value in merged.items()
    }


def _count_changes(changes: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, value in changes.items():
        if isinstance(value, dict):
            counts[key] = sum(len(items) for items in value.values())
        else:
            counts[key] = len(value)
    return counts


def _grade(
    *,
    readable_count: int,
    raw_version_count: int,
    normalized_version_count: int,
    semantic_version_count: int,
    path_counts: Counter[str],
    changes: dict[str, Any],
) -> tuple[str, str, float, float, str]:
    if readable_count < 2:
        return (
            "insufficient_evidence",
            "insufficient_evidence",
            0.0,
            0.0,
            "Fewer than two readable comparable JSON objects were available.",
        )
    temp_count = path_counts.get("temp_fixture", 0)
    canonical_count = path_counts.get("canonicalish_source", 0)
    fixture_pressure = temp_count > 0 and canonical_count > 0
    if semantic_version_count <= 1:
        if raw_version_count <= 1:
            noise = "exact_copy"
            noise_score = 0.1
            summary = "All readable copies collapse to one raw and semantic version."
        elif normalized_version_count <= 1:
            noise = "fixture_lineage_noise" if fixture_pressure else "format_or_order_noise"
            noise_score = 0.8 if fixture_pressure else 0.55
            summary = "Raw copies differ, but normalized structured JSON is equivalent."
        else:
            noise = "fixture_lineage_noise" if fixture_pressure else "path_or_metadata_noise"
            noise_score = 0.75 if fixture_pressure else 0.6
            summary = "Normalized JSON differs, but semantic signatures match after cosmetic metadata removal."
        return ("none" if normalized_version_count <= 1 else "cosmetic_metadata", noise, 0.0, noise_score, summary)

    counts = _count_changes(changes)
    breaking = (
        counts["required_added"]
        + counts["required_removed"]
        + counts["properties_removed"]
        + counts["type_changed"]
        + counts["type_added"]
        + counts["type_removed"]
        + counts["enum_removed"]
        + counts["enum_values_removed"]
        + counts["pattern_added"]
        + counts["pattern_changed"]
    )
    additive = (
        counts["properties_added"]
        + counts["enum_added"]
        + counts["enum_values_added"]
        + counts["format_changed"]
    )
    total = sum(counts.values())
    if breaking:
        grade = "breaking_semantic"
        score = 0.9
    elif total >= 8:
        grade = "major_semantic"
        score = 0.72
    elif additive >= 3 or total >= 4:
        grade = "moderate_semantic"
        score = 0.48
    else:
        grade = "minor_semantic"
        score = 0.25
    noise = "mixed_signal" if fixture_pressure or raw_version_count > semantic_version_count else "path_or_metadata_noise"
    noise_score = 0.55 if noise == "mixed_signal" else 0.25
    summary = (
        f"{semantic_version_count} semantic versions detected; {breaking} breaking-risk "
        f"signals and {additive} additive/compatible signals."
    )
    return grade, noise, score, noise_score, summary


def _guidance(evolution_grade: str, noise_class: str) -> tuple[str, str, list[str]]:
    if noise_class in {"fixture_lineage_noise", "mixed_signal"}:
        current = (
            "Do not score every copied fixture as an independent high-value current asset; "
            "score canonical/source variants and route copies as lineage evidence."
        )
    else:
        current = "Use duplicate/variant review before changing current scores."
    if evolution_grade in {"breaking_semantic", "major_semantic"}:
        family = "High family-level signal: review semantic evolution before merge/default or calibration decisions."
    elif evolution_grade in {"minor_semantic", "moderate_semantic"}:
        family = "Moderate family-level signal: preserve a candidate delta and check examples/tests."
    elif evolution_grade == "cosmetic_metadata":
        family = "Low semantic signal: preserve metadata/path lineage without treating it as behavior change."
    elif evolution_grade == "none":
        family = "No semantic evolution detected; copies are duplicate or propagation evidence."
    else:
        family = "Insufficient evidence; collect readable content or human review."
    edges = ["lineage_evidence_for"]
    if evolution_grade in {"minor_semantic", "moderate_semantic", "major_semantic", "breaking_semantic"}:
        edges.extend(["semantic_variant_of", "evolved_from", "has_delta_candidate"])
    if noise_class in {"fixture_lineage_noise", "format_or_order_noise", "path_or_metadata_noise"}:
        edges.append("noise_variant_of")
    if noise_class == "mixed_signal":
        edges.extend(["noise_variant_of", "semantic_variant_of"])
    return current, family, sorted(set(edges))


def build_semantic_evolution_records(
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    *,
    scan_id: str,
    source_id: str = "all",
    basename: str | None = None,
    asset_type: str = "schema",
    max_families: int = 100,
    max_read_bytes: int = 1_000_000,
    generated_at: str | None = None,
) -> list[SemanticEvolutionRecord]:
    generated = generated_at or utc_now()
    groups: dict[str, list[AssetRecord]] = defaultdict(list)
    basename_filter = basename.lower() if basename else None
    for asset in assets:
        if source_id != "all" and asset.source_id != source_id:
            continue
        if asset_type != "all" and asset.asset_type != asset_type:
            continue
        name = PurePosixPath(asset.logical_path.replace("\\", "/")).name.lower()
        if basename_filter and name != basename_filter:
            continue
        if not name.endswith(".json"):
            continue
        groups[name].append(asset)

    ranked_groups = sorted(
        ((key, value) for key, value in groups.items() if len(value) >= 2),
        key=lambda item: (-len(item[1]), item[0]),
    )[:max_families]
    records: list[SemanticEvolutionRecord] = []
    for family_key, group in ranked_groups:
        path_counts = Counter(path_class(asset.logical_path) for asset in group)
        readable: list[dict[str, Any]] = []
        read_status_counts: Counter[str] = Counter()
        for asset in sorted(group, key=lambda item: item.logical_path):
            payload, content_hash, status = _load_json_asset(
                asset,
                local_sources,
                max_read_bytes=max_read_bytes,
            )
            read_status_counts[status] += 1
            if payload is None:
                continue
            features = _schema_features(payload)
            readable.append(
                {
                    "asset": asset,
                    "content_hash": content_hash,
                    "features": features,
                    "normalized_hash": features["normalized_hash"],
                    "semantic_hash": features["semantic_hash"],
                }
            )
        if len(readable) < 2:
            raw_hashes = set()
            normalized_hashes = set()
            semantic_hashes = set()
            changes: dict[str, Any] = {}
        else:
            raw_hashes = {item["content_hash"] for item in readable}
            normalized_hashes = {item["normalized_hash"] for item in readable}
            semantic_hashes = {item["semantic_hash"] for item in readable}
            semantic_representatives: dict[str, dict[str, Any]] = {}
            for item in readable:
                semantic_representatives.setdefault(item["semantic_hash"], item)
            ordered_representatives = sorted(
                semantic_representatives.values(),
                key=_lineage_sort_key,
            )
            pair_changes = [
                _compare_features(left["features"], right["features"])
                for left, right in combinations(ordered_representatives, 2)
            ]
            changes = _merge_pair_changes(pair_changes) if pair_changes else {}
        grade, noise, semantic_score, noise_score, summary = _grade(
            readable_count=len(readable),
            raw_version_count=len(raw_hashes),
            normalized_version_count=len(normalized_hashes),
            semantic_version_count=len(semantic_hashes),
            path_counts=path_counts,
            changes=changes,
        )
        current_guidance, family_guidance, edge_suggestions = _guidance(grade, noise)
        representative_paths = [item["asset"].logical_path for item in readable[:8]]
        if not representative_paths:
            representative_paths = [asset.logical_path for asset in group[:8]]
        records.append(
            SemanticEvolutionRecord(
                evolution_id=stable_id("semantic-evolution", family_key, scan_id),
                family_key=family_key,
                asset_type=asset_type,
                source_asset_ids=[asset.asset_id for asset in group[:200]],
                representative_paths=representative_paths,
                path_class_counts=dict(sorted(path_counts.items())),
                raw_version_count=len(raw_hashes),
                normalized_version_count=len(normalized_hashes),
                semantic_version_count=len(semantic_hashes),
                evolution_grade=grade,  # type: ignore[arg-type]
                noise_class=noise,  # type: ignore[arg-type]
                semantic_change_score=semantic_score,
                noise_score=noise_score,
                grading_summary=summary,
                structural_changes=changes,
                current_instance_score_guidance=current_guidance,
                family_value_guidance=family_guidance,
                graph_edge_suggestions=edge_suggestions,
                applies_when=[
                    "A temp copy, near duplicate, changelog, schema variant, or copied fixture is being scored or compared.",
                    "A family-level version lineage may affect current score, ceiling, or graph edges.",
                ],
                does_not_apply_when=[
                    "Only one readable comparable asset exists.",
                    "A human has already reviewed the exact delta and recorded source authority.",
                ],
                evidence={
                    "methodology_version": METHODOLOGY_VERSION,
                    "asset_count": len(group),
                    "readable_count": len(readable),
                    "read_status_counts": dict(sorted(read_status_counts.items())),
                    "raw_hash_count": len(raw_hashes),
                    "normalized_hash_count": len(normalized_hashes),
                    "semantic_hash_count": len(semantic_hashes),
                    "lineage_ordering": "candidate_path_version_and_timestamp_cues",
                    "cosmetic_json_keys_ignored_for_semantic_signature": sorted(COSMETIC_JSON_KEYS),
                    "candidate_only": True,
                },
                generated_at=generated,
                scan_id=scan_id,
            )
        )
    return sorted(records, key=lambda item: (-item.semantic_change_score, -item.noise_score, item.family_key))


def semantic_evolution_markdown(records: list[SemanticEvolutionRecord], *, generated_at: str, review_sample: int) -> str:
    grade_counts = Counter(record.evolution_grade for record in records)
    noise_counts = Counter(record.noise_class for record in records)
    lines = [
        "# Semantic Evolution Candidates",
        "",
        "Generated candidate report only. Evolution grades route review; they do not change asset scores.",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Candidate families: **{len(records)}**",
        "",
        "## Evolution Grades",
        "",
    ]
    for grade, count in grade_counts.most_common():
        lines.append(f"- `{grade}`: **{count}**")
    lines.extend(["", "## Noise Classes", ""])
    for noise, count in noise_counts.most_common():
        lines.append(f"- `{noise}`: **{count}**")
    lines.extend(["", "## Review Sample", ""])
    for record in records[:review_sample]:
        lines.extend(
            [
                f"### {record.family_key}",
                f"- Evolution grade: `{record.evolution_grade}` ({record.semantic_change_score})",
                f"- Noise class: `{record.noise_class}` ({record.noise_score})",
                f"- Summary: {record.grading_summary}",
                f"- Path classes: `{record.path_class_counts}`",
                f"- Current score guidance: {record.current_instance_score_guidance}",
                f"- Family guidance: {record.family_value_guidance}",
                f"- Edge suggestions: `{record.graph_edge_suggestions}`",
                "",
            ]
        )
    return "\n".join(lines)


def write_semantic_evolution_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    *,
    scan_id: str,
    source_id: str = "all",
    basename: str | None = None,
    asset_type: str = "schema",
    max_families: int = 100,
    review_sample: int = 50,
    max_read_bytes: int = 1_000_000,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    records = build_semantic_evolution_records(
        assets,
        local_sources,
        scan_id=scan_id,
        source_id=source_id,
        basename=basename,
        asset_type=asset_type,
        max_families=max_families,
        max_read_bytes=max_read_bytes,
        generated_at=generated,
    )
    learning_dir = repo_root / "processed" / "learning"
    reports_dir = repo_root / "processed" / "reports"
    candidates_path = learning_dir / "semantic_evolution_candidates.jsonl"
    report_path = reports_dir / "semantic_evolution_candidates.md"
    write_jsonl(candidates_path, [record.model_dump(mode="json") for record in records])
    atomic_write_text(
        report_path,
        semantic_evolution_markdown(records, generated_at=generated, review_sample=review_sample)
        + "\n",
    )
    return {
        "semantic_evolution_count": len(records),
        "evolution_grade_counts": dict(Counter(record.evolution_grade for record in records)),
        "noise_class_counts": dict(Counter(record.noise_class for record in records)),
        "source_id": source_id,
        "scan_id": scan_id,
        "max_read_bytes": max_read_bytes,
        "output_type": "generated_candidate_report",
        "outputs": {
            "semantic_evolution_candidates": str(candidates_path),
            "semantic_evolution_report": str(report_path),
        },
    }
