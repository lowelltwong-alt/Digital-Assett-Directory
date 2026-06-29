from __future__ import annotations

from collections import defaultdict
from itertools import combinations
import re
from typing import Iterable

from .ids import chunk_id, delta_id, duplicate_cluster_id, edge_id
from .models import AssetChunkRecord, AssetDeltaRecord, AssetRecord, DuplicateClusterRecord, EdgeRecord
from .utils import json_dumps, sha256_bytes, utc_now

SHINGLE_SIZE = 4
MINHASH_PERMUTATIONS = 64
MAX_TEXT_CHUNKS_PER_ASSET = 2000
MAX_DUPLICATE_PAIR_EDGES_PER_ASSET = 8
MAX_ASSETS_PER_CHUNK_POSTING = 100
NEAR_DUPLICATE_OVERLAP_THRESHOLD = 0.5
CONTAINMENT_THRESHOLD = 0.82
NEAR_DUPLICATE_CONFIDENCE_CAP = 0.8
SHINGLE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+.#/-]{1,63}")


def _content_text(asset: AssetRecord) -> str:
    text = str(asset.metadata.get("chunk_text") or asset.metadata.get("excerpt") or "")
    if text.strip():
        return text.replace("\r\n", "\n").replace("\r", "\n")
    return ""


def _token_spans(text: str) -> list[tuple[str, int, int]]:
    return [
        (match.group(0).lower().strip("_./-+"), match.start(), match.end())
        for match in SHINGLE_RE.finditer(text)
    ]


def _text_shingles(text: str) -> list[tuple[str, int, int, str]]:
    token_spans = _token_spans(text)
    if not token_spans:
        return []
    width = min(SHINGLE_SIZE, len(token_spans))
    shingles: list[tuple[str, int, int, str]] = []
    for index in range(0, len(token_spans) - width + 1):
        window = token_spans[index : index + width]
        shingle_text = " ".join(token for token, _start, _end in window)
        digest = sha256_bytes(shingle_text.encode("utf-8"))
        shingles.append((digest, window[0][1], window[-1][2], shingle_text))
    return shingles


def _shingle_hashes(text: str) -> set[str]:
    return {digest for digest, _start, _end, _text in _text_shingles(text)}


def _stable_int_hash(value: str) -> int:
    return int(sha256_bytes(value.encode("utf-8"))[:16], 16)


def _minhash_signature(hashes: set[str]) -> tuple[int, ...]:
    if not hashes:
        return ()
    signature: list[int] = []
    for index in range(MINHASH_PERMUTATIONS):
        signature.append(min(_stable_int_hash(f"{index}:{digest}") for digest in hashes))
    return tuple(signature)


