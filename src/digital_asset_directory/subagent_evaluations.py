from __future__ import annotations

import hashlib
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from jsonschema.validators import validator_for

from .transport import data_relative_path
from .utils import (
    SECRET_PATTERNS,
    append_jsonl,
    sha256_text_file_lf,
    utc_now,
    write_json,
    write_jsonl,
)


AUTHORITY_BOUNDARY = (
    "Subagent attempts, ratings, graph edges, and consolidation rows are candidate "
    "evidence. They do not rank model families, identify a person, change agent routing, "
    "merge or retire role profiles, or authorize keep/promote/combine/supersede actions."
)
METHODOLOGY_PATH = Path("registry/subagent-evaluation-methodology.json")
METHODOLOGY_SNAPSHOT_DIR = Path("registry/subagent-evaluation-methodologies")
CAPABILITY_REGISTRY_PATH = Path("registry/subagent-capability-registry.json")
EDGE_REGISTRY_PATH = Path("registry/graph-edge-registry.json")
RAW_BASE = Path("raw/agent-evaluations")
RAW_PACKET_DIR = RAW_BASE / "packets"
RAW_FILES = {
    "role_profiles": RAW_BASE / "role-profile-revisions.jsonl",
    "attempts": RAW_BASE / "execution-attempts.jsonl",
    "evaluations": RAW_BASE / "attempt-evaluations.jsonl",
    "unrated_inventory": RAW_BASE / "unrated-inventory.jsonl",
}
PACKET_FILES = {
    "role_profiles": "role-profile-revisions.jsonl",
    "attempts": "execution-attempts.jsonl",
    "evaluations": "attempt-evaluations.jsonl",
    "unrated_inventory": "unrated-inventory.jsonl",
}
PROCESSED_BASE = Path("processed/agents")
GRAPH_PATH = PROCESSED_BASE / "subagent-capability-graph.json"
MANIFEST_PATH = PROCESSED_BASE / "subagent-capability-graph-manifest.json"
NORMALIZED_EVALUATIONS_PATH = PROCESSED_BASE / "attempt-evaluations.jsonl"
CONSOLIDATION_QUEUE_PATH = PROCESSED_BASE / "consolidation-review-queue.jsonl"
BUILDER_VERSION = "subagent-capability-graph-builder.v0.1.0"
SCHEMA_NAMES = {
    "role_profiles": "subagent_role_profile_revision",
    "attempts": "subagent_execution_attempt",
    "evaluations": "subagent_attempt_evaluation",
    "unrated_inventory": "subagent_unrated_inventory",
}
EDGE_TYPES = {
    "attempt_instantiates_role_revision",
    "attempt_in_repository",
    "attempt_used_model_claim",
    "evaluation_of_attempt",
    "evaluation_assesses_capability",
}
LOCK_TIMEOUT_SECONDS = 15.0
LOCK_STALE_SECONDS = 300.0
FORBIDDEN_RECORD_KEYS = {
    "password",
    "secret",
    "token",
    "credential",
    "authorization",
    "source_blob",
    "raw_text",
    "full_prompt",
    "hidden_reasoning",
    "chain_of_thought",
}
ABSOLUTE_PATH_RE = re.compile(
    r"(?:(?<![A-Za-z0-9])[A-Za-z]:[/\\]|\\\\|(?<![A-Za-z0-9+.:_/-])/(?!/))",
    re.IGNORECASE,
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def content_hash(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical_bytes(value)).hexdigest()}"