def _signature_jaccard(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(1 for left_value, right_value in zip(left, right) if left_value == right_value) / len(left)


def _metadata_chunk_payload(asset: AssetRecord) -> str:
    return json_dumps(
        {
            "asset_id": asset.asset_id,
            "revision_id": asset.revision_id,
            "logical_path": asset.logical_path,
            "metadata_fingerprint": asset.metadata_fingerprint,
            "content_hash": asset.content_hash,
            "content_sha256": asset.content_sha256,
            "size_bytes": asset.size_bytes,
            "modified_at": asset.modified_at,
        }
    )


def build_asset_chunks(assets: Iterable[AssetRecord], scan_id: str) -> list[AssetChunkRecord]:
    created_at = utc_now()
    chunks: list[AssetChunkRecord] = []
    for asset in sorted(assets, key=lambda item: item.asset_id):
        text = _content_text(asset)
        if text:
            for chunk_index, (
                digest,
                start,
                end,
                shingle_text,
            ) in enumerate(_text_shingles(text)):
                if chunk_index >= MAX_TEXT_CHUNKS_PER_ASSET:
                    break
                chunks.append(
                    AssetChunkRecord(
                        chunk_id=chunk_id(asset.asset_id, asset.revision_id, chunk_index, digest),
                        asset_id=asset.asset_id,
                        revision_id=asset.revision_id,
                        source_id=asset.source_id,
                        logical_path=asset.logical_path,
                        chunk_index=chunk_index,
                        chunk_kind="text",
                        content_hash=digest,
                        char_start=start,
                        char_end=end,
                        text_excerpt=shingle_text[:500],
                        evidence={
                            "source": "asset.metadata.chunk_text",
                            "chunking": "overlapping_token_shingle",
                            "shingle_size": SHINGLE_SIZE,
                            "authority": "Generated shingle chunk candidate from extracted text; source remains authoritative.",
                        },
                        created_at=created_at,
                        scan_id=scan_id,
                    )
                )
        else:
            payload = _metadata_chunk_payload(asset)
            digest = sha256_bytes(payload.encode("utf-8"))
            chunks.append(
                AssetChunkRecord(
                    chunk_id=chunk_id(asset.asset_id, asset.revision_id, 0, digest),
                    asset_id=asset.asset_id,
                    revision_id=asset.revision_id,
                    source_id=asset.source_id,
                    logical_path=asset.logical_path,
                    chunk_index=0,
                    chunk_kind="metadata",
                    content_hash=digest,
                    char_start=0,
                    char_end=0,
                    text_excerpt="",
                    evidence={
                        "source": "asset_identity_metadata",
                        "metadata_fingerprint": asset.metadata_fingerprint,
                        "revision_identity_mode": asset.metadata.get("revision_identity_mode"),
                        "authority": "Metadata chunk only; not proof of content equivalence.",
                    },
                    created_at=created_at,
                    scan_id=scan_id,
                )
            )
    return chunks


def _bounded_pairs(asset_ids: list[str]) -> Iterable[tuple[str, str]]:
    pair_counts: dict[str, int] = defaultdict(int)
    for left, right in combinations(sorted(asset_ids), 2):
        if (
            pair_counts[left] >= MAX_DUPLICATE_PAIR_EDGES_PER_ASSET
            or pair_counts[right] >= MAX_DUPLICATE_PAIR_EDGES_PER_ASSET
        ):
            continue
        pair_counts[left] += 1
        pair_counts[right] += 1
        yield left, right


def _symmetric_edge(
    edge_type: str,
    left_asset_id: str,
    right_asset_id: str,
    method: str,
    confidence: float,
    evidence: dict,
    created_at: str,
    scan_id: str,
) -> EdgeRecord:
    left, right = sorted([left_asset_id, right_asset_id])
    return EdgeRecord(
        edge_id=edge_id(edge_type, left, right),
        edge_type=edge_type,
        source_asset_id=left,
        target_asset_id=right,
        method=method,
        confidence=confidence,
        evidence=evidence,
        created_at=created_at,
        scan_id=scan_id,
    )


def _exact_duplicate_records(
    assets: list[AssetRecord], scan_id: str, created_at: str
) -> tuple[list[DuplicateClusterRecord], list[AssetDeltaRecord], list[EdgeRecord]]:
    by_sha: dict[str, list[AssetRecord]] = defaultdict(list)
    for asset in assets:
        if asset.content_sha256 and asset.size_bytes > 0:
            by_sha[asset.content_sha256].append(asset)

    clusters: list[DuplicateClusterRecord] = []
    deltas: list[AssetDeltaRecord] = []
    edges: list[EdgeRecord] = []
    for digest, group in sorted(by_sha.items()):
        if len(group) < 2:
            continue
        asset_ids = sorted(asset.asset_id for asset in group)
        cluster = DuplicateClusterRecord(
            cluster_id=duplicate_cluster_id("exact_content_duplicate", digest),
            cluster_type="exact_content_duplicate",
            asset_ids=asset_ids,
            methods=["content_sha256"],
            evidence={
                "content_sha256": digest,
                "asset_count": len(asset_ids),
                "authority": "Exact content match only; role, provenance, and preferred source require review.",
            },
            confidence=1.0,
            generated_at=created_at,
            scan_id=scan_id,
        )
        clusters.append(cluster)
        for left, right in _bounded_pairs(asset_ids):
            did = delta_id(left, right, "content_sha256")
            deltas.append(
                AssetDeltaRecord(
                    delta_id=did,
                    left_asset_id=left,
                    right_asset_id=right,
                    delta_type="exact_duplicate",
                    summary="Exact content SHA-256 match; no content delta detected by this layer.",
                    evidence={
                        "content_sha256": digest,
                        "cluster_id": cluster.cluster_id,
                        "authority": "Generated duplicate candidate; source repositories remain authoritative.",
                    },
                    confidence=1.0,
                    generated_at=created_at,
                    scan_id=scan_id,
                )
            )
            evidence = {"content_sha256": digest, "cluster_id": cluster.cluster_id}
            edges.append(
                _symmetric_edge(
                    "exact_duplicate_of",
                    left,
                    right,
                    "content_sha256",
                    1.0,
                    evidence,
                    created_at,
                    scan_id,
                )
            )
            edges.append(
                _symmetric_edge(
                    "has_delta_candidate",
                    left,
                    right,
                    "content_sha256_delta",
                    1.0,
                    {"delta_id": did, **evidence},
                    created_at,
                    scan_id,
                )
            )
    return clusters, deltas, edges


def _shingle_profiles(assets: list[AssetRecord]) -> dict[str, tuple[set[str], tuple[int, ...]]]:
    profiles: dict[str, tuple[set[str], tuple[int, ...]]] = {}
    for asset in assets:
        hashes = _shingle_hashes(_content_text(asset))
        if hashes:
            profiles[asset.asset_id] = (hashes, _minhash_signature(hashes))
    return profiles


def _near_duplicate_records(
    assets: list[AssetRecord], chunks: list[AssetChunkRecord], scan_id: str, created_at: str
) -> tuple[list[DuplicateClusterRecord], list[AssetDeltaRecord], list[EdgeRecord]]:
    assets_by_id = {asset.asset_id: asset for asset in assets}
    _ = chunks
    profiles = _shingle_profiles(assets)
    postings: dict[str, list[str]] = defaultdict(list)
    for asset_id, (hashes, _signature) in profiles.items():
        for digest in hashes:
            postings[digest].append(asset_id)

    candidate_pairs: set[tuple[str, str]] = set()
    for asset_ids in postings.values():
        unique_ids = sorted(set(asset_ids))
        if len(unique_ids) < 2 or len(unique_ids) > MAX_ASSETS_PER_CHUNK_POSTING:
            continue
        candidate_pairs.update(combinations(unique_ids, 2))

    clusters: list[DuplicateClusterRecord] = []
    deltas: list[AssetDeltaRecord] = []
    edges: list[EdgeRecord] = []
    near_pairs: list[tuple[str, str, float, float, set[str], set[str], set[str]]] = []
    containment_pairs: list[tuple[str, str, float, float, set[str], set[str], set[str]]] = []
    for left, right in sorted(candidate_pairs):
        left_asset = assets_by_id[left]
        right_asset = assets_by_id[right]
        if (
            left_asset.content_sha256
            and left_asset.content_sha256 == right_asset.content_sha256
            and left_asset.size_bytes > 0
            and right_asset.size_bytes > 0
        ):
            continue
        left_hashes, left_signature = profiles[left]
        right_hashes, right_signature = profiles[right]
        shared = left_hashes & right_hashes
        if not shared:
            continue
        containment = len(shared) / max(1, min(len(left_hashes), len(right_hashes)))
        estimated_jaccard = _signature_jaccard(left_signature, right_signature)
        left_only = left_hashes - shared
        right_only = right_hashes - shared
        if estimated_jaccard >= NEAR_DUPLICATE_OVERLAP_THRESHOLD:
            near_pairs.append(
                (left, right, estimated_jaccard, containment, shared, left_only, right_only)
            )
        elif containment >= CONTAINMENT_THRESHOLD:
            contained, container = (
                (left, right) if len(left_hashes) <= len(right_hashes) else (right, left)
            )
            contained_only = profiles[contained][0] - shared
            container_only = profiles[container][0] - shared
            containment_pairs.append(
                (
                    contained,
                    container,
                    estimated_jaccard,
                    containment,
                    shared,
                    contained_only,
                    container_only,
                )
            )

    if not near_pairs and not containment_pairs:
        return clusters, deltas, edges

    parent: dict[str, str] = {}

    def find(asset_id: str) -> str:
        parent.setdefault(asset_id, asset_id)
        while parent[asset_id] != asset_id:
            parent[asset_id] = parent[parent[asset_id]]
            asset_id = parent[asset_id]
        return asset_id

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left, right, *_ in near_pairs:
        union(left, right)

    grouped: dict[str, set[str]] = defaultdict(set)
    for left, right, *_ in near_pairs:
        grouped[find(left)].update([left, right])
    for members in grouped.values():
        asset_ids = sorted(members)
        clusters.append(
            DuplicateClusterRecord(
                cluster_id=duplicate_cluster_id("near_duplicate_candidate", "|".join(asset_ids)),
                cluster_type="near_duplicate_candidate",
                asset_ids=asset_ids,
                methods=["text_chunk_overlap"],
                evidence={
                    "asset_count": len(asset_ids),
                    "overlap_threshold": NEAR_DUPLICATE_OVERLAP_THRESHOLD,
                    "minhash_permutations": MINHASH_PERMUTATIONS,
                    "shingle_size": SHINGLE_SIZE,
                    "authority": "Near-duplicate candidate from deterministic token shingles and MinHash; human review required.",
                },
                confidence=0.75,
                generated_at=created_at,
                scan_id=scan_id,
            )
        )

    cluster_by_asset: dict[str, str] = {}
    for cluster in clusters:
        for asset_id in cluster.asset_ids:
            cluster_by_asset[asset_id] = cluster.cluster_id

    pair_counts: dict[str, int] = defaultdict(int)
    for left, right, overlap, containment, shared, left_only, right_only in near_pairs:
        if (
            pair_counts[left] >= MAX_DUPLICATE_PAIR_EDGES_PER_ASSET
            or pair_counts[right] >= MAX_DUPLICATE_PAIR_EDGES_PER_ASSET
        ):
            continue
        pair_counts[left] += 1
        pair_counts[right] += 1
        did = delta_id(left, right, "text_chunk_overlap")
        shared_sorted = sorted(shared)
        evidence = {
            "cluster_id": cluster_by_asset.get(left),
            "minhash_jaccard_estimate": round(overlap, 4),
            "exact_shingle_containment": round(containment, 4),
            "shared_shingle_count": len(shared),
            "left_only_shingle_count": len(left_only),
            "right_only_shingle_count": len(right_only),
            "minhash_permutations": MINHASH_PERMUTATIONS,
            "shingle_size": SHINGLE_SIZE,
        }
        deltas.append(
            AssetDeltaRecord(
                delta_id=did,
                left_asset_id=left,
                right_asset_id=right,
                delta_type="near_duplicate_candidate",
                summary=(
                    "Near-duplicate candidate based on deterministic token shingles and "
                    "MinHash; review shared and one-sided shingles before merging or "
                    "preferring a source."
                ),
                shared_chunk_hashes=shared_sorted[:50],
                left_only_chunk_hashes=sorted(left_only)[:50],
                right_only_chunk_hashes=sorted(right_only)[:50],
                evidence=evidence,
                confidence=round(min(NEAR_DUPLICATE_CONFIDENCE_CAP, overlap), 4),
                generated_at=created_at,
                scan_id=scan_id,
            )
        )
        edges.append(
            _symmetric_edge(
                "near_duplicate_of",
                left,
                right,
                "token_shingle_minhash",
                round(min(NEAR_DUPLICATE_CONFIDENCE_CAP, overlap), 4),
                evidence,
                created_at,
                scan_id,
            )
        )
        edges.append(
            _symmetric_edge(
                "has_delta_candidate",
                left,
                right,
                "token_shingle_minhash_delta",
                round(min(NEAR_DUPLICATE_CONFIDENCE_CAP, overlap), 4),
                {"delta_id": did, **evidence},
                created_at,
                scan_id,
            )
        )
    for left, right, overlap, containment, shared, left_only, right_only in containment_pairs:
        did = delta_id(left, right, "token_shingle_containment")
        evidence = {
            "minhash_jaccard_estimate": round(overlap, 4),
            "exact_shingle_containment": round(containment, 4),
            "shared_shingle_count": len(shared),
            "contained_only_shingle_count": len(left_only),
            "container_only_shingle_count": len(right_only),
            "minhash_permutations": MINHASH_PERMUTATIONS,
            "shingle_size": SHINGLE_SIZE,
            "authority": "Generated containment candidate; source repositories remain authoritative.",
        }
        deltas.append(
            AssetDeltaRecord(
                delta_id=did,
                left_asset_id=left,
                right_asset_id=right,
                delta_type="containment_candidate",
                summary=(
                    "Containment candidate: most shingles from the source asset appear "
                    "inside the target asset, while symmetric near-duplicate overlap stays lower."
                ),
                shared_chunk_hashes=sorted(shared)[:50],
                left_only_chunk_hashes=sorted(left_only)[:50],
                right_only_chunk_hashes=sorted(right_only)[:50],
                evidence=evidence,
                confidence=round(min(NEAR_DUPLICATE_CONFIDENCE_CAP, containment), 4),
                generated_at=created_at,
                scan_id=scan_id,
            )
        )
        edges.append(
            EdgeRecord(
                edge_id=edge_id("contained_in", left, right),
                edge_type="contained_in",
                source_asset_id=left,
                target_asset_id=right,
                method="token_shingle_containment",
                confidence=round(min(NEAR_DUPLICATE_CONFIDENCE_CAP, containment), 4),
                evidence=evidence,
                created_at=created_at,
                scan_id=scan_id,
            )
        )
        edges.append(
            _symmetric_edge(
                "has_delta_candidate",
                left,
                right,
                "token_shingle_containment_delta",
                round(min(NEAR_DUPLICATE_CONFIDENCE_CAP, containment), 4),
                {"delta_id": did, **evidence},
                created_at,
                scan_id,
            )
        )
    return clusters, deltas, edges


def build_identity_layers(
    assets: list[AssetRecord], scan_id: str
) -> tuple[list[AssetChunkRecord], list[DuplicateClusterRecord], list[AssetDeltaRecord], list[EdgeRecord]]:
    created_at = utc_now()
    chunks = build_asset_chunks(assets, scan_id)
    exact_clusters, exact_deltas, exact_edges = _exact_duplicate_records(assets, scan_id, created_at)
    near_clusters, near_deltas, near_edges = _near_duplicate_records(
        assets, chunks, scan_id, created_at
    )
    clusters = sorted(
        [*exact_clusters, *near_clusters],
        key=lambda record: (record.cluster_type, record.cluster_id),
    )
    deltas = sorted([*exact_deltas, *near_deltas], key=lambda record: record.delta_id)
    edges = sorted(
        [*exact_edges, *near_edges],
        key=lambda record: (record.edge_type, record.source_asset_id, record.target_asset_id),
    )
    return chunks, clusters, deltas, edges