def _hash_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    parts = [
        f"{child.relative_to(path).as_posix()}\0{hashlib.sha256(child.read_bytes()).hexdigest()}"
        for child in sorted(item for item in path.rglob("*") if item.is_file())
    ]
    return f"sha256:{hashlib.sha256(chr(10).join(parts).encode('utf-8')).hexdigest()}"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL {path}:{number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Expected object row at {path}:{number}")
        rows.append(value)
    return rows


def _validate_no_private_payload(value: Any, *, location: str) -> None:
    stack: list[tuple[str, Any]] = [(location, value)]
    while stack:
        current_path, current = stack.pop()
        if isinstance(current, dict):
            for key, child in current.items():
                normalized = str(key).strip().lower()
                if (
                    any(term in normalized for term in FORBIDDEN_RECORD_KEYS)
                    and child not in (None, "", [], {})
                ):
                    raise ValueError(f"Forbidden sensitive field {current_path}.{key}")
                stack.append((f"{current_path}.{key}", child))
        elif isinstance(current, list):
            stack.extend((f"{current_path}[{index}]", child) for index, child in enumerate(current))
        elif isinstance(current, str):
            if ABSOLUTE_PATH_RE.search(current):
                raise ValueError(f"Absolute/private path is not allowed in {current_path}")
            if any(pattern.search(current) for pattern in SECRET_PATTERNS):
                raise ValueError(f"Secret or sensitive value is not allowed in {current_path}")


def _verify_source_artifacts(hub_root: Path, attempts: Iterable[dict[str, Any]]) -> None:
    for attempt in attempts:
        for artifact in attempt.get("artifact_refs", []):
            ref = str(artifact.get("ref", ""))
            expected = str(artifact.get("sha256", ""))
            hash_policy = str(artifact.get("hash_policy", ""))
            if ref.startswith("source://"):
                relative = Path(ref.removeprefix("source://"))
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError(f"Unsafe source evidence ref: {ref}")
                evidence_path = hub_root / relative
                if hash_policy == "text_lf_normalized_v1":
                    actual = (
                        f"sha256:{sha256_text_file_lf(evidence_path)}"
                        if evidence_path.exists()
                        else "missing"
                    )
                elif hash_policy == "bytes_v1":
                    actual = _hash_path(evidence_path)
                else:
                    raise ValueError(
                        f"Attempt {attempt['attempt_id']} uses unsupported evidence hash policy"
                    )
                if actual != expected:
                    raise ValueError(
                        f"Attempt {attempt['attempt_id']} evidence hash mismatch for {ref}: "
                        f"{expected} != {actual}"
                    )
            elif expected != "unavailable":
                raise ValueError(
                    f"Attempt {attempt['attempt_id']} has hashed but unresolvable evidence ref {ref}"
                )


@contextmanager
def _ingest_lock(raw_root: Path):
    raw_root.mkdir(parents=True, exist_ok=True)
    lock_path = raw_root / ".ingest.lock"
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()}\n".encode("utf-8"))
            break
        except FileExistsError:
            try:
                stale = time.time() - lock_path.stat().st_mtime > LOCK_STALE_SECONDS
            except OSError:
                stale = False
            if stale:
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for subagent intake lock: {lock_path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            os.close(fd)
        finally:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


def _schema_validator(hub_root: Path, schema_name: str):
    registry = _load_json(hub_root / "registry/schema-registry.json")
    schema_rel = registry.get("schemas", {}).get(schema_name)
    if not schema_rel:
        raise ValueError(f"Schema registry missing {schema_name}")
    schema = _load_json(hub_root / str(schema_rel))
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    return validator_cls(schema)


def _validate_rows(hub_root: Path, kind: str, rows: Iterable[dict[str, Any]]) -> None:
    validator = _schema_validator(hub_root, SCHEMA_NAMES[kind])
    for index, row in enumerate(rows, start=1):
        try:
            validator.validate(row)
        except Exception as exc:
            raise ValueError(f"Invalid {kind} row {index}: {exc}") from exc


def _dimension_score(evaluation: dict[str, Any], methodology: dict[str, Any]) -> float | None:
    dimensions = evaluation["dimension_results"]
    weighted = 0.0
    for definition in methodology["dimensions"]:
        row = dimensions[definition["id"]]
        if row["status"] != "scored" or row["score"] is None:
            return None
        weighted += float(row["score"]) * float(definition["weight"])
    return round(weighted, 2)


def _evaluation_bundle_hash(evaluation: dict[str, Any]) -> str:
    return content_hash(
        {
            "dimension_results": evaluation["dimension_results"],
            "capability_results": evaluation["capability_results"],
            "strengths": evaluation["strengths"],
            "failures": evaluation["failures"],
            "improvement_recommendations": evaluation["improvement_recommendations"],
            "limitations": evaluation["limitations"],
            "evidence_grade": evaluation["evidence_grade"],
            "evaluator_identity": evaluation["evaluator_identity"],
        }
    )


def _is_verified_independent(
    evaluation: dict[str, Any], attempts_by_id: dict[str, dict[str, Any]]
) -> bool:
    evaluator_attempt_id = evaluation.get("evaluator_attempt_id")
    identity = evaluation.get("evaluator_identity", {})
    evaluator_attempt = attempts_by_id.get(str(evaluator_attempt_id or ""))
    allowed_actor_ids = {
        str(evaluator_attempt_id or ""),
        str((evaluator_attempt or {}).get("runtime_attempt_id") or ""),
    }
    evaluator_artifact_refs = {
        str(row.get("ref") or "")
        for row in (evaluator_attempt or {}).get("artifact_refs", [])
    }
    return bool(
        evaluation.get("evaluator_independence") == "independent"
        and evaluator_attempt_id
        and evaluator_attempt_id != evaluation.get("attempt_id")
        and evaluator_attempt is not None
        and evaluator_attempt.get("terminal_status") == "completed"
        and identity.get("relationship_to_attempt") == "independent"
        and identity.get("verification_status") in {"runtime_verified", "human_verified"}
        and str(identity.get("actor_id") or "") in allowed_actor_ids
        and str(identity.get("evidence_ref") or "") in evaluator_artifact_refs
    )


def validate_records(
    hub_root: Path,
    role_profiles: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
    unrated_inventory: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _validate_rows(hub_root, "role_profiles", role_profiles)
    _validate_rows(hub_root, "attempts", attempts)
    _validate_rows(hub_root, "evaluations", evaluations)
    if unrated_inventory is not None:
        _validate_rows(hub_root, "unrated_inventory", unrated_inventory)
    for kind, rows in (
        ("role_profiles", role_profiles),
        ("attempts", attempts),
        ("evaluations", evaluations),
        ("unrated_inventory", unrated_inventory or []),
    ):
        for index, row in enumerate(rows, start=1):
            _validate_no_private_payload(row, location=f"{kind}[{index}]")
    _verify_source_artifacts(hub_root, attempts)

    methodology_path = hub_root / METHODOLOGY_PATH
    methodology = _load_json(methodology_path)
    methodology_hash = _hash_path(methodology_path)
    current_snapshot_path = (
        hub_root / METHODOLOGY_SNAPSHOT_DIR / f"{methodology['methodology_version']}.json"
    )
    if _hash_path(current_snapshot_path) != methodology_hash:
        raise ValueError(
            "Current subagent evaluation methodology must match its immutable version snapshot"
        )
    capabilities = {
        str(row["id"])
        for row in _load_json(hub_root / CAPABILITY_REGISTRY_PATH).get("capabilities", [])
    }
    dimension_ids = [str(row["id"]) for row in methodology.get("dimensions", [])]
    expected_dimensions = {
        "correctness",
        "scope_discipline",
        "evidence_traceability",
        "efficiency_compute_fit",
        "escalation_calibration",
    }
    if set(dimension_ids) != expected_dimensions or len(dimension_ids) != len(expected_dimensions):
        raise ValueError("Subagent evaluation methodology dimensions are incomplete or duplicated")
    if abs(sum(float(row["weight"]) for row in methodology["dimensions"]) - 1.0) > 1e-9:
        raise ValueError("Subagent evaluation methodology weights must sum to 1.0")
    if len(capabilities) != len(
        _load_json(hub_root / CAPABILITY_REGISTRY_PATH).get("capabilities", [])
    ):
        raise ValueError("Subagent capability registry has duplicate capability ids")
    graph_edge_types = {
        str(row["edge_type"])
        for row in _load_json(hub_root / EDGE_REGISTRY_PATH).get("edge_types", [])
    }
    general_edge_types = {
        str(row["id"])
        for row in _load_json(hub_root / "registry/edge-type-registry.json").get(
            "edge_types", []
        )
    }
    if not EDGE_TYPES <= graph_edge_types or not EDGE_TYPES <= general_edge_types:
        raise ValueError("Subagent graph edge vocabulary is not registered in both edge registries")

    def unique(rows: list[dict[str, Any]], field: str, label: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = str(row[field])
            if key in result:
                raise ValueError(f"Duplicate {label} {key}")
            result[key] = row
        return result

    profiles_by_revision = unique(role_profiles, "revision_id", "role revision")
    attempts_by_id = unique(attempts, "attempt_id", "attempt")
    evaluations_by_id = unique(evaluations, "evaluation_id", "evaluation")

    for profile in role_profiles:
        unhashed = {key: value for key, value in profile.items() if key != "revision_sha256"}
        if profile["revision_sha256"] != content_hash(unhashed):
            raise ValueError(f"Role revision {profile['revision_id']} content hash mismatch")

    for attempt in attempts:
        revision_id = str(attempt["role_revision_id"])
        profile = profiles_by_revision.get(revision_id)
        if profile is None:
            raise ValueError(f"Attempt {attempt['attempt_id']} references missing {revision_id}")
        if attempt["role_profile_id"] != profile["role_profile_id"]:
            raise ValueError(f"Attempt {attempt['attempt_id']} role profile/revision mismatch")

    for evaluation in evaluations:
        attempt = attempts_by_id.get(str(evaluation["attempt_id"]))
        if attempt is None:
            raise ValueError(
                f"Evaluation {evaluation['evaluation_id']} references missing attempt "
                f"{evaluation['attempt_id']}"
            )
        if evaluation["evaluator_independence"] == "independent" and not _is_verified_independent(
            evaluation, attempts_by_id
        ):
            raise ValueError(
                f"Evaluation {evaluation['evaluation_id']} has unverified independence"
            )
        expected_relationship = {
            "parent_review": "parent",
            "self_review": "self",
            "unknown": "unknown",
        }.get(str(evaluation["evaluator_independence"]))
        if expected_relationship and evaluation["evaluator_identity"][
            "relationship_to_attempt"
        ] != expected_relationship:
            raise ValueError(
                f"Evaluation {evaluation['evaluation_id']} reviewer relationship mismatch"
            )
        expected_snapshot_hash = content_hash(attempt)
        if evaluation["attempt_snapshot_sha256"] != expected_snapshot_hash:
            raise ValueError(
                f"Evaluation {evaluation['evaluation_id']} attempt snapshot hash mismatch"
            )
        snapshot_path = hub_root / METHODOLOGY_SNAPSHOT_DIR / f"{evaluation['rubric_version']}.json"
        if not snapshot_path.exists():
            raise ValueError(
                f"Evaluation {evaluation['evaluation_id']} rubric snapshot is missing: "
                f"{snapshot_path.relative_to(hub_root)}"
            )
        snapshot = _load_json(snapshot_path)
        _schema_validator(hub_root, "subagent_evaluation_methodology").validate(snapshot)
        snapshot_hash = _hash_path(snapshot_path)
        if evaluation["rubric_id"] != snapshot["methodology_id"]:
            raise ValueError(f"Evaluation {evaluation['evaluation_id']} rubric id mismatch")
        if evaluation["rubric_version"] != snapshot["methodology_version"]:
            raise ValueError(f"Evaluation {evaluation['evaluation_id']} rubric version mismatch")
        if evaluation["rubric_sha256"] != snapshot_hash:
            raise ValueError(f"Evaluation {evaluation['evaluation_id']} rubric hash mismatch")
        if evaluation["evidence_bundle_sha256"] != _evaluation_bundle_hash(evaluation):
            raise ValueError(f"Evaluation {evaluation['evaluation_id']} evidence hash mismatch")
        unknown = {
            str(row["capability_id"])
            for row in evaluation["capability_results"]
            if str(row["capability_id"]) not in capabilities
        }
        if unknown:
            raise ValueError(
                f"Evaluation {evaluation['evaluation_id']} has unknown capabilities: "
                + ", ".join(sorted(unknown))
            )
        for capability in evaluation["capability_results"]:
            if capability["status"] == "scored":
                if capability["rating"] is None or not capability["evidence_refs"]:
                    raise ValueError(
                        f"Evaluation {evaluation['evaluation_id']} scored capability lacks evidence"
                    )
            elif capability["rating"] is not None or capability["evidence_refs"]:
                raise ValueError(
                    f"Evaluation {evaluation['evaluation_id']} unscored capability carries a score/evidence"
                )
        calculated = _dimension_score(evaluation, snapshot)
        aggregate = evaluation["aggregate_result"]
        if calculated is None:
            if aggregate["status"] != "insufficient_evidence" or aggregate["score"] is not None:
                raise ValueError(
                    f"Evaluation {evaluation['evaluation_id']} must remain insufficient_evidence"
                )
        elif aggregate["status"] not in {
            "rated_attempt",
            "parent_observational_rating",
        } or float(aggregate["score"]) != calculated:
            raise ValueError(
                f"Evaluation {evaluation['evaluation_id']} score mismatch: "
                f"{aggregate['score']} != {calculated}"
            )
        evidence_grade = str(evaluation["evidence_grade"])
        if evidence_grade == "parent_reconstructed_summary":
            if aggregate["status"] != "parent_observational_rating":
                raise ValueError(
                    f"Evaluation {evaluation['evaluation_id']} reconstructed evidence cannot be profile-rated"
                )
            if float(aggregate["confidence"]) > 0.9:
                raise ValueError(
                    f"Evaluation {evaluation['evaluation_id']} reconstructed confidence exceeds 0.9"
                )
        elif evidence_grade == "execution_failure_log":
            if aggregate["status"] != "insufficient_evidence":
                raise ValueError(
                    f"Evaluation {evaluation['evaluation_id']} failure log cannot carry a rating"
                )
        elif evidence_grade == "independent_hashed_review" and not _is_verified_independent(
            evaluation, attempts_by_id
        ):
            raise ValueError(
                f"Evaluation {evaluation['evaluation_id']} independent evidence is not verified"
            )
        if aggregate["status"] in {"rated_attempt", "parent_observational_rating"}:
            if not attempt["artifact_refs"] or any(
                artifact["sha256"] == "unavailable" for artifact in attempt["artifact_refs"]
            ):
                raise ValueError(
                    f"Rated evaluation {evaluation['evaluation_id']} lacks replayable artifact hashes"
                )

    return {
        "role_profiles": profiles_by_revision,
        "attempts": attempts_by_id,
        "evaluations": evaluations_by_id,
        "methodology": methodology,
        "methodology_hash": methodology_hash,
        "methodology_snapshot_dir_hash": _hash_path(hub_root / METHODOLOGY_SNAPSHOT_DIR),
    }


def load_packet(packet_dir: Path) -> dict[str, list[dict[str, Any]]]:
    required = {kind: _read_jsonl(packet_dir / filename) for kind, filename in PACKET_FILES.items()}
    for kind in ("role_profiles", "attempts", "evaluations"):
        if not required[kind]:
            raise ValueError(f"Packet is missing non-empty {PACKET_FILES[kind]}")
    return required


def _plan_idempotent(
    path: Path,
    rows: list[dict[str, Any]],
    id_field: str,
) -> tuple[list[dict[str, Any]], int]:
    existing_rows = _read_jsonl(path)
    existing = {str(row[id_field]): row for row in existing_rows}
    planned: list[dict[str, Any]] = []
    unchanged = 0
    for row in rows:
        key = str(row[id_field])
        if key in existing:
            if _canonical_bytes(existing[key]) != _canonical_bytes(row):
                raise ValueError(f"Conflicting immutable record {key} in {path}")
            unchanged += 1
            continue
        existing[key] = row
        planned.append(row)
    return planned, unchanged


def ingest_packet(hub_root: Path, packet_dir: Path) -> dict[str, Any]:
    packet = load_packet(packet_dir)
    validate_records(
        hub_root,
        packet["role_profiles"],
        packet["attempts"],
        packet["evaluations"],
        packet["unrated_inventory"],
    )
    results: dict[str, dict[str, int]] = {}
    fields = {
        "role_profiles": "revision_id",
        "attempts": "attempt_id",
        "evaluations": "evaluation_id",
        "unrated_inventory": "inventory_id",
    }
    raw_root = data_relative_path(hub_root, RAW_BASE)
    packet_hash = content_hash(packet)
    receipt = {
        "schema_version": "0.1.0",
        "packet_id": f"dad:subagent-packet:{packet_hash.removeprefix('sha256:')[:24]}",
        "packet_hash": packet_hash,
        "source_label": packet_dir.name,
        "records": packet,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    receipt_path = data_relative_path(
        hub_root,
        RAW_PACKET_DIR / f"{packet_hash.removeprefix('sha256:')}.json",
    )
    with _ingest_lock(raw_root):
        plans: dict[str, list[dict[str, Any]]] = {}
        unchanged_counts: dict[str, int] = {}
        for kind, rows in packet.items():
            path = data_relative_path(hub_root, RAW_FILES[kind])
            planned, unchanged = _plan_idempotent(path, rows, fields[kind])
            plans[kind] = planned
            unchanged_counts[kind] = unchanged
        if receipt_path.exists():
            if _canonical_bytes(_load_json(receipt_path)) != _canonical_bytes(receipt):
                raise ValueError(f"Conflicting immutable packet receipt {receipt_path}")
        else:
            write_json(receipt_path, receipt, allow_direct_fallback=True)
        for kind, rows in plans.items():
            path = data_relative_path(hub_root, RAW_FILES[kind])
            for row in rows:
                append_jsonl(path, row)
            results[kind] = {
                "appended": len(rows),
                "unchanged": unchanged_counts[kind],
            }
    return {
        "packet": packet_dir.name,
        "packet_hash": packet_hash,
        "receipt_path": str(receipt_path),
        "results": results,
        "raw_root": str(raw_root),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _count_by(rows: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        value = str(row[key])
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _node_id(kind: str, value: str) -> str:
    return f"{kind}:{value}"


def _edge(
    source: str,
    target: str,
    edge_type: str,
    basis: str,
    evidence_ref: str,
    method_version: str,
) -> dict[str, Any]:
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"Unregistered subagent graph edge {edge_type}")
    edge_key = hashlib.sha256(
        f"{source}\0{target}\0{edge_type}\0{basis}".encode("utf-8")
    ).hexdigest()[:24]
    return {
        "edge_id": f"dad:subagent-edge:{edge_key}",
        "source": source,
        "target": target,
        "edge_type": edge_type,
        "edge_class": "join",
        "edge_basis": basis,
        "method_version": method_version,
        "evidence_refs": [evidence_ref],
        "review_status": "candidate",
    }


def build_graph(hub_root: Path) -> dict[str, Any]:
    role_profiles = _read_jsonl(data_relative_path(hub_root, RAW_FILES["role_profiles"]))
    attempts = _read_jsonl(data_relative_path(hub_root, RAW_FILES["attempts"]))
    evaluations = _read_jsonl(data_relative_path(hub_root, RAW_FILES["evaluations"]))
    unrated = _read_jsonl(data_relative_path(hub_root, RAW_FILES["unrated_inventory"]))
    if not role_profiles or not attempts or not evaluations:
        raise ValueError("Subagent graph inputs are incomplete; ingest a validated packet first")
    validated = validate_records(hub_root, role_profiles, attempts, evaluations, unrated)
    methodology = validated["methodology"]
    method_version = str(methodology["methodology_version"])
    capabilities = _load_json(hub_root / CAPABILITY_REGISTRY_PATH).get("capabilities", [])

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    for profile in role_profiles:
        node_id = _node_id("role-revision", str(profile["revision_id"]))
        nodes[node_id] = {
            "node_id": node_id,
            "node_type": "role_profile_revision",
            "label": str(profile["role_id"]),
            "role_profile_id": profile["role_profile_id"],
            "revision_id": profile["revision_id"],
            "review_status": profile["review_status"],
        }
    for capability in capabilities:
        node_id = _node_id("capability", str(capability["id"]))
        nodes[node_id] = {
            "node_id": node_id,
            "node_type": "capability",
            "label": str(capability["id"]),
            "description": str(capability["description"]),
        }
    for attempt in attempts:
        attempt_node = _node_id("attempt", str(attempt["attempt_id"]))
        role_node = _node_id("role-revision", str(attempt["role_revision_id"]))
        repo_node = _node_id("repo", str(attempt["source_repository"]))
        runtime_claims = attempt["runtime_claims"]
        model_value = ":".join(
            str(runtime_claims[field])
            for field in (
                "provider",
                "model_id",
                "model_family",
                "reasoning_effort",
                "verification_status",
            )
        )
        model_node = _node_id("model-claim", model_value)
        nodes[attempt_node] = {
            "node_id": attempt_node,
            "node_type": "execution_attempt",
            "label": str(attempt.get("display_label") or attempt["attempt_id"]),
            "attempt_id": attempt["attempt_id"],
            "terminal_status": attempt["terminal_status"],
            "capture_completeness": attempt["capture_completeness"]["status"],
        }
        nodes.setdefault(
            repo_node,
            {"node_id": repo_node, "node_type": "repository", "label": str(attempt["source_repository"])},
        )
        nodes.setdefault(
            model_node,
            {
                "node_id": model_node,
                "node_type": "model_claim",
                "label": model_value,
                "verification_status": attempt["runtime_claims"]["verification_status"],
            },
        )
        for row in (
            _edge(attempt_node, role_node, "attempt_instantiates_role_revision", "attempt.role_revision_id", str(attempt["attempt_id"]), method_version),
            _edge(attempt_node, repo_node, "attempt_in_repository", "attempt.source_repository", str(attempt["attempt_id"]), method_version),
            _edge(attempt_node, model_node, "attempt_used_model_claim", "attempt.runtime_claims", str(attempt["attempt_id"]), method_version),
        ):
            edges[row["edge_id"]] = row

    evaluations_by_attempt: dict[str, list[dict[str, Any]]] = {}
    for evaluation in evaluations:
        evaluation_node = _node_id("evaluation", str(evaluation["evaluation_id"]))
        attempt_node = _node_id("attempt", str(evaluation["attempt_id"]))
        nodes[evaluation_node] = {
            "node_id": evaluation_node,
            "node_type": "evaluation",
            "label": str(evaluation["evaluation_id"]),
            "evaluation_id": evaluation["evaluation_id"],
            "score": evaluation["aggregate_result"]["score"],
            "score_status": evaluation["aggregate_result"]["status"],
            "outcome": evaluation["outcome"],
            "independence": evaluation["evaluator_independence"],
        }
        row = _edge(evaluation_node, attempt_node, "evaluation_of_attempt", "evaluation.attempt_id", str(evaluation["evaluation_id"]), method_version)
        edges[row["edge_id"]] = row
        evaluations_by_attempt.setdefault(str(evaluation["attempt_id"]), []).append(evaluation)
        for capability in evaluation["capability_results"]:
            if capability["status"] != "scored":
                continue
            capability_node = _node_id("capability", str(capability["capability_id"]))
            row = _edge(evaluation_node, capability_node, "evaluation_assesses_capability", "evaluation.capability_results", str(evaluation["evaluation_id"]), method_version)
            edges[row["edge_id"]] = row

    attempts_by_revision: dict[str, list[dict[str, Any]]] = {}
    for attempt in attempts:
        attempts_by_revision.setdefault(str(attempt["role_revision_id"]), []).append(attempt)
    profile_summaries: list[dict[str, Any]] = []
    for profile in sorted(role_profiles, key=lambda row: str(row["revision_id"])):
        rows = attempts_by_revision.get(str(profile["revision_id"]), [])
        all_role_evaluations = [
            evaluation
            for attempt in rows
            for evaluation in evaluations_by_attempt.get(str(attempt["attempt_id"]), [])
        ]
        current_ratings_by_attempt: dict[str, list[dict[str, Any]]] = {}
        observational_attempt_ids = {
            str(evaluation["attempt_id"])
            for evaluation in all_role_evaluations
            if evaluation["aggregate_result"]["status"]
            == "parent_observational_rating"
        }
        for evaluation in all_role_evaluations:
            if (
                evaluation["aggregate_result"]["status"] == "rated_attempt"
                and not evaluation["aggregate_result"]["gate_failed"]
                and evaluation["rubric_version"] == methodology["methodology_version"]
            ):
                current_ratings_by_attempt.setdefault(str(evaluation["attempt_id"]), []).append(
                    evaluation
                )
        attempt_scores = {
            attempt_id: round(
                sum(float(row["aggregate_result"]["score"]) for row in attempt_ratings)
                / len(attempt_ratings),
                2,
            )
            for attempt_id, attempt_ratings in current_ratings_by_attempt.items()
        }
        rated_attempt_ids = set(attempt_scores)
        independent_evaluations = [
            evaluation
            for evaluation in all_role_evaluations
            if evaluation["attempt_id"] in rated_attempt_ids
            and _is_verified_independent(evaluation, validated["attempts"])
            and not evaluation["aggregate_result"]["gate_failed"]
        ]
        independent_reviewers = {
            str(row["evaluator_identity"]["actor_id"])
            for row in independent_evaluations
        }
        failed_gate_attempt_ids = {
            str(evaluation["attempt_id"])
            for evaluation in all_role_evaluations
            if evaluation["aggregate_result"]["gate_failed"]
        }
        rated_attempts = [
            attempt for attempt in rows if str(attempt["attempt_id"]) in rated_attempt_ids
        ]
        repos = {str(attempt["source_repository"]) for attempt in rated_attempts}
        tasks = {str(attempt["task_id"]) for attempt in rated_attempts}
        minimum_contexts = int(
            methodology["profile_evidence_thresholds"][
                "default_comparison_min_repositories_or_task_families"
            ]
        )
        context_diverse = len(repos) >= minimum_contexts or len(tasks) >= minimum_contexts
        eligible_provisional = (
            len(attempt_scores)
            >= int(
                methodology["profile_evidence_thresholds"][
                    "provisional_profile_min_comparable_attempts"
                ]
            )
            and len(independent_reviewers) >= 1
            and not failed_gate_attempt_ids
        )
        eligible_default = (
            len(attempt_scores)
            >= int(methodology["profile_evidence_thresholds"]["default_comparison_min_attempts"])
            and context_diverse
            and len(independent_reviewers) >= 2
            and not failed_gate_attempt_ids
        )
        blockers: list[str] = []
        if len(attempt_scores) < int(
            methodology["profile_evidence_thresholds"]["default_comparison_min_attempts"]
        ):
            blockers.append("minimum distinct rated attempts not met")
        if not context_diverse:
            blockers.append("minimum repository or task-context diversity not met")
        if len(independent_reviewers) < 2:
            blockers.append("minimum distinct independent reviewers not met")
        if failed_gate_attempt_ids:
            blockers.append("gate-failed attempt requires human resolution")
        profile_summaries.append(
            {
                "role_profile_id": profile["role_profile_id"],
                "revision_id": profile["revision_id"],
                "attempt_count": len(rows),
                "evaluation_count": len(all_role_evaluations),
                "rated_attempt_count": len(attempt_scores),
                "observational_attempt_count": len(observational_attempt_ids),
                "independent_evaluation_count": len(independent_evaluations),
                "independent_reviewer_count": len(independent_reviewers),
                "gate_failed_attempt_count": len(failed_gate_attempt_ids),
                "repository_count": len(repos),
                "task_count": len(tasks),
                "profile_score_status": "provisional" if eligible_provisional else "attempt_evidence_only",
                "profile_score": (
                    round(
                        sum(attempt_scores.values()) / len(attempt_scores),
                        2,
                    )
                    if eligible_provisional
                    else None
                ),
                "default_comparison_eligible": eligible_default,
                "blockers": [] if eligible_default else blockers,
            }
        )

    consolidation_queue = []
    recommendation_validator = _schema_validator(hub_root, "subagent_action_recommendation")
    for row in profile_summaries:
        if row["default_comparison_eligible"]:
            continue
        role_attempts = attempts_by_revision.get(str(row["revision_id"]), [])
        role_evaluations = [
            evaluation
            for attempt in role_attempts
            for evaluation in evaluations_by_attempt.get(str(attempt["attempt_id"]), [])
        ]
        capability_ids = sorted(
            {
                str(capability["capability_id"])
                for evaluation in role_evaluations
                for capability in evaluation["capability_results"]
            }
        )
        evaluation_ids = sorted(str(evaluation["evaluation_id"]) for evaluation in role_evaluations)
        fingerprint = content_hash(
            {
                "revision_id": row["revision_id"],
                "evaluation_ids": evaluation_ids,
                "methodology_hash": validated["methodology_hash"],
            }
        )
        recommendation = {
            "schema_version": "0.1.0",
            "recommendation_id": f"dad:subagent-recommendation:{hashlib.sha256(str(row['revision_id']).encode()).hexdigest()[:20]}",
            "target_role_revision_ids": [row["revision_id"]],
            "action": "insufficient_evidence",
            "comparison_cohort": {
                "repositories": sorted({str(attempt["source_repository"]) for attempt in role_attempts}),
                "task_ids": sorted({str(attempt["task_id"]) for attempt in role_attempts}),
            },
            "evaluation_ids": evaluation_ids,
            "rubric_refs": [
                f"{methodology['methodology_id']}@{methodology['methodology_version']}",
                validated["methodology_hash"],
            ],
            "capability_ids": capability_ids,
            "sample_counts": {
                "attempts": row["attempt_count"],
                "evaluations": row["evaluation_count"],
                "rated_attempts": row["rated_attempt_count"],
                "observational_attempts": row["observational_attempt_count"],
                "independent_evaluations": row["independent_evaluation_count"],
                "gate_failed_attempts": row["gate_failed_attempt_count"],
                "repositories": row["repository_count"],
                "tasks": row["task_count"],
            },
            "independence_counts": {
                "independent": row["independent_evaluation_count"],
                "distinct_independent_reviewers": row["independent_reviewer_count"],
                "non_independent": sum(
                    evaluation["evaluator_independence"] != "independent"
                    for evaluation in role_evaluations
                ),
            },
            "rationale": "Preserve the role revision and collect comparable cross-context evidence before keep/combine/promote/supersede review.",
            "counterevidence": sorted(
                {
                    failure
                    for evaluation in role_evaluations
                    for failure in evaluation["failures"]
                }
            ),
            "blockers": list(row["blockers"]),
            "risk": "high",
            "input_fingerprint": fingerprint,
            "human_gate_required": True,
            "auto_apply": False,
            "review_status": "generated_candidate",
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
        recommendation_validator.validate(recommendation)
        consolidation_queue.append(recommendation)

    generated_at = utc_now()
    node_rows = sorted(nodes.values(), key=lambda row: str(row["node_id"]))
    edge_rows = sorted(edges.values(), key=lambda row: str(row["edge_id"]))
    graph = {
        "schema_version": "0.1.0",
        "generated_at": generated_at,
        "methodology_id": methodology["methodology_id"],
        "methodology_version": methodology["methodology_version"],
        "node_count": len(node_rows),
        "edge_count": len(edge_rows),
        "nodes_by_type": _count_by(node_rows, "node_type"),
        "edges_by_type": _count_by(edge_rows, "edge_type"),
        "nodes": node_rows,
        "edges": edge_rows,
        "profile_summaries": profile_summaries,
        "consolidation_review_queue": consolidation_queue,
        "unrated_inventory": unrated,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    graph_validator = _schema_validator(hub_root, "subagent_capability_graph")
    graph_validator.validate(graph)

    graph_path = data_relative_path(hub_root, GRAPH_PATH)
    normalized_path = data_relative_path(hub_root, NORMALIZED_EVALUATIONS_PATH)
    queue_path = data_relative_path(hub_root, CONSOLIDATION_QUEUE_PATH)
    manifest_path = data_relative_path(hub_root, MANIFEST_PATH)
    write_json(graph_path, graph, allow_direct_fallback=True)
    write_jsonl(normalized_path, sorted(evaluations, key=lambda row: str(row["evaluation_id"])), allow_direct_fallback=True)
    write_jsonl(queue_path, consolidation_queue, allow_direct_fallback=True)
    edge_registry_hash = _hash_path(hub_root / EDGE_REGISTRY_PATH)
    input_hashes = {
        str(path): _hash_path(data_relative_path(hub_root, path)) for path in RAW_FILES.values()
    }
    manifest = {
        "schema_version": "0.1.0",
        "surface_id": "subagent-capability-graph",
        "ontology_id": "knowledge",
        "generated_at": generated_at,
        "builder_version": BUILDER_VERSION,
        "graph_path": GRAPH_PATH.as_posix(),
        "manifest_path": MANIFEST_PATH.as_posix(),
        "edge_registry_hash": edge_registry_hash,
        "input_hashes": input_hashes,
        "methodology_hashes": {
            METHODOLOGY_PATH.as_posix(): validated["methodology_hash"],
            METHODOLOGY_SNAPSHOT_DIR.as_posix(): validated[
                "methodology_snapshot_dir_hash"
            ],
            CAPABILITY_REGISTRY_PATH.as_posix(): _hash_path(hub_root / CAPABILITY_REGISTRY_PATH),
            "builder_source": _hash_path(Path(__file__)),
        },
        "graph_content_hash": _hash_path(graph_path),
        "freshness": {"state": "fresh", "computed_at": generated_at, "reasons": []},
        "counts": {
            "node_count": len(node_rows),
            "edge_count": len(edge_rows),
            "evaluation_count": len(evaluations),
            "attempt_count": len(attempts),
            "role_revision_count": len(role_profiles),
            "unrated_inventory_count": len(unrated),
        },
        "edges_by_type": graph["edges_by_type"],
        "method_versions_used": [method_version],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    write_json(manifest_path, manifest, allow_direct_fallback=True)
    return {
        "graph_path": str(graph_path),
        "manifest_path": str(manifest_path),
        "normalized_evaluations_path": str(normalized_path),
        "consolidation_queue_path": str(queue_path),
        "counts": manifest["counts"],
        "profile_summaries": profile_summaries,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def validate_hub_records(hub_root: Path) -> dict[str, Any]:
    role_profiles = _read_jsonl(data_relative_path(hub_root, RAW_FILES["role_profiles"]))
    attempts = _read_jsonl(data_relative_path(hub_root, RAW_FILES["attempts"]))
    evaluations = _read_jsonl(data_relative_path(hub_root, RAW_FILES["evaluations"]))
    unrated = _read_jsonl(data_relative_path(hub_root, RAW_FILES["unrated_inventory"]))
    present = [bool(role_profiles), bool(attempts), bool(evaluations)]
    if any(present) and not all(present):
        raise ValueError("Subagent evaluation raw inputs are partial, not an empty valid state")
    if all(present):
        validate_records(hub_root, role_profiles, attempts, evaluations, unrated)
    graph_path = data_relative_path(hub_root, GRAPH_PATH)
    if graph_path.exists():
        _schema_validator(hub_root, "subagent_capability_graph").validate(_load_json(graph_path))
    return {
        "role_profile_count": len(role_profiles),
        "attempt_count": len(attempts),
        "evaluation_count": len(evaluations),
        "graph_present": graph_path.exists(),
    }


def status(hub_root: Path) -> dict[str, Any]:
    counts = {
        kind: len(_read_jsonl(data_relative_path(hub_root, path)))
        for kind, path in RAW_FILES.items()
    }
    graph_path = data_relative_path(hub_root, GRAPH_PATH)
    return {
        "raw_counts": counts,
        "graph_present": graph_path.exists(),
        "graph_path": str(graph_path),
        "manifest_path": str(data_relative_path(hub_root, MANIFEST_PATH)),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
